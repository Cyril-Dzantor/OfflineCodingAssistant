# Offline Coding Assistant (Cydags)

A personal, fully offline coding assistant that runs locally. It combines a local language model with repository inspection tools so it can understand the project structure, locate relevant code, and answer questions without sending any data over the internet.

## Why I Built This

Most AI coding assistants rely on cloud APIs. That works fine in many cases, but it introduces clear trade-offs: privacy concerns with proprietary code, recurring subscription costs, and total dependency on an active internet connection.

I wanted something self-contained that runs on local hardware. To keep it practical on consumer GPUs and Apple Silicon, the project pairs a compact model (Qwen 2.5 Coder 1.5B) with a fast, deterministic retrieval layer rather than relying on heavy vector databases or cloud search APIs.

## How It Works

The assistant operates as an interactive CLI that inspects the local project before generating answers:

1. Repository Detection: Identifies project roots using common project files (.git, package.json, requirements.txt, pyproject.toml, etc.).
2. File Filtering: Excludes build artifacts, virtual environments, large binary assets (such as model weights), and respects rules in .gitignore.
3. Code Search: Fast keyword and regex search through project files to locate relevant code lines.
4. AST Parsing: Uses Tree-sitter to parse source files into structural symbols (classes, functions, methods, parameters, docstrings, imports) along with line ranges.
5. Context Builder: Merges matching search hits and parsed symbols, ranks them, and fits them into a strict character/token budget so the model context window is not overwhelmed.
6. Local Inference: Streams completions through llama-cpp-python using quantized GGUF weights, with hardware acceleration via NVIDIA CUDA or Apple Metal.

## Project Structure

- assistant/
  - agent/ - Agent orchestrator and execution state (Phase 4).
  - config/ - System configuration, hardware layers, and model settings.
  - core/ - Model interface (llama-cpp wrapper) and conversation history manager.
  - prompts/ - Base system prompt templates.
  - repo/ - Project understanding layer:
    - detector.py - Project root detection.
    - scanner.py - File traversal, metadata collection, and filtering.
    - search.py - Keyword and regex search engine.
    - parser.py - Tree-sitter code parser for structural symbols.
    - context.py - Budget-aware context assembler for prompts.
  - utils/ - Logging and helper utilities.
  - main.py - Interactive CLI interface.
- ProjectPlan/ - Detailed phase-by-phase design specifications.
- tests/ - Benchmark validation scripts and sample test projects.
- requirements.txt - Project dependencies and minimum versions.

## Requirements

- Python 3.10+
- Git
- Hardware:
  - NVIDIA GPU with CUDA support, or
  - Apple Silicon Mac (M-series with Metal), or
  - Modern multi-core CPU

## Setup

1. Clone or navigate to the repository:
   ```bash
   cd OfflineCodingAssistant
   ```

2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   # On Windows:
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   Hardware acceleration notes:
   - Windows (NVIDIA): Install the CUDA-enabled wheel for llama-cpp-python and ensure CUDA runtime DLLs are accessible.
   - macOS (Apple Silicon): Install llama-cpp-python with Metal support enabled.

4. Download model weights:
   Place the quantized GGUF model in the project folder (for example: `Qwen 2.5/Q8/qwen2.5-coder-1.5b-instruct-q8_0.gguf`).
   Verify the path matches `MODEL_PATH` in `assistant/config/settings.py`.

## Usage

Start the interactive session:

```powershell
python -m assistant.main
```

### Available Commands

Within the CLI, you can use the following commands:

- /project - Display detected project information, root directory, and languages.
- /tree - Print a clean directory tree of the project.
- /files - List all indexed files in the repository.
- /search <query> - Search project files for keywords or patterns.
- /symbols <file> - Display parsed symbols (classes, methods, functions) in a specific file.
- /context <query> - Preview the exact context constructed and sent to the model for a query.
- /clear - Reset conversation history.
- /help - Show available commands.
- /exit - Quit the assistant.

You can also ask questions directly in natural language (for example: "Where is project root detection implemented?"). The assistant searches the codebase, extracts relevant symbols, and provides an answer grounded in the actual source code.

## Current Status

- Phase 1: Environment & Local Inference (Complete)
- Phase 2: CLI Interface & Conversation Manager (Complete)
- Phase 3: Project & Code Understanding (Complete)
- Phase 4: Tool Integration & Agent System (In Progress)

