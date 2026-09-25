"""Explicit-ID operational reset; no source/configuration discovery or blanket delete."""
import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path

from miner.analysis import save_json
from miner.store import Store


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup(data, destination):
    data, destination = Path(data).resolve(), Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(data):
        raise ValueError("Backup deve ser novo e externo ao diretório operacional.")
    destination.mkdir(parents=True)
    with sqlite3.connect(data / "history.sqlite3") as src, sqlite3.connect(destination / "history.sqlite3") as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup SQLite inválido.")
    manifest = {}
    for source in data.rglob("*"):
        if source.is_symlink() or (hasattr(source, "is_junction") and source.is_junction()):
            raise ValueError("Link/junction inesperado nos dados; backup interrompido.")
        if not source.is_file() or source.name in ("history.sqlite3", "history.sqlite3-wal", "history.sqlite3-shm", ".instance.lock"):
            continue
        relative = source.relative_to(data)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        checksum = digest(source)
        if digest(target) != checksum:
            raise ValueError("Cópia não confere: " + str(relative))
        manifest[str(relative)] = checksum
    manifest["history.sqlite3"] = digest(destination / "history.sqlite3")
    save_json(destination / "manifest.json", manifest)
    return destination


def reset(data, destination, ids, test_sources=()):
    data, destination = Path(data).resolve(), Path(destination).resolve()
    store = Store(data)
    if store.rows("SELECT id FROM jobs WHERE state IN ('FILA','EXECUTANDO')"):
        raise ValueError("Há tarefas ativas; encerre o aplicativo antes do reset.")
    vods = [store.get_vod(vid) for vid in ids]
    if any(not re.fullmatch(r"[\w-]+", str(v[k])) for v in vods for k in ("id", "campaign")):
        raise ValueError("Identificador operacional inseguro.")
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    if digest(destination / "history.sqlite3") != manifest["history.sqlite3"]:
        raise ValueError("Backup alterado; reset recusado.")
    with sqlite3.connect(destination / "history.sqlite3") as db, store.connect() as current:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup inválido.")
        for table in ("vods", "candidates", "jobs", "exports"):
            if db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() != [tuple(r) for r in current.execute(f"SELECT * FROM {table} ORDER BY rowid")]:
                raise ValueError("Banco mudou desde o backup; crie outro backup.")
    targets = []
    for vod in vods:
        for kind in ("vods", "transcripts", "candidates", "raw", "prep"):
            path = data / "campaigns" / vod["campaign"] / kind / vod["id"]
            resolved = path.resolve()
            if not resolved.is_relative_to(data / "campaigns") or path.is_symlink() or path.is_junction():
                raise ValueError("Diretório fora do escopo seguro.")
            targets.append(resolved)
    for name in test_sources:
        path = Path(name).resolve()
        if not path.is_file() or not path.is_relative_to(data / "imports"):
            raise ValueError("Só imports explicitamente identificados como teste podem ser removidos.")
        targets.append(path)
    for target in targets:
        files = target.rglob("*") if target.is_dir() else [target]
        for file in files:
            if file.is_symlink() or file.is_junction():
                raise ValueError("Link inesperado; reset recusado.")
            if file.is_file():
                key = str(file.relative_to(data))
                if key not in manifest or digest(file) != manifest[key] or digest(destination / key) != manifest[key]:
                    raise ValueError("Arquivo não validado no backup: " + key)
    # All targets are resolved and all copies verified before the first mutation.
    with store.connect() as db:
        for vid in ids:
            for table in ("exports", "jobs", "candidates"):
                db.execute(f"DELETE FROM {table} WHERE vod_id=?", (vid,))
            db.execute("DELETE FROM vods WHERE id=?", (vid,))
    for target in targets:
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()
    save_json(destination / "reset.json", {"ids": list(ids), "removed": [str(p) for p in targets],
                                         "external_originals_preserved": [v.get("local_path") for v in vods if v.get("local_path") not in test_sources]})
