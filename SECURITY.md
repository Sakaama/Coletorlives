# Security Policy & Audit Notice — TUTUCO CLIP MINER

## 1. Security Advisory & Credential Rotation Notice

> [!CAUTION]
> **AVISO DE SEGURANÇA E ROTAÇÃO DE CREDENCIAIS:**
> Uma credencial hardcoded histórica foi removida e deve ser considerada comprometida.
> 
> **Ações adotadas no repositório canônico unificado:**
> 1. A credencial hardcoded histórica foi **completamente removida** de todo o código-fonte, configurações e documentação.
> 2. O motor de autenticação (`miner/auth.py`) não possui senhas padrão embutidas e adota política de *fail-closed* caso `AUTH_REQUIRED=true` sem que um administrador seguro seja fornecido via ambiente.
> 3. Senhas são fornecidas exclusivamente via variáveis de ambiente (`ADMIN_PASSWORD`, `EDITOR_PASSWORD`, `VIEWER_PASSWORD`) e armazenadas com hash seguro PBKDF2/scrypt (`werkzeug.security`).
> 4. **Caso qualquer ambiente legado, projeto GCP ou deployment tenha utilizado a credencial histórica do projeto paralelo, os administradores devem rotacionar credenciais e chaves imediatamente.**

---

## 2. Cloud Storage Security: Private Buckets & Signed URLs

In historical iterations, Google Cloud Storage objects were marked public using `blob.make_public()`.

In **TUTUCO CLIP MINER**:
- `blob.make_public()` is **STRICTLY FORBIDDEN**.
- Buckets are maintained as private resources.
- Media assets and edited clips are served via **time-limited Signed URLs** (V4 signing, expiring in 60 minutes) or through authenticated application proxies.
- In local mode, files are served via internal streaming endpoints (`/media/edited/`) with path traversal guards (`os.path.commonpath` / `Path.resolve()` boundary checks).

---

## 3. Webhook Authentication (`/api/webhook/radar`)

External radar triggers (monitoring Twitch, YouTube, and Kick lives) must authenticate against the mining server:
- Calls to `POST /api/webhook/radar` require a valid secret token.
- Supported authentication mechanisms:
  - Header: `X-Radar-Secret: <secret>`
  - Header: `Authorization: Bearer <secret>`
  - Query parameter: `?token=<secret>`
- Secret validation uses **constant-time string comparison** (`secrets.compare_digest`) to prevent timing side-channel attacks.
- If authentication is required and no secret is provided, the endpoint returns `401 Unauthorized`.

---

## 4. Role-based Access Control (RBAC)

The system supports 3 explicit hierarchical roles:

| Role | Hierarchy Level | Capabilities |
|---|---|---|
| **Admin** | Level 30 | Full access to pipeline, mining engine, backlog runner, configuration, user management, and exports. |
| **Editor** | Level 20 | Access to candidate curation, approving/discarding, uploading final edited videos, generating captions, and publishing to Telegram. |
| **Viewer** | Level 10 | Read-only access to view candidates, campaigns, public previews, and compliance packages. |

---

## 5. Local Developer Mode vs Cloud Enforcement

- **Local Mode (`AUTH_REQUIRED=false`, default):** Designed for zero-friction local desktop usage and CLI execution on Windows/macOS/Linux. Requests originating from localhost (`127.0.0.1`, `::1`) are assigned `Admin` access with CSRF token verification.
- **Production / Cloud Mode (`AUTH_REQUIRED=true`):** Enforces strict session cookie or API token authentication for all mutating actions.

---

## 6. Reporting a Vulnerability

To report a vulnerability or security issue:
1. Please do **NOT** open a public issue on GitHub.
2. Email the core development team or open a private security advisory on GitHub.
3. Include detailed steps to reproduce, affected endpoints, and suggested remediation.
