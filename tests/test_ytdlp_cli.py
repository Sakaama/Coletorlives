import io
import os
import subprocess

import pytest

from app import ROOT
from miner import ytdlp_cli
from miner.errors import present_job


@pytest.mark.parametrize("download", [False, True])
def test_cli_uses_project_venv_cwd_and_unchanged_environment(tmp_path, monkeypatch, download):
    root = tmp_path / "Projeto com espaços"
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "fixture-original-path")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("NO_PROXY", "localhost")
    before = dict(os.environ)
    calls, updates = [], []

    class Process:
        def __init__(self, args, **kwargs):
            calls.append((args, kwargs))
            self.stdout = io.StringIO("TUTUCO: 45.2%\n" if download else '{"title":"Live","duration":123}\n')

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(ytdlp_cli.subprocess, "Popen", Process)
    url = "https://kick.com/brabox/videos/example?test=a&b=c"
    result = ytdlp_cli.extract_info(
        root, url, download=download, folder=root / "vods", progress=lambda *a: updates.append(a)
    )
    args, kwargs = calls[0]
    assert args[:3] == [str(python), "-m", "yt_dlp"]
    assert args[-2:] == ["--", url]
    assert kwargs["cwd"] == str(root)
    assert kwargs["env"] is None and kwargs["shell"] is False
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["creationflags"] == (subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert os.environ == before
    assert not set(args) & {"--proxy", "--impersonate", "--ignore-config", "--no-check-certificates"}
    if download:
        assert "--no-overwrites" in args and "--continue" in args
        assert "--no-simulate" in args and "--skip-download" not in args
        assert updates == [(45.2, "Baixando VOD…")]
    else:
        assert "--skip-download" in args and "--dump-single-json" in args
        assert result == {"title": "Live", "duration": 123}


@pytest.mark.parametrize("error", ["HTTP Error 404: Not Found", "WinError 10013"])
def test_cli_keeps_error_identity_for_existing_404_handler(monkeypatch, error):
    class Process:
        def __init__(self, args, **kwargs):
            self.stdout = io.StringIO("")
            kwargs["stderr"].write(f"ERROR: [kick:vod] fixture: {error}".encode())

        def wait(self):
            return 1

        def poll(self):
            return 1

    monkeypatch.setattr(ytdlp_cli.subprocess, "Popen", Process)
    with pytest.raises(ValueError) as exc:
        ytdlp_cli.extract_info(ROOT, "https://kick.com/brabox/videos/fixture")
    assert error in str(exc.value)
    job = present_job({"state": "ERRO", "message": str(exc.value)})
    assert (job.get("fallback") == "import_local") == ("404" in error)


def test_missing_venv_does_not_fall_back_to_system_python(tmp_path):
    with pytest.raises(ValueError, match="Python do .venv"):
        ytdlp_cli.extract_info(tmp_path, "https://kick.com/brabox/videos/fixture")


def test_real_venv_module_can_start():
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    result = subprocess.run(
        [str(python), "-m", "yt_dlp", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    from yt_dlp.version import __version__

    assert result.stdout.strip() == __version__
