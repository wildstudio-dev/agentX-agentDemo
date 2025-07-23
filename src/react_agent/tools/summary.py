import logging
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
from langchain_core.tools import InjectedToolArg
from react_agent.configuration import Configuration

# Tool function for LangGraph binding
async def summary(query: str) -> str:
    """User requests summary of a specific document name
    Args:
        query (str): The query or request for summarization.
    """
    return "Summary tool called"

async def process_summary(
        query: str,
        config: RunnableConfig,
        store: BaseStore,
) -> str:
    """User requests summary of a specific document name
    Args:
        query (str): The query or request for summarization.
        config (RunnableConfig): Configuration for the run.
        store (BaseStore): Store for accessing memories.
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
            memories = await store.asearch(
                namespace_prefix,
                query=query,
                limit=1,
            )
            logging.info(f"Memories found: {memories}")
            formatted = "\n".join(f"{mem.value}" for mem in memories)
    except Exception as e:
        logging.error(f"Error retrieving memories: {e}")
        formatted = "Error retrieving summary."
    logging.info(f"Summarizing document: {query} {formatted}")
    return formatted
