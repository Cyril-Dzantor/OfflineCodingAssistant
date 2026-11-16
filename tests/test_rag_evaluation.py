"""
Phase 5.11 — RAG & Context Management Evaluation Benchmark
Evaluates the retrieval, indexing, hybrid ranking, memory, and context efficiency
across all 8 test categories defined in Phase 5 Section 14.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.rag.embeddings import get_embedding_model
from assistant.rag.chunker import CodeChunker
from assistant.rag.vector_store import VectorStore
from assistant.rag.indexer import RepositoryIndexer
from assistant.rag.semantic_search import SemanticSearchEngine
from assistant.rag.hybrid import HybridRetriever
from assistant.rag.memory import ProjectMemory
from assistant.repo.context import ContextBuilder


def run_rag_benchmark():
    print("================================================================")
    print("      Phase 5.11: Advanced Context Management & RAG Benchmark   ")
    print("================================================================\n")

    sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample_project"))
    test_db = os.path.abspath(".cydags/eval_rag_store.db")

    # Clean up previous eval database if exists
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    store = VectorStore(db_path=test_db)
    store.clear()
    embedder = get_embedding_model()
    chunker = CodeChunker()
    indexer = RepositoryIndexer(
        root_dir=sample_dir,
        vector_store=store,
        embedding_model=embedder,
        chunker=chunker,
    )

    print("[*] Performing initial indexing on sample project...")
    t0 = time.time()
    init_stats = indexer.index_repository(force_rebuild=True)
    idx_time = time.time() - t0
    print(f"    Indexed {init_stats['total_chunks_added']} chunks across {init_stats['total_scanned']} files in {idx_time:.2f}s.\n")

    sem_engine = SemanticSearchEngine(vector_store=store, embedding_model=embedder)
    retriever = HybridRetriever(vector_store=store, semantic_search=sem_engine)
    builder = ContextBuilder(scanner=indexer.scanner, retriever=retriever, max_budget_chars=4000)

    tests_passed = 0
    total_tests = 8

    # -------------------------------------------------------------
    # Test 1: Semantic Retrieval
    # -------------------------------------------------------------
    print("Test 1 [Semantic Retrieval]:")
    q1 = "Where does the application verify user login credentials?"
    print(f"  Query:    \"{q1}\"")
    results1 = sem_engine.search(q1, top_k=3, min_score=0.3)
    found_auth = any(
        "service.py" in r.chunk.file_path or "authenticate_user" in r.chunk.symbol_name or "AuthenticationService" in r.chunk.symbol_name
        for r in results1
    )
    if found_auth:
        top_match = results1[0]
        print(f"  Result:   [PASS] Retrieved {top_match.chunk.symbol_name} in {top_match.chunk.file_path} (Score: {top_match.score:.4f})")
        tests_passed += 1
    else:
        print(f"  Result:   [FAIL] Did not retrieve authentication service. Results: {[r.chunk.symbol_name for r in results1]}")
    print()

    # -------------------------------------------------------------
    # Test 2: Documentation & Config Retrieval
    # -------------------------------------------------------------
    print("Test 2 [Documentation & Configuration Retrieval]:")
    q2 = "How do I configure the database connection?"
    print(f"  Query:    \"{q2}\"")
    results2 = sem_engine.search(q2, top_k=3, min_score=0.3)
    found_db = any(
        "config.py" in r.chunk.file_path or "DatabaseConfig" in r.chunk.symbol_name or "init_db_connection" in r.chunk.symbol_name
        for r in results2
    )
    if found_db:
        top_match = results2[0]
        print(f"  Result:   [PASS] Retrieved {top_match.chunk.symbol_name} in {top_match.chunk.file_path} (Score: {top_match.score:.4f})")
        tests_passed += 1
    else:
        print(f"  Result:   [FAIL] Did not retrieve database config. Results: {[r.chunk.symbol_name for r in results2]}")
    print()

    # -------------------------------------------------------------
    # Test 3: Hybrid Search (RRF Keyword + Semantic)
    # -------------------------------------------------------------
    print("Test 3 [Hybrid Retrieval with Reciprocal Rank Fusion]:")
    q3 = "Find where JWT tokens are generated and validated."
    print(f"  Query:    \"{q3}\"")
    results3 = retriever.search(q3, top_k=3, mode="hybrid")
    found_jwt = any(
        "service.py" in r.chunk.file_path or "middleware.py" in r.chunk.file_path or "token" in r.chunk.content.lower()
        for r in results3
    )
    if found_jwt:
        top_match = results3[0]
        print(f"  Result:   [PASS] Retrieved {top_match.chunk.symbol_name} (Sources: {top_match.sources}, Score: {top_match.score:.4f})")
        tests_passed += 1
    else:
        print(f"  Result:   [FAIL] Did not retrieve token logic. Results: {[r.chunk.symbol_name for r in results3]}")
    print()

    # -------------------------------------------------------------
    # Test 4: Cross-File Understanding
    # -------------------------------------------------------------
    print("Test 4 [Cross-File Understanding]:")
    q4 = "Explain the complete flow of a user registration request."
    print(f"  Query:    \"{q4}\"")
    results4 = retriever.search(q4, top_k=5, mode="hybrid")
    files_retrieved = {r.chunk.file_path for r in results4}
    # Expected across api routes, user models, auth service
    has_multiple_files = len(files_retrieved) >= 2
    if has_multiple_files:
        print(f"  Result:   [PASS] Retrieved relevant chunks spanning {len(files_retrieved)} distinct files: {list(files_retrieved)}")
        tests_passed += 1
    else:
        print(f"  Result:   [FAIL] Cross-file coverage insufficient: {files_retrieved}")
    print()

    # -------------------------------------------------------------
    # Test 5: Incremental Indexing
    # -------------------------------------------------------------
    print("Test 5 [Incremental Indexing on File Modification]:")
    scratch_file = os.path.join(sample_dir, "scratch_inc_test.py")
    try:
        # Create new file
        with open(scratch_file, "w", encoding="utf-8") as f:
            f.write("def calculate_discount(price, pct):\n    return price * (1 - pct)\n")

        inc_stats1 = indexer.index_repository(force_rebuild=False)
        added_ok = inc_stats1["added_files"] == 1 and inc_stats1["modified_files"] == 0

        # Modify the file
        with open(scratch_file, "a", encoding="utf-8") as f:
            f.write("\ndef calculate_tax(price, rate=0.08):\n    return price * rate\n")

        inc_stats2 = indexer.index_repository(force_rebuild=False)
        mod_ok = inc_stats2["modified_files"] == 1 and inc_stats2["added_files"] == 0

        if added_ok and mod_ok:
            print("  Result:   [PASS] Detected 1 added file on creation, 1 modified file on update.")
            tests_passed += 1
        else:
            print(f"  Result:   [FAIL] Expected 1 added, 1 modified. Got added={inc_stats1['added_files']}, mod={inc_stats2['modified_files']}")
    finally:
        if os.path.exists(scratch_file):
            os.remove(scratch_file)
    print()

    # -------------------------------------------------------------
    # Test 6: Deleted Files Cleanup
    # -------------------------------------------------------------
    print("Test 6 [Stale Chunk Removal on File Deletion]:")
    # File scratch_file was deleted in finally block
    del_stats = indexer.index_repository(force_rebuild=False)
    if del_stats["deleted_files"] == 1:
        print(f"  Result:   [PASS] Stale chunks purged. Deleted files detected: {del_stats['deleted_files']}")
        tests_passed += 1
    else:
        print(f"  Result:   [FAIL] Expected 1 deleted file, got {del_stats['deleted_files']}")
    print()

    # -------------------------------------------------------------
    # Test 7: Context Efficiency & Budgeting
    # -------------------------------------------------------------
    print("Test 7 [Context Efficiency & Token Budgeting]:")
    q7 = "How does user authentication work in the backend?"
    ctx = builder.build_context(q7)
    char_len = len(ctx)
    under_budget = 0 < char_len <= builder.max_budget_chars
    has_structure = "File `" in ctx and "Lines " in ctx

    if under_budget and has_structure:
        print(f"  Result:   [PASS] Context constructed cleanly ({char_len} chars <= {builder.max_budget_chars} limit)")
        tests_passed += 1
    else:
        print(f"  Result:   [FAIL] Context empty or exceeded budget ({char_len} chars)")
    print()

    # -------------------------------------------------------------
    # Test 8: Offline Operation Verification
    # -------------------------------------------------------------
    print("Test 8 [100% Offline Operation Verification]:")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        t_off = time.time()
        q_off = "Where is the database host configured?"
        off_results = retriever.search(q_off, top_k=2)
        off_dur = time.time() - t_off
        if off_results:
            print(f"  Result:   [PASS] Offline search succeeded in {off_dur:.3f}s with HF_HUB_OFFLINE=1.")
            tests_passed += 1
        else:
            print("  Result:   [FAIL] Offline retrieval yielded no results.")
    except Exception as e:
        print(f"  Result:   [FAIL] Network exception raised in offline mode: {e}")
    print()

    # Cleanup test store
    store.clear()
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    # Benchmark Summary
    print("----------------------------------------------------------------")
    print(f"Benchmark Summary: {tests_passed}/{total_tests} Tests Passed ({(tests_passed/total_tests)*100:.1f}%)")
    print("----------------------------------------------------------------\n")
    return tests_passed == total_tests


if __name__ == "__main__":
    success = run_rag_benchmark()
    sys.exit(0 if success else 1)

