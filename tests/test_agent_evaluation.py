"""
Phase 4.9: Agent Evaluation Benchmark Suite
Evaluates all 8 test categories defined in Phase 4 Section 12.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.tools import get_default_registry
from assistant.agent.control import ExecutionController
from assistant.agent.planner import TaskPlanner, TaskStatus
from assistant.agent.state import RequestType
from assistant.agent.manager import AgentManager


def run_phase4_benchmark():
    print("================================================================")
    print("      Phase 4.9: Agent System & Tool Evaluation Benchmark       ")
    print("================================================================\n")

    registry = get_default_registry()
    controller = ExecutionController(registry, auto_approve_modifications=True)
    planner = TaskPlanner()
    agent = AgentManager(registry=registry)
    agent.controller.auto_approve_modifications = True

    passed = 0
    total = 8

    # --- Test 1: File Reading ---
    print("Test 1 [File Reading]:")
    res1 = controller.controlled_execute("read_file", {"path": "assistant/config/settings.py", "start_line": 1, "end_line": 5})
    if res1.success and "settings.py" in str(res1.output):
        print("  Result: [PASS] File read successfully with line bounds.\n")
        passed += 1
    else:
        print(f"  Result: [FAIL] {res1.error}\n")

    # --- Test 2: File Creation ---
    print("Test 2 [File Creation]:")
    test_file = "scratch_calc.py"
    res2 = controller.controlled_execute("create_file", {"path": test_file, "content": "def multiply(a, b):\n    return a * b\n", "overwrite": True})
    if res2.success and os.path.exists(test_file):
        print("  Result: [PASS] File created and verified on disk.\n")
        passed += 1
    else:
        print(f"  Result: [FAIL] {res2.error}\n")

    # --- Test 3: File Modification ---
    print("Test 3 [File Modification]:")
    res3 = controller.controlled_execute("edit_file", {"path": test_file, "old_str": "a * b", "new_str": "int(a) * int(b)"})
    if res3.success and "diff" in res3.output and res3.output["diff"]:
        print("  Result: [PASS] Targeted string replacement succeeded with diff.\n")
        passed += 1
    else:
        print(f"  Result: [FAIL] {res3.error}\n")

    # --- Test 4: Terminal Execution ---
    print("Test 4 [Terminal Execution]:")
    res4 = controller.controlled_execute("execute_command", {"command": f'"{sys.executable}" tests/test_validation.py'})
    if res4.success and res4.output["exit_code"] == 0:
        print("  Result: [PASS] Command executed and output captured cleanly.\n")
        passed += 1
    else:
        print(f"  Result: [FAIL] {res4.error}\n")

    # --- Test 5: Error Diagnosis ---
    print("Test 5 [Error Diagnosis & Code Search]:")
    res5 = controller.controlled_execute("search_code", {"query": "class DatabaseConfig"})
    if res5.success and len(res5.output) > 0:
        print(f"  Result: [PASS] Search engine located symbol in {res5.output[0]['file']}.\n")
        passed += 1
    else:
        print(f"  Result: [FAIL] {res5.error}\n")

    # --- Test 6: Multi-Step Task Planning ---
    print("Test 6 [Multi-Step Planning]:")
    plan = planner.create_plan("Create a notes service and run its tests")
    if len(plan.tasks) >= 2 and all(t.status == TaskStatus.PENDING for t in plan.tasks):
        print(f"  Result: [PASS] Generated structured plan with {len(plan.tasks)} steps.\n")
        passed += 1
    else:
        print("  Result: [FAIL] Plan generation incomplete.\n")

    # --- Test 7: Permission Enforcement ---
    print("Test 7 [Permission Enforcement]:")
    bad_cmd_res = controller.controlled_execute("execute_command", {"command": "format C: /y"})
    denied_controller = ExecutionController(registry, approval_callback=lambda tool, args: False)
    denied_res = denied_controller.controlled_execute("delete_file", {"path": test_file})
    if not bad_cmd_res.success and not denied_res.success:
        print("  Result: [PASS] Destructive commands blocked & user denial respected.\n")
        passed += 1
    else:
        print("  Result: [FAIL] Permissions not properly enforced.\n")

    # --- Test 8: Path Protection ---
    print("Test 8 [Path Traversal Protection]:")
    escape_res = controller.controlled_execute("read_file", {"path": "../../Windows/System32/drivers/etc/hosts"})
    if not escape_res.success and "Security Violation" in str(escape_res.error):
        print("  Result: [PASS] Sandbox contained path traversal attempt.\n")
        passed += 1
    else:
        print("  Result: [FAIL] Path traversal was not blocked.\n")

    # Cleanup temporary test file
    if os.path.exists(test_file):
        os.remove(test_file)

    print("----------------------------------------------------------------")
    print(f"Benchmark Summary: {passed}/{total} Tests Passed ({passed/total*100:.1f}%)")
    print("----------------------------------------------------------------\n")
    return passed == total


if __name__ == "__main__":
    success = run_phase4_benchmark()
    sys.exit(0 if success else 1)