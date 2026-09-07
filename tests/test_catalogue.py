import sqlite3

import pytest

from meh_studio.catalogue import Catalogue
from meh_studio.domain import DriverRevision


def test_revisions_are_immutable_idempotent_and_persistent(tmp_path, driver):
    path = tmp_path / "driver # data.sqlite"
    with Catalogue.create(path) as cat:
        assert cat.add(driver)
        assert not cat.add(driver)
        changed = DriverRevision.model_validate(driver.model_dump() | {"depth_m": 0.05})
        with pytest.raises(ValueError, match="immutable revision"):
            cat.add(changed)
        revision2 = DriverRevision.model_validate(changed.model_dump() | {"revision": 2})
        assert cat.add(revision2)  # transaction recovered after rejected mutation
    with Catalogue(path, readonly=True) as cat:
        assert cat.list() == [driver, revision2]
        with pytest.raises(ValueError, match="read-only"):
            cat.add(driver)
    with pytest.raises(FileExistsError):
        Catalogue.create(path)


def test_unknown_database_is_not_created(tmp_path):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        Catalogue(path)
    assert not path.exists()


def test_unknown_schema_is_rejected(tmp_path):
    path = tmp_path / "future.sqlite"
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="schema version"):
        Catalogue(path)


def test_tampered_record_is_detected(tmp_path, driver):
    path = tmp_path / "data.sqlite"
    with Catalogue.create(path) as cat:
        cat.add(driver)
    with sqlite3.connect(path) as con:
        con.execute("UPDATE drivers SET hash=?", ("0"*64,))
    with Catalogue(path, readonly=True) as cat:
        with pytest.raises(ValueError, match="integrity"):
            cat.list()


@pytest.mark.parametrize("column,value", [("id", "displaced"), ("revision", 99)])
def test_displaced_keys_rejected_on_read_and_before_write(tmp_path, driver, column, value):
    path = tmp_path / "displaced.sqlite"
    with Catalogue.create(path) as cat:
        cat.add(driver)
    with sqlite3.connect(path) as con:
        # Column names are restricted to the literal parametrized cases above.
        con.execute(f"UPDATE drivers SET {column}=?", (value,))
    with Catalogue(path) as cat:
        with pytest.raises(ValueError, match="integrity"):
            cat.list()
        with pytest.raises(ValueError, match="integrity"):
            cat.add(driver)
        assert cat.connection.execute("SELECT count(*) FROM drivers").fetchone()[0] == 1
