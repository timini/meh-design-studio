"""Durable job leases and verified artifact publication; no worker execution yet."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sqlite3
import time
from typing import Annotated, Literal
import uuid

from pydantic import Field, field_validator, model_validator

from .domain import Digest, Identifier, Record


MAX_COMPLETION_BYTES = 16 * 1024 * 1024


def completion_bytes(path: Path) -> bytes:
    with path.open("rb") as stream:
        if path.stat().st_size > MAX_COMPLETION_BYTES:
            raise ValueError("completion descriptor exceeds size limit")
        payload = stream.read(MAX_COMPLETION_BYTES + 1)
    if len(payload) > MAX_COMPLETION_BYTES:
        raise ValueError("completion descriptor exceeds size limit")
    return payload


class JobSpec(Record):
    kind: Literal["geometry", "mesh", "compile", "solve", "validate"]
    input_digest: Digest
    parameters_json: Annotated[str, Field(min_length=2, max_length=1_000_000)]
    max_attempts: Annotated[int, Field(strict=True, ge=1, le=10)] = 3

    @field_validator("parameters_json")
    @classmethod
    def canonical_parameters(cls, value):
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("job parameters must be a JSON object")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Artifact(Record):
    path: Annotated[str, Field(min_length=1, max_length=512)]
    sha256: Digest
    size_bytes: Annotated[int, Field(strict=True, ge=0)]

    @field_validator("path")
    @classmethod
    def portable_relative_path(cls, value):
        path = PurePosixPath(value)
        if (not path.parts or path.is_absolute() or path.as_posix() != value or any(p in {"..", "."} for p in path.parts)
                or "\\" in value or ":" in value or value == "completion.json"):
            raise ValueError("artifact path must be a normalized relative path below the attempt directory")
        return value


class Completion(Record):
    status: Literal["complete"] = "complete"
    job_id: Digest
    attempt_token: Identifier
    # Describes worker evidence; accepting a bundle never creates qualification.
    evidence: Literal["predicted", "experimental_geometry", "numerical_check"]
    files: Annotated[tuple[Artifact, ...], Field(min_length=1, max_length=10000)]

    @model_validator(mode="after")
    def unique_files(self):
        if len({f.path for f in self.files}) != len(self.files):
            raise ValueError("artifact paths must be unique")
        return self


@dataclass(frozen=True)
class Lease:
    job_id: str
    token: str
    attempt: int
    output_directory: Path
    spec: JobSpec


def file_digest(path: Path, *, check=None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            if check is not None:
                check()
            digest.update(chunk)
    return digest.hexdigest()


class JobQueue:
    def __init__(self, path: Path, *, clock=time.time):
        self.path = Path(path).resolve()
        self.clock = clock
        self.connection = sqlite3.connect(f"{self.path.as_uri()}?mode=rw", uri=True, isolation_level=None, timeout=30)
        try:
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys=ON")
            if self.connection.execute("PRAGMA user_version").fetchone()[0] != 2:
                raise ValueError("unsupported job database schema")
            setting = self.connection.execute("SELECT value FROM settings WHERE key='artifact_root'").fetchone()
            if setting is None:
                raise ValueError("job database has no artifact root")
            self.artifact_root = Path(setting[0])
        except BaseException:
            self.connection.close()
            raise

    @classmethod
    def create(cls, path: Path, artifact_root: Path, *, clock=time.time):
        path, artifact_root = Path(path), Path(artifact_root).resolve()
        if artifact_root == path.resolve() or (artifact_root.exists() and not artifact_root.is_dir()):
            raise ValueError("artifact root must be a directory separate from the database")
        with path.open("xb"):
            pass
        con = sqlite3.connect(path)
        try:
            with con:
                con.execute("PRAGMA journal_mode=WAL")
                con.executescript('''
                    CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE jobs(
                        id TEXT PRIMARY KEY, spec TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('queued','running','cancel_requested','succeeded','failed','cancelled')),
                        created REAL NOT NULL, attempt INTEGER NOT NULL DEFAULT 0, automatic_retries INTEGER NOT NULL DEFAULT 0,
                        token TEXT, owner TEXT, deadline REAL, completion_hash TEXT, error TEXT);
                    CREATE TABLE attempts(
                        token TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                        number INTEGER NOT NULL, owner TEXT NOT NULL, started REAL NOT NULL,
                        finished REAL, outcome TEXT, error TEXT, UNIQUE(job_id, number));
                    PRAGMA user_version=2;
                ''')
                con.execute("INSERT INTO settings VALUES ('artifact_root',?)", (str(artifact_root),))
        except BaseException:
            con.close()
            path.unlink(missing_ok=True)
            raise
        finally:
            con.close()
        return cls(path, clock=clock)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()

    @contextmanager
    def _transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _now(self):
        value = self.clock()
        if not math.isfinite(value) or value < 0:
            raise ValueError("job clock must return finite UTC seconds")
        return value

    def _row(self, job_id):
        row = self.connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("unknown job")
        if JobSpec.model_validate_json(row["spec"]).content_hash != row["id"]:
            raise ValueError("job input identity is corrupt")
        return row

    def get(self, job_id):
        return dict(self._row(job_id))

    def enqueue(self, spec: JobSpec) -> str:
        with self._transaction():
            self.connection.execute("INSERT OR IGNORE INTO jobs(id,spec,status,created) VALUES (?,?,'queued',?)",
                                    (spec.content_hash, spec.canonical_json(), self._now()))
            self._row(spec.content_hash)
        return spec.content_hash

    def _duration(self, seconds):
        if isinstance(seconds, bool) or not math.isfinite(seconds) or not 0 < seconds <= 86400:
            raise ValueError("lease duration must be positive and at most one day")
        return seconds

    def claim(self, owner: str, *, lease_seconds=60, kind: str | None = None) -> Lease | None:
        duration = self._duration(lease_seconds)
        if not isinstance(owner, str) or not owner.strip() or len(owner) > 128:
            raise ValueError("worker owner must be a nonempty short identifier")
        if kind is not None and kind not in {"geometry", "mesh", "compile", "solve", "validate"}:
            raise ValueError("unsupported job kind")
        with self._transaction():
            row = self.connection.execute(
                "SELECT id FROM jobs WHERE status='queued' AND (? IS NULL OR json_extract(spec,'$.kind')=?) "
                "ORDER BY created,id LIMIT 1", (kind, kind)).fetchone()
            if row is None:
                return None
            row = self._row(row["id"])
            spec = JobSpec.model_validate_json(row["spec"])
            if row["attempt"] >= spec.max_attempts:
                raise ValueError("queued job exhausted its attempt budget")
            token, attempt, now = uuid.uuid4().hex, row["attempt"]+1, self._now()
            self.connection.execute("UPDATE jobs SET status='running',attempt=?,token=?,owner=?,deadline=?,error=NULL WHERE id=?",
                                    (attempt,token,owner,now+duration,row["id"]))
            self.connection.execute("INSERT INTO attempts(token,job_id,number,owner,started) VALUES (?,?,?,?,?)",
                                    (token,row["id"],attempt,owner,now))
        return Lease(row["id"],token,attempt,self.artifact_root/row["id"]/token,spec)

    def _active(self, lease: Lease):
        row = self._row(lease.job_id)
        if (row["status"] not in {"running","cancel_requested"} or row["token"] != lease.token
                or row["attempt"] != lease.attempt or row["deadline"] <= self._now()):
            raise ValueError("worker lease is stale or inactive")
        return row

    def heartbeat(self, lease: Lease, *, lease_seconds=60) -> bool:
        with self._transaction():
            row = self._active(lease)
            self.connection.execute("UPDATE jobs SET deadline=? WHERE id=?", (self._now()+self._duration(lease_seconds),lease.job_id))
            return row["status"] == "cancel_requested"

    def cancel(self, job_id):
        with self._transaction():
            row = self._row(job_id)
            status = "cancelled" if row["status"] == "queued" else "cancel_requested"
            if row["status"] in {"queued","running"}:
                self.connection.execute("UPDATE jobs SET status=? WHERE id=?", (status,job_id))

    def _finish(self, row, outcome, error=None, digest=None):
        self.connection.execute("UPDATE attempts SET finished=?,outcome=?,error=? WHERE token=?",
                                (self._now(),outcome,error,row["token"]))
        self.connection.execute("UPDATE jobs SET status=?,deadline=NULL,completion_hash=?,error=? WHERE id=?",
                                (outcome,digest,error,row["id"]))

    def fail(self, lease: Lease, error: str):
        if not isinstance(error,str) or not error.strip():
            raise ValueError("failure requires a diagnostic")
        with self._transaction():
            row = self._active(lease)
            self._finish(row,"cancelled" if row["status"] == "cancel_requested" else "failed",error)

    def acknowledge_cancel(self, lease: Lease):
        with self._transaction():
            row = self._active(lease)
            if row["status"] != "cancel_requested":
                raise ValueError("job has no cancellation request")
            self._finish(row,"cancelled")

    def retry(self, job_id):
        with self._transaction():
            row = self._row(job_id)
            if row["status"] not in {"failed","cancelled"} or row["attempt"] >= JobSpec.model_validate_json(row["spec"]).max_attempts:
                raise ValueError("job cannot be retried")
            self.connection.execute("UPDATE jobs SET status='queued',token=NULL,owner=NULL,deadline=NULL,completion_hash=NULL,error=NULL WHERE id=?", (job_id,))

    def recover_expired(self) -> int:
        with self._transaction():
            rows = self.connection.execute("SELECT id FROM jobs WHERE status IN ('running','cancel_requested') AND deadline<=?",(self._now(),)).fetchall()
            for item in rows:
                row = self._row(item["id"])
                self._finish(row,"cancelled" if row["status"] == "cancel_requested" else "failed","worker lease expired")
                if (row["status"] != "cancel_requested" and row["automatic_retries"] < 1
                        and row["attempt"] < JobSpec.model_validate_json(row["spec"]).max_attempts):
                    self.connection.execute("UPDATE jobs SET status='queued',token=NULL,owner=NULL,automatic_retries=automatic_retries+1 WHERE id=?",(row["id"],))
            return len(rows)

    def _verified_completion(self, row, *, check=None):
        directory = (self.artifact_root/row["id"]/row["token"]).resolve()
        if not directory.is_relative_to(self.artifact_root.resolve()):
            raise ValueError("attempt directory escaped artifact root")
        path = directory/"completion.json"
        if path.is_symlink():
            raise ValueError("completion descriptor cannot be a symbolic link")
        payload = completion_bytes(path)
        digest = hashlib.sha256(payload).hexdigest()
        record = Completion.model_validate_json(payload)
        if record.job_id != row["id"] or record.attempt_token != row["token"]:
            raise ValueError("completion belongs to another job or attempt")
        for artifact in record.files:
            file = (directory/artifact.path).resolve()
            if not file.is_relative_to(directory) or not file.is_file():
                raise ValueError("artifact is missing or escaped the attempt directory")
            if file.stat().st_size != artifact.size_bytes or file_digest(file,check=check) != artifact.sha256:
                raise ValueError("completion artifact integrity mismatch")
        if hashlib.sha256(completion_bytes(path)).hexdigest() != digest:
            raise ValueError("completion descriptor changed during verification")
        return record,digest

    def complete(self, lease: Lease, *, check=None):
        row = self._active(lease)
        if row["status"] == "cancel_requested":
            raise ValueError("cancelled work cannot publish a successful result")
        _,digest = self._verified_completion(row) if check is None else self._verified_completion(row,check=check)
        # Keep slow file hashing outside the writer lock so cancellation can win.
        with self._transaction():
            row = self._active(lease)
            if row["status"] == "cancel_requested":
                raise ValueError("cancelled work cannot publish a successful result")
            path = self.artifact_root/row["id"]/row["token"]/"completion.json"
            if hashlib.sha256(completion_bytes(path)).hexdigest() != digest:
                raise ValueError("completion descriptor changed before publication")
            self._finish(row,"succeeded",digest=digest)

    def result(self, job_id) -> Completion:
        row = self._row(job_id)
        if row["status"] != "succeeded":
            raise ValueError("job has no successful result")
        record,digest = self._verified_completion(row)
        if digest != row["completion_hash"]:
            raise ValueError("published completion descriptor changed")
        return record
