"""Define the state structures for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, Dict, List, Any, Optional, Union

from langchain_core.messages import AnyMessage, BaseMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep
from typing_extensions import Annotated


@dataclass
class InputState:
    """Defines the input state for the agent, representing a narrower interface to the outside world.

    This class is used to define the initial state and structure of incoming data.
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """
    Messages tracking the primary execution state of the agent.

    Typically accumulates a pattern of:
    1. HumanMessage - user input
    2. AIMessage with .tool_calls - agent picking tool(s) to use to collect information
    3. ToolMessage(s) - the responses (or errors) from the executed tools
    4. AIMessage without .tool_calls - agent responding in unstructured format to the user
    5. HumanMessage - user responds with the next conversational turn

    Steps 2-5 may repeat as needed.

    The `add_messages` annotation ensures that new messages are merged with existing ones,
    updating by ID to maintain an "append-only" state unless a message with the same ID is provided.
    """
    
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    """
    List of file attachments for multimodal processing.
    Each attachment dict contains:
    - filename: str - The name of the file
    - content_type: str - MIME type of the file
    - size: int - File size in bytes
    - data: str - Base64 encoded file content (for images/PDFs)
    - text: Optional[str] - Text content (for text files)
    """


@dataclass
class State(InputState):
    """Represents the complete state of the agent, extending InputState with additional attributes.

    This class can be used to store any information needed throughout the agent's lifecycle.
    """

    is_last_step: IsLastStep = field(default=False)
    """
    Indicates whether the current step is the last one before the graph raises an error.

    This is a 'managed' variable, controlled by the state machine rather than user code.
    It is set to 'True' when the step count reaches recursion_limit - 1.
    """

    rate: Optional[float] = field(default=None)
    """
    Optional interest rate from metadata to be used in rate calculations.

    This rate can be provided via metadata and will be passed to the get_rate tool
    if no rate is explicitly specified in the tool call.
    """
    
