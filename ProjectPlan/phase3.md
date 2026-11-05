# Phase 3 — Project & Code Understanding

## 1. Phase Overview

### Objective

Build the repository-awareness layer that allows the Offline Coding Assistant to inspect, navigate, search, and understand a local software project.

At the end of Phase 3, the assistant should be able to answer questions such as:

- Where is authentication implemented?
- Which files use the `UserService` class?
- Explain how the API handles authentication.
- Where is the database connection configured?
- Which files are related to payment processing?

The assistant should obtain this information from the user's local repository instead of relying solely on information manually supplied in the prompt.

---

## 2. Phase Architecture

```text
                         ┌──────────────────┐
                         │       User       │
                         │   CLI Interface  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │    Assistant     │
                         │     Manager      │
                         └────────┬─────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │   Context Manager   │
                       └──────────┬──────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
             ┌────────────┐ ┌────────────┐ ┌────────────┐
             │ Repository │ │ Code Search│ │   Parser   │
             │  Scanner   │ │   Engine   │ │ tree-sitter│
             └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
                   │              │              │
                   └──────────────┼──────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Relevant Project │
                         │     Context      │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Qwen2.5-Coder    │
                         │      1.5B        │
                         └──────────────────┘
3. Phase Breakdown
Sub-Phase	Focus	Expected Result
✅ 3.1	Repository Detection	Assistant identifies the active project
✅ 3.2	Repository Scanner	Assistant understands project structure
✅ 3.3	File Filtering	Irrelevant files are excluded
✅ 3.4	Code Search	Assistant can locate relevant code
✅ 3.5	Code Parsing	Assistant understands code structure
✅ 3.6	Context Builder	Relevant code is prepared for Qwen
✅ 3.7	Repository Commands	User can interact with repository context
✅ 3.8	Testing & Validation	Repository understanding is evaluated



4. Sub-Phase 3.1 — Repository Detection
Objective

Allow the assistant to identify the project or repository it is working with.
The assistant should determine whether the directory contains a software project.

Tasks
Detect the current working directory.
Detect Git repositories.
Identify the project root.
Resolve relative paths.
Handle projects without Git.
Detect common project files.

Deliverable

Repository detection and project metadata functionality.

Milestone

The assistant can identify the project it is operating within.

5. Sub-Phase 3.2 — Repository Scanner
Objective

Create a scanner that builds a lightweight representation of the project.

The scanner should collect metadata rather than loading every file into the model.

Metadata

Potential metadata includes:

File path
File extension
File size
Language
Directory
Git status

Later:

Classes
Functions
Methods
Imports
Exports
Tasks
Recursively scan the project directory.
Record relevant files.
Record file metadata.
Identify programming languages.
Identify documentation files.
Identify configuration files.
Generate a project tree.
Store the scan results in a local index.
Deliverable

A repository index containing lightweight project metadata.

Milestone

The assistant has a structured representation of the repository without loading the entire repository into Qwen.

6. Sub-Phase 3.3 — File Filtering
Objective

Prevent irrelevant files from being scanned, indexed, or supplied to the model.

This is particularly important because the assistant is designed to run on hardware with limited resources.

Examples of directories that should normally be excluded:

.git/
node_modules/
venv/
.venv/
__pycache__/
dist/
build/
coverage/
File Filtering Rules

Exclude:

Binary files.
Images.
Videos.
Archives.
Generated files.
Build artifacts.
Very large files.
Dependency directories.
Temporary files.

Respect:

.gitignore
Example

Instead of:

Repository
    ↓
Every file
    ↓
Qwen

The system should use:

Repository
    ↓
File Filter
    ↓
Relevant files
    ↓
Context Builder
    ↓
Qwen
Tasks
Implement default exclusion rules.
Read and respect .gitignore.
Detect binary files.
Detect generated files.
Detect unusually large files.
Allow configurable exclusion rules.
Prevent excluded files from entering the context.
Deliverable

A file filtering system that keeps repository processing lightweight.

Milestone

Only useful project files are available to the repository understanding system.

7. Sub-Phase 3.4 — Code Search Engine
Objective

Allow the assistant to locate relevant code before sending context to Qwen.

The initial implementation should use fast deterministic search rather than semantic search.

A lightweight tool such as ripgrep can be used for this purpose.

Example

User:

Where is authentication handled?

The search engine can look for terms such as:

authentication
authenticate
login
JWT
token
middleware

Potential results:

backend/auth/authentication.py
backend/auth/middleware.py
backend/api/login.py
tests/test_authentication.py
Search Capabilities

Implement:

Keyword search.
Exact string search.
Case-insensitive search.
Filename search.
File-type filtering.
Directory filtering.
Regular expression search.
Conceptual Interface
search_code(
    query="authentication",
    language="python"
)
Deliverable

A fast local code-search engine.

Milestone

The assistant can locate relevant files and code using deterministic local search.

8. Sub-Phase 3.5 — Code Parsing
Objective

Go beyond keyword search by understanding the structural elements of source code.

A parser such as tree-sitter can be used to analyze supported programming languages.

Example:

class UserService:

    def authenticate(self, username, password):
        ...

The parser should identify:

Class:
    UserService

Method:
    authenticate

Parameters:
    username
    password
Initial Information to Extract
Classes.
Functions.
Methods.
Imports.
Exports.
Function parameters.
Relevant declarations.
File-level relationships where practical.
Example
backend/auth/authentication.py

Classes:
    AuthenticationService

Functions:
    authenticate_user()
    generate_token()

Imports:
    jwt
    bcrypt
    User
Tasks
Identify supported programming languages.
Integrate a syntax parser.
Parse source files.
Extract classes.
Extract functions and methods.
Extract imports.
Store extracted symbols.
Associate symbols with source files and line ranges.
Deliverable

A structural representation of source code.

Milestone

The assistant can identify important code structures rather than treating source files as plain text.

9. Sub-Phase 3.6 — Context Builder
Objective

Construct focused context for Qwen based on the user's request.

The model should not receive raw search results or the entire repository.

The context flow should be:

User Request
      │
      ▼
Code Search
      │
      ▼
Relevant Files
      │
      ▼
Relevant Symbols
      │
      ▼
Context Builder
      │
      ▼
Context Budget
      │
      ▼
Qwen
Example

User:

Explain how authentication works in this project.

The context builder may identify:

Project:
MyApplication

Relevant files:

backend/auth/authentication.py
backend/auth/middleware.py
backend/api/login.py
tests/test_authentication.py

Relevant symbols:

AuthenticationService.authenticate_user()
AuthenticationMiddleware.process_request()
login()

The system should then select the most relevant portions of these files.

Context Prioritization

When context is limited, prioritize:

Current user request.
Relevant functions.
Relevant classes.
Relevant files.
Relevant documentation.
Older conversation history.
Context Budget

The context builder should track:

System Prompt
+
Conversation History
+
Retrieved Code
+
User Request

The system should avoid exceeding the model's practical context and memory limits.

Tasks
Build a context assembly mechanism.
Rank retrieved files and symbols.
Select relevant code sections.
Include useful file metadata.
Track context size.
Remove low-priority context when necessary.
Produce a final prompt for Qwen.
Deliverable

A context builder that supplies focused repository information to the model.

Milestone

Qwen receives relevant project context rather than the entire repository.

10. Sub-Phase 3.7 — Repository Commands

Add commands to the CLI for interacting with repository information.

/project

Display information about the current project.

/project

Example:

Project: MyApplication
Root: D:\Projects\MyApplication
Git: Detected
Languages: Python, TypeScript
/tree

Display the project structure.

/tree
/files

List relevant project files.

/files
/search

Search the repository.

/search authentication
/symbols

Display discovered symbols.

/symbols authentication.py
/context

Show the context that would be supplied to the model.

/context

This command will be particularly useful for debugging and evaluating retrieval quality.

11. Natural Language Repository Questions

The final goal is for users to interact naturally without needing to know repository commands.

Example:

You > Where is the database connection configured?

The assistant should internally perform:

User Request
     ↓
Identify Information Need
     ↓
Search Repository
     ↓
Find Relevant Files
     ↓
Find Relevant Symbols
     ↓
Build Context
     ↓
Send Context to Qwen
     ↓
Generate Answer

Another example:

You > Which class handles authentication?

The assistant should:

Search
  ↓
authentication-related files
  ↓
parse symbols
  ↓
identify authentication classes
  ↓
provide relevant code/context to Qwen
  ↓
answer user

This is the beginning of the agent architecture that will be developed in Phase 4.

12. Sub-Phase 3.8 — Testing & Validation
Objective

Create a controlled test repository to evaluate repository understanding.

Example:

sample-project/
│
├── backend/
│   ├── auth/
│   ├── users/
│   └── database/
│
├── frontend/
├── tests/
└── README.md
Test Categories
File Discovery

Question:

Where is authentication implemented?

Expected behavior:

The system identifies the relevant authentication files.

Symbol Discovery

Question:

Which class handles user authentication?

Expected behavior:

The system identifies the relevant class and file.

Dependency Discovery

Question:

What files import AuthenticationService?

Expected behavior:

The system identifies files containing the relevant import.

Architecture Understanding

Question:

Explain how a login request flows through the application.

Expected behavior:

The system retrieves the relevant authentication, routing, middleware, and test code before asking Qwen to explain the flow.

Configuration Discovery

Question:

Where is the database connection configured?

Expected behavior:

The system locates the appropriate configuration or database initialization code.

Testing Discovery

Question:

Which tests cover authentication?

Expected behavior:

The system identifies relevant test files and test functions.