from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.search import search


def test_concurrent_sync_and_search_keep_the_index_consistent(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    root = tmp_path / "course"
    root.mkdir()
    for index in range(40):
        (root / f"lecture-{index:02d}.md").write_text(
            f"# Lecture {index}\n\nMomentum marker-{index:02d} is conserved.",
            encoding="utf-8",
        )
    database_path = tmp_path / "classcorpus.sqlite3"
    setup = Database(database_path)
    setup.initialize()
    assert sync_course(setup, "Physics", root).indexed == 40
    setup.connection.close()

    for index in range(40):
        (root / f"lecture-{index:02d}.md").write_text(
            f"# Lecture {index}\n\nUpdated momentum marker-{index:02d} is conserved.",
            encoding="utf-8",
        )

    barrier = Barrier(6)

    def synchronize() -> tuple[int, int]:
        database = Database(database_path)
        database.initialize()
        barrier.wait()
        report = sync_course(database, "Physics", root)
        database.connection.close()
        return report.failed, report.indexed + report.skipped

    def search_repeatedly() -> int:
        database = Database(database_path)
        database.initialize()
        barrier.wait()
        matches = 0
        for _ in range(25):
            matches += int(bool(search(database, "momentum", course="Physics")))
        database.connection.close()
        return matches

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(synchronize) for _ in range(2)]
        futures.extend(executor.submit(search_repeatedly) for _ in range(4))
        results = [future.result(timeout=45) for future in futures]

    assert all(failed == 0 and handled == 40 for failed, handled in results[:2])
    assert results[2:] == [25, 25, 25, 25]
    final = Database(database_path)
    final.initialize()
    assert final.source_health("Physics").ready == 40
    assert final.slide_count("Physics") == 40
    assert len(search(final, "updated momentum", course="Physics")) == 8
    assert final.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
