"""Invoke the installed yt-dlp CLI using the project's venv, like iniciar.bat."""

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

LOG = logging.getLogger(__name__)


def extract_info(root, url, download=False, folder=None, progress=None):
    root = Path(root).resolve()
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        raise ValueError("Python do .venv não encontrado. Execute iniciar.bat para preparar o ambiente.")
    args = [str(python), "-m", "yt_dlp"]
    if download:
        if folder is None:
            raise ValueError("Diretório de download não informado.")
        args += [
            "--no-simulate",
            "--format",
            "bv*+ba/b",
            "--output",
            str(Path(folder).resolve() / "source.%(ext)s"),
            "--merge-output-format",
            "mkv",
            "--continue",
            "--no-overwrites",
            "--retries",
            "3",
            "--newline",
            "--progress",
            "--progress-template",
            "download:TUTUCO:%(progress._percent_str)s",
        ]
    else:
        args += ["--skip-download", "--dump-single-json", "--ignore-no-formats-error", "--retries", "2"]
    args += ["--no-playlist", "--socket-timeout", "30", "--js-runtimes", "node", "--", url]
    # No shell, activation script, PATH/proxy mutation, privilege changes or custom networking.
    # CLI config discovery and the inherited environment match a manual -m yt_dlp invocation.
    LOG.info(
        "yt-dlp CLI: python=%s cwd=%s env=herdado PATH/proxy=inalterados download=%s", python, root, download
    )
    info = None
    with tempfile.TemporaryFile(mode="w+b") as errors:
        process = subprocess.Popen(
            args,
            cwd=str(root),
            env=None,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            for line in process.stdout:
                if not download and line.lstrip().startswith("{"):
                    info = json.loads(line)
                elif download and progress:
                    match = re.search(r"TUTUCO:\s*(\d+(?:\.\d+)?)%", line)
                    if match:
                        progress(min(95, float(match[1])), "Baixando VOD…")
            code = process.wait()
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                process.wait()
        errors.seek(0, 2)
        errors.seek(max(0, errors.tell() - 16000))
        diagnostic = errors.read().decode("utf-8", errors="replace").strip()
    if diagnostic:
        LOG.warning("yt-dlp: %s", diagnostic)
    if code:
        raise ValueError(diagnostic or f"yt-dlp terminou com código {code}.")
    if not download and not isinstance(info, dict):
        raise ValueError("yt-dlp não retornou metadados JSON válidos.")
    return info


def discovery_args(python, url, limit):
    """Bounded metadata-only listing, independent of user download settings."""
    return [python, "-m", "yt_dlp", "--ignore-config", "--flat-playlist",
            "--skip-download", "--dump-single-json", "--playlist-end", str(limit),
            "--socket-timeout", "30", "--retries", "2", "--", url]
