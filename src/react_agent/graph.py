"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.base import BaseStore
from langgraph.types import Command, interrupt
from react_agent.configuration import Configuration
from react_agent.custom_get_rate_tool_v3 import get_rate
from react_agent.state import InputState, State
from react_agent.upsert_memory import upsert_memory
from react_agent.utils import load_chat_model
from react_agent.tools.document_analysis import document_analysis, process_document_analysis
from react_agent.prompts import DOCUMENT_ANALYSIS_PROMPTS
from dotenv import load_dotenv
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)

from react_agent.tools.summary import summary, process_summary

load_dotenv()


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

    if len(state.messages) == 1 and state.messages[0].type == "ai":
        logging.info("Skipping model call as the first message is AIMessage without tool calls.")
        return {"messages": []}

    logging.info("Calling the model langsmith settings:")
    logging.info("LANGSMITH_API_KEY: %s", os.getenv("LANGSMITH_API_KEY"))
    logging.info("LANGSMITH_TRACING: %s", os.getenv("LANGSMITH_TRACING"))
    logging.info("LANGSMITH_ENDPOINT: %s", os.getenv("LANGSMITH_ENDPOINT"))
    logging.info("LANGSMITH_PROJECT: %s", os.getenv("LANGSMITH_PROJECT"))
    try:
        for key, value in os.environ.items():
            logging.info("%s: %s", key, value)
    except Exception as e:
        logging.error("Error logging environment variables: %s", e)

    configuration = Configuration.from_context()

    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(configuration.model).bind_tools([get_rate, upsert_memory, document_analysis, summary])

    """Extract the user's state from the conversation and update the memory."""
    configurable = Configuration.from_runnable_config(config)
    metadata = Configuration.from_metadata(config)

    memories = []
    try:
        namespace_prefix = ("memories", configurable.user_id)
        if metadata.property_id:
            logging.info(f"Property ID found, using it in the namespace. {metadata.property_id}")
            namespace_prefix = (configurable.user_id, metadata.property_id)
        logging.info(f"Retrieving memories for namespace: {namespace_prefix}")
        namespaces = await store.alist_namespaces()
        logging.info(f"Available namespaces: {namespaces}")
        memories = await store.asearch(
            namespace_prefix,
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

    messages = trim_messages(
        state.messages,
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=1024,
        start_on="human",
        end_on=("human", "tool"),
    )

    # Prepare messages with multimodal support
    messages_to_send = [{"role": "system", "content": system_message}]

    for i, msg in enumerate(messages):
        messages_to_send.append(msg)
        if msg.additional_kwargs and "prompt_key" in msg.additional_kwargs \
                and "text" in msg.additional_kwargs and "document_type" in msg.additional_kwargs:
            prompt = DOCUMENT_ANALYSIS_PROMPTS.get(msg.additional_kwargs["prompt_key"], "")
            if prompt:
                messages_to_send.append({
                    "role": "user",
                    "content": prompt.format(
                        text=msg.additional_kwargs["text"],
                        document_type=msg.additional_kwargs["document_type"]
                    )
                })

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(messages_to_send),
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


async def document_analysis_node(state: State, config: RunnableConfig):
    # Extract tool calls from the last message
    if not state.messages:
        logging.error("document_analysis_node No messages found in the state.")
        return {"messages": []}

    last_message = state.messages[-1]
    tool_calls = last_message.tool_calls
    analysis_calls = [
        tc
        for tc in tool_calls
        if tc["name"] == "document_analysis"
    ]

    # Process document analysis to get multimodal content
    analysis_results = await asyncio.gather(
        *(
            process_document_analysis(state)
            for _tc in analysis_calls
        )
    )

    if len(analysis_results) == 0:
        logging.error("document_analysis_node no analysis results found.")
        results = [
            {
                "role": "tool",
                "content": "Cannot process document analysis, please upload the file",
                "tool_call_id": tc["id"],
                "name": tc["name"],
            }
            for tc in analysis_calls
        ]
        return {"messages": results}

    # Aggregate all messages including the multimodal content
    aggregated_messages = []

    # Add system message
    configuration = Configuration.from_context()
    system_message = configuration.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat(),
        memories="",  # No memories for document analysis
    )
    aggregated_messages.append({"role": "system", "content": system_message})

    # Combine all multimodal content into a single user message
    all_content = []
    for result in analysis_results:
        if result.get("messages"):
            for msg in result["messages"]:
                if msg.get("content"):
                    # Ensure content is always a list of objects for multimodal
                    content = msg["content"]
                    if isinstance(content, list):
                        all_content.extend(content)
                    else:
                        # If it's a string, wrap it in a text object
                        all_content.append({"type": "text", "text": str(content)})

    if all_content:
        aggregated_messages.append({
            "role": "user",
            "content": all_content
        })

    model = load_chat_model(configuration.model)
    response = cast(
        AIMessage,
        await model.ainvoke(aggregated_messages),
    )

    # Format as tool call responses
    results = [
        {
            "role": "tool",
            "content": str(response.content),
            "tool_call_id": tc["id"],
            "name": tc["name"],
            "additional_kwargs": {
                "text": all_content,
            }
        }
        for tc in analysis_calls
    ]

    return {"messages": results}


async def summary_node(state: State, config: RunnableConfig, *, store: BaseStore):
    """Handle summary tool calls with proper store and config access."""
    if not state.messages:
        logging.error("summary_node: No messages found in the state.")
        return {"messages": []}

    last_message = state.messages[-1]
    tool_calls = last_message.tool_calls
    summary_calls = [
        tc for tc in tool_calls
        if tc["name"] == "summary"
    ]

    # Execute all summary calls concurrently
    summary_results = await asyncio.gather(
        *(
            process_summary(tc["args"]["query"], config, store)
            for tc in summary_calls
        )
    )

    # Format results as tool responses
    results = [
        {
            "role": "tool",
            "content": result,
            "tool_call_id": tc["id"],
            "name": tc["name"],
        }
        for tc, result in zip(summary_calls, summary_results)
    ]

    return {"messages": results}


# Define a new graph

builder = StateGraph(
    State,
    input=InputState,
    config_schema=Configuration,
)

# Define the nodes
builder.add_node(call_model)
builder.add_node("get_rate", ToolNode([get_rate]))
builder.add_node("summary_node", summary_node)
builder.add_node("store_memory", store_memory)
builder.add_node("document_analysis_node", document_analysis_node)

# Set the entrypoint - directly call model since files are handled in messages
builder.set_entry_point("call_model")


def approve_memory_store(state: State) -> Command[Literal["store_memory", "__end__"]]:
    decision = interrupt({
        "question": "Would you like to save preference?",
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


def route_model_output(state: State) -> Literal[
    "__end__", "get_rate", "approve_memory_store", "document_analysis_node", "summary_node"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    if not last_message.tool_calls:
        return END

    tool_name = last_message.tool_calls[0]["name"]
    logging.info("Routing model output to tool: %s", tool_name)
    if tool_name == "get_rate":
        return "get_rate"
    elif tool_name == "summary":
        logging.info("Routing to summary tool")
        return "summary_node"
    elif tool_name == "upsert_memory":
        return "approve_memory_store"
    elif tool_name == "document_analysis":
        return "document_analysis_node"
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
builder.add_edge("summary_node", END)
builder.add_edge("document_analysis_node", END)

# Compile the builder into an executable graph
graph = builder.compile(
    name="WillStudio Agent X Agent",
)
