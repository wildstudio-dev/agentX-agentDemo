"""This "graph" simply exposes an endpoint for a user to upload docs to be indexed."""
import logging
import os
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from react_agent.state import InputState
from react_agent.configuration import Configuration
from react_agent.utils import get_token_size
from langgraph.store.base import BaseStore
import uuid
import asyncio

from langchain_text_splitters import RecursiveCharacterTextSplitter

# This is not really a special number
# Generally should be below 8000
# roughly the max embedding size input of the common models
SPLIT_TOKEN_COUNT = 2000
text_splitter = RecursiveCharacterTextSplitter(chunk_size=SPLIT_TOKEN_COUNT, chunk_overlap=100)


async def insert_memory(text, store, user_id, property_id):
    mem_id = uuid.uuid4()
    await store.aput(
        (user_id, property_id),
        key=str(mem_id),
        value={"text": text},
    )
    return mem_id


async def index_docs(
        state: InputState,
        config: Optional[RunnableConfig] = None,
        *,
        store: BaseStore
) -> dict[str, str]:
    """Asynchronously index documents in the given state using the configured retriever.

    This function takes the documents from the state, ensures they have a user ID,
    adds them to the retriever's index, and then signals for the documents to be
    deleted from the state.

    Args:
        state (IndexState): The current state containing documents and retriever.
        config (Optional[RunnableConfig]): Configuration for the indexing process.r
    """
    last_message = state.messages[-1]
    if not config:
        raise ValueError("Configuration required to run index_docs.")

    local_config = Configuration.from_runnable_config(config)
    user_id = local_config.user_id

    text = last_message.additional_kwargs.get("extractedText", None)
    property_id = last_message.additional_kwargs.get("propertyId", None)
    if text is None or property_id is None:
        return {"messages": "no text or property ID found in last message."}

    text_splits = []
    logging.info("=============================== in index graph")
    logging.info(text)
    logging.info("=============================== in index graph")
    # I am applying a text splitter here
    # since there is no built-in process for this
    # inside the embed process
    if get_token_size(text) > SPLIT_TOKEN_COUNT:
        logging.info("Splitting text: %s", get_token_size(text))
        text_splits.extend(text_splitter.split_text(text))
    else:
        logging.info("Not splitting text: %s", get_token_size(text))
        text_splits.append(text)
    logging.info("Text splits: %s", len(text_splits))

    saved_memories = await asyncio.gather(
        *(
            insert_memory(split, store, user_id, property_id)
            for split in text_splits
        )
    )
    try:
        document_id = last_message.additional_kwargs.get("documentId", None)
        summary = last_message.additional_kwargs.get("summary", None)
        document_name = last_message.additional_kwargs.get("documentName", None)
        logging.info("Document ID: %s", document_id)
        if document_id is not None and summary is not None and document_name is not None:
            await store.aput(
                (user_id, "summary_" + property_id),
                key=str(document_id),
                value={
                    "summary": summary,
                    "document_name": document_name,
                },
            )

            logging.info("Saved summaries for document ID %s: %s", document_id, summary)
    except Exception as e:
        logging.error("Error saving summary: %s", e)

    logging.info("Calling the model langsmith settings:")
    logging.info("LANGSMITH_API_KEY: %s", os.getenv("LANGSMITH_API_KEY"))
    logging.info("LANGSMITH_TRACING: %s", os.getenv("LANGSMITH_TRACING"))
    logging.info("LANGSMITH_ENDPOINT: %s", os.getenv("LANGSMITH_ENDPOINT"))
    logging.info("LANGSMITH_PROJECT: %s", os.getenv("LANGSMITH_PROJECT"))
    return {"messages": str(saved_memories)}


builder = StateGraph(InputState, config_schema=Configuration)
builder.add_node(index_docs)
builder.add_edge("__start__", "index_docs")
graph = builder.compile()
graph.name = "IndexGraph"
