import io
from pathlib import Path
from miner.storage import LocalStorageService, get_storage_service


def test_local_storage_lifecycle(tmp_path):
    storage = LocalStorageService(tmp_path)
    assert not storage.is_cloud

    fake_video = io.BytesIO(b"FAKE_MP4_CONTENT_12345")
    stored = storage.store_file(fake_video, "sample_cut.mp4", content_type="video/mp4")

    assert stored["id"]
    assert stored["filename"] == "sample_cut.mp4"
    assert "access_url" in stored
    assert Path(stored["storage_path"]).is_file()
    assert Path(stored["storage_path"]).read_bytes() == b"FAKE_MP4_CONTENT_12345"

    url = storage.get_access_url(stored["storage_path"])
    assert url.startswith("/media/edited/")

    # Deletion
    deleted = storage.delete_file(stored["storage_path"])
    assert deleted is True
    assert not Path(stored["storage_path"]).exists()


def test_storage_factory_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("BUCKET_NAME", raising=False)

    svc = get_storage_service(tmp_path)
    assert isinstance(svc, LocalStorageService)
    assert not svc.is_cloud
