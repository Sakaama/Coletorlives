import pytest

from app import ROOT
from miner.collector import Collector
from miner.rules import eligibility, load_campaigns
from miner.service import Service


@pytest.fixture
def gabe_campaign():
    campaigns = load_campaigns(ROOT / "config/campaigns")
    return campaigns["gabepeixe"]


def test_gabepeixe_configuration_contract(gabe_campaign):
    c = gabe_campaign
    assert c["id"] == "gabepeixe"
    assert c["name"] == "GabePeixe"
    assert c["streamer"] == "GabePeixe"
    assert c["allowed_sources"] == ["Kick"], "GabePeixe deve ter Kick como fonte exclusiva"
    assert c["min_date"] == "2026-09-01", "Conteúdo elegível a partir de 01/09/2026"
    assert c["max_date"] == "2026-10-22", "Período do campeonato encerra em 22/10/2026"
    assert c["hashtags"] == ["#gabepeixe"]
    assert c["required_visuals"] == ["LOWER (gabepeixe) abaixo do rosto"]
    assert any("perfil oficial" in text for text in c["required_texts"])
    assert len(c["prohibitions"]) >= 5
    assert "IA" in c["ai_policy"]
    assert len(c["operational_requirements"]) >= 3


def test_gabepeixe_eligibility_by_date_and_platform(gabe_campaign):
    c = gabe_campaign
    base = {
        "platform": "Kick",
        "date_kind": "live",
        "was_live": True,
        "channel": "gabepeixe",
        "channel_id": "verified",
    }
    # Within championship dates
    for d in ("2026-09-01", "2026-09-22", "2026-10-22"):
        res = eligibility(c, {**base, "date": d})
        assert res["status"] in ("PERMITIDA", "REVISÃO HUMANA")
        assert not any("fora do período" in r for r in res["reasons"])

    # Outside championship dates
    res_early = eligibility(c, {**base, "date": "2026-08-31"})
    assert res_early["status"] == "NÃO PERMITIDA"
    assert any("fora do período" in r for r in res_early["reasons"])

    res_late = eligibility(c, {**base, "date": "2026-10-23"})
    assert res_late["status"] == "NÃO PERMITIDA"
    assert any("fora do período" in r for r in res_late["reasons"])

    # Platform restrictions: YouTube and Twitch are blocked for GabePeixe
    res_yt = eligibility(c, {**base, "platform": "YouTube", "date": "2026-09-22"})
    assert res_yt["status"] == "NÃO PERMITIDA"
    assert any("Fonte não permitida" in r for r in res_yt["reasons"])

    res_twitch = eligibility(c, {**base, "platform": "Twitch", "date": "2026-09-22"})
    assert res_twitch["status"] == "NÃO PERMITIDA"
    assert any("Fonte não permitida" in r for r in res_twitch["reasons"])

    # Local files request human review
    res_local = eligibility(c, {"platform": "Local", "date": "2026-09-22"})
    assert res_local["status"] == "REVISÃO HUMANA"


def test_collector_enforces_kick_provider_for_gabepeixe(tmp_path):
    service = Service(ROOT, tmp_path / "data")
    collector = Collector(service, None, tmp_path / "RAW")
    try:
        # Kick is accepted
        run = collector.configure({
            "creator": "gabepeixe",
            "provider": "Kick",
            "channel": "gabepeixe",
            "start": "2026-09-01",
            "end": "2026-10-22",
        })
        assert run["id"] is not None

        # YouTube is rejected for GabePeixe
        with pytest.raises(ValueError, match="Provider não permitido"):
            collector.configure({
                "creator": "gabepeixe",
                "provider": "YouTube",
                "channel": "@gabepeixe",
                "start": "2026-09-01",
                "end": "2026-10-22",
            })
    finally:
        service.executor.shutdown(wait=True)
