"""This "graph" simply exposes an endpoint for a user to upload docs to be indexed."""
import logging
from typing import Optional, Sequence

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from react_agent.state import InputState, State
from react_agent.configuration import Configuration
from langgraph.store.base import BaseStore
import uuid
from react_agent.tools.document_analysis import process_document_analysis


# def ensure_docs_have_user_id(
#     docs: Sequence[Document], config: RunnableConfig
# ) -> list[Document]:
#     """Ensure that all documents have a user_id in their metadata.
#
#         docs (Sequence[Document]): A sequence of Document objects to process.
#         config (RunnableConfig): A configuration object containing the user_id.
#
#     Returns:
#         list[Document]: A new list of Document objects with updated metadata.
#     """
#     user_id = config["configurable"]["user_id"]
#     return [
#         Document(
#             page_content=doc.page_content, metadata={**doc.metadata, "user_id": user_id}
#         )
#         for doc in docs
#     ]


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
    result = await process_document_analysis(state)
    messages = result.get("messages", [])
    if not config:
        raise ValueError("Configuration required to run index_docs.")

    logging.info(messages)

    local_config = Configuration.from_runnable_config(config)
    user_id = local_config.user_id
    mem_id = uuid.uuid4()
    content = messages[0]["content"]
    await store.aput(
        ("property1", user_id),
        key=str(mem_id),
        value={"text":  content[2]["text"]},
    )
    # with retrieval.make_retriever(config) as retriever:
        # stamped_docs = ensure_docs_have_user_id(state.docs, config)

    # await retriever.aadd_documents(stamped_docs)
    return {"messages": "delete"}


# Define a new graph


builder = StateGraph(InputState, config_schema=Configuration)
builder.add_node(index_docs)
builder.add_edge("__start__", "index_docs")
# Finally, we compile it!
# This compiles it into a graph you can invoke and deploy.
graph = builder.compile()
graph.name = "IndexGraph"