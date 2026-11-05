"""
Sub-Phase 3.8 — Testing & Validation Benchmark
Evaluates the assistant's repository understanding across all 6 test categories
from Phase 3 Section 12 on a controlled sample project.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.repo.scanner import ProjectScanner
from assistant.repo.context import ContextBuilder
from assistant.repo.search import SearchEngine
from assistant.repo.parser import CodeParser


def run_benchmark():
    sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample_project"))
    print("================================================================")
    print("      Phase 3.8: Repository Understanding Validation Benchmark   ")
    print(f"      Target Project: {sample_dir}")
    print("================================================================\n")

    scanner = ProjectScanner(root_dir=sample_dir)
    builder = ContextBuilder(scanner=scanner)
    search_engine = SearchEngine(scanner)
    parser = CodeParser()

    all_files = scanner.get_all_files()
    print(f"[*] Project Scanned: {len(all_files)} files indexed.\n")

    tests = [
        {
            "id": 1,
            "category": "File Discovery",
            "query": "Where is authentication implemented?",
            "validator": lambda ctx: any(p in ctx.replace("/", "\\") for p in ["backend\\auth\\service.py", "backend\\auth\\middleware.py"]),
            "expected": "Locate backend/auth/service.py or middleware.py"
        },
        {
            "id": 2,
            "category": "Symbol Discovery",
            "query": "Which class handles user authentication?",
            "validator": lambda ctx: "AuthenticationService" in ctx,
            "expected": "Identify 'AuthenticationService' class"
        },
        {
            "id": 3,
            "category": "Dependency Discovery",
            "query": "What files import AuthenticationService?",
            "validator": lambda ctx: any(f in ctx for f in ["routes.py", "middleware.py", "test_auth.py"]),
            "expected": "Identify files importing AuthenticationService"
        },
        {
            "id": 4,
            "category": "Architecture Flow",
            "query": "Explain how a login request flows through the application",
            "validator": lambda ctx: "login_route" in ctx or "authenticate_user" in ctx,
            "expected": "Retrieve route and service login methods"
        },
        {
            "id": 5,
            "category": "Configuration Discovery",
            "query": "Where is the database connection configured?",
            "validator": lambda ctx: "DatabaseConfig" in ctx or "init_db_connection" in ctx,
            "expected": "Locate DatabaseConfig / init_db_connection"
        },
        {
            "id": 6,
            "category": "Testing Discovery",
            "query": "Which tests cover authentication?",
            "validator": lambda ctx: "test_auth.py" in ctx or "test_authenticate_success" in ctx,
            "expected": "Identify test_auth.py and test functions"
        },
    ]

    passed_count = 0

    for t in tests:
        print(f"Test {t['id']} [{t['category']}]:")
        print(f"  Query:    \"{t['query']}\"")
        print(f"  Expected: {t['expected']}")

        context = builder.build_context(t["query"])
        passed = t["validator"](context)

        if passed:
            print("  Result:   [PASS] Found expected context.")
            passed_count += 1
        else:
            print("  Result:   [FAIL] Expected elements missing from retrieved context.")
            if context:
                print(f"  Preview:  {context[:200]}...")
            else:
                print("  Preview:  (Empty context)")
        print()

    print("----------------------------------------------------------------")
    print(f"Benchmark Summary: {passed_count}/{len(tests)} Tests Passed ({passed_count/len(tests)*100:.1f}%)")
    print("----------------------------------------------------------------\n")
    return passed_count == len(tests)


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)

