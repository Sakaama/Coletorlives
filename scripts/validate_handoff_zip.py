"""Validate the integrity and completeness of the TUTUCO_CLIP_MINER_HANDOFF.zip package."""
from pathlib import Path
import sqlite3
import tempfile
import zipfile

ZIP_PATH = Path("C:/Users/Administrador/Desktop/TUTUCO_CLIP_MINER_HANDOFF.zip")

ESSENTIAL_FILES = [
    "LEIA-ME-ENTREGA.md",
    ".env.example",
    "app.py",
    "iniciar.bat",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-lock.txt",
    "pyproject.toml",
    "README.md",
    "EDITORIAL.md",
    "TESTES.md",
    "miner/backlog.py",
    "miner/collector.py",
    "miner/editorial.py",
    "miner/store.py",
    "miner/remote_provider.py",
    "miner/remote_analysis.py",
    "miner/analysis.py",
    "miner/media.py",
    "config/campaigns/gabepeixe.json",
    "data/history.sqlite3",
    "static/app.js",
    "static/remote.js",
    "templates/index.html",
    "tests/test_backlog.py",
    "tests/test_editorial.py",
]

FORBIDDEN_PATTERNS = [
    ".venv/", ".git/", "__pycache__/", ".pytest_cache/", ".ruff_cache/",
    "models/", "backups/", "test-results/", ".mp4", ".wav"
]


def validate():
    print("--- VALIDATING HANDOFF PACKAGE ---")
    print(f"Target: {ZIP_PATH}")
    assert ZIP_PATH.exists(), f"ZIP file not found at {ZIP_PATH}"

    # 1. Test zip integrity (CRC check)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        print("Testing ZIP archive integrity (CRC-32 of all files)...")
        bad_file = zf.testzip()
        assert bad_file is None, f"Corrupted file in ZIP: {bad_file}"
        print("  Archive integrity check PASSED (0 corrupted files).")

        namelist = set(zf.namelist())
        print(f"Total entries in ZIP: {len(namelist)}")

        # 2. Check essential files
        print("\nChecking essential files presence...")
        missing = [f for f in ESSENTIAL_FILES if f not in namelist]
        if missing:
            raise AssertionError(f"Missing essential files in ZIP: {missing}")
        print(f"  All {len(ESSENTIAL_FILES)} essential files are PRESENT in ZIP.")

        # 3. Check checkpoints for interrupted VOD (2026-09-12)
        print("\nChecking Fast Scan checkpoints for 2026-09-12 VOD...")
        checkpoint_files = [
            n for n in namelist 
            if "GABEPEIXE_2026-09-23_56025e66df" in n and "scan_" in n
        ]
        print(f"  Found {len(checkpoint_files)} checkpoint files for 2026-09-12 VOD in ZIP.")
        assert len(checkpoint_files) > 100, "Expected >100 checkpoint files for 2026-09-12"

        # 4. Check forbidden files
        print("\nVerifying absence of forbidden files/caches/media...")
        violations = []
        for name in namelist:
            for pat in FORBIDDEN_PATTERNS:
                if pat in name or name.endswith(pat):
                    violations.append((name, pat))
        if violations:
            raise AssertionError(f"Found forbidden files in ZIP: {violations[:10]}")
        print("  No forbidden patterns found in ZIP.")

        # 5. Extract and test SQLite integrity
        print("\nValidating SQLite database extracted from ZIP...")
        with tempfile.TemporaryDirectory() as tmpdir:
            extracted_db = zf.extract("data/history.sqlite3", path=tmpdir)
            conn = sqlite3.connect(extracted_db)
            cur = conn.cursor()

            # PRAGMA integrity_check
            cur.execute("PRAGMA integrity_check;")
            integrity_result = cur.fetchall()
            print(f"  PRAGMA integrity_check result: {integrity_result}")
            assert integrity_result == [("ok",)], f"Integrity check failed: {integrity_result}"

            # Query row counts
            cur.execute("SELECT count(*) FROM vods WHERE campaign='gabepeixe';")
            gabe_vods = cur.fetchone()[0]
            print(f"  GabePeixe VODs in database: {gabe_vods}")
            assert gabe_vods == 18, f"Expected 18 GabePeixe VODs, got {gabe_vods}"

            cur.execute("""
                SELECT count(*) 
                FROM candidates c 
                JOIN vods v ON c.vod_id = v.id 
                WHERE v.campaign = 'gabepeixe';
            """)
            gabe_cands = cur.fetchone()[0]
            print(f"  GabePeixe candidates in database: {gabe_cands}")
            assert gabe_cands == 307, f"Expected 307 GabePeixe candidates, got {gabe_cands}"

            cur.execute("SELECT count(*) FROM candidates;")
            total_cands = cur.fetchone()[0]
            print(f"  Total candidates across all campaigns: {total_cands}")
            assert total_cands == 436, f"Expected 436 candidates, got {total_cands}"

            # Check official campaign existence
            cur.execute("SELECT id FROM remote_campaigns WHERE id='2137c0d0e8d54b67';")
            official = cur.fetchone()
            assert official is not None, "Official campaign 2137c0d0e8d54b67 missing!"
            print("  Official campaign 2137c0d0e8d54b67 verified.")

            conn.close()

    print("\n--- ALL VALIDATIONS PASSED SUCCESSFULLY ---")


if __name__ == "__main__":
    validate()
