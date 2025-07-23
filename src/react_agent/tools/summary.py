import logging
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
from langchain_core.tools import InjectedToolArg
from react_agent.configuration import Configuration

async def summary(
        query: str,
        *,
        config: Annotated[RunnableConfig, InjectedToolArg],
        store: Annotated[BaseStore, InjectedToolArg],
) -> str:
    """User requests summary of a specific document name
    Args:
        query (str): The query or request for summarization.
    """
    configurable = Configuration.from_runnable_config(config)
    metadata = Configuration.from_metadata(config)
    formatted = "Default summary"
    logging.info(f"Summary Metadata: {metadata}")
    try:
        if metadata.property_id:
            logging.info(f"Property ID found, using it in the namespace. {metadata.property_id}")
            namespace_prefix = (configurable.user_id, "summary_" + metadata.property_id)
            logging.info(f"Retrieving memories for namespace: {namespace_prefix}")
            namespaces = await store.alist_namespaces()
            logging.info(f"Available namespaces: {namespaces}")
            memories = await store.asearch(
                namespace_prefix,
                query=query,
                limit=3,
            )
            formatted = "\n".join(f"[{mem.key}]: {mem.value} (similarity: {mem.score})" for mem in memories)
    except Exception as e:
        logging.error(f"Error retrieving memories: {e}")
        formatted = "Error retrieving summary."
    logging.info(f"Summarizing document: {query} {formatted}")
    return formatted
