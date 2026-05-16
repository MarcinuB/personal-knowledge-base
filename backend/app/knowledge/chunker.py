from langchain_text_splitters import RecursiveCharacterTextSplitter

# Character-based sizes approximating 200 and 800 token windows
CHILD_CHUNK_SIZE = 800
PARENT_CHUNK_SIZE = 3200
CHILD_CHUNK_OVERLAP = 80
PARENT_CHUNK_OVERLAP = 0

_parent_splitter = RecursiveCharacterTextSplitter(
    chunk_size=PARENT_CHUNK_SIZE,
    chunk_overlap=PARENT_CHUNK_OVERLAP,
)
_child_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHILD_CHUNK_SIZE,
    chunk_overlap=CHILD_CHUNK_OVERLAP,
)


def chunk_document(text: str, doc_id: str, collection_id: str) -> list[dict]:
    """Split text into child chunks, each carrying its parent text as metadata.

    Returns a list of dicts with keys: child_text, parent_id, parent_text,
    doc_id, collection_id. Callers embed child_text and store the rest as
    ChromaDB metadata.
    """
    parents = _parent_splitter.split_text(text)
    chunks: list[dict] = []
    for i, parent_text in enumerate(parents):
        parent_id = f"{doc_id}_p{i}"
        for child_text in _child_splitter.split_text(parent_text):
            chunks.append(
                {
                    "child_text": child_text,
                    "parent_id": parent_id,
                    "parent_text": parent_text,
                    "doc_id": doc_id,
                    "collection_id": collection_id,
                }
            )
    return chunks
