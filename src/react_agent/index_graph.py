"""This "graph" simply exposes an endpoint for a user to upload docs to be indexed."""
import logging
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from react_agent.state import InputState
from react_agent.configuration import Configuration
from langgraph.store.base import BaseStore
import uuid
import asyncio

from langchain_text_splitters import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=100)


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
    if len(text) / 4 > 4000:
        logging.info("Splitting text: %s", len(text) / 4)
        text_splits.extend(text_splitter.split_text(text))
    else:
        logging.info("Not splitting text: %s", len(text) / 4)
        text_splits.append(text)
    logging.info("Text splits: %s", len(text_splits))

    saved_memories = await asyncio.gather(
        *(
            insert_memory(split, store, user_id, property_id)
            for split in text_splits
        )
    )
    return {"messages": str(saved_memories)}


builder = StateGraph(InputState, config_schema=Configuration)
builder.add_node(index_docs)
builder.add_edge("__start__", "index_docs")
graph = builder.compile()
graph.name = "IndexGraph"
