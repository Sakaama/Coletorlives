import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def load_campaigns(directory):
    result = {}
    for path in Path(directory).glob("*.json"):
        campaign = json.loads(path.read_text(encoding="utf-8"))
        if not re.fullmatch(r"[a-z0-9_-]+", campaign["id"]):
            raise ValueError("ID de campanha inválido.")
        result[campaign["id"]] = campaign
    return result


def validate_url(url):
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.port:
        raise ValueError("Use uma URL HTTPS de VOD do YouTube, Kick ou Twitch.")
    host = (parsed.hostname or "").lower()
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"):
        if "youtu.be" in host:
            video = parsed.path.strip("/")
        elif parsed.path in ("/watch", "/watch/"):
            video = parse_qs(parsed.query).get("v", [""])[0]
        else:
            match = re.fullmatch(r"/(?:live|shorts|embed)/([A-Za-z0-9_-]{11})/?", parsed.path)
            video = match[1] if match else ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
            raise ValueError("Informe o link de um vídeo, não de um canal ou playlist.")
        return "YouTube", f"https://www.youtube.com/watch?v={video}"
    if host in ("kick.com", "www.kick.com"):
        if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)?videos/[A-Za-z0-9-]+/?", parsed.path):
            raise ValueError("Informe a URL da VOD da Kick (…/videos/ID), não a live ao vivo.")
        return "Kick", "https://kick.com" + parsed.path.rstrip("/")
    if host in ("twitch.tv", "www.twitch.tv", "m.twitch.tv"):
        match = re.fullmatch(r"/videos/([0-9]+)/?", parsed.path)
        if not match:
            raise ValueError("Informe a gravação da Twitch (…/videos/ID), não um canal ou clip.")
        return "Twitch", f"https://www.twitch.tv/videos/{match[1]}"
    raise ValueError("A V1 aceita URLs de VOD do YouTube, Kick e Twitch, ou arquivo local.")


def eligibility(campaign, metadata):
    blocked, review = [], []
    platform = metadata.get("platform")
    if platform == "Local":
        review.append("Arquivo local: confirmar plataforma e origem manualmente.")
    elif platform not in campaign["allowed_sources"]:
        blocked.append("Fonte não permitida nesta campanha.")
    disputed = campaign.get("date_disputed", False)
    if disputed:
        review.append(campaign["date_dispute_note"])
    published = metadata.get("date")
    if published:
        try:
            actual = date.fromisoformat(published)
            outside = (campaign["min_date"] is not None and actual < date.fromisoformat(campaign["min_date"])) or (
                campaign.get("max_date") and actual > date.fromisoformat(campaign["max_date"])
            )
            if outside:
                if disputed:
                    review.append(
                        "Data fora do período informado na página; divergência exige revisão humana."
                    )
                elif metadata.get("date_kind") in ("live", "human"):
                    blocked.append("Data da live fora do período da campanha.")
                else:
                    review.append("Data de upload fora do período; confirmar data da live original.")
        except ValueError:
            review.append("Data inválida; conferir manualmente.")
    else:
        review.append("Data da live não disponível.")
    if campaign["min_date"] is None:
        review.append("Data mínima da campanha não informada; confirmar período com revisão humana.")
    if metadata.get("date_kind") not in ("live", "human"):
        review.append("A data de upload não comprova a data da live.")
    # Promotional text is not evidence of ownership/content. Only an exact excluded
    # source identity can establish this source restriction; never title/description.
    channel = str(metadata.get("channel") or "").strip().lstrip("@").casefold()
    if channel and channel in {term.casefold() for term in campaign.get("excluded_terms", [])}:
        blocked.append("Canal de origem identificado como fonte excluída pela campanha.")
    if metadata.get("channel_id") not in campaign.get("verified_channel_ids", []):
        review.append("Identidade do canal não verificada; conferir se a live é do streamer correto.")
    if not metadata.get("was_live"):
        review.append("Metadados não comprovam que o vídeo é uma live gravada.")
    if campaign.get("original_lives_only"):
        if metadata.get("was_live") is False or metadata.get("content_type") in campaign.get(
            "excluded_content_types", []
        ):
            blocked.append(
                "A campanha aceita somente lives originais; conteúdo identificado como não-live ou editado não é permitido."
            )
        review.append(
            campaign.get("original_live_review") or
            f"Conferir se é live ORIGINAL do {campaign.get('streamer', 'criador')} nas fontes oficiais, sem edição prévia nem origem em outras contas de cortes."
        )
    return {
        "status": "NÃO PERMITIDA" if blocked else "REVISÃO HUMANA" if review else "PERMITIDA",
        "reasons": blocked + review,
    }


def candidate_eligibility(text):
    """Textual indications request review of this excerpt, never classify its images."""
    normalized = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
    pattern = (r"\b(?:assistindo|assistir|passando|exibindo)\s+(?:(?:a|ao|o|um|uma|essa|esse|esta|este)\s+){0,2}"
               r"(?:filme|serie|episodio)\b|\bcena\s+(?:do|da|de um|de uma)\s+(?:filme|serie)\b|"
               r"\btransmissao\s+(?:protegida|pirata|sem autorizacao)\b")
    match = re.search(pattern, normalized)
    if not match:
        return {}
    return {"status": "REVISÃO DE ELEGIBILIDADE", "reasons": [
        f'Indício textual no trecho: "{match[0]}". Conferir possível conteúdo protegido no Preview; não comprova infração nem bloqueia a VOD.'
    ]}
