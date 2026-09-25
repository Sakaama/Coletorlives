"""Create the official TUTUCO_CLIP_MINER_HANDOFF.zip archive.

Follows strict handoff requirements:
- Excludes .venv, .git, __pycache__, caches, node_modules, models, backups, test-results
- Excludes large media (VODs, RAW mp4s, preview mp4s, partial audio)
- Includes source code, UI, configs, tests, docs, SQLite database, candidate metadata,
  Whisper transcripts and Fast Scan checkpoints.
- Adds LEIA-ME-ENTREGA.md and .env.example at the archive root.
"""
import hashlib
import os
from pathlib import Path
import time
import zipfile

PROJECT_ROOT = Path("D:/Projetos/TUTUCO-CLIP-MINER").resolve()
OUTPUT_ZIP = Path("C:/Users/Administrador/Desktop/TUTUCO_CLIP_MINER_HANDOFF.zip")

EXCLUDE_DIRS = {
    ".venv", ".git", "__pycache__", ".pytest_cache", ".ruff_cache",
    "node_modules", "models", "backups", "test-results"
}

MEDIA_EXTS = {".mp4", ".wav", ".m4a", ".mkv", ".ts", ".aac", ".mp3", ".webm"}


def should_exclude(rel_path: Path) -> bool:
    parts = rel_path.parts
    # Root level or nested excluded directory
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
        if part.endswith(".egg-info"):
            return True

    name = rel_path.name
    # Lock files and partial temporary artifacts
    if name == ".instance.lock" or ".partial-" in name or name.startswith(".partial"):
        return True
    if name.endswith(".pyc"):
        return True

    # Temporary / cache media folders inside data/
    if len(parts) >= 2 and parts[0] == "data":
        if parts[1] in ("remote_tmp", "preview_cache", "test_kick"):
            return True
        # Exclude raw audio/video files in campaigns (keep JSON/TXT checkpoints)
        if name.endswith(tuple(MEDIA_EXTS)):
            return True

    # Exclude full VODs and raw media inside TUTUCO-TV
    if len(parts) >= 2 and parts[0] == "TUTUCO-TV":
        if parts[1] in ("02_VODS", "04_RAW") and name.endswith(tuple(MEDIA_EXTS)):
            return True

    return False


def main():
    print(f"Creating handoff package from: {PROJECT_ROOT}")
    print(f"Destination: {OUTPUT_ZIP}")
    start_time = time.time()

    # Ensure parent directory exists
    OUTPUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    files_added = 0
    total_uncompressed = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
            # Prune excluded directories in-place
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

            for fname in filenames:
                full_path = Path(dirpath) / fname
                rel_path = full_path.relative_to(PROJECT_ROOT)

                if should_exclude(rel_path):
                    continue

                arcname = str(rel_path).replace("\\", "/")
                file_size = full_path.stat().st_size
                zf.write(full_path, arcname=arcname)

                files_added += 1
                total_uncompressed += file_size

                if files_added % 1000 == 0:
                    print(f"  ... packed {files_added} files ({total_uncompressed / (1024*1024):.1f} MB uncompressed)")

        # Also add structure placeholder entries for expected empty media directories
        placeholder_dirs = [
            "data/remote_tmp",
            "data/preview_cache",
            "TUTUCO-TV/02_VODS/GABEPEIXE",
            "TUTUCO-TV/04_RAW/GABEPEIXE",
        ]
        for pdir in placeholder_dirs:
            zf.writestr(f"{pdir}/.gitkeep", "")

    duration = time.time() - start_time
    zip_size = OUTPUT_ZIP.stat().st_size

    # Compute SHA-256 hash of the generated zip
    sha256 = hashlib.sha256()
    with open(OUTPUT_ZIP, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha256.update(chunk)
    zip_hash = sha256.hexdigest()

    print("\n--- HANDOFF PACKAGE CREATION COMPLETE ---")
    print(f"Total files added: {files_added} files")
    print(f"Uncompressed size: {total_uncompressed / (1024*1024):.2f} MB")
    print(f"ZIP file path: {OUTPUT_ZIP}")
    print(f"ZIP file size: {zip_size / (1024*1024):.2f} MB ({zip_size} bytes)")
    print(f"SHA-256: {zip_hash}")
    print(f"Time taken: {duration:.2f}s")


if __name__ == "__main__":
    main()
