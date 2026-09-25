"""Present known extractor failures without changing their persisted diagnostics."""

import re

KICK_VOD_MESSAGE = (
    "O extrator atual do yt-dlp para VODs da Kick está temporariamente incompatível com a plataforma. "
    "O projeto, os metadados e os arquivos já obtidos foram preservados. "
    "Use Importar arquivo local para vincular uma VOD baixada manualmente e continuar neste mesmo registro."
)


def present_job(job):
    result = dict(job)
    message = job.get("message", "")
    if (
        job.get("state") == "ERRO"
        and re.search(r"\bkick:vod\b", message, re.IGNORECASE)
        and re.search(r"\bHTTP Error 404\b", message, re.IGNORECASE)
    ):
        result.update(message=KICK_VOD_MESSAGE, error_code="kick_vod_incompatible", fallback="import_local")
    return result
