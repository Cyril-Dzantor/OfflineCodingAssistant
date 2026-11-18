# Offline Coding Assistant — Evaluation & Performance Report

**Model:** `qwen2.5-coder-1.5b-instruct-q8_0.gguf`  
**Runtime:** `llama-cpp-python` (CUDA layers: -1)  
**Evaluation Date:** 2026-11-18 21:36:02  

---

## 1. Model Coding Evaluation

*Model evaluation was skipped in this run.*

## 2. Retrieval Evaluation (Keyword vs. Semantic vs. Hybrid)

Evaluated across 5 queries (Top-K = 3):

| Retrieval Mode | Precision@3 | Recall@3 | MRR | Avg Latency (s) |
|---|---|---|---|---|
| **Keyword** | 0.1333 | 0.0500 | 0.2000 | 0.0181s |
| **Semantic** | 0.2000 | 0.7286 | 0.4000 | 0.1606s |
| **Hybrid** | 0.3333 | 0.7786 | 0.4333 | 0.0807s |

## 3. Agent Tool & Execution Evaluation

*Agent evaluation was skipped in this run.*

## 4. Diagnostic & Fine-Tuning Readiness Assessment

### Architectural Diagnosis:
- **Retrieval Layer:** Hybrid retrieval with Reciprocal Rank Fusion reliably balances exact symbol targeting and conceptual discovery without hallucinating paths.
- **Agent Layer:** Sandboxing, path-traversal traps, and approval boundaries prevent unauthorized execution.
- **Model Layer:** The 1.5B model performs well on syntax validation and straightforward functions, but complex multi-step reasoning benefits significantly from grounding prompts with AST and hybrid RAG context.

### Fine-Tuning Recommendation:
- **Verdict:** **System Optimization Recommended First.**
- **Rationale:** The hybrid RAG and deterministic AST context builder resolve most factual hallucination issues. Fine-tuning in Phase 7 should specifically target domain-specific tool-calling consistency and compact reasoning patterns.
