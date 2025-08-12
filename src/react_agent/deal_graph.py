import logging
from datetime import UTC, datetime
from typing import Dict, List, cast

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.store.base import BaseStore
from react_agent.configuration import Configuration
from react_agent.state import InputState, State
from dotenv import load_dotenv
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from langchain.chat_models import init_chat_model

load_dotenv()


async def call_model(state: State, config: RunnableConfig, *, store: BaseStore) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_context()

    provider, model = configuration.model.split("/", maxsplit=1)
    chat_model = init_chat_model(
        model,
        model_provider=provider,
        max_tokens=256,
    )

    """Extract the user's state from the conversation and update the memory."""
    configurable = Configuration.from_runnable_config(config)
    metadata = Configuration.from_metadata(config)

    memories = []
    try:
        if metadata.property_id:
            logging.info(f"Property ID found, using it in the namespace. {metadata.property_id}")
            namespace_prefix = (configurable.user_id, metadata.property_id)
            logging.info(f"Retrieving memories for namespace: {namespace_prefix}")
            namespaces = await store.alist_namespaces()
            logging.info(f"Available namespaces: {namespaces}")
            memories = await store.asearch(
                namespace_prefix,
                query=str([m.content for m in state.messages[-3:]]),
                limit=5,
            )
            logging.info(f"Retrieved memories: {memories}")
    except Exception as e:
        logging.error(f"Error retrieving memories: {e}")

    # Format memories for inclusion in the prompt
    formatted = "\n".join(f"[{mem.key}]: {mem.value} (similarity: {mem.score})" for mem in memories)
    if formatted:
        formatted = f"""
    <memories>
    {formatted}
    </memories>"""

    system_message = configuration.deal_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat(),
        memories=formatted,
    )

    messages = trim_messages(
        state.messages,
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=256,
        start_on="human",
        end_on=("human", "tool"),
    )

    # Prepare messages with multimodal support
    messages_to_send = [{"role": "system", "content": system_message}]

    for i, msg in enumerate(messages):
        messages_to_send.append(msg)

    # Get the model's response
    response = cast(
        AIMessage,
        await chat_model.ainvoke(messages_to_send),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }
    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}


builder = StateGraph(
    State,
    input=InputState,
    config_schema=Configuration,
)

# Define the nodes
builder.add_node(call_model)

# Set the entrypoint - directly call model since files are handled in messages
builder.set_entry_point("call_model")

# This creates a cycle: after using tools, we always return to the model
builder.add_edge("call_model", END)

# Compile the builder into an executable graph
graph = builder.compile(
    name="WillStudio Deal Dashboard Agent",
)
