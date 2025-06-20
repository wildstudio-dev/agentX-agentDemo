# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
- `make dev` - Run the agent in development mode using LangGraph Studio (requires conda environment 'loanx')
- `uvx --from="langgraph-cli[inmem]" --with-editable=. langgraph dev --allow-blocking` - Alternative dev command

### Testing
- `make test` - Run unit tests in tests/unit_tests/
- `make test TEST_FILE=<path>` - Run specific test file
- `make test_watch` - Run tests in watch mode with auto-reload
- `make extended_tests` - Run extended test suite
- `python -m pytest tests/integration_tests/` - Run integration tests

### Code Quality
- `make lint` - Run linting with ruff and mypy type checking
- `make format` - Format code with ruff
- `make lint_diff` - Lint only changed files vs main branch
- `make format_diff` - Format only changed files vs main branch

## Architecture

### Core Components

**LangGraph Agent Structure**
- `src/react_agent/graph.py` - Main agent graph definition with ReAct pattern (Reasoning + Action)
- `src/react_agent/state.py` - Agent state management with message history
- `src/react_agent/configuration.py` - Configuration schema with model selection and prompts
- `src/react_agent/prompts.py` - System prompts for different agent behaviors

**Key Flows**
1. **Main Agent Loop**: `call_model` → `route_model_output` → tool execution → back to model
2. **Memory Integration**: Agent retrieves semantic memories via vector store and can save new memories
3. **Tool Execution**: Currently supports `get_rate` (loan calculations) and `upsert_memory` (memory storage)
4. **Human-in-the-Loop**: Memory storage requires approval via `approve_memory_store` interrupt
5. **Multimodal Support**: Native handling of images and documents via GPT-4's vision capabilities

### Tools
- `src/react_agent/custom_get_rate_tool.py` - Mortgage rate calculator with loan limits validation
  - Flexible input parsing: supports "20k", "20 thousand", "20 grand", "$20,000", "20000 down"
  - Handles natural language currency formats and real estate terminology
- `src/react_agent/upsert_memory.py` - Memory storage functionality for user context
- Supports both Conventional and FHA loan types with different limits and requirements

### Multimodal File Handling
- `src/react_agent/file_handler.py` - Native multimodal file processing
  - **Images**: Sent directly to GPT-4 for visual analysis
  - **PDFs**: Converted to images to preserve formatting and visual elements
  - **Text files**: Included as text content in messages
- Files are processed in-conversation without storage
- See `FILE_HANDLING.md` for detailed documentation

### Authentication & Security
- `src/react_agent/security/auth.py` - JWT token validation with bearer scheme
- User-scoped resources via `add_owner` filtering by `ctx.user.identity`
- Memory and resources are private to authenticated users

### Configuration
- `langgraph.json` - LangGraph deployment config with graph entry point, memory store, and auth
- Memory store configured with 1536-dim embeddings via `src/react_agent/embed.py:aembed_texts`
- Environment variables loaded from `.env` file (copy from `.env.example`)

### Model Support & Personality
- Default: `openai/gpt-4.1` (configurable in `configuration.py`)
- Supports Anthropic, OpenAI, and Google GenAI models
- Model binding includes tool access for rate calculations and memory operations
- Agent personality: Professional, helpful AI assistant aware of its rate calculation capabilities
- Conversational tone with clear explanations of assumptions and methodology

## Development Notes

### Memory System
- Uses semantic search over stored user interactions and loan scenarios
- Embeddings function specified in langgraph.json due to custom requirements
- Memories are user-scoped and include similarity scoring

### Loan Calculation Logic
- Conventional loans: max 95% LTV, limits up to $1.5M+ based on units
- FHA loans: includes MIP (0.85% annually), different loan limits
- Default assumptions: 7.5% interest, 30-year term, 760 FICO, 20% down payment

### File Handling System
- Automatic processing of uploaded files at conversation start
- Supports PDF, CSV, JSON, text, and image files
- File contents are extracted and included in agent context
- Files are passed via state: `{"files": [{"filename": "...", "path": "...", "content_type": "...", "size": ...}]}`
- Processed contents stored in `state.file_contents` dictionary

### Testing Structure
- Unit tests: `tests/unit_tests/` with configuration testing
- Integration tests: `tests/integration_tests/` with graph execution testing  
- File processing tests: `tests/integration_tests/test_file_processing.py`
- VCR cassettes in `tests/cassettes/` for API interaction recording