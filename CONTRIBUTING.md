# Contributing to TUTUCO CLIP MINER

Thank you for your interest in contributing to **TUTUCO CLIP MINER**!  
This document outlines our development process, architectural guidelines, testing practices, and branch strategy.

---

## 1. Branch Strategy

We use a structured Git workflow to protect stability:

- **`main`**: Production-ready branch. Only merges from `develop` via Pull Request with all tests passing.
- **`develop`**: Primary integration branch for active development.
- **`feature/<feature-name>`**: New capabilities and enhancements. Branched from `develop`.
- **`fix/<bug-name>`**: Targeted bug fixes. Branched from `develop` (or `main` for critical hotfixes).

All Pull Requests must:
1. Pass the complete test suite (both Python and Node.js).
2. Adhere to coding and linting standards.
3. Contain zero secrets, API keys, or database files.

---

## 2. Environment Setup

### Prerequisites
- **Python:** 3.11 or 3.12
- **Node.js:** v20 or later (for frontend tests)
- **FFmpeg & FFprobe:** Installed and available in system `PATH`
- **Git**

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/tutuco-clip-miner.git
cd tutuco-clip-miner

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest ruff
```

---

## 3. Running the Application Locally

```bash
# Windows / Direct python
python app.py

# Without automatic browser launch:
python app.py --no-browser

# With container / Docker Compose:
docker-compose up --build
```

The application runs at `http://127.0.0.1:8765`.

---

## 4. Running Verification and Tests

Always ensure both test suites pass before submitting changes:

```bash
# Run Python unit & integration tests
pytest

# Run frontend / Node.js headless tests
node --test tests/*.cjs

# Syntax & Linting checks
node --check static/product.js
ruff check .
```

---

## 5. Architectural Principles

1. **Canonical Engine Protection:**
   The heuristic mining engine (`Fast Scan`, `Whisper` extraction, and candidate deduplication) is the core intellectual property. Modifications must benchmark against existing baseline tests.
2. **Local-First Resilience:**
   The application must always function 100% offline without cloud credentials, using SQLite (`data/history.sqlite3`) and local file storage.
3. **Product State vs Local Processing State:**
   - **Product State** (candidates, VOD metadata, campaign configs, editorial reviews) can be synchronized to Cloud Firestore when configured.
   - **Local Processing State** (temporary chunks, FFmpeg jobs, queues) must remain local.
4. **Security by Default:**
   - Never store plain text passwords.
   - Never use `blob.make_public()` on Cloud Storage; always use signed URLs.
   - Protect modifying webhooks with secret tokens.
   - Never commit `.env`, credentials JSON, or database files.
