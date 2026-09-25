from pathlib import Path

import pytest

from app import ROOT
from miner import media, range_download
from miner.service import Service


def test_any_dl_public_range_arguments_and_quality(monkeypatch):
    monkeypatch.setattr(range_download, "any_command", lambda: ["node", "any-dl.js"])
    cmd = range_download.command(ROOT, "https://kick.com/brkk/videos/1234-abcd", "raw.mp4", 22662.25, 22720.5)
    assert cmd[:2] == ["node", "any-dl.js"]
    assert cmd[cmd.index("--from") + 1] == "22662.250"
    assert cmd[cmd.index("--to") + 1] == "22720.500"
    assert cmd[cmd.index("--quality") + 1] == "1080p60"


def test_ytdlp_ranges_use_venv_and_strict_quality():
    cmd = range_download.command(ROOT, "https://youtu.be/abcdefghijk", "raw.mp4", 21600, 21630)
    assert Path(cmd[0]).resolve() == (ROOT / ".venv/Scripts/python.exe").resolve()
    assert cmd[1:3] == ["-m", "yt_dlp"]
    assert cmd[cmd.index("--download-sections") + 1] == "*21600.000-21630.000"
    assert "--force-keyframes-at-cuts" in cmd
    assert "[height=1080][fps>=59]" in cmd[cmd.index("--format") + 1]


@pytest.mark.parametrize("height,fps", [(720, 60), (1080, 30)])
def test_never_labels_missing_1080p60_as_high_quality(tmp_path, monkeypatch, height, fps):
    class Process:
        def __init__(self, args, **kwargs):
            assert kwargs["shell"] is False and kwargs["env"] is None
        def wait(self, **kwargs):
            return 0
        def poll(self):
            return 0
    monkeypatch.setattr(range_download, "command", lambda *a: ["any-dl"])
    monkeypatch.setattr(range_download.subprocess, "Popen", Process)
    monkeypatch.setattr(media, "probe", lambda *a: {"height": height, "fps": fps, "duration": 30})
    target = tmp_path / "raw.mp4"
    with pytest.raises(ValueError, match="1080p60"):
        range_download.obtain(ROOT, "https://kick.com/brkk/videos/1234-abcd", target, 100, 130, lambda *a: None)
    assert not target.exists()


def test_local_fallback_preserves_absolute_bounds_and_approval(tmp_path, monkeypatch):
    service = Service(ROOT, tmp_path / "data")
    source = tmp_path / "proxy.mp4"
    source.write_bytes(b"original")
    monkeypatch.setattr(media, "probe", lambda *a: {"duration": 43200, "width": 1280, "height": 720, "has_audio": True})
    requests = []
    def unavailable(root, url, target, start, end, progress):
        requests.append((start, end))
        raise ValueError("1080p60 ausente")
    def clip(source, target, start, end, **kwargs):
        requests.append((start, end))
        Path(target).write_bytes(b"raw-local")
    monkeypatch.setattr(range_download, "obtain", unavailable)
    monkeypatch.setattr(media, "clip", clip)
    try:
        vid = service.import_local("brkk", str(source))["vod"]["id"]
        service.store.execute("INSERT INTO candidates(id,vod_id,start,end,score,status,data) VALUES('c',?,22662,22700,80,'NOVO','{}')", (vid,))
        remote = {"url": "https://kick.com/brkk/videos/1234-abcd", "aligned": True}
        with pytest.raises(ValueError, match="Aprove"):
            service.export(vid, ["c"], "raw", 5, 5, lambda *a: None, remote)
        service.store.execute("UPDATE candidates SET status='APROVADO' WHERE id='c'")
        message = service.export(vid, ["c"], "raw", 5, 5, lambda *a: None, remote)
        assert "Fallback local" in message and "1080p60 ausente" in message
        assert requests == [(22657, 22705), (22657, 22705)]
        row = service.store.rows("SELECT * FROM exports")[0]
        assert (row["start"], row["end"]) == (22657, 22705)
        assert source.read_bytes() == b"original"
    finally:
        service.executor.shutdown(wait=True)
