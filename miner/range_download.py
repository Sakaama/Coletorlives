"""Use installed public CLIs; never implement platform access or stream fetching."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from miner import media
from miner.rules import validate_url


def any_command():
    executable = shutil.which("any-dl")
    if not executable:
        raise ValueError("any-dl não está instalado; use arquivo local.")
    if os.name == "nt":
        entry = Path(executable).parent / "node_modules/any-dl/bin/any-dl.js"
        node = shutil.which("node")
        if not entry.is_file() or not node:
            raise ValueError("Instalação npm do any-dl não localizada; use arquivo local.")
        return [node, str(entry)]
    return [executable]


def command(root, url, target, start, end):
    platform, url = validate_url(url)
    if not 0 <= start < end:
        raise ValueError("Intervalo remoto inválido.")
    if platform in ("Kick", "Twitch"):
        return [*any_command(), url, "--quality", "1080p60", "--from", f"{start:.3f}",
                "--to", f"{end:.3f}", "--output", str(target), "--yes", "--progress", "none"]
    python = Path(root) / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return [str(python), "-m", "yt_dlp", "--no-playlist", "--format",
            "bv[height=1080][fps>=59]+ba/b[height=1080][fps>=59]",
            "--download-sections", f"*{start:.3f}-{end:.3f}", "--force-keyframes-at-cuts",
            "--merge-output-format", "mp4", "--output", str(target), "--no-overwrites",
            "--socket-timeout", "30", "--retries", "2", "--js-runtimes", "node", "--", url]


def obtain(root, url, target, start, end, progress):
    target = Path(target)
    temporary = target.with_name(target.stem + ".remote.mp4")
    if temporary.exists():
        raise ValueError("Arquivo remoto já existe; tente uma nova extração.")
    args = command(root, url, temporary, start, end)
    begin = time.perf_counter()
    with temporary.with_suffix(".log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(args, cwd=str(root), env=None, shell=False,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                creationflags=media.FLAGS)
        try:
            while True:
                progress(10, f"Obtendo intervalo 1080p60 · {time.perf_counter() - begin:.0f}s")
                try:
                    code = proc.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.perf_counter() - begin > 900:
                        raise ValueError("Tempo excedido no download do intervalo.") from None
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait()
    if code:
        raise ValueError("A ferramenta não entregou 1080p60; veja o log do intervalo. Use o original local.")
    info = media.probe(temporary)
    if info["height"] != 1080 or info.get("fps", 0) < 59:
        raise ValueError("1080p60 não disponível/confirmado. Não foi feito upscale nem interpolação.")
    if abs(info["duration"] - (end - start)) > 10:
        raise ValueError("Duração remota diverge do intervalo pedido; resultado não publicado.")
    # Re-encode only the short downloaded range for CapCut, without inventing detail/fps.
    media.clip(temporary, target, 0, info["duration"], progress=lambda n: progress(20 + n * 0.8, "Preparando RAW 1080p60…"))
    note = "1080p60 confirmado por ffprobe."
    if validate_url(url)[0] in ("Kick", "Twitch"):
        note += " any-dl corta em keyframes; início/fim podem variar alguns segundos. Confira o RAW."
    target.with_suffix(".json").write_text(json.dumps({"requested_start": start, "requested_end": end,
                                                      "actual_media": info, "note": note}, indent=2), encoding="utf-8")
    return note
