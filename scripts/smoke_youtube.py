"""Optional small public transport test; never downloads a video longer than a minute."""

import json
from pathlib import Path

import yt_dlp

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "test-results" / "youtube"
folder.mkdir(parents=True, exist_ok=True)
report = {}
try:
    options = {
        "quiet": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 1,
        "js_runtimes": {"node": {}},
        "ignore_no_formats_error": True,
        "format": "bv*[height<=360]+ba/bv*+ba/b",
        "outtmpl": str(folder / "sample.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        data = downloader.extract_info("https://www.youtube.com/watch?v=jNQXAC9IVRw", download=False)
        report = {"title": data.get("title"), "duration": data.get("duration"), "metadata": "passed"}
        assert 0 < (data.get("duration") or 0) <= 60, "Video exceeds test budget"
        downloader.params["ignore_no_formats_error"] = False
        downloader.extract_info("https://www.youtube.com/watch?v=jNQXAC9IVRw", download=True)
        report["download"] = "passed"
except Exception as exc:
    report["error"] = str(exc)
(folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
