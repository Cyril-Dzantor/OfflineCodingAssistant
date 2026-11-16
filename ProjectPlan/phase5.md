# Phase 5 — Advanced Context Management & RAG

## 1. Phase Overview

### Objective

Build an advanced retrieval and context-management system that allows the Offline Coding Assistant to retrieve relevant information from large codebases, documentation, and previous interactions.

Phase 3 established deterministic repository search using tools such as ripgrep and tree-sitter.

Phase 4 introduced the agent and its ability to interact with project files and execute approved development operations.

Phase 5 builds on these capabilities by introducing semantic search, embeddings, vector indexing, and Retrieval-Augmented Generation (RAG).

The objective is to ensure that Qwen receives the most relevant information before generating an answer or performing a development task.

### Problems This Phase Should Solve

- Keyword searches may miss relevant code.
- Large repositories contain more information than can fit into the model's context.
- Related functionality may be spread across multiple files.
- Documentation may explain implementation details that are not obvious from source code.
- Previous conversations may contain useful decisions and project-specific information.
- Retrieving too much irrelevant information can reduce answer quality.

### Expected Capabilities

At the end of Phase 5, the assistant should be able to:

- Search code using natural-language descriptions.
- Retrieve semantically related code.
- Search project documentation.
- Combine keyword and semantic search.
- Rank retrieved results by relevance.
- Retrieve related functions, classes, and files.
- Manage conversation and project context.
- Avoid unnecessary context duplication.
- Provide source references for retrieved information.
- Work entirely offline.

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
                         │  Agent Manager   │
                         └────────┬─────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │   Context Manager   │
                       └──────────┬──────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │ Retrieval Engine    │
                       └──────────┬──────────┘
                                  │
                    ┌─────────────┼──────────────┐
                    │             │              │
                    ▼             ▼              ▼
             ┌────────────┐ ┌────────────┐ ┌────────────┐
             │ Keyword    │ │ Semantic   │ │ Metadata   │
             │ Search     │ │ Search     │ │ Search     │
             └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
                   │              │              │
                   └──────────────┼──────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Result Ranking   │
                         │ & Filtering      │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Context Builder  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Context Budget   │
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
| Embedding Model | Converts code and documentation into numerical representations |
| Indexing Engine | Processes and indexes project content |
| Vector Database | Stores and retrieves vector representations |
| Keyword Search | Performs traditional text-based retrieval |
| Semantic Search | Retrieves conceptually related content |
| Metadata Search | Filters results using file and symbol information |
| Retrieval Engine | Combines different retrieval methods |
| Reranker | Improves the relevance ordering of retrieved results |
| Context Manager | Controls which information reaches the model |
| Context Builder | Assembles the final prompt for Qwen |

---

# 3. Phase Breakdown

| Sub-Phase | Focus | Expected Result |
|---|---|---|
| 5.1 | Embedding Model Selection | Local embedding model |
| 5.2 | Code Chunking | Meaningful code segments |
| 5.3 | Vector Database | Persistent vector storage |
| 5.4 | Repository Indexing | Indexed code and documentation |
| 5.5 | Semantic Search | Natural-language code retrieval |
| 5.6 | Hybrid Retrieval | Combined keyword and semantic search |
| 5.7 | Ranking and Filtering | More relevant search results |
| 5.8 | Advanced Context Management | Better context selection |
| 5.9 | Conversation and Project Memory | Persistent contextual information |
| 5.10 | RAG Integration | Complete retrieval-augmented generation |
| 5.11 | Testing and Evaluation | Retrieval and answer-quality evaluation |

---

# 4. Sub-Phase 5.1 — Embedding Model Selection

## Objective

Select and integrate a lightweight embedding model that can run locally.

An embedding model converts text into numerical vectors that represent semantic information.

For example:

```text
"Authenticate a user using a password"
```

and:

```text
"Verify login credentials"
```

may produce vectors that are close to each other because they describe related concepts.

This allows the assistant to retrieve information based on meaning rather than exact word matches.

## Candidate Models

Evaluate lightweight embedding models such as:

- all-MiniLM-L6-v2
- BGE-small-en-v1.5
- Nomic Embed Text
- Other suitable compact embedding models.

The final choice should be based on:

- Model size.
- RAM usage.
- Inference speed.
- Embedding quality.
- Offline compatibility.
- Compatibility with code and technical documentation.
- Storage requirements.

Do not assume that the largest embedding model is automatically the best choice.

## Tasks

- Evaluate available embedding models.
- Download the selected model.
- Store it locally.
- Implement embedding generation.
- Test document embeddings.
- Test query embeddings.
- Measure memory usage and inference speed.
- Confirm that embedding generation works without internet access.

## Deliverable

A locally running embedding model with a reusable embedding interface.

## Milestone

The assistant can convert queries and project content into embeddings without relying on cloud APIs.

---

# 5. Sub-Phase 5.2 — Code Chunking

## Objective

Break source code and documentation into meaningful segments before generating embeddings.

Embedding entire source files can be inefficient, especially when files are large.

The system should divide content into smaller, meaningful units.

### Example

Consider:

```python
class UserService:

    def create_user(self, user_data):
        ...

    def authenticate_user(self, username, password):
        ...

    def update_user(self, user_id, user_data):
        ...
```

Instead of embedding the entire file as one document, the system should create separate chunks for relevant methods and their surrounding context.

### Chunk Types

- Functions.
- Methods.
- Classes.
- Imports and declarations where useful.
- Documentation sections.
- Configuration sections.
- Code blocks.
- General text segments.

### Chunking Strategy

Prefer syntax-aware chunking using the tree-sitter infrastructure developed in Phase 3.

For example:

```text
Chunk 1:
File: users.py
Symbol: UserService.create_user
Lines: 10-20

Chunk 2:
File: users.py
Symbol: UserService.authenticate_user
Lines: 22-35

Chunk 3:
File: users.py
Symbol: UserService.update_user
Lines: 37-48
```

For documentation, use heading-aware and size-limited text chunking.

### Metadata

Each chunk should contain:

```text
Chunk ID
Project ID
File path
Programming language
Symbol name
Symbol type
Start line
End line
Content
Content hash
Last indexed timestamp
```

Additional metadata may include imports, parent classes, and related symbols.

### Important Considerations

- Avoid splitting functions unnecessarily.
- Preserve enough surrounding context to understand individual code segments.
- Avoid excessively large chunks.
- Support configurable chunk sizes.
- Prevent duplicate chunks.
- Preserve source locations for later citations.
- Use overlapping chunks only where they improve retrieval.

## Deliverable

A code-aware chunking system that produces meaningful, searchable units.

## Milestone

The assistant can divide repositories into useful code and documentation segments without losing their structural information.

---

# 6. Sub-Phase 5.3 — Vector Database

## Objective

Introduce local vector storage for embeddings and associated metadata.

The vector database will allow the assistant to retrieve semantically similar code and documentation efficiently.

## Candidate Technologies

Evaluate:

- ChromaDB.
- FAISS.
- Qdrant.

### Considerations

| Technology | Consideration |
|---|---|
| ChromaDB | Convenient local persistent vector storage |
| FAISS | Efficient similarity search and local indexing |
| Qdrant | More advanced filtering and retrieval capabilities |

For the initial implementation, prefer a lightweight solution that is easy to run locally.

ChromaDB or FAISS would be reasonable starting points.

Do not introduce multiple vector databases simultaneously.

### Tasks

- Select the vector storage technology.
- Implement local persistence.
- Create project-specific collections or indexes.
- Store embeddings.
- Store chunk metadata.
- Implement similarity search.
- Implement metadata filtering.
- Support index updates.
- Support index deletion and rebuilding.

### Storage Considerations

The vector database should remain local.

The system should not require:

- Cloud vector databases.
- External API keys.
- Remote embedding services.
- Internet connectivity during normal operation.

### Deliverable

A persistent local vector index.

### Milestone

The assistant can store and retrieve code embeddings across application sessions.

---

# 7. Sub-Phase 5.4 — Repository Indexing

## Objective

Build an indexing pipeline that processes the project and makes its contents searchable through semantic retrieval.

### Indexing Pipeline

```text
Repository
     ↓
Repository Scanner
     ↓
File Filtering
     ↓
Content Extraction
     ↓
Code Chunking
     ↓
Embedding Generation
     ↓
Vector Database
     ↓
Indexed Repository
```

### Content to Index

Initially support:

**Source code**

- Python.
- JavaScript.
- TypeScript.
- Java.
- Other languages supported by the existing parser.

**Documentation**

- Markdown.
- Plain text.
- README files.
- Technical documentation.

**Configuration**

- JSON.
- YAML.
- TOML.
- Environment variable names and configuration structure where safe.

Do not index secrets or sensitive environment values.

### Incremental Indexing

The system should not regenerate every embedding whenever the assistant starts.

Implement incremental indexing using file metadata and content hashes.

Example:

```text
File: backend/auth.py

Previous Hash:
abc123

Current Hash:
abc123

Status:
Unchanged

Action:
Skip embedding generation
```

If the hash changes:

```text
File: backend/auth.py

Previous Hash:
abc123

Current Hash:
xyz789

Status:
Modified

Action:
Reprocess affected chunks
```

### Tasks

- Build the indexing pipeline.
- Index source files.
- Index documentation.
- Generate embeddings.
- Store metadata.
- Track file hashes.
- Detect added files.
- Detect modified files.
- Detect deleted files.
- Update affected vector entries.
- Support complete index rebuilding.
- Display indexing progress.

### Deliverable

A repository indexing system with incremental updates.

### Milestone

The assistant can build and maintain a searchable semantic index of a local project.

---

# 8. Sub-Phase 5.5 — Semantic Search

## Objective

Allow the assistant to retrieve relevant code using natural-language descriptions.

Unlike keyword search, semantic search should identify related content even when the exact terms differ.

### Example 1

User:

```text
Where does the application verify user credentials?
```

Possible retrieved symbols:

```text
authenticate_user()
verify_password()
check_login_credentials()
```

### Example 2

User:

```text
Find the code responsible for restricting access to protected endpoints.
```

Possible retrieved symbols:

```text
AuthenticationMiddleware
require_permissions()
validate_access_token()
```

### Example 3

User:

```text
How does the application connect to its database?
```

Possible retrieved files:

```text
database/connection.py
database/config.py
core/settings.py
```

### Tasks

- Convert user queries into embeddings.
- Search the local vector index.
- Retrieve the nearest matching chunks.
- Apply metadata filters.
- Return source locations.
- Support language-specific searches.
- Support directory-specific searches.
- Support project-specific searches.
- Handle queries with no relevant results.

### Deliverable

A semantic code-search engine.

### Milestone

The assistant can find conceptually related code without relying entirely on matching keywords.

---

# 9. Sub-Phase 5.6 — Hybrid Retrieval

## Objective

Combine deterministic keyword search with semantic search.

Neither method should replace the other.

Keyword search is particularly useful when the user knows an exact function, class, variable, or error message.

Semantic search is useful when the user describes functionality without knowing the implementation names.

### Hybrid Retrieval Architecture

```text
                  User Query
                       │
                       ▼
                Query Analysis
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
       Keyword Search      Semantic Search
             │                   │
             ▼                   ▼
       Text Results        Vector Results
             │                   │
             └─────────┬─────────┘
                       │
                       ▼
                 Result Fusion
                       │
                       ▼
                Ranked Results
```

### Example

User:

```text
Find where JWT tokens are generated and validated.
```

Keyword search may find:

```text
generate_jwt()
jwt.encode()
jwt.decode()
```

Semantic search may find:

```text
create_access_token()
verify_authentication_token()
validate_session()
```

The retrieval engine should combine the results.

### Tasks

- Integrate keyword search from Phase 3.
- Integrate semantic search.
- Normalize retrieval scores where appropriate.
- Combine results.
- Remove duplicates.
- Preserve source metadata.
- Support configurable retrieval weights.
- Allow keyword-only and semantic-only retrieval modes.

### Result Fusion

Evaluate a method such as Reciprocal Rank Fusion (RRF) for combining rankings from different retrieval systems.

Do not blindly add incompatible raw search scores.

### Deliverable

A hybrid retrieval engine.

### Milestone

The assistant can retrieve relevant code using both exact matching and semantic similarity.

---

# 10. Sub-Phase 5.7 — Ranking and Filtering

## Objective

Improve retrieval quality by ensuring that the most useful results are prioritized.

Retrieving relevant information is not enough. The system must also decide which results deserve to enter the model's context.

### Ranking Signals

Potential ranking signals include:

- Semantic similarity.
- Keyword relevance.
- Exact symbol matches.
- File path relevance.
- Programming language.
- Directory relevance.
- Symbol type.
- Import relationships.
- Recency of modification.
- User-selected files.

### Reranking

Evaluate whether a lightweight reranker improves retrieval quality.

A reranker takes an initial set of search results and evaluates their relevance against the original query.

Because of the hardware constraints, reranking should be optional and measured before being enabled by default.

### Filtering

Remove:

- Duplicate chunks.
- Irrelevant results.
- Generated code.
- Excluded files.
- Empty chunks.
- Stale index entries.

### Tasks

- Implement result deduplication.
- Implement ranking logic.
- Implement metadata filtering.
- Evaluate reranking models if needed.
- Configure retrieval limits.
- Track retrieval scores.
- Preserve source references.

### Deliverable

A retrieval ranking and filtering component.

### Milestone

The system consistently selects useful code and documentation instead of overwhelming Qwen with loosely related results.

---

# 11. Sub-Phase 5.8 — Advanced Context Management

## Objective

Improve the existing context builder so that it can manage information from multiple sources.

The context manager should consider:

- Current user request.
- Conversation history.
- Repository metadata.
- Retrieved code.
- Retrieved documentation.
- Tool execution results.
- Previous development decisions.

### Context Assembly

```text
User Request
     │
     ▼
Query Analysis
     │
     ▼
Hybrid Retrieval
     │
     ▼
Result Ranking
     │
     ▼
Relevant Code and Documentation
     │
     ▼
Context Manager
     │
     ├── Conversation Context
     ├── Repository Context
     ├── Tool Results
     └── User Instructions
     │
     ▼
Context Budget
     │
     ▼
Prompt Construction
     │
     ▼
Qwen
```

### Context Prioritization

The system should prioritize:

1. Current user request and explicit instructions.
2. Relevant source code.
3. Direct dependencies and related symbols.
4. Relevant project documentation.
5. Recent tool execution results.
6. Necessary conversation history.
7. Older contextual information.

### Context Budgeting

The context manager must account for:

- System prompt.
- User request.
- Conversation history.
- Retrieved chunks.
- Tool results.
- Output token allowance.

The assistant should not simply append every retrieved result to the prompt.

It should select and organize information within a configurable context budget.

### Context Compression

Implement lightweight context reduction techniques where appropriate:

- Remove duplicate information.
- Remove irrelevant history.
- Summarize older conversation turns.
- Preserve important technical decisions.
- Truncate oversized tool outputs carefully.
- Retrieve additional context only when necessary.

### Deliverable

An advanced context manager that combines retrieval, conversation information, and tool results.

### Milestone

The assistant can maintain useful context while operating within the practical limitations of the local model.

---

# 12. Sub-Phase 5.9 — Conversation and Project Memory

## Objective

Introduce persistent memory for information that should remain available across sessions.

This memory is separate from the model's temporary context window.

### Memory Categories

**Project Memory**

Information about the current repository:

- Project architecture.
- Important directories.
- Technology stack.
- Key classes and services.
- Database structure.
- Important configuration decisions.
- Known limitations.

**Development Memory**

Information about ongoing work:

- Features currently being implemented.
- Completed changes.
- Outstanding tasks.
- Known bugs.
- Previous debugging decisions.
- Important implementation choices.

**Conversation Memory**

Useful information from previous interactions:

- User instructions.
- Agreed development approaches.
- Relevant decisions.
- Unresolved questions.

### Memory Storage

Use local persistent storage.

SQLite is a suitable starting point for structured project and development memory.

The vector index can separately support semantic retrieval of longer memory records when useful.

### Important Requirements

- Memory should be project-specific.
- Different repositories must not accidentally share project context.
- Memory must be editable and inspectable.
- Outdated information should be updated or removed.
- Sensitive values such as passwords, tokens, and API keys must not be stored.
- Memory should not override explicit current user instructions.
- The assistant should distinguish verified project facts from generated assumptions.

### Tasks

- Define memory categories.
- Implement local memory storage.
- Associate memory with project identifiers.
- Retrieve relevant memories.
- Update outdated records.
- Prevent duplicate records.
- Implement memory inspection commands.
- Implement memory deletion and rebuilding.

### Suggested Commands

```text
/memory
/memory project
/memory recent
/memory clear
```

### Deliverable

A local project and development memory system.

### Milestone

The assistant can retain useful project knowledge across sessions without depending entirely on conversation history.

---

# 13. Sub-Phase 5.10 — RAG Integration

## Objective

Connect all retrieval components to the agent so that retrieved information becomes available during normal development tasks.

### Complete RAG Workflow

```text
User Request
     │
     ▼
Agent Manager
     │
     ▼
Query Analysis
     │
     ▼
Hybrid Retrieval
     │
     ├── Keyword Search
     ├── Semantic Search
     └── Metadata Search
     │
     ▼
Result Ranking
     │
     ▼
Context Builder
     │
     ├── Retrieved Code
     ├── Documentation
     ├── Project Memory
     └── Conversation Context
     │
     ▼
Context Budget
     │
     ▼
Qwen2.5-Coder-1.5B
     │
     ▼
Response or Tool Request
     │
     ▼
Agent Execution
     │
     ▼
Final Response
```

### Example 1: Understanding Existing Code

User:

```text
Explain how the application handles user authentication.
```

Expected behavior:

1. Analyze the question.
2. Search the repository.
3. Retrieve authentication-related code.
4. Retrieve relevant middleware and configuration.
5. Retrieve relevant documentation.
6. Build focused context.
7. Ask Qwen to explain the implementation.
8. Include file references in the answer.

### Example 2: Implementing a Feature

User:

```text
Add role-based access control to the application.
```

Expected behavior:

1. Retrieve authentication implementation.
2. Retrieve user models.
3. Retrieve existing permission logic.
4. Retrieve relevant API endpoints.
5. Identify existing architectural conventions.
6. Build an implementation plan.
7. Generate proposed modifications.
8. Request approval.
9. Apply approved changes.
10. Run tests.
11. Report results.

### Example 3: Debugging

User:

```text
Why does the application return a 401 error when accessing protected endpoints?
```

Expected behavior:

1. Retrieve authentication middleware.
2. Retrieve token validation logic.
3. Retrieve protected endpoint definitions.
4. Retrieve relevant configuration.
5. Inspect relevant execution logs if available.
6. Build context.
7. Ask Qwen to investigate possible causes.
8. Propose a diagnosis supported by retrieved evidence.

### Deliverable

A fully integrated local RAG pipeline connected to the agent.

### Milestone

The assistant can use semantic and hybrid retrieval during normal coding, debugging, and project-understanding workflows.

---

# 14. Sub-Phase 5.11 — Testing and Evaluation

## Objective

Evaluate retrieval quality, context efficiency, and the impact of RAG on the assistant's responses.

A working vector database does not automatically mean the retrieval system is effective.

The system must be evaluated using questions with known relevant files and code segments.

### Test Categories

**Test 1: Semantic Retrieval**

Question:

```text
Where does the application verify user login credentials?
```

Expected result:

The system retrieves relevant authentication functions even when the exact query terms do not appear in their names.

**Test 2: Documentation Retrieval**

Question:

```text
How do I configure the database connection?
```

Expected result:

The system retrieves the relevant configuration documentation and source files.

**Test 3: Hybrid Search**

Question:

```text
Find where JWT tokens are generated and validated.
```

Expected result:

The system combines exact keyword matches and semantically related functions.

**Test 4: Cross-File Understanding**

Question:

```text
Explain the complete flow of a user registration request.
```

Expected result:

The system retrieves relevant routes, service functions, models, database operations, and tests.

**Test 5: Incremental Indexing**

Modify an existing source file.

Expected result:

Only affected content is reprocessed rather than rebuilding the entire index.

**Test 6: Deleted Files**

Delete a previously indexed file.

Expected result:

The corresponding stale chunks are removed from the index.

**Test 7: Context Efficiency**

Ask a question about a small feature in a large repository.

Expected result:

The system retrieves a focused selection of relevant content rather than supplying the entire repository.

**Test 8: Offline Operation**

Disable internet connectivity and perform indexing and retrieval.

Expected result:

All required functionality continues to work locally.

---

# 15. Performance and Retrieval Evaluation

Track the following metrics:

| Metric | Purpose |
|---|---|
| Embedding generation time | Measure indexing speed |
| Indexing time | Measure repository processing |
| Vector search latency | Measure semantic retrieval |
| Keyword search latency | Measure deterministic retrieval |
| Retrieval precision | Measure relevance of retrieved results |
| Recall@K | Measure whether relevant results appear in the top K |
| MRR | Measure ranking quality |
| Context construction time | Measure prompt preparation |
| Context token count | Monitor context usage |
| RAM usage | Monitor system resources |
| Vector index size | Monitor storage requirements |
| Incremental indexing time | Measure update efficiency |
| Answer correctness | Evaluate final response quality |

Compare at least three configurations:

1. Keyword search only.
2. Semantic search only.
3. Hybrid retrieval.

This will help determine whether the additional complexity of semantic search provides measurable improvements.

---

# 16. Hardware and Resource Optimization

The assistant is being developed for a machine with:

- 16 GB system RAM.
- NVIDIA GTX 1650.
- 4 GB VRAM.
- Qwen2.5-Coder-1.5B-Instruct as the primary coding model.

The retrieval system should therefore be designed to minimize unnecessary resource consumption.

### Recommendations

- Use a compact embedding model.
- Generate embeddings in small batches.
- Avoid loading multiple large models into VRAM simultaneously.
- Consider running embeddings on CPU if GPU memory becomes constrained.
- Keep vector storage local.
- Use incremental indexing.
- Cache frequently requested embeddings.
- Limit retrieved chunks.
- Avoid unnecessarily large context windows.
- Make reranking optional.
- Measure memory usage before introducing additional models.

### Model Separation

The coding model and embedding model have different responsibilities.

```text
Qwen2.5-Coder-1.5B
    └── Code generation
    └── Reasoning
    └── Explanation
    └── Development tasks

Embedding Model
    └── Text embeddings
    └── Code embeddings
    └── Semantic retrieval
```

Do not assume both models must remain loaded on the GPU simultaneously.

---

# 17. Phase 5 Scope Boundaries

The following capabilities are not required in this phase:

- QLoRA fine-tuning.
- Custom model training.
- Multi-agent collaboration.
- Cloud-based retrieval.
- Remote vector databases.
- VS Code extension.
- Unrestricted autonomous execution.
- Distributed indexing.
- Large-scale enterprise code search.

Phase 5 should focus specifically on:

**Semantic retrieval, hybrid search, persistent project knowledge, and efficient context construction.**

---

# 18. Phase 5 Completion Criteria

Phase 5 is complete when:

- [x] A local embedding model is selected.
- [x] Embedding generation works offline.
- [x] Source code can be divided into meaningful chunks.
- [x] Documentation can be chunked.
- [x] Chunk metadata is preserved.
- [x] A local vector database is implemented.
- [x] Embeddings can be stored and retrieved.
- [x] Repository indexing works.
- [x] Incremental indexing works.
- [x] Modified files are reindexed.
- [x] Deleted files are removed from the index.
- [x] Semantic search works.
- [x] Keyword search is integrated.
- [x] Hybrid retrieval works.
- [x] Duplicate results are removed.
- [x] Results can be ranked and filtered.
- [x] Optional reranking has been evaluated.
- [x] Advanced context management works.
- [x] Context budgeting is implemented.
- [x] Project memory is persistent.
- [x] Conversation memory is supported.
- [x] RAG is integrated with the agent.
- [x] Retrieved sources can be referenced in responses.
- [x] Retrieval quality has been evaluated.
- [x] Incremental indexing has been tested.
- [x] Offline operation has been verified.
- [x] Resource usage remains practical on the target hardware.

---

# 19. Phase 4 → Phase 5 Transition

At the end of Phase 4, the assistant should operate as:

```text
User
  ↓
Agent
  ↓
Understand Task
  ↓
Search Repository
  ↓
Read Files
  ↓
Generate Changes
  ↓
Execute Approved Actions
  ↓
Run Tests
  ↓
Inspect Results
  ↓
Final Response
```

After Phase 5, the workflow becomes:

```text
User
  ↓
Agent
  ↓
Analyze Request
  ↓
Hybrid Retrieval
  ↓
Retrieve Relevant Code
  ↓
Retrieve Documentation
  ↓
Retrieve Project Memory
  ↓
Rank and Filter Results
  ↓
Build Context
  ↓
Qwen
  ↓
Answer or Tool Request
  ↓
Execute Approved Actions
  ↓
Validate Results
  ↓
Final Response
```

The assistant now has a more advanced understanding of the project because it can retrieve information based on meaning, relationships, and previously established project knowledge.

---

# 20. Phase 5 → Phase 6 Transition

Phase 5 establishes the retrieval and context-management foundation.

Phase 6 should focus on evaluating the entire assistant and improving its reliability and performance.

Potential areas include:

- Coding benchmarks.
- Repository understanding benchmarks.
- Agent task-completion evaluation.
- Retrieval-quality evaluation.
- Prompt optimization.
- Model inference optimization.
- Quantization comparisons.
- Latency optimization.
- Memory optimization.
- Failure analysis.
- Regression testing.

The goal is to identify where the current system performs well and where it needs improvement before introducing fine-tuning.

---

# 21. Phase 5 Primary Goal

> Build a fully local Retrieval-Augmented Generation system that allows the Offline Coding Assistant to search, retrieve, rank, and use relevant code, documentation, and project knowledge when answering questions or performing development tasks.

The focus of this phase is to improve the quality of information supplied to Qwen rather than immediately increasing the size of the coding model.

The retrieval system should make the existing 1.5B model more useful by ensuring that it receives accurate, relevant, and well-organized project context.