"""Define the configurable parameters for the agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Annotated, Optional, Any

from langchain_core.runnables import ensure_config, RunnableConfig
from langgraph.config import get_config

from react_agent.prompts import SECOND_SYSTEM_PROMPT, RECOMMEND_PROMPT, REPC_ANALYSIS_PROMPT


@dataclass(kw_only=True)
class Configuration:
    """The configuration for the agent."""
    user_id: str = "default"
    system_prompt: str = field(
        default=SECOND_SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )

    recommend_prompt: str = field(
        default=RECOMMEND_PROMPT,
        metadata={
            "description": "The system prompt to optimise the product received from the Loan X get rate api"
        },
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        # default="anthropic/claude-opus-4-20250514",
        default="openai/gpt-4.1",
        # default="google_genai/gemini-2.5-flash-preview-05-20",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )

    @classmethod
    def from_context(cls) -> Configuration:
        # TODO: This and the bottom function are more or less the same
        """Create a Configuration instance from a RunnableConfig object."""
        try:
            config = get_config()
        except RuntimeError:
            config = None
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})

    @classmethod
    def from_runnable_config(
            cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        # This querying configurable and checks if the fields here are present
        # in configurable and passes their value along.
        # Owner is present in metadata not in the configurable, so it won't be present
        # But user_id is set internally and its present in configurable and would be passed
        values: dict[str, Any] = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
            for f in fields(cls)
            if f.init
        }

        return cls(**{k: v for k, v in values.items() if v})
