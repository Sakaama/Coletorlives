import copy
import json
from pathlib import Path

import pytest

from app import ROOT, create_app
from miner.rules import eligibility, load_campaigns, validate_url


@pytest.fixture
def campaigns():
    return load_campaigns(ROOT / "config/campaigns")


@pytest.mark.parametrize("cid", ["gabepeixe", "brkk", "brabox", "joaopichau", "juninhomanella"])
def test_campaign_contract(campaigns, cid):
    c = campaigns[cid]
    assert c["id"] == cid and c["name"] and c["streamer"]
    assert c["allowed_sources"] and c["hashtags"]
    for field in ("required_texts", "required_visuals", "channel_aliases", "verified_channel_ids"):
        assert isinstance(c[field], list)
    p = c["vertical"]
    assert p["camera_height"] >= 100 and p["band_height"] >= 60
    assert 1920 - p["camera_height"] - p["band_height"] >= 200
    assert isinstance(p["text"], str)


def test_joao_rules_and_inclusive_date(campaigns):
    c = campaigns["joaopichau"]
    assert c["hashtags"] == ["#joaopichau"]
    assert c["min_date"] == "2026-09-01"
    assert c["original_lives_only"]
    assert c["publication_platforms"] == ["Instagram", "TikTok", "YouTube"]
    assert c["pinned_comment"]["required_until"] == "2026-10-09"
    assert c["pinned_comment"]["text"] == (
        "Evento Pichau Arena, o maior evento gamer do Sul do Brasil, de 10 a 12 de outubro em Joinville - SC"
    )
    for day, status in [("2026-08-31", "NÃO PERMITIDA"), ("2026-09-01", "REVISÃO HUMANA")]:
        result = eligibility(c, dict(platform="YouTube", date=day, date_kind="live", was_live=True))
        assert result["status"] == status
        assert any("participação ativa" in reason for reason in result["reasons"])
        assert not any("Brabox" in reason for reason in result["reasons"])
    assert eligibility(c, dict(platform="YouTube", was_live=False))["status"] == "NÃO PERMITIDA"


def test_juninho_rules_and_unknown_period(campaigns):
    c = campaigns["juninhomanella"]
    assert c["hashtags"] == ["#juninhomanella"]
    assert c["official_profile"] is None and c["min_date"] is None
    assert not c.get("original_lives_only")
    assert "kick.com/juninhomanella" in c["vertical"]["text"]
    assert any("NO PRÓPRIO CORTE" in text for text in c["required_visuals"])
    assert any("perfil oficial" in text for text in c["required_texts"])
    assert any("Kings League" in text for text in c["source_channels"])
    result = eligibility(c, dict(platform="YouTube", date="2025-01-01", date_kind="human", was_live=False))
    assert result["status"] == "REVISÃO HUMANA"
    assert any("Data mínima" in reason for reason in result["reasons"])
    assert eligibility(c, dict(platform="Local", date="2026-09-22"))["status"] == "REVISÃO HUMANA"


@pytest.mark.parametrize("cid", ["joaopichau", "juninhomanella"])
def test_informational_rules_do_not_certify_or_block(campaigns, cid):
    c = campaigns[cid]
    assert "WhatsApp" in c["operational_requirements"][0]
    assert "plataformas de IA" in c["ai_policy"]
    assert len(c["prohibitions"]) == 9
    stripped = {k: v for k, v in c.items() if k not in
                {"operational_requirements", "pinned_comment", "prohibitions", "ai_policy"}}
    m = dict(platform="YouTube", date="2026-09-22", date_kind="live", was_live=True)
    assert eligibility(c, m) == eligibility(stripped, m)
    assert c["verified_channel_ids"] == []


def test_generic_creator_and_legacy_message(campaigns):
    c = copy.deepcopy(campaigns["brabox"])
    m = dict(platform="Kick", date="2026-09-22", date_kind="live", was_live=True)
    original = eligibility(c, m)
    assert "Conferir se é live ORIGINAL do Brabox nas fontes oficiais, sem edição prévia nem origem em outras contas de cortes." in original["reasons"]
    c.update(id="arbitrary", streamer="Pessoa de teste")
    result = eligibility(c, m)
    assert any("Pessoa de teste" in reason for reason in result["reasons"])
    assert not any("Brabox" in reason for reason in result["reasons"])
    assert result["status"] == original["status"]


@pytest.mark.parametrize("contents,error", [('not json', ValueError), ('{"id":"../invalid"}', ValueError),
                                           ('{}', KeyError)])
def test_existing_invalid_configuration_contract(tmp_path, contents, error):
    (tmp_path / "invalid.json").write_text(contents, encoding="utf-8")
    with pytest.raises(error):
        load_campaigns(tmp_path)


def test_unknown_metadata_does_not_break_loader(tmp_path, campaigns):
    c = copy.deepcopy(campaigns["gabepeixe"])
    c["operational_requirements"] = ["Informação manual"]
    c["pinned_comment"] = {"text": "Exemplo", "required_until": "2026-10-09"}
    (tmp_path / "test.json").write_text(json.dumps(c), encoding="utf-8")
    loaded = load_campaigns(tmp_path)[c["id"]]
    m = dict(platform="YouTube", date="2026-09-22", was_live=True)
    assert eligibility(loaded, m) == eligibility(campaigns["gabepeixe"], m)


def test_existing_api_and_remote_configuration_without_jobs(tmp_path):
    app = create_app(tmp_path / "data")
    service = app.extensions["miner"]
    collector = app.extensions["collector"]
    try:
        client = app.test_client()
        state = client.get("/api/state").json
        assert {"joaopichau", "juninhomanella", "gabepeixe", "brkk", "brabox"} <= set(state["campaigns"])
        for cid in ("joaopichau", "juninhomanella"):
            run = collector.configure(dict(creator=cid, provider="YouTube", channel="unverified_example",
                                           start="2026-09-01", end="2026-09-22"))
            assert run["creator"] == cid
            assert collector.view(run["id"])["summary"]["found"] == 0
        with pytest.raises(ValueError, match="Campanha inválida"):
            service.campaign("does_not_exist")
        assert not service.store.rows("SELECT * FROM jobs")
        assert not service.store.rows("SELECT * FROM remote_jobs")
        assert not service.store.rows("SELECT * FROM vods")
        assert client.get("/").status_code == 200
    finally:
        service.executor.shutdown(wait=True)


def test_instagram_tiktok_not_silently_added_to_downloader():
    for url in ("https://www.instagram.com/example/", "https://www.tiktok.com/@example"):
        with pytest.raises(ValueError):
            validate_url(url)


def test_old_campaign_files_unchanged():
    # Contratos operacionais, sem cópia do JSON inteiro nos testes.
    campaigns = load_campaigns(Path(ROOT) / "config/campaigns")
    assert campaigns["brkk"]["excluded_terms"] == ["cinefy"]
    assert campaigns["brabox"]["date_disputed"] is True
    assert campaigns["gabepeixe"]["required_visuals"] == ["LOWER (gabepeixe) abaixo do rosto"]
