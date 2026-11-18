# assistant/evaluation/runner.py

import argparse
import os
import sys
import time
from typing import Dict, Any

from assistant.evaluation.evaluator import ModelEvaluator, RetrievalEvaluator, AgentEvaluator
from assistant.evaluation.reporter import EvaluationReporter
from assistant.utils.logger import setup_logger

logger = setup_logger("EvalRunner")


class EvaluationRunner:
    """Central runner for automated offline assistant benchmarks and evaluations."""

    def __init__(self, datasets_dir: Optional[str] = None, reports_dir: str = "reports"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.datasets_dir = datasets_dir or os.path.join(base_dir, "datasets")
        self.reporter = EvaluationReporter(output_dir=reports_dir)

    def run_all(self, run_model: bool = True, run_retrieval: bool = True, run_agent: bool = True) -> Dict[str, Any]:
        """Runs the requested evaluation suites and produces an aggregated report."""
        eval_data: Dict[str, Any] = {
            "timestamp": time.time(),
            "suites_executed": [],
        }

        print("\n" + "=" * 64)
        print("     Offline Coding Assistant — Automated Benchmark Suite       ")
        print("=" * 64)

        # 1. Retrieval Benchmark
        if run_retrieval:
            retrieval_tasks = os.path.join(self.datasets_dir, "retrieval_tasks.json")
            if os.path.isfile(retrieval_tasks):
                print("\n[*] Suite 1: Retrieval Evaluation (Keyword vs. Semantic vs. Hybrid)...")
                ret_eval = RetrievalEvaluator()
                ret_data = ret_eval.evaluate_retrieval_tasks(retrieval_tasks, k=3)
                eval_data["retrieval_evaluation"] = ret_data
                eval_data["suites_executed"].append("retrieval")

                summary = ret_data["summary"]
                print("    Results Summary (Top-3):")
                for mode, s in summary.items():
                    print(f"      • {mode.upper():<8} | Precision@3: {s['mean_precision_at_3']:.4f} | Recall@3: {s['mean_recall_at_3']:.4f} | MRR: {s['mrr']:.4f} | Latency: {s['avg_latency_seconds']:.4f}s")
            else:
                logger.warning(f"Retrieval dataset not found: {retrieval_tasks}")

        # 2. Agent Action & Tool Benchmark
        if run_agent:
            agent_tasks = os.path.join(self.datasets_dir, "agent_tasks.json")
            if os.path.isfile(agent_tasks):
                print("\n[*] Suite 2: Agent Tool & State Verification Evaluation...")
                agent_eval = AgentEvaluator()
                agent_data = agent_eval.evaluate_agent_tasks(agent_tasks)
                eval_data["agent_evaluation"] = agent_data
                eval_data["suites_executed"].append("agent")

                print(f"    Results Summary:")
                print(f"      • Tool Selection Accuracy: {agent_data['tool_selection_accuracy'] * 100:.1f}%")
                print(f"      • Task Completion Rate:    {agent_data['task_completion_rate'] * 100:.1f}%")
            else:
                logger.warning(f"Agent dataset not found: {agent_tasks}")

        # 3. Model Coding & Reasoning Benchmark
        if run_model:
            code_tasks = os.path.join(self.datasets_dir, "code_tasks.json")
            if os.path.isfile(code_tasks):
                print("\n[*] Suite 3: Local LLM Code Generation & Syntax Verification...")
                model_eval = ModelEvaluator()
                model_data = model_eval.evaluate_code_tasks(code_tasks)
                eval_data["model_evaluation"] = model_data
                eval_data["suites_executed"].append("model")

                print(f"    Results Summary:")
                print(f"      • Syntax Pass Rate (AST):  {model_data['syntax_pass_rate'] * 100:.1f}%")
                print(f"      • Functional Pass Rate:    {model_data['functional_pass_rate'] * 100:.1f}%")
                print(f"      • Avg Generation Speed:    {model_data['average_tokens_per_second']} tokens/sec")
            else:
                logger.warning(f"Code dataset not found: {code_tasks}")

        # Save Report
        saved_report_path = self.reporter.save_report(eval_data)
        print("\n" + "=" * 64)
        print(f"[+] Benchmark Run Completed.")
        print(f"[+] Structured Report Generated: {saved_report_path}")
        print("=" * 64 + "\n")

        return eval_data


def main():
    parser = argparse.ArgumentParser(description="Run Offline Coding Assistant benchmarks")
    parser.add_argument("--suite", choices=["all", "retrieval", "agent", "model"], default="all", help="Evaluation suite to execute")
    args = parser.parse_args()

    run_model = args.suite in ("all", "model")
    run_retrieval = args.suite in ("all", "retrieval")
    run_agent = args.suite in ("all", "agent")

    runner = EvaluationRunner()
    runner.run_all(run_model=run_model, run_retrieval=run_retrieval, run_agent=run_agent)


if __name__ == "__main__":
    from typing import Optional
    main()

