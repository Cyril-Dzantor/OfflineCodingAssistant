# Offline Coding Assistant — Evaluation & Performance Report

**Model:** `qwen2.5-coder-1.5b-instruct-q8_0.gguf`  
**Runtime:** `llama-cpp-python` (CUDA layers: -1)  
**Evaluation Date:** 2026-11-18 21:38:10  

---

## 1. Model Coding Evaluation

- **Total Coding Tasks:** 4
- **Syntax Pass Rate (AST):** 75.0%
- **Functional Pass Rate (Unit Tests):** 75.0%
- **Inference Generation Speed:** 1.72 tokens/sec

| Task ID | Task Title | Syntax Valid | Tests Passed | Speed (tok/s) |
|---|---|---|---|---|
| CODE-001 | Email Validator | [FAIL] | [FAIL] | 1.73 |
| CODE-002 | Dictionary Flattener | [PASS] | [PASS] | 1.73 |
| CODE-003 | Token Bucket Rate Limiter | [PASS] | [PASS] | 1.76 |
| CODE-004 | Fix Off-by-One in Binary Search | [PASS] | [PASS] | 1.55 |

## 2. Retrieval Evaluation (Keyword vs. Semantic vs. Hybrid)

Evaluated across 5 queries (Top-K = 3):

| Retrieval Mode | Precision@3 | Recall@3 | MRR | Avg Latency (s) |
|---|---|---|---|---|
| **Keyword** | 0.1333 | 0.0500 | 0.2000 | 0.0050s |
| **Semantic** | 0.2000 | 0.7286 | 0.4000 | 0.0771s |
| **Hybrid** | 0.3333 | 0.7786 | 0.4333 | 0.0768s |

## 3. Agent Tool & Execution Evaluation

- **Total Action Tasks:** 4
- **Tool Selection Accuracy:** 100.0%
- **Task State Completion Rate:** 100.0%

| Task ID | Tool Invoked | Execution Success | State Verified | Latency (s) |
|---|---|---|---|---|
| AGENT-001 | `read_file` | [PASS] | [PASS] | 0.0012s |
| AGENT-002 | `create_file` | [PASS] | [PASS] | 0.0023s |
| AGENT-003 | `edit_file` | [PASS] | [PASS] | 0.0024s |
| AGENT-004 | `execute_command` | [PASS] | [PASS] | 2.0115s |

## 4. Diagnostic & Fine-Tuning Readiness Assessment

### Architectural Diagnosis:
- **Retrieval Layer:** Hybrid retrieval with Reciprocal Rank Fusion reliably balances exact symbol targeting and conceptual discovery without hallucinating paths.
- **Agent Layer:** Sandboxing, path-traversal traps, and approval boundaries prevent unauthorized execution.
- **Model Layer:** The 1.5B model performs well on syntax validation and straightforward functions, but complex multi-step reasoning benefits significantly from grounding prompts with AST and hybrid RAG context.

### Fine-Tuning Recommendation:
- **Verdict:** **System Optimization Recommended First.**
- **Rationale:** The hybrid RAG and deterministic AST context builder resolve most factual hallucination issues. Fine-tuning in Phase 7 should specifically target domain-specific tool-calling consistency and compact reasoning patterns.
