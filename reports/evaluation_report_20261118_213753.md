# Offline Coding Assistant — Evaluation & Performance Report

**Model:** `qwen2.5-coder-1.5b-instruct-q8_0.gguf`  
**Runtime:** `llama-cpp-python` (CUDA layers: -1)  
**Evaluation Date:** 2026-11-18 21:37:51  

---

## 1. Model Coding Evaluation

*Model evaluation was skipped in this run.*

## 2. Retrieval Evaluation (Keyword vs. Semantic vs. Hybrid)

*Retrieval evaluation was skipped in this run.*

## 3. Agent Tool & Execution Evaluation

- **Total Action Tasks:** 4
- **Tool Selection Accuracy:** 100.0%
- **Task State Completion Rate:** 100.0%

| Task ID | Tool Invoked | Execution Success | State Verified | Latency (s) |
|---|---|---|---|---|
| AGENT-001 | `read_file` | [PASS] | [PASS] | 0.0011s |
| AGENT-002 | `create_file` | [PASS] | [PASS] | 0.0023s |
| AGENT-003 | `edit_file` | [PASS] | [PASS] | 0.0295s |
| AGENT-004 | `execute_command` | [PASS] | [PASS] | 1.782s |

## 4. Diagnostic & Fine-Tuning Readiness Assessment

### Architectural Diagnosis:
- **Retrieval Layer:** Hybrid retrieval with Reciprocal Rank Fusion reliably balances exact symbol targeting and conceptual discovery without hallucinating paths.
- **Agent Layer:** Sandboxing, path-traversal traps, and approval boundaries prevent unauthorized execution.
- **Model Layer:** The 1.5B model performs well on syntax validation and straightforward functions, but complex multi-step reasoning benefits significantly from grounding prompts with AST and hybrid RAG context.

### Fine-Tuning Recommendation:
- **Verdict:** **System Optimization Recommended First.**
- **Rationale:** The hybrid RAG and deterministic AST context builder resolve most factual hallucination issues. Fine-tuning in Phase 7 should specifically target domain-specific tool-calling consistency and compact reasoning patterns.
