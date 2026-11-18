# assistant/evaluation/metrics.py

import ast
import subprocess
import sys
import tempfile
import time
from typing import List, Set, Dict, Any, Tuple, Optional


# =====================================================================
# 1. Retrieval Metrics
# =====================================================================

def precision_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """
    Compute Precision@K: the fraction of top-K retrieved items that are relevant.
    
    Formula:
        Precision@K = |Retrieved_K ∩ Relevant| / K
    """
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    relevant_retrieved = sum(1 for item in top_k if item in relevant)
    return relevant_retrieved / float(k)


def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """
    Compute Recall@K: the fraction of all known relevant items captured in top-K.
    
    Formula:
        Recall@K = |Retrieved_K ∩ Relevant| / |Relevant|
    """
    if not relevant:
        return 1.0  # If nothing was relevant, recall is vacuously complete
    top_k = retrieved[:k]
    relevant_retrieved = sum(1 for item in top_k if item in relevant)
    return relevant_retrieved / float(len(relevant))


def reciprocal_rank(retrieved: List[str], relevant: Set[str]) -> float:
    """
    Compute the Reciprocal Rank (RR): 1 / rank of the first relevant item.
    Returns 0.0 if no relevant item is found in retrieved list.
    """
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / float(rank)
    return 0.0


def mean_reciprocal_rank(all_retrieved: List[List[str]], all_relevant: List[Set[str]]) -> float:
    """
    Compute Mean Reciprocal Rank (MRR) across a collection of evaluation queries.
    """
    if not all_retrieved or not all_relevant or len(all_retrieved) != len(all_relevant):
        return 0.0
    total_rr = sum(
        reciprocal_rank(retrieved, relevant)
        for retrieved, relevant in zip(all_retrieved, all_relevant)
    )
    return total_rr / float(len(all_retrieved))


# =====================================================================
# 2. Code Generation & Execution Metrics
# =====================================================================

def validate_python_syntax(code: str) -> Tuple[bool, Optional[str]]:
    """
    Verify whether the code compiles under Python's Abstract Syntax Tree (AST).
    Returns (True, None) if valid, or (False, error_message) on syntax failure.
    """
    if not code or not code.strip():
        return False, "Code string is empty."
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"


def execute_unit_tests(
    code_under_test: str,
    test_suite_code: str,
    timeout_seconds: int = 5,
) -> Tuple[bool, Optional[str]]:
    """
    Execute generated code against a unit test suite in an isolated subprocess.
    Measures functional correctness (Pass@1) without modifying the local environment.
    """
    # Combine user code and test suite into a single executable script
    combined = f"{code_under_test.strip()}\n\n{test_suite_code.strip()}\n"
    
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
        temp_file.write(combined)
        temp_path = temp_file.name

    try:
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if result.returncode == 0:
            return True, None
        else:
            err = result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}"
            return False, err
    except subprocess.TimeoutExpired:
        return False, f"Execution timed out after {timeout_seconds} seconds (potential infinite loop)."
    except Exception as e:
        return False, f"Execution exception: {e}"
    finally:
        import os
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# =====================================================================
# 3. Agent & Tool Metrics
# =====================================================================

def tool_selection_accuracy(selected_tool: str, expected_tool: str) -> float:
    """
    Evaluate if the agent selected the expected tool for a specific task step.
    """
    return 1.0 if selected_tool.strip().lower() == expected_tool.strip().lower() else 0.0


def argument_coverage(actual_args: Dict[str, Any], required_keys: Set[str]) -> float:
    """
    Calculate the ratio of required tool arguments provided by the agent.
    """
    if not required_keys:
        return 1.0
    present_keys = sum(1 for k in required_keys if k in actual_args and actual_args[k] is not None)
    return present_keys / float(len(required_keys))


# =====================================================================
# 4. Performance & Hardware Metrics
# =====================================================================

def calculate_tokens_per_second(token_count: int, duration_seconds: float) -> float:
    """
    Compute inference generation throughput.
    """
    if duration_seconds <= 0.0 or token_count <= 0:
        return 0.0
    return float(token_count) / float(duration_seconds)


if __name__ == "__main__":
    print("=" * 60)
    print("      Sub-Phase 6.1: Evaluation Metrics Verification")
    print("=" * 60)

    # 1. Retrieval Metrics Test
    retrieved_items = ["auth.py", "database.py", "models.py", "utils.py", "config.py"]
    relevant_items = {"auth.py", "models.py"}

    p_at_3 = precision_at_k(retrieved_items, relevant_items, k=3)
    r_at_3 = recall_at_k(retrieved_items, relevant_items, k=3)
    rr = reciprocal_rank(retrieved_items, relevant_items)

    print(f"\n[+] Retrieval Test:")
    print(f"    Retrieved: {retrieved_items[:3]}")
    print(f"    Relevant:  {list(relevant_items)}")
    print(f"    Precision@3: {p_at_3:.4f} (Expected: 2/3 = 0.6667)")
    print(f"    Recall@3:    {r_at_3:.4f} (Expected: 2/2 = 1.0000)")
    print(f"    Reciprocal Rank: {rr:.4f} (Expected: 1/1 = 1.0000)")
    assert abs(p_at_3 - 0.6667) < 0.001
    assert abs(r_at_3 - 1.0) < 0.001
    assert abs(rr - 1.0) < 0.001

    # 2. Syntax Validation Test
    valid_code = "def add(a: int, b: int) -> int:\n    return a + b"
    invalid_code = "def add(a: int, b:\n    return a +"
    valid_ok, _ = validate_python_syntax(valid_code)
    invalid_ok, err_msg = validate_python_syntax(invalid_code)

    print(f"\n[+] Syntax Validation Test:")
    print(f"    Valid Code Check:   {valid_ok}")
    print(f"    Invalid Code Check: {not invalid_ok} (Reported: {err_msg})")
    assert valid_ok and not invalid_ok

    # 3. Isolated Unit Test Execution Test
    test_suite = "assert add(2, 3) == 5\nassert add(-1, 1) == 0"
    pass_ok, _ = execute_unit_tests(valid_code, test_suite)
    failing_test_suite = "assert add(2, 3) == 10"
    fail_ok, fail_err = execute_unit_tests(valid_code, failing_test_suite)

    print(f"\n[+] Unit Test Execution Test:")
    print(f"    Passing Test Run:   {pass_ok}")
    print(f"    Failing Test Run:   {not fail_ok}")
    assert pass_ok and not fail_ok

    print("\n[PASS] Metrics verification complete. All calculations verified.")
