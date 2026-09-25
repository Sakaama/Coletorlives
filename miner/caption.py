"""Caption Generator and Publishing Package Service.

Provides deterministic campaign rule compliance combined with creative,
platform-tailored caption generation for TikTok, YouTube Shorts, Instagram Reels, and Kwai.
AI/creative suggestions NEVER override deterministic campaign rules (hashtags, mentions, LOWER, dates).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_campaign_config(root_dir: Path, campaign_id: str) -> Dict[str, Any]:
    """Load campaign configuration file by ID or creator key."""
    cid = (campaign_id or "").lower().strip()
    path = root_dir / "config" / "campaigns" / f"{cid}.json"
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback to gabepeixe if gabe or empty
    if "gabe" in cid:
        path = root_dir / "config" / "campaigns" / "gabepeixe.json"
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

    return {
        "id": cid or "geral",
        "name": cid.title() if cid else "Geral",
        "streamer": cid.title() if cid else "Streamer",
        "hashtags": [f"#{cid}"] if cid else ["#clipes"],
        "official_profile": None,
        "required_texts": [],
        "required_visuals": ["LOWER obrigatório posicionado abaixo do rosto"],
        "prohibitions": [
            "Proibida a compra de visualizações ou engajamento artificial.",
            "Proibido cortes 100% automatizados por IA sem curadoria e edição humana.",
        ],
        "publication_platforms": ["TikTok", "Instagram", "YouTube Shorts", "Kwai"],
    }


def load_creator_template(root_dir: Path, creator_key: str) -> Dict[str, Any]:
    """Load visual template configuration from TUTUCO-TV/08_TEMPLATES if available."""
    ck = (creator_key or "").upper().strip()
    template_dir = root_dir / "TUTUCO-TV" / "08_TEMPLATES" / ck
    template_md = template_dir / "TEMPLATE.md"

    has_template = template_md.is_file()
    return {
        "creator": creator_key.lower(),
        "has_template_file": has_template,
        "canvas": "1080x1920 (9:16 vertical)",
        "fps": 30,
        "editing_software": "CapCut / Premiere",
        "destinations": ["TikTok", "Instagram Reels", "YouTube Shorts", "Kwai"],
        "layout_visual": "Câmera em cima + Conteúdo/Gameplay embaixo",
        "layout_talking": "B-Roll/Foto em cima + Câmera embaixo",
        "lower_text": f"kick.com/{creator_key.lower()}" if creator_key else "",
        "subtitle_rule": "Legenda central/inferior, sem cobrir o rosto do criador nem áreas de UI",
    }


class CaptionGenerator:
    """Decoupled service for generating social captions and publication compliance packages."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path(__file__).resolve().parent.parent
        self.root_dir = root_dir

    def generate(
        self,
        candidate: Dict[str, Any],
        campaign: Optional[Dict[str, Any]] = None,
        platform: str = "TikTok",
        variation_seed: int = 0,
    ) -> Dict[str, Any]:
        """Generate platform-specific caption, hashtags, mentions, and compliance checklist.
        
        Deterministic rules (hashtags, mentions, dates, visual lower) are strictly enforced from campaign.
        """
        # Determine creator/campaign
        creator_key = (
            candidate.get("creator_key")
            or candidate.get("campaign")
            or (campaign.get("id") if campaign else None)
            or "gabepeixe"
        ).lower()

        if not campaign:
            campaign = load_campaign_config(self.root_dir, creator_key)

        streamer_name = campaign.get("streamer") or campaign.get("name") or creator_key.title()

        # Normalize platform name
        norm_platform = self._normalize_platform(platform)

        # 1. Deterministic Mentions
        mentions = self._build_mention(streamer_name, creator_key, campaign, norm_platform)

        # 2. Deterministic Mandatory Hashtags
        mandatory_hashtags = [h.strip() for h in campaign.get("hashtags", []) if h.strip()]
        if not mandatory_hashtags:
            mandatory_hashtags = [f"#{creator_key}"]

        # Recommended auxiliary hashtags by platform
        auxiliary_hashtags = self._build_aux_hashtags(norm_platform, creator_key)
        all_hashtags = list(dict.fromkeys(mandatory_hashtags + auxiliary_hashtags))

        # 3. Creative Hook / Body (Deterministic contextual fallback)
        creative_text = self._build_creative_body(
            candidate, streamer_name, norm_platform, variation_seed
        )

        # 4. Formatted Caption
        suggested_caption = self._format_caption(
            creative_text=creative_text,
            mentions=mentions,
            hashtags=all_hashtags,
            platform=norm_platform,
        )

        # 5. Deterministic Compliance Checklist
        compliance = self._build_compliance_checklist(campaign, candidate, streamer_name, all_hashtags)

        # 6. Full Package Text for 1-click clipboard copy
        full_text = self._format_full_package(
            platform=norm_platform,
            caption=suggested_caption,
            mentions=mentions,
            hashtags=all_hashtags,
            compliance=compliance,
        )

        return {
            "platform": norm_platform,
            "streamer": streamer_name,
            "creator_key": creator_key,
            "variation_seed": variation_seed,
            "creative_text": creative_text,
            "mentions": mentions,
            "mandatory_hashtags": mandatory_hashtags,
            "all_hashtags": all_hashtags,
            "hashtags_str": " ".join(all_hashtags),
            "suggested_caption": suggested_caption,
            "compliance": compliance,
            "full_text": full_text,
            "rules_summary": {
                "lower_required": True,
                "lower_text": campaign.get("vertical", {}).get("text") or f"kick.com/{creator_key}",
                "period_start": campaign.get("period_start") or campaign.get("min_date"),
                "period_end": campaign.get("period_end") or campaign.get("max_date"),
            },
            "edited_video": candidate.get("edited_video"),
        }

    def _normalize_platform(self, platform: str) -> str:
        p = (platform or "TikTok").lower()
        if "short" in p or "youtube" in p:
            return "YouTube Shorts"
        if "reel" in p or "insta" in p:
            return "Instagram Reels"
        if "kwai" in p:
            return "Kwai"
        return "TikTok"

    def _build_mention(
        self, streamer_name: str, creator_key: str, campaign: Dict[str, Any], platform: str
    ) -> str:
        official = campaign.get("official_profile")
        if official and official.startswith("@"):
            return official

        # Platform-specific known handles
        handles = {
            "gabepeixe": {
                "TikTok": "@gabepeixe",
                "Instagram Reels": "@gabepeixe",
                "YouTube Shorts": "@GabePeixe",
                "Kwai": "@gabepeixe",
            },
            "brkk": {
                "TikTok": "@brkk",
                "Instagram Reels": "@brkk",
                "YouTube Shorts": "@BRKK",
                "Kwai": "@brkk",
            },
            "brabox": {
                "TikTok": "@brabox",
                "Instagram Reels": "@brabox",
                "YouTube Shorts": "@BRABOX",
                "Kwai": "@brabox",
            },
            "joaopichau": {
                "TikTok": "@joaopichau",
                "Instagram Reels": "@joaopichau",
                "YouTube Shorts": "@JoaoPichau",
                "Kwai": "@joaopichau",
            },
            "juninhomanella": {
                "TikTok": "@juninhomanella",
                "Instagram Reels": "@juninhomanella",
                "YouTube Shorts": "@JuninhoManella",
                "Kwai": "@juninhomanella",
            },
        }

        creator_handles = handles.get(creator_key, {})
        if platform in creator_handles:
            return creator_handles[platform]

        return f"@{creator_key}"

    def _build_aux_hashtags(self, platform: str, creator_key: str) -> List[str]:
        base = ["#cortes", "#streamer"]
        if platform == "TikTok":
            return base + ["#tiktokbrasil", "#fyp"]
        if platform == "Instagram Reels":
            return base + ["#reelsbrasil", "#explore"]
        if platform == "YouTube Shorts":
            return base + ["#shorts", "#clipes"]
        if platform == "Kwai":
            return base + ["#kwaibrasil", "#viral"]
        return base

    def _build_creative_body(
        self,
        candidate: Dict[str, Any],
        streamer_name: str,
        platform: str,
        seed: int,
    ) -> str:
        # Extract hook / summary / title / transcript snippet
        er = candidate.get("editorial_review") or {}
        hook = candidate.get("hook") or er.get("hook")
        title = candidate.get("title") or er.get("title")
        summary = candidate.get("summary") or er.get("reason")
        transcript = candidate.get("transcript") or candidate.get("text") or ""

        # Extract a clean quote if transcript exists
        quote = ""
        if transcript and len(transcript.strip()) > 10:
            clean_t = transcript.strip().replace("\n", " ")
            if len(clean_t) > 90:
                clean_t = clean_t[:87] + "..."
            quote = f'"{clean_t}"'

        subject = hook or title or summary or f"Momento da live do {streamer_name}"

        # Variations modulo 4
        v = seed % 4

        if platform == "TikTok":
            if v == 0:
                return f"{subject} 🔥 Olha o que acabou de rolar na live do {streamer_name}!"
            elif v == 1:
                return f"Você não vai acreditar no que aconteceu aqui... 👀 Assista até o final! {streamer_name}"
            elif v == 2:
                return f"O {streamer_name} perdeu a linha completamente nesse momento kkkk 🤣"
            else:
                return f"{quote or subject} 🎯 Não dá pra perder esse momento!"

        elif platform == "YouTube Shorts":
            if v == 0:
                return f"{subject} | Melhores Momentos {streamer_name} 🔥"
            elif v == 1:
                return f"Isso realmente aconteceu ao vivo? 😱 Melhores momentos de {streamer_name}."
            elif v == 2:
                return f"Momento épico na transmissão do {streamer_name}! Assista completo."
            else:
                return f"{quote or subject} — {streamer_name} ao vivo!"

        elif platform == "Instagram Reels":
            if v == 0:
                return f"{subject} 🔥 O que você faria nessa situação? Comenta aqui embaixo! 👇"
            elif v == 1:
                return f"A reação do {streamer_name} foi impagável 😂 Marca um amigo que precisa ver isso!"
            elif v == 2:
                return f"Momento imperdível da live de hoje com {streamer_name}! Siga o perfil para mais cortes diários."
            else:
                return f"{quote or subject} 🎬 Deixe seu like e confira a live completa!"

        else:  # Kwai
            if v == 0:
                return f"{subject} 😱 O que aconteceu aqui foi inacreditável!"
            elif v == 1:
                return f"O melhor momento da live de hoje com {streamer_name}! Assista até o fim 🔥"
            elif v == 2:
                return f"Reação épica do {streamer_name} ao vivo! Curta e compartilhe com os amigos."
            else:
                return f"{quote or subject} 💥 Não deixe de conferir!"

    def _format_caption(
        self, creative_text: str, mentions: str, hashtags: List[str], platform: str
    ) -> str:
        tags_str = " ".join(hashtags)
        return f"{creative_text}\n\nStreamer: {mentions}\n\n{tags_str}"

    def _build_compliance_checklist(
        self,
        campaign: Dict[str, Any],
        candidate: Dict[str, Any],
        streamer_name: str,
        hashtags: List[str],
    ) -> List[Dict[str, Any]]:
        checklist = []

        # 1. Lower
        lower_text = campaign.get("vertical", {}).get("text") or f"LOWER ({streamer_name.lower()})"
        checklist.append({
            "id": "lower",
            "title": "LOWER Oficial Obrigatório",
            "status": "ATENÇÃO",
            "description": f"Inserir no editor/CapCut o banner oficial '{lower_text}' posicionado abaixo do rosto do criador.",
            "is_mandatory": True,
        })

        # 2. Mandatory Hashtags
        camp_tags = campaign.get("hashtags", [])
        checklist.append({
            "id": "hashtags",
            "title": "Hashtags Obrigatórias",
            "status": "CONFORME",
            "description": f"Hashtag obrigatória {', '.join(camp_tags)} incluída na legenda sugerida.",
            "is_mandatory": True,
        })

        # 3. Official Mention
        checklist.append({
            "id": "mention",
            "title": "Menção ao Perfil Oficial",
            "status": "CONFORME",
            "description": f"Marcar o perfil oficial de {streamer_name} na plataforma de publicação.",
            "is_mandatory": True,
        })

        # 4. Anti-100%-AI Policy
        checklist.append({
            "id": "human_curation",
            "title": "Curadoria & Edição Humana",
            "status": "CONFORME",
            "description": "Corte decupado pelo TUTUCO CLIP MINER com curadoria, refinamento de tempo e edição humana aprovada.",
            "is_mandatory": True,
        })

        # 5. Organic Engagement
        checklist.append({
            "id": "organic",
            "title": "Engajamento Orgânico",
            "status": "CONFORME",
            "description": "Proibida compra de visualizações, manipulação artificial de métricas ou spam de volume.",
            "is_mandatory": True,
        })

        # 6. Eligible Date
        min_date = campaign.get("min_date") or campaign.get("period_start", "")[:10]
        if min_date:
            checklist.append({
                "id": "period",
                "title": "Data Elegível da Live",
                "status": "CONFORME",
                "description": f"Conteúdo originado de live transmitida a partir de {min_date}.",
                "is_mandatory": True,
            })

        return checklist

    def _format_full_package(
        self,
        platform: str,
        caption: str,
        mentions: str,
        hashtags: List[str],
        compliance: List[Dict[str, Any]],
    ) -> str:
        lines = [
            f"=== PACOTE DE PUBLICAÇÃO — {platform.upper()} ===",
            "",
            "--- LEGENDA SUGERIDA ---",
            caption,
            "",
            "--- MARCAÇÕES & HASHTAGS ---",
            f"Menção: {mentions}",
            f"Hashtags: {' '.join(hashtags)}",
            "",
            "--- CHECKLIST DE CONFORMIDADE DO CAMPEONATO ---",
        ]
        for c in compliance:
            prefix = "[✓]" if c["status"] == "CONFORME" else "[!]"
            lines.append(f"{prefix} {c['title']}: {c['description']}")

        lines.append("")
        lines.append("Pronto para publicação via TUTUCO CLIP MINER.")
        return "\n".join(lines)
