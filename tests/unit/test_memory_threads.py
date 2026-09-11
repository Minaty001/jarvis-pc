"""Test concurrency and multi-threading safety of MemoryStore."""

import concurrent.futures
from jarvis.brain.memory import MemoryStore


def test_memory_store_thread_safety(tmp_path):
    db_path = tmp_path / "concurrent_memory.db"
    store = MemoryStore(db_path)

    def write_worker(idx: int):
        store.add(f"user query {idx}", f"assistant reply {idx}")
        store.store_reflection(
            goal_query=f"goal {idx}",
            lesson=f"lesson {idx}",
            category="testing",
            verified=True,
        )
        return idx

    def read_worker(idx: int):
        rec = store.recall(f"query {idx}")
        ref = store.recall_reflections(f"goal {idx}")
        recent = store.recent(5)
        refs = store.list_reflections(5)
        return len(rec) + len(ref) + len(recent) + len(refs)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for i in range(20):
            futures.append(executor.submit(write_worker, i))
            futures.append(executor.submit(read_worker, i))

        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        assert len(results) == 40

    store.close()
