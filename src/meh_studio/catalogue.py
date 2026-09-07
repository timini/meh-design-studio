"""Private, immutable driver revisions. This is not a bundled qualified pack."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .domain import DriverRevision


class Catalogue:
    def __init__(self, path: Path, *, readonly: bool = False):
        self.path = Path(path).resolve()
        self.readonly = readonly
        mode = "ro" if readonly else "rw"
        self.connection = sqlite3.connect(f"{self.path.as_uri()}?mode={mode}", uri=True)
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version != 1:
            self.connection.close()
            raise ValueError(f"unsupported catalogue schema version: {version}")

    @classmethod
    def create(cls, path: Path) -> Catalogue:
        path = Path(path)
        # Exclusive create prevents accidental replacement of a user's database.
        with path.open("xb"):
            pass
        try:
            with sqlite3.connect(path) as con:
                con.execute("CREATE TABLE drivers (id TEXT NOT NULL, revision INTEGER NOT NULL, "
                            "hash TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(id, revision))")
                con.execute("PRAGMA user_version=1")
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return cls(path)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()

    def add(self, driver: DriverRevision) -> bool:
        if self.readonly:
            raise ValueError("catalogue is read-only")
        # Serialize writers so conflict-check + insert is atomic.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.list()  # Reject displaced/corrupt keys before any new revision is inserted.
            row = self.connection.execute(
                "SELECT hash FROM drivers WHERE id=? AND revision=?",
                (driver.id, driver.revision)).fetchone()
            if row:
                if row[0] != driver.content_hash:
                    raise ValueError("immutable revision conflict; create a new revision")
                self.connection.commit()
                return False
            self.connection.execute("INSERT INTO drivers VALUES (?, ?, ?, ?)",
                                    (driver.id, driver.revision, driver.content_hash, driver.canonical_json()))
            self.connection.commit()
            return True
        except Exception:
            self.connection.rollback()
            raise

    def list(self) -> list[DriverRevision]:
        records = []
        for driver_id, revision, content_hash, raw in self.connection.execute(
            "SELECT id, revision, hash, record FROM drivers ORDER BY id, revision"
        ):
            record = DriverRevision.model_validate_json(raw)
            if (record.content_hash != content_hash or record.id != driver_id
                    or record.revision != revision):
                raise ValueError("catalogue integrity mismatch")
            records.append(record)
        return records
