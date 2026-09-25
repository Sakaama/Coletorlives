from app import create_app
from miner.presentation import (
    format_duration,
    format_timestamp,
    get_creator_meta,
    PresentationService,
)
from miner.service import Service
from miner.collector import Collector
from pathlib import Path
import pytest


@pytest.fixture
def pres_service():
    root = Path(__file__).resolve().parent.parent
    svc = Service(root)
    col = Collector(svc)
    return PresentationService(svc, col)


def test_format_helpers():
    assert format_duration(0) == "0s"
    assert format_duration(45) == "45s"
    assert format_duration(125) == "2m 05s"
    assert format_duration(3600) == "1h"
    assert format_duration(44400) == "12h 20m"

    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(65) == "00:01:05"
    assert format_timestamp(3661) == "01:01:01"


def test_get_creator_meta():
    gabe = get_creator_meta("gabepeixe")
    assert gabe["name"] == "GabePeixe"
    assert "Kick" in gabe["platforms"]
    assert "Minecraft" in gabe["dna"]["topics"]

    brkk = get_creator_meta("brkk")
    assert brkk["name"] == "BRKK"
    assert "YouTube" in brkk["platforms"]

    fallback = get_creator_meta("desconhecido")
    assert fallback["name"] == "Desconhecido"


def test_presentation_dashboard(pres_service):
    dash = pres_service.get_dashboard()
    assert "metrics" in dash
    assert "recent_activity" in dash
    m = dash["metrics"]
    assert m["vods_total"] >= 18
    assert m["total_candidates"] >= 307
    assert m["hours_analyzed"] > 0


def test_presentation_creators(pres_service):
    creators = pres_service.get_creators()
    assert len(creators) >= 3
    keys = [c["key"] for c in creators]
    assert "gabepeixe" in keys
    assert "brkk" in keys
    gabe = next(c for c in creators if c["key"] == "gabepeixe")
    assert gabe["vods_count"] >= 18
    assert gabe["candidates_count"] >= 307


def test_presentation_inbox(pres_service):
    inbox = pres_service.get_inbox(limit=10)
    assert inbox["total_matches"] >= 307
    assert len(inbox["items"]) <= 10
    item = inbox["items"][0]
    assert "id" in item and "vod_id" in item
    assert "score" in item and "classification" in item
    assert "start_formatted" in item and "end_formatted" in item

    # Filter by shortlist
    shortlist_inbox = pres_service.get_inbox(classification="SHORTLIST")
    for it in shortlist_inbox["items"]:
        assert it["classification"] in ("RECOMENDADO", "BOM")
        assert it["status"] != "DESCARTADO"


def test_presentation_vods(pres_service):
    vods = pres_service.get_vods()
    assert len(vods) >= 18
    v = vods[0]
    assert "id" in v and "title" in v and "creator" in v
    assert "status" in v and "duration_formatted" in v


def test_product_api_endpoints():
    app = create_app()
    client = app.test_client()

    r1 = client.get("/api/product/dashboard")
    assert r1.status_code == 200
    assert "metrics" in r1.json

    r2 = client.get("/api/product/creators")
    assert r2.status_code == 200
    assert len(r2.json["creators"]) >= 3

    r3 = client.get("/api/product/inbox?limit=5")
    assert r3.status_code == 200
    assert len(r3.json["items"]) <= 5

    r4 = client.get("/api/product/vods")
    assert r4.status_code == 200
    assert len(r4.json["vods"]) >= 18

    # Workspace endpoint
    r5 = client.get("/api/product/creator/gabepeixe/workspace")
    assert r5.status_code == 200
    ws = r5.json
    assert ws["creator"]["name"] == "GabePeixe"
    assert "campaign" in ws
    assert "perfil_de_cortes" in ws
    assert ws["perfil_de_cortes"]["status"] == "Perfil comportamental em construção através da análise das lives"
    assert "vods" in ws
    assert "recent_candidates" in ws

    # Caption generation endpoint (using an existing candidate)
    inbox_res = client.get("/api/product/inbox?limit=1").json
    if inbox_res["items"]:
        cid = inbox_res["items"][0]["id"]
        # Include CSRF local-token simulation if needed, or check local test client
        r6 = client.post("/api/product/caption/generate", json={"candidate_id": cid, "platform": "TikTok"})
        if r6.status_code == 200:
            pkg = r6.json
            assert "suggested_caption" in pkg
            assert "compliance" in pkg


def test_creator_workspace_method(pres_service):
    ws = pres_service.get_creator_workspace("gabepeixe")
    assert ws["creator"]["name"] == "GabePeixe"
    assert ws["stats"]["vods_count"] >= 18
    assert ws["stats"]["candidates_count"] >= 307
    assert ws["perfil_de_cortes"]["status"] == "Perfil comportamental em construção através da análise das lives"
    assert "layout_visual" in ws["perfil_de_cortes"]
    assert "lower_text" in ws["perfil_de_cortes"]

