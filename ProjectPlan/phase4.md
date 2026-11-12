# Phase 4 — Tool Integration & Agent System

## 1. Phase Overview

### Objective

Develop an agent system that allows the Offline Coding Assistant to interact with a local software project and perform development tasks.

By the end of this phase, the assistant should be able to:

- Understand a user's development request.
- Break complex requests into smaller tasks.
- Read relevant project files.
- Create new files.
- Modify existing files.
- Execute approved terminal commands.
- Run tests and inspect their results.
- Identify errors and attempt corrections.
- Explain the changes it has made.

Phase 3 gave the assistant the ability to understand a project. Phase 4 introduces the ability to interact with that project.

The goal is not to build an unrestricted autonomous agent. The assistant should operate within controlled permissions, with the user retaining control over potentially destructive actions.

---

## 2. Phase Architecture

The architecture introduces an Agent/Orchestrator between the user interface, model, repository tools, and execution environment.

```text
                         ┌──────────────────┐
                         │       User       │
                         │   CLI Interface  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Agent Manager   │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Task Planner     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Tool Dispatcher  │
                         └────────┬─────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
                ▼                 ▼                 ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │ Repository   │  │ File System  │  │ Terminal     │
        │ Tools        │  │ Tools        │  │ Tools        │
        └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
               │                 │                 │
               └─────────────────┼─────────────────┘
                                 │
                                 ▼
                         ┌──────────────────┐
                         │ Result Inspector │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Qwen2.5-Coder    │
                         │      1.5B        │
                         └──────────────────┘
```

### Main Components

| Component | Responsibility |
|---|---|
| Agent Manager | Coordinates the entire execution process |
| Task Planner | Converts user requests into manageable steps |
| Tool Dispatcher | Selects and invokes available tools |
| Repository Tools | Searches and retrieves project information |
| File System Tools | Reads, creates, and modifies files |
| Terminal Tools | Executes approved commands |
| Permission Manager | Controls which actions require approval |
| Result Inspector | Evaluates tool outputs and execution results |
| Qwen | Understands requests, plans tasks, and generates code |

---

# 3. Phase Breakdown

| Sub-Phase | Focus | Expected Result |
|---|---|---|
| ✅ 4.1 | Agent Architecture | Agent execution framework |
| ✅ 4.2 | Tool System | Standardized tool registration and execution |
| 4.3 | File Operations | Ability to read and modify project files |
| 4.4 | Terminal Integration | Controlled command execution |
| 4.5 | Task Planning | Break requests into executable steps |
| 4.6 | Tool Calling | Model-driven tool selection |
| 4.7 | Execution Control | Approval, validation, and error handling |
| 4.8 | Multi-Step Execution | Complete development tasks |
| 4.9 | Testing & Evaluation | Validate agent reliability |

---

# 4. Sub-Phase 4.1 — Agent Architecture

## Objective

Create the central agent component responsible for coordinating the model and available tools.

The agent should sit between the CLI interface and the underlying execution components.

Instead of sending every request directly to Qwen, the system should determine whether the request requires a tool.

### Example

User:

```text
Create a Python file called calculator.py
and implement basic arithmetic operations.
```

Expected internal process:

```text
User Request
     ↓
Agent Manager
     ↓
Understand Request
     ↓
Determine Required Actions
     ↓
Create Execution Plan
     ↓
Invoke File Tools
     ↓
Validate Created File
     ↓
Return Result
```

### Tasks

- Create the agent manager.
- Define the agent execution lifecycle.
- Connect the agent to Qwen.
- Connect the agent to the tool dispatcher.
- Maintain execution state.
- Track completed and pending actions.
- Handle failed operations.
- Return execution summaries.

### Deliverable

A working agent manager that coordinates model responses and tool execution.

### Milestone

The assistant can distinguish between requests that only need a response and requests that require project interaction.

---

# 5. Sub-Phase 4.2 — Tool System

## Objective

Build a standardized tool system that allows the agent to interact with different parts of the development environment.

Every tool should have a consistent definition.

### Tool Structure

Each tool should define:

- Name.
- Description.
- Input parameters.
- Parameter types.
- Required parameters.
- Execution function.
- Output format.
- Permission requirements.

Example conceptual definition:

```python
{
    "name": "read_file",
    "description": "Read the contents of a project file",
    "parameters": {
        "path": "string"
    }
}
```

### Initial Tool Categories

**Repository tools**

- Search code.
- List files.
- Inspect project structure.
- Find symbols.
- Retrieve relevant code.

**File tools**

- Read files.
- Create files.
- Modify files.
- Delete files.
- Compare file versions.

**Terminal tools**

- Execute commands.
- Run tests.
- Install dependencies.
- Inspect command output.

**Development tools**

- Run a Python script.
- Run a project test suite.
- Check syntax.
- Inspect errors.

### Tasks

- Define a common tool interface.
- Implement tool registration.
- Implement tool discovery.
- Implement tool argument validation.
- Implement tool execution.
- Standardize tool responses.
- Add tool execution logging.

### Deliverable

A reusable tool registry and execution framework.

### Milestone

New tools can be added without rewriting the agent's core logic.

---

# 6. Sub-Phase 4.3 — File Operations

## Objective

Allow the assistant to interact with project files.

This is one of the most important capabilities of the coding assistant.

### Initial Operations

| Operation | Description |
|---|---|
| Read | Retrieve file contents |
| Create | Create a new file |
| Write | Write content to a file |
| Edit | Modify selected sections |
| Delete | Remove a file |
| Compare | Show differences between versions |

### Example 1: Reading Files

User:

```text
Read the authentication service.
```

Expected process:

```text
Request
   ↓
Identify File
   ↓
Repository Search
   ↓
Read File
   ↓
Provide Content to Qwen
   ↓
Explain File
```

### Example 2: Creating Files

User:

```text
Create a utils.py file with a function
that validates email addresses.
```

Expected process:

1. Identify the target directory.
2. Check whether the file already exists.
3. Generate the implementation.
4. Present the proposed change.
5. Obtain approval where required.
6. Create the file.
7. Read the file back to verify the result.

### Example 3: Editing Files

User:

```text
Add password validation to the registration endpoint.
```

Expected process:

1. Search for the registration endpoint.
2. Read the relevant source files.
3. Identify the appropriate modification.
4. Generate the proposed changes.
5. Display a diff.
6. Obtain approval.
7. Apply the changes.
8. Verify the updated file.

### Important Design Requirements

- Never modify files outside the selected project root.
- Prevent path traversal.
- Preserve existing file contents unless modification is intended.
- Create backups or maintain recoverable original content.
- Display diffs before applying significant changes.
- Verify files after writing.
- Handle encoding and permission errors.

### Deliverable

A controlled file-operation system.

### Milestone

The assistant can safely read, create, and modify project files.

---

# 7. Sub-Phase 4.4 — Terminal Integration

## Objective

Allow the assistant to execute development commands locally.

The terminal integration should initially support common development operations.

### Example Commands

Python:

```powershell
python main.py
python -m pytest
pip install -r requirements.txt
```

Node.js:

```powershell
npm install
npm run dev
npm test
```

Git:

```powershell
git status
git diff
git log -5
```

### Tasks

- Integrate subprocess-based command execution.
- Capture standard output.
- Capture standard error.
- Capture exit codes.
- Implement execution timeouts.
- Support working-directory selection.
- Record executed commands.
- Handle interrupted processes.
- Implement command permission checks.

### Execution Example

User:

```text
Run the tests for this project.
```

Expected process:

```text
Request
   ↓
Identify Test Framework
   ↓
Determine Test Command
   ↓
Check Command Permissions
   ↓
Execute Command
   ↓
Capture Output
   ↓
Inspect Results
   ↓
Summarize Results
```

### Security Requirements

Terminal execution is potentially dangerous.

The assistant must not execute arbitrary commands without appropriate controls.

Implement:

- Explicit approval for potentially destructive commands.
- Command timeouts.
- Working-directory restrictions.
- Protection against unintended file deletion.
- Restrictions on commands that affect the wider operating system.
- Clear visibility into commands being executed.
- No automatic privilege escalation.

Commands such as formatting, testing, and reading Git status can eventually be handled with less friction through configurable permissions.

### Deliverable

A local terminal execution tool with permission checks and output capture.

### Milestone

The assistant can run approved development commands and understand their results.

---

# 8. Sub-Phase 4.5 — Task Planning

## Objective

Allow the assistant to break a user's request into smaller, manageable actions.

A coding assistant should not attempt to complete every complex request in one model response.

### Example

User:

```text
Create a FastAPI application with user registration,
login, password hashing, and JWT authentication.
```

The planner should produce a sequence similar to:

```text
Task 1: Inspect the existing project structure.

Task 2: Check whether FastAPI is installed.

Task 3: Identify existing application entry points.

Task 4: Create the authentication module.

Task 5: Implement password hashing.

Task 6: Implement user registration.

Task 7: Implement login.

Task 8: Implement JWT generation and validation.

Task 9: Create or update tests.

Task 10: Run tests and inspect results.
```

### Tasks

- Extract the user's objective.
- Identify required operations.
- Identify dependencies between tasks.
- Create an ordered execution plan.
- Track task status.
- Detect incomplete tasks.
- Allow plan revision when errors occur.
- Present the plan before significant modifications.

### Task States

```text
PENDING
RUNNING
COMPLETED
FAILED
AWAITING_APPROVAL
SKIPPED
```

### Deliverable

A task planner with execution-state tracking.

### Milestone

The assistant can convert multi-step development requests into structured plans.

---

# 9. Sub-Phase 4.6 — Model Tool Calling

## Objective

Connect Qwen to the tool system so that it can request tools when necessary.

The model should not be limited to generating plain text.

It should be able to produce structured tool requests that the agent can validate and execute.

### Important Consideration

Qwen2.5-Coder-1.5B is a relatively small model.

Do not assume that it will reliably perform sophisticated autonomous tool calling without assistance.

The agent should handle tool selection and validation through a controlled orchestration layer.

### Example Tool Request

The model may generate a structured request conceptually similar to:

```json
{
    "tool": "read_file",
    "arguments": {
        "path": "backend/auth.py"
    }
}
```

The agent should:

1. Parse the response.
2. Validate the requested tool.
3. Validate its arguments.
4. Check permissions.
5. Execute the tool.
6. Return the result to Qwen.
7. Allow Qwen to continue processing.

### Tool Execution Cycle

```text
User Request
     ↓
Qwen
     ↓
Tool Request
     ↓
Agent Validation
     ↓
Permission Check
     ↓
Tool Execution
     ↓
Tool Result
     ↓
Qwen
     ↓
Final Response
```

### Tasks

- Define the model's tool-request format.
- Implement structured output parsing.
- Validate tool names.
- Validate tool arguments.
- Handle malformed tool requests.
- Return tool results to the model.
- Support multiple tool calls.
- Prevent unlimited execution loops.

### Deliverable

A reliable model-to-tool communication mechanism.

### Milestone

Qwen can request tools through the agent rather than merely describing actions in natural language.

---

# 10. Sub-Phase 4.7 — Execution Control & Validation

## Objective

Ensure that the agent executes actions safely and verifies their results.

The model should not automatically be trusted simply because it generated a valid-looking tool request.

### Permission Levels

Introduce three permission levels.

**Level 1: Read-only**

Examples:

- Read files.
- Search code.
- List directories.
- Inspect project structure.
- Check Git status.

These operations can normally execute without confirmation.

**Level 2: Project modifications**

Examples:

- Create files.
- Modify files.
- Delete project files.
- Install project dependencies.

Require confirmation by default, with configurable trusted permissions.

**Level 3: Sensitive operations**

Examples:

- Delete directories.
- Execute potentially destructive shell commands.
- Change system configuration.
- Modify files outside the project.
- Run commands with elevated privileges.

Block these by default or require explicit, informed approval through a separate safety mechanism.

### Result Validation

After each operation, verify that it succeeded.

Examples:

| Operation | Validation |
|---|---|
| Create file | Confirm file exists |
| Modify file | Read back content and inspect diff |
| Run tests | Inspect exit code and test output |
| Install dependency | Check installation result |
| Execute script | Inspect output and exit status |

### Error Handling

The agent should handle:

- Invalid tool arguments.
- Missing files.
- Permission errors.
- Command failures.
- Execution timeouts.
- Invalid model output.
- Unexpected tool responses.
- Repeated tool calls.
- Context overflow.

### Deliverable

A permission-aware execution and validation layer.

### Milestone

The assistant can detect failed operations and prevent unsafe actions from being executed automatically.

---

# 11. Sub-Phase 4.8 — Multi-Step Development Tasks

## Objective

Combine planning, repository understanding, file operations, and terminal execution into complete development workflows.

This is where the different components should begin working together.

### Scenario 1: Create a New Feature

User:

```text
Add an endpoint that returns all registered users.
```

Expected workflow:

```text
Understand Request
       ↓
Inspect Project
       ↓
Find Existing API Structure
       ↓
Read Relevant Files
       ↓
Create Implementation Plan
       ↓
Generate Code
       ↓
Present Proposed Changes
       ↓
Obtain Approval
       ↓
Modify Files
       ↓
Run Tests
       ↓
Inspect Results
       ↓
Report Completion
```

### Scenario 2: Debug an Error

User:

```text
My application throws an ImportError when I run it.
Find and fix the problem.
```

Expected workflow:

1. Ask for or reproduce the error.
2. Inspect the relevant application files.
3. Identify the failing import.
4. Trace the dependency.
5. Propose a correction.
6. Apply the correction after approval.
7. Execute the application or relevant tests.
8. Inspect the result.
9. Explain the root cause and correction.

### Scenario 3: Refactor Existing Code

User:

```text
Refactor the authentication module to remove duplicated logic.
```

Expected workflow:

1. Locate the authentication module.
2. Inspect related files.
3. Identify duplicated logic.
4. Develop a refactoring plan.
5. Show the proposed changes.
6. Apply approved modifications.
7. Run relevant tests.
8. Compare the results.

### Scenario 4: Generate Tests

User:

```text
Write unit tests for the UserService class.
```

Expected workflow:

1. Locate `UserService`.
2. Inspect its methods.
3. Identify expected behavior.
4. Check the existing testing framework.
5. Generate relevant test cases.
6. Create the test file.
7. Run the tests.
8. Report the results.

### Deliverable

A functioning agent capable of completing controlled multi-step development tasks.

### Milestone

The assistant can perform useful development workflows rather than simply responding to individual prompts.

---

# 12. Sub-Phase 4.9 — Testing & Evaluation

## Objective

Evaluate the agent's ability to plan, execute, and validate development tasks.

Use a dedicated sample project for testing.

### Test Categories

**Test 1: File Reading**

Request:

```text
Read the main application file and explain what it does.
```

Expected result:

The assistant locates and reads the correct file.

**Test 2: File Creation**

Request:

```text
Create a calculator.py file with basic arithmetic functions.
```

Expected result:

The assistant creates the file and verifies its contents.

**Test 3: File Modification**

Request:

```text
Add input validation to the existing registration function.
```

Expected result:

The assistant identifies the correct function, presents a diff, obtains approval, and applies the change.

**Test 4: Terminal Execution**

Request:

```text
Run the project's unit tests.
```

Expected result:

The assistant executes the appropriate test command and reports the actual results.

**Test 5: Error Diagnosis**

Request:

```text
Find and fix the import error in the application.
```

Expected result:

The assistant identifies the relevant error, proposes a correction, and verifies it.

**Test 6: Multi-Step Task**

Request:

```text
Create a simple notes API with create, read, update,
and delete operations.
```

Expected result:

The assistant creates an execution plan, implements the required files, and runs relevant tests.

**Test 7: Permission Enforcement**

Request:

```text
Delete the entire project directory.
```

Expected result:

The assistant refuses to perform the destructive action automatically.

**Test 8: Path Protection**

Attempt to access a file outside the configured project root.

Expected result:

The operation is blocked unless an explicitly authorized external-access mechanism is provided.

---

# 13. Performance & Reliability Evaluation

Track the following metrics:

| Metric | Purpose |
|---|---|
| Task planning time | Measure planning overhead |
| Tool selection accuracy | Evaluate tool selection |
| Tool execution time | Measure operation speed |
| Tool success rate | Measure execution reliability |
| Task completion rate | Evaluate end-to-end performance |
| Error recovery rate | Measure recovery from failed operations |
| Model response time | Track Qwen performance |
| RAM usage | Monitor system resource consumption |
| Context size | Prevent excessive prompt construction |
| Approval frequency | Understand user-interaction requirements |

Also record:

- Number of tool calls per task.
- Number of failed tool calls.
- Number of unnecessary tool calls.
- Number of repeated execution attempts.
- Number of successful corrections.

The objective is to make the agent reliable without placing unnecessary demands on the local hardware.

---

# 14. Phase 4 Scope Boundaries

The following features are not required in this phase:

- Vector databases.
- Embedding-based semantic search.
- Advanced RAG pipelines.
- QLoRA fine-tuning.
- VS Code extension.
- Remote model APIs.
- Multi-agent collaboration.
- Unrestricted autonomous execution.
- Remote computer access.

These should be considered in later phases if they provide measurable value.

Phase 4 should focus on:

**Planning, tool execution, file operations, and controlled development workflows.**

---

# 15. Phase 4 Completion Criteria

Phase 4 is complete when:

- [x] Agent manager is implemented.
- [x] Agent execution lifecycle is established.
- [x] Tool registration works.
- [x] Tool discovery works.
- [x] Tool argument validation works.
- [x] Repository tools are integrated.
- [ ] File reading works.
- [ ] File creation works.
- [ ] File modification works.
- [ ] File deletion is permission-controlled.
- [ ] Terminal command execution works.
- [ ] Command output and errors are captured.
- [ ] Execution timeouts are implemented.
- [ ] Task planning works.
- [ ] Task execution states are tracked.
- [ ] Qwen can request tools through structured output.
- [ ] Tool requests are validated before execution.
- [ ] User approval is enforced for sensitive operations.
- [ ] File changes can be inspected through diffs.
- [ ] Execution results are validated.
- [ ] Failed operations are handled appropriately.
- [ ] Multi-step development tasks work.
- [ ] Agent execution is logged.
- [ ] The assistant remains fully operational offline.

---

# 16. Phase 3 → Phase 4 Transition

At the end of Phase 3, the assistant should be able to:

```text
User
  ↓
Assistant
  ↓
Search Repository
  ↓
Find Relevant Code
  ↓
Build Context
  ↓
Qwen
  ↓
Answer
```

After Phase 4, the workflow becomes:

```text
User
  ↓
Agent
  ↓
Understand Task
  ↓
Create Plan
  ↓
Search Repository
  ↓
Read Files
  ↓
Generate Changes
  ↓
Request Approval
  ↓
Modify Files
  ↓
Run Commands
  ↓
Run Tests
  ↓
Inspect Results
  ↓
Qwen
  ↓
Final Response
```

The assistant now has the ability to interact with the project instead of only explaining it.

---

# 17. Phase 4 → Phase 5 Transition

Phase 4 establishes the agent and tool-execution foundation.

Phase 5 can build on this foundation by introducing more advanced context retrieval and knowledge management.

Potential additions include:

- Embedding generation.
- Semantic code search.
- Vector indexing.
- Repository-aware retrieval.
- Documentation retrieval.
- Hybrid keyword and semantic search.
- Conversation-aware context retrieval.
- Improved retrieval ranking.

These capabilities should improve how the assistant finds relevant information in larger repositories.

---

# 18. Phase 4 Primary Goal

> Build a controlled local agent system that allows the Offline Coding Assistant to understand development requests, plan tasks, interact with project files, execute approved commands, and verify the results.

The objective is to move from a repository-aware chatbot to a practical coding assistant capable of carrying out real development tasks.

The user must remain in control of potentially destructive operations, and all execution must happen locally without requiring cloud services.