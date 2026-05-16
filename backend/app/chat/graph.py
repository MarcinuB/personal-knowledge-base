import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from app.chat.reranker import rerank
from app.shared.chromadb import get_chroma_client
from app.shared.config import get_settings
from app.shared.embeddings import get_embeddings
from app.shared.llm import get_llm


class ChatState(TypedDict):
    collection_id: str
    conversation_id: str
    user_message: str
    rewritten_query: str
    retrieved_chunks: list[str]
    reranked_chunks: list[str]
    messages: list[dict]
    answer: str
    early_exit: bool


async def collection_router(state: ChatState) -> dict:
    client = await get_chroma_client()
    try:
        collection = await client.get_collection(state["collection_id"])
        count = await collection.count()
        if count == 0:
            return {
                "early_exit": True,
                "answer": "This collection has no documents yet. Please upload some documents first.",
            }
    except Exception:
        return {
            "early_exit": True,
            "answer": "Collection not found or unavailable.",
        }
    return {"early_exit": False}


async def query_rewriter(state: ChatState) -> dict:
    messages = state.get("messages", [])
    if not messages:
        return {"rewritten_query": state["user_message"]}

    settings = get_settings()
    llm = get_llm(settings)

    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages[-6:]
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Given the conversation history and the user's follow-up question, "
            "rewrite the question to be standalone and optimized for document retrieval. "
            "Output only the rewritten question, nothing else.",
        ),
        ("human", "History:\n{history}\n\nFollow-up question: {question}"),
    ])

    chain = prompt | llm | StrOutputParser()
    rewritten = await chain.ainvoke({"history": history_text, "question": state["user_message"]})
    return {"rewritten_query": rewritten.strip()}


async def retriever(state: ChatState) -> dict:
    settings = get_settings()
    embeddings = get_embeddings(settings)
    query = state.get("rewritten_query") or state["user_message"]

    query_embedding = await asyncio.to_thread(embeddings.embed_query, query)

    client = await get_chroma_client()
    collection = await client.get_collection(state["collection_id"])

    results = await collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        include=["metadatas"],
    )

    seen_parent_ids: set[str] = set()
    parent_texts: list[str] = []

    for metadata in results["metadatas"][0]:
        parent_id = metadata.get("parent_id")
        parent_text = metadata.get("parent_text", "")
        if parent_id and parent_id not in seen_parent_ids and parent_text:
            seen_parent_ids.add(parent_id)
            parent_texts.append(parent_text)

    if not parent_texts:
        return {
            "retrieved_chunks": [],
            "early_exit": True,
            "answer": "I couldn't find any relevant information in this collection.",
        }

    return {"retrieved_chunks": parent_texts, "early_exit": False}


async def reranker_node(state: ChatState) -> dict:
    query = state.get("rewritten_query") or state["user_message"]
    reranked = await asyncio.to_thread(rerank, query, state["retrieved_chunks"], 5)
    return {"reranked_chunks": reranked}


async def generator(state: ChatState) -> dict:
    settings = get_settings()
    llm = get_llm(settings)

    context = "\n\n---\n\n".join(state["reranked_chunks"])
    system_prompt = (
        "You are a helpful assistant answering questions based on the provided context. "
        "Use only the context below to answer. If the answer isn't in the context, say so.\n\n"
        f"Context:\n{context}"
    )

    lc_messages: list = [SystemMessage(content=system_prompt)]
    for msg in state.get("messages", []):
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))
    lc_messages.append(HumanMessage(content=state["user_message"]))

    parts: list[str] = []
    async for chunk in llm.astream(lc_messages):
        parts.append(chunk.content)

    return {"answer": "".join(parts)}


def _route_after_collection(state: ChatState) -> str:
    return END if state.get("early_exit") else "query_rewriter"


def _route_after_retriever(state: ChatState) -> str:
    return END if state.get("early_exit") else "reranker"


def _build_graph():
    builder = StateGraph(ChatState)
    builder.add_node("collection_router", collection_router)
    builder.add_node("query_rewriter", query_rewriter)
    builder.add_node("retriever", retriever)
    builder.add_node("reranker", reranker_node)
    builder.add_node("generator", generator)

    builder.set_entry_point("collection_router")
    builder.add_conditional_edges("collection_router", _route_after_collection)
    builder.add_edge("query_rewriter", "retriever")
    builder.add_conditional_edges("retriever", _route_after_retriever)
    builder.add_edge("reranker", "generator")
    builder.add_edge("generator", END)

    return builder.compile()


graph = _build_graph()


async def run_rag_pipeline(
    collection_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_message: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream answer tokens from the RAG pipeline via astream_events."""
    initial_state: ChatState = {
        "collection_id": str(collection_id),
        "conversation_id": str(conversation_id),
        "user_message": user_message,
        "rewritten_query": "",
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "messages": messages,
        "answer": "",
        "early_exit": False,
    }

    yielded_any = False
    final_answer = ""

    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event["event"]
        if (
            kind == "on_chat_model_stream"
            and event.get("metadata", {}).get("langgraph_node") == "generator"
        ):
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield chunk.content
                yielded_any = True
        elif kind == "on_chain_end" and event.get("name") == "LangGraph":
            output = event["data"].get("output", {})
            final_answer = output.get("answer", "")

    if not yielded_any and final_answer:
        yield final_answer
