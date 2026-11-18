# assistant/evaluation/__init__.py
"""
Evaluation and benchmarking framework for OfflineCodingAssistant.
Provides metrics, datasets, evaluators, runners, and automated reporting.
"""

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
from assistant.evaluation.evaluator import (
    ModelEvaluator,
    RetrievalEvaluator,
    AgentEvaluator,
)
from assistant.evaluation.reporter import EvaluationReporter
from assistant.evaluation.runner import EvaluationRunner

__all__ = [
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "mean_reciprocal_rank",
    "validate_python_syntax",
    "execute_unit_tests",
    "tool_selection_accuracy",
    "argument_coverage",
    "calculate_tokens_per_second",
    "ModelEvaluator",
    "RetrievalEvaluator",
    "AgentEvaluator",
    "EvaluationReporter",
    "EvaluationRunner",
]

