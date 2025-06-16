"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import asyncio
import logging
from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.base import BaseStore
from langgraph.types import Command, interrupt

from react_agent.state import InputState, State
from react_agent.custom_get_rate_tool import get_rate
from react_agent.upsert_memory import upsert_memory
from react_agent.configuration import Configuration
from react_agent.utils import load_chat_model


# Define the function that calls the model

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

    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(configuration.model).bind_tools([get_rate, upsert_memory])

    """Extract the user's state from the conversation and update the memory."""
    configurable = Configuration.from_runnable_config(config)

    memories = []
    try:
        memories = await store.asearch(
            ("memories", configurable.user_id if configurable.user_id else "default"),
            query=str([m.content for m in state.messages[-3:]]),
            limit=10,
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

    system_message = configuration.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat(),
        memories=formatted,
    )

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
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


async def recommend_product(state: State) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_context()

    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(configuration.model)

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = configuration.recommend_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}


async def store_memory(
        state: State,
        config: RunnableConfig,
        *,
        store: BaseStore
):
    # Extract tool calls from the last message
    if not state.messages:
        logging.error("No messages found in the state.")
        return {"messages": []}
    last_message = state.messages[-1]
    tool_calls = last_message.tool_calls
    upsert_memory_calls = [
        tc
        for tc in tool_calls
        if tc["name"] == "upsert_memory"
    ]

    # Concurrently execute all upsert_memory calls
    saved_memories = await asyncio.gather(
        *(
            upsert_memory(**tc["args"], config=config, store=store)
            for tc in upsert_memory_calls
        )
    )

    # Format the results of memory storage operations
    # This provides confirmation to the model that the actions it took were completed
    results = [
        {
            "role": "tool",
            "content": mem,
            "tool_call_id": tc["id"],
            "name": tc["name"],
        }
        for tc, mem in zip(tool_calls, saved_memories)
    ]
    return {"messages": results}


# Define a new graph

builder = StateGraph(
    State,
    input=InputState,
    config_schema=Configuration,
)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node("get_rate", ToolNode([get_rate]))
builder.add_node("store_memory", store_memory)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")


def approve_memory_store(state: State) -> Command[Literal["store_memory", "__end__"]]:
    decision = interrupt({
        "question": "Would you like to save scenario?",
    })
    logging.info(f"Decision made: {decision}")
    if decision == "Yes":
        return Command(goto="store_memory")
    else:
        # Don't create edges from this node to the end or store_memory because
        # it will directly store_memory whatever we pass here as Command goto
        # https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/review-tool-calls/#simple-usage
        # https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/add-human-in-the-loop/#approve-or-reject
        last_message = state.messages[-1]
        tool_call = last_message.tool_calls[-1]
        tool_message = {
            "role": "tool",
            "content": "Memory not created",
            "name": tool_call["name"],
            "tool_call_id": tool_call["id"],
        }
        return Command(goto=END, update={"messages": [tool_message]})


builder.add_node("approve_memory_store", approve_memory_store)


def route_model_output(state: State) -> Literal["__end__", "get_rate", "approve_memory_store"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("__end__" or "get_rate" or "store_memory").
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    if not last_message.tool_calls:
        return END
    if last_message.tool_calls[0]["name"] == "get_rate":
        return "get_rate"
    if last_message.tool_calls[0]["name"] == "upsert_memory":
        return "approve_memory_store"
    return END


# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
    "call_model",
    # After call_model finishes running, the next node(s) are scheduled
    # based on the output from route_model_output
    route_model_output,
)

# This creates a cycle: after using tools, we always return to the model
builder.add_edge("get_rate", END)
builder.add_edge("store_memory", END)

# Compile the builder into an executable graph
graph = builder.compile(
    name="WillStudio LoanX Agent",
)
