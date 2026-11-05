                         ┌─────────────────────────┐
                         │          IDE            │
                         │   VS Code / Terminal    │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   Local Assistant CLI   │
                         │      / VS Code API      │
                         └────────────┬────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │       Agent / Orchestrator       │
                    │                                 │
                    │  • Prompt construction          │
                    │  • Context management           │
                    │  • Tool selection               │
                    │  • Task planning                │
                    │  • Response validation          │
                    └───────────────┬─────────────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
       ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
       │      LLM       │  │ Code Retrieval │  │     Tools      │
       │                │  │                │  │                │
       │ Qwen2.5-Coder  │  │ • ripgrep      │  │ • read_file    │
       │     1.5B       │  │ • tree-sitter  │  │ • write_file   │
       │                │  │ • embeddings   │  │ • terminal     │
       │ 4-bit / QLoRA  │  │ • vector DB    │  │ • git          │
       └───────┬────────┘  └───────┬────────┘  │ • tests        │
               │                   │           └───────┬────────┘
               │                   │                   │
               └───────────────────┼───────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────────┐
                        │      Project Context    │
                        │                         │
                        │ • Source code           │
                        │ • Documentation         │
                        │ • Configuration         │
                        │ • Tests                  │
                        │ • Git history           │
                        └─────────────────────────┘