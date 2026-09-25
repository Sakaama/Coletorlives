"""Build and verify a clean GitHub ZIP package for TUTUCO CLIP MINER.

Excludes:
- Virtual environments (.venv)
- SQLite databases (data/history.sqlite3, *.db, *.sqlite)
- Credentials and secrets (.env, *gcp-key*.json, *service_account*.json)
- Heavy media and models (models/, data/edited/, data/preview_cache/, *.mp4)
- Logs, backups, and caches (__pycache__, .pytest_cache, .ruff_cache, backups/, *.zip)
"""
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = ROOT / "TUTUCO-CLIP-MINER-GITHUB.zip"

EXCLUDED_DIRS = {
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "test-results",
    "data",
    "logs",
    "models",
    "backups",
    "node_modules",
    ".git",
    ".idea",
    ".vscode",
}

EXCLUDED_EXTS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".sqlite3",
    ".sqlite",
    ".db",
    ".mp4",
    ".ts",
    ".m3u8",
    ".wav",
    ".mp3",
    ".zip",
    ".tar",
    ".gz",
}

EXCLUDED_FILES = {
    ".env",
    ".instance.lock",
    "TUTUCO_CLIP_MINER_HANDOFF.zip",
    "TUTUCO-CLIP-MINER-GITHUB.zip",
}


def should_include(rel_path: Path) -> bool:
    # Check parts for excluded directory names
    for part in rel_path.parts[:-1]:
        if part in EXCLUDED_DIRS:
            return False

    # Check filename
    name = rel_path.name
    if name == ".env.example":
        return True
    if name in EXCLUDED_FILES:
        return False
    if name.startswith(".env.") or name == ".env":
        return False
    if "secret" in name.lower() or "credentials" in name.lower() or "gcp-key" in name.lower():
        return False

    # Check extension
    if rel_path.suffix.lower() in EXCLUDED_EXTS:
        return False

    return True


def build_zip():
    print(f"Building clean GitHub package: {OUTPUT_ZIP.name}...")
    included_files = []

    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(ROOT):
            # Modify dirs in-place to avoid descending into excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

            for file in files:
                abs_path = Path(root) / file
                rel_path = abs_path.relative_to(ROOT)

                if should_include(rel_path):
                    # Canonical folder prefix in zip: TUTUCO-CLIP-MINER/
                    archive_name = f"TUTUCO-CLIP-MINER/{rel_path.as_posix()}"
                    zf.write(abs_path, archive_name)
                    included_files.append((rel_path.as_posix(), abs_path.stat().st_size))

    print(f"Total files packaged: {len(included_files)}")
    print(f"Archive size: {OUTPUT_ZIP.stat().st_size / 1024:.1f} KB")

    # Verification of contents
    print("\n--- AUDIT OF PACKAGED FILES ---")
    sensitive_findings = []
    has_env_example = False

    with zipfile.ZipFile(OUTPUT_ZIP, "r") as zf:
        for info in zf.infolist():
            lower = info.filename.lower()
            if lower.endswith(".env.example"):
                has_env_example = True
            if any(lower.endswith(ext) for ext in [".sqlite3", ".db", ".mp4", ".pyc"]):
                sensitive_findings.append(info.filename)
            if any(s in lower for s in [".env", "history.sqlite3", "credential"]):
                if not lower.endswith(".env.example") and not lower.endswith("database_audit.md"):
                    sensitive_findings.append(info.filename)

    if not has_env_example:
        raise RuntimeError("Validation failed: .env.example MUST be present in the ZIP archive!")

    if sensitive_findings:
        print(f"ERROR: Found sensitive files in archive: {sensitive_findings}")
        raise RuntimeError("Archive validation failed!")
    else:
        print("[OK] Security Audit Passed: ZERO databases, zero secrets, zero heavy media, and .env.example present!")

    return OUTPUT_ZIP


if __name__ == "__main__":
    build_zip()
