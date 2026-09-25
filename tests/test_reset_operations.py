import sqlite3

import pytest

from miner.maintenance import backup, reset
from miner.store import Store


def fixture(tmp_path):
    store = Store(tmp_path / "data")
    store.execute("INSERT INTO vods(id,campaign,source_key,data) VALUES('TEST_1','gabepeixe','key','{}')")
    folder = store.dirs("gabepeixe", "TEST_1")["candidates"]
    (folder / "preview.mp4").write_bytes(b"test")
    config = tmp_path / "config/campaigns"
    config.mkdir(parents=True)
    for name in ("gabepeixe", "brkk", "brabox"):
        (config / (name + ".json")).write_text(name)
    return store, folder, config


def test_reset_verified_backup_preserves_campaigns_and_external_sources(tmp_path):
    store, folder, config = fixture(tmp_path)
    original = tmp_path / "TUTUCO-TV/02_VODS/real.mp4"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"keep")
    destination = backup(store.root, tmp_path / "backup")
    reset(store.root, destination, ["TEST_1"])
    assert not store.rows("SELECT * FROM vods") and not folder.exists()
    assert original.read_bytes() == b"keep"
    assert len(list(config.glob("*.json"))) == 3
    with sqlite3.connect(destination / "history.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM vods").fetchone()[0] == 1


def test_changed_or_unverified_data_is_never_deleted(tmp_path):
    store, folder, _ = fixture(tmp_path)
    destination = backup(store.root, tmp_path / "backup")
    (folder / "preview.mp4").write_bytes(b"changed")
    with pytest.raises(ValueError, match="validado"):
        reset(store.root, destination, ["TEST_1"])
    assert folder.exists() and store.get_vod("TEST_1")


def test_reset_rejects_new_records_and_external_test_source(tmp_path):
    store, _, _ = fixture(tmp_path)
    destination = backup(store.root, tmp_path / "backup")
    external = tmp_path / "real.mp4"
    external.write_bytes(b"keep")
    with pytest.raises(ValueError, match="imports"):
        reset(store.root, destination, ["TEST_1"], [str(external)])
    store.execute("INSERT INTO jobs(id,vod_id,kind,state) VALUES('j','TEST_1','test','CONCLUÍDO')")
    with pytest.raises(ValueError, match="mudou"):
        reset(store.root, destination, ["TEST_1"])
