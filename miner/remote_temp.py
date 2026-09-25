"""Lease-owned media; cleanup requires a durable checkpoint and never traverses links."""
import hashlib
import json
import shutil
from pathlib import Path

from miner.analysis import save_json


class Temporaries:
    def __init__(self, data):
        self.data = Path(data).resolve()
        self.root = self.data / "remote_tmp"
        self.root.mkdir(exist_ok=True)

    def checked(self, folder):
        folder = Path(folder)
        if self.root.is_symlink() or self.root.is_junction() or folder.is_symlink() or folder.is_junction():
            raise ValueError("Links não são permitidos na área temporária remota.")
        resolved = folder.resolve()
        if resolved.parent != self.root.resolve() or len(resolved.name) != 24:
            raise ValueError("Pasta fora da área temporária gerenciada.")
        return resolved

    def lease(self, vid, start, end, stage, quality):
        identity = [vid, start, end, stage, quality]
        folder = self.root / hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
        folder = self.checked(folder)
        folder.mkdir(exist_ok=True)
        manifest = folder / "lease.json"
        if not manifest.exists():
            save_json(manifest, {"owner": "remote-collector-1", "vod_id": vid, "start": start, "end": end,
                                 "stage": stage, "quality": quality, "state": "NEEDED"})
        return folder

    def commit(self, folder, checkpoint):
        folder = self.checked(folder)
        checkpoint = Path(checkpoint).resolve()
        if not checkpoint.is_file() or not checkpoint.is_relative_to(self.data) or checkpoint.is_relative_to(self.root):
            raise ValueError("Checkpoint persistente obrigatório antes da limpeza.")
        data = json.loads((folder / "lease.json").read_text(encoding="utf-8"))
        data.update(state="DISPOSABLE", checkpoint=str(checkpoint), checksum=hashlib.sha256(checkpoint.read_bytes()).hexdigest())
        save_json(folder / "lease.json", data)
        self.clean(folder)

    def clean(self, folder):
        folder = self.checked(folder)
        manifest = folder / "lease.json"
        if not manifest.exists():
            return False
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("owner") != "remote-collector-1" or data.get("state") != "DISPOSABLE":
            return False
        checkpoint = Path(data["checkpoint"]).resolve()
        if not checkpoint.is_relative_to(self.data) or not checkpoint.is_file() or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != data["checksum"]:
            return False
        if any(p.is_symlink() or p.is_junction() for p in folder.rglob("*")):
            return False
        shutil.rmtree(folder)
        return True

    def cleanup(self):
        for folder in self.root.iterdir():
            if folder.is_dir():
                try:
                    self.clean(folder)
                except (ValueError, OSError, KeyError):
                    continue

    def space(self, seconds, quality="analysis"):
        self.cleanup()
        # Conservative working reserve for source + PCM + encoded result; not a download-size promise.
        required = 512 * 1024**2 + int(seconds * (4_000_000 if quality != "analysis" else 1_000_000))
        if shutil.disk_usage(self.root).free < required:
            raise ValueError(f"Espaço insuficiente para o range: reserve ao menos {required / 1024**3:.1f} GB. Nenhum arquivo do usuário foi removido.")

    def usage(self):
        return sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file() and not p.is_symlink())
