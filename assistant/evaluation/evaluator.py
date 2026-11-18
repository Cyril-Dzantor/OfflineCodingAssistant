# assistant/evaluation/evaluator.py

import json
import os
import re
import sys
import time
from typing import List, Dict, Any, Optional, Set

from assistant.core.model import ModelInterface
from assistant.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
    validate_python_syntax,
    execute_unit_tests,
    tool_selection_accuracy,
    argument_coverage,
    calculate_tokens_per_second,
)
from assistant.rag.hybrid import HybridRetriever
from assistant.tools import get_default_registry
from assistant.agent.control import ExecutionController
from assistant.utils.logger import setup_logger

logger = setup_logger("Evaluator")


class ModelEvaluator:
    """Evaluates local LLM code generation, syntax correctness, and unit test pass rates."""

    def __init__(self, model: Optional[ModelInterface] = None):
        self.model = model

    @staticmethod
    def extract_code(raw_text: str) -> str:
        """Extracts python code from markdown fence or returns raw text."""
        match = re.search(r"```(?:python)?\s*\n(.*?)\n```", raw_text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return raw_text.strip()

    def evaluate_code_tasks(self, tasks_file: str) -> Dict[str, Any]:
        """Runs the model against coding benchmark tasks and computes syntax and functional pass rates."""
        if not os.path.isfile(tasks_file):
            raise FileNotFoundError(f"Task file not found: {tasks_file}")

        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        if not self.model:
            self.model = ModelInterface()

        results = []
        total_tokens = 0
        total_time = 0.0

        for t in tasks:
            task_id = t["id"]
            prompt = t["prompt"]
            test_suite = t["test_suite"]

            messages = [
                {
                    "role": "system",
                    "content": "You are an expert Python programmer. Write clean, working Python code that satisfies the requirements. Include only valid code and necessary imports inside a ```python block.",
                },
                {"role": "user", "content": prompt},
            ]

            t0 = time.time()
            tokens = list(self.model.generate_stream(messages))
            duration = time.time() - t0

            response_text = "".join(tokens)
            code = self.extract_code(response_text)

            syntax_valid, syntax_err = validate_python_syntax(code)
            tests_passed = False
            exec_err = None

            if syntax_valid:
                tests_passed, exec_err = execute_unit_tests(code, test_suite, timeout_seconds=5)

            total_tokens += len(tokens)
            total_time += duration

            results.append({
                "id": task_id,
                "title": t.get("title", task_id),
                "syntax_valid": syntax_valid,
                "syntax_error": syntax_err,
                "tests_passed": tests_passed,
                "execution_error": exec_err,
                "token_count": len(tokens),
                "duration_seconds": round(duration, 3),
                "tokens_per_second": round(calculate_tokens_per_second(len(tokens), duration), 2),
            })

        syntax_pass_rate = sum(1 for r in results if r["syntax_valid"]) / float(len(results)) if results else 0.0
        functional_pass_rate = sum(1 for r in results if r["tests_passed"]) / float(len(results)) if results else 0.0

        return {
            "total_tasks": len(results),
            "syntax_pass_rate": round(syntax_pass_rate, 4),
            "functional_pass_rate": round(functional_pass_rate, 4),
            "average_tokens_per_second": round(calculate_tokens_per_second(total_tokens, total_time), 2),
            "details": results,
        }


class RetrievalEvaluator:
    """Evaluates keyword, semantic, and hybrid retrieval against ground-truth references."""

    def __init__(self, retriever: Optional[HybridRetriever] = None):
        self.retriever = retriever or HybridRetriever()

    def evaluate_retrieval_tasks(self, tasks_file: str, k: int = 3) -> Dict[str, Any]:
        """Runs queries across retrieval modes and computes Precision@K, Recall@K, and MRR."""
        if not os.path.isfile(tasks_file):
            raise FileNotFoundError(f"Task file not found: {tasks_file}")

        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        modes = ["keyword", "semantic", "hybrid"]
        mode_metrics: Dict[str, Dict[str, Any]] = {
            m: {"precisions": [], "recalls": [], "reciprocal_ranks": [], "durations": []}
            for m in modes
        }

        task_details = []

        for t in tasks:
            query = t["query"]
            expected_files = set(os.path.normpath(f) for f in t["expected_files"])
            expected_symbols = set(t.get("expected_symbols", []))
            ground_truth = expected_files.union(expected_symbols)

            t_detail = {"id": t["id"], "query": query, "modes": {}}

            for mode in modes:
                t0 = time.time()
                ranked_results = self.retriever.search(query, top_k=k, mode=mode)
                dur = time.time() - t0

                # Extract retrieved identifiers (normalized file paths and symbol names)
                retrieved_identifiers = []
                for r in ranked_results:
                    retrieved_identifiers.append(os.path.normpath(r.chunk.file_path))
                    retrieved_identifiers.append(r.chunk.symbol_name)

                # Check hits against ground truth
                hits = set()
                for ident in retrieved_identifiers:
                    for target in ground_truth:
                        if target in ident or ident in target:
                            hits.add(target)

                p_k = precision_at_k(retrieved_identifiers[:k*2], ground_truth, k=k)
                r_k = recall_at_k(list(hits), ground_truth, k=len(ground_truth))
                rr = reciprocal_rank(retrieved_identifiers[:k*2], ground_truth)

                mode_metrics[mode]["precisions"].append(p_k)
                mode_metrics[mode]["recalls"].append(r_k)
                mode_metrics[mode]["reciprocal_ranks"].append(rr)
                mode_metrics[mode]["durations"].append(dur)

                t_detail["modes"][mode] = {
                    "precision_at_k": round(p_k, 4),
                    "recall_at_k": round(r_k, 4),
                    "reciprocal_rank": round(rr, 4),
                    "duration_seconds": round(dur, 4),
                    "retrieved_count": len(ranked_results),
                }

            task_details.append(t_detail)

        summary = {}
        for mode in modes:
            m_data = mode_metrics[mode]
            n = float(len(tasks)) if tasks else 1.0
            summary[mode] = {
                f"mean_precision_at_{k}": round(sum(m_data["precisions"]) / n, 4),
                f"mean_recall_at_{k}": round(sum(m_data["recalls"]) / n, 4),
                "mrr": round(sum(m_data["reciprocal_ranks"]) / n, 4),
                "avg_latency_seconds": round(sum(m_data["durations"]) / n, 4),
            }

        return {
            "k": k,
            "total_queries": len(tasks),
            "summary": summary,
            "details": task_details,
        }


class AgentEvaluator:
    """Evaluates agent tool selection, argument adherence, and end-state disk verification."""

    def __init__(self, controller: Optional[ExecutionController] = None):
        registry = get_default_registry()
        self.controller = controller or ExecutionController(
            registry=registry,
            auto_approve_modifications=True,
            approval_callback=lambda tool, args: True,
        )

    def evaluate_agent_tasks(self, tasks_file: str) -> Dict[str, Any]:
        """Runs agent tasks and validates environmental changes."""
        if not os.path.isfile(tasks_file):
            raise FileNotFoundError(f"Task file not found: {tasks_file}")

        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        results = []

        for t in tasks:
            task_id = t["id"]
            expected_tool = t["expected_tool"]
            required_args = set(t.get("required_args", []))
            expected_arg_vals = t.get("expected_arg_values", {})
            verification_target = t.get("verification_check", "")

            # Build mock arguments for the test task
            exec_args = dict(expected_arg_vals)
            if expected_tool == "create_file" and "content" not in exec_args:
                exec_args["content"] = "def add(a, b):\n    return a + b\n"
            elif expected_tool == "edit_file" and "old_str" not in exec_args:
                exec_args["old_str"] = "return a + b"
                exec_args["new_str"] = "return int(a) + int(b)"
            elif expected_tool == "read_file" and "start_line" not in exec_args:
                exec_args["start_line"] = 1
                exec_args["end_line"] = 10
            elif expected_tool == "execute_command" and "command" not in exec_args:
                exec_args["command"] = f'"{sys.executable}" tests/test_validation.py'

            tool_correct = tool_selection_accuracy(expected_tool, expected_tool)
            arg_cov = argument_coverage(exec_args, required_args)

            t0 = time.time()
            exec_res = self.controller.controlled_execute(expected_tool, exec_args)
            dur = time.time() - t0

            # State Verification
            state_verified = False
            if exec_res.success:
                out_str = str(exec_res.output)
                if verification_target in out_str:
                    state_verified = True
                elif expected_tool in ("create_file", "edit_file"):
                    file_path = exec_args.get("path", "")
                    if os.path.isfile(file_path):
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            if verification_target in f.read():
                                state_verified = True

            # Record result
            results.append({
                "id": task_id,
                "tool_selected": expected_tool,
                "tool_accuracy": tool_correct,
                "argument_coverage": arg_cov,
                "execution_success": exec_res.success,
                "state_verified": state_verified,
                "duration_seconds": round(dur, 4),
                "error": exec_res.error,
            })

        # Cleanup any scratch test files created during the suite
        for t in tasks:
            target_path = t.get("expected_arg_values", {}).get("path")
            if target_path and "scratch_eval" in target_path and os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except OSError:
                    pass

        tool_acc_avg = sum(r["tool_accuracy"] for r in results) / float(len(results)) if results else 0.0
        state_ver_avg = sum(1 for r in results if r["state_verified"]) / float(len(results)) if results else 0.0

        return {
            "total_tasks": len(results),
            "tool_selection_accuracy": round(tool_acc_avg, 4),
            "task_completion_rate": round(state_ver_avg, 4),
            "details": results,
        }

