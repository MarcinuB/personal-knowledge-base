"""Generate the RAGAS evaluation testset from the sample document.

Run once from the backend/ directory, then review and commit testset.json:

    cd backend
    OPENAI_API_KEY=sk-... python -m evals.generate_testset

The script uses RAGAS's TestsetGenerator to produce diverse questions from
the sample architecture document. Review the output and delete any poor-quality
entries before committing testset.json.
"""
import json
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.testset import TestsetGenerator

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.shared.config import get_settings  # noqa: E402

SAMPLE_DOC = Path(__file__).parent / "sample_docs" / "knowledge.txt"
OUTPUT = Path(__file__).parent / "testset.json"
TESTSET_SIZE = 10


def main() -> None:
    settings = get_settings()
    api_key = settings.openai_api_key or None  # falls back to OPENAI_API_KEY env var if empty

    docs = TextLoader(str(SAMPLE_DOC)).load()

    llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", api_key=api_key))
    embeddings = OpenAIEmbeddings(api_key=api_key)

    generator = TestsetGenerator(llm=llm, embedding_model=embeddings)
    testset = generator.generate_with_langchain_docs(docs, testset_size=TESTSET_SIZE)

    samples = testset.to_list()
    OUTPUT.write_text(json.dumps(samples, indent=2))
    print(f"Wrote {len(samples)} samples to {OUTPUT}")
    print("Review testset.json, remove poor-quality entries, then commit.")


if __name__ == "__main__":
    main()
