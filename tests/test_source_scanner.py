import json
from pathlib import Path
import pytest

from app import create_app
from miner.remote_provider import Provider, Cancelled, youtube_source, youtube_row
from miner.rules import validate_url
from miner.service import Service

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("source,ending", [
    ("@creator", "/@creator/videos"), ("creator", "/@creator/videos"),
    ("https://youtube.com/@creator/streams", "/@creator/streams"),
    ("https://youtube.com/c/creator", "/c/creator/videos"),
    ("https://youtube.com/channel/UC" + "x" * 22, "/channel/UC" + "x" * 22 + "/videos"),
    ("https://youtube.com/playlist?list=PL1234567890", "/playlist?list=PL1234567890"),
])
def test_sources(source, ending):
    assert youtube_source(source).endswith(ending)


@pytest.mark.parametrize("source", [
    "https://evil.com/@x", "http://youtube.com/@x",
    "https://youtube.com@evil.com/@x", "https://youtube.com:443/@x", "file:///x",
    "https://youtube.com/watch?v=abcdefghijk", "https://youtube.com/@x?list=bad",
    "https://youtube.com/playlist?list=bad", "https://youtube.com/@x/../watch"
])
def test_reject_sources(source):
    with pytest.raises(ValueError):
        youtube_source(source)


def test_single_video_contract_unchanged():
    with pytest.raises(ValueError):
        validate_url("https://youtube.com/@creator")


def test_listing_metadata_only_bounded_deduplicated(tmp_path, monkeypatch):
    p = Provider(tmp_path)
    commands = []
    rows = [
        dict(id="abcdefghijk", upload_date="20260916", duration=90),
        dict(id="abcdefghijk", upload_date="20260916"),
        dict(id="12345678901", is_live=True), None, dict(id="bad"),
        dict(id="23456789012", availability="private"),
        dict(id="34567890123", live_status="is_upcoming"),
        dict(id="45678901234")
    ]

    def execute(args, *a, **kw):
        commands.append(args)
        return json.dumps({"entries": rows})

    monkeypatch.setattr(p, "execute", execute)
    monkeypatch.setattr(p, "metadata", lambda *a, **kw: youtube_row(dict(id="45678901234", upload_date="20260917")))
    result = p.discover("YouTube", "@creator")
    assert len(result) == 2
    assert result[0]["date_kind"] == "upload" and result[0]["was_live"] is None
    args = commands[0]
    assert all(flag in args for flag in ("--flat-playlist", "--skip-download", "--ignore-config"))
    assert args[args.index("--playlist-end") + 1] == "100"
    assert args[-2:] == ["--", "https://www.youtube.com/@creator/videos"]


def test_unknown_dates_failure_and_cancellation(tmp_path, monkeypatch):
    p = Provider(tmp_path)
    monkeypatch.setattr(p, "execute", lambda *a, **kw: json.dumps({"entries": [{"id": "abcdefghijk"}]}))

    def failure(*a, **kw):
        raise ValueError("unavailable")

    monkeypatch.setattr(p, "metadata", failure)
    assert p.discover("YouTube", "creator")[0]["startTime"] is None

    def cancel(*a, **kw):
        raise Cancelled()

    monkeypatch.setattr(p, "metadata", cancel)
    with pytest.raises(Cancelled):
        p.discover("YouTube", "creator")

    monkeypatch.setattr(p, "execute", lambda *a, **kw: "[]")
    with pytest.raises(ValueError):
        p.discover("YouTube", "creator")


@pytest.mark.parametrize("limit", [0, 101, True, "100"])
def test_listing_limit(tmp_path, limit):
    with pytest.raises(ValueError):
        Provider(tmp_path).discover("YouTube", "creator", limit)


def test_date_provenance():
    row = youtube_row(dict(id="abcdefghijk", was_live=True, upload_date="20260917", release_timestamp=1789516800))
    assert row["date_kind"] == "live" and row["was_live"] is True
    row = youtube_row(dict(id="abcdefghijk", upload_date="invalid", release_timestamp=1789516800))
    assert row["startTime"] is None and row["was_live"] is None


# =========================================================================
# 12 REQUISITOS MANDATÓRIOS DE DESCOBERTA EFÊMERA (A2 ARQUITETURA CORRIGIDA)
# =========================================================================

def test_1_and_2_discovery_does_not_create_vod_or_alter_database(tmp_path, monkeypatch):
    """1. Discovery não cria VOD; 2. Discovery não altera banco."""
    svc = Service(ROOT, tmp_path / "data")
    executed = []

    def fake_execute(args, *a, **kw):
        executed.append(args)
        return json.dumps({
            "entries": [
                {"id": "vid11111111", "title": "Vídeo 1", "upload_date": "20260910", "duration": 120},
                {"id": "vid22222222", "title": "Vídeo 2", "upload_date": "20260912", "duration": 300},
            ]
        })

    monkeypatch.setattr(svc.provider, "execute", fake_execute)

    # Verifica estado pré-descoberta
    assert svc.store.rows("SELECT count(*) as c FROM vods")[0]["c"] == 0
    assert svc.store.rows("SELECT count(*) as c FROM jobs")[0]["c"] == 0

    # Executa descoberta
    result = svc.discover("joaopichau", "https://youtube.com/@joaopichau", limit=50)

    # 1. Retorna os vídeos no catálogo efêmero
    assert result["count"] == 2
    assert result["summary"]["new"] == 2

    # 2. Comprova que zero VODs e zero registros foram criados no banco
    assert svc.store.rows("SELECT count(*) as c FROM vods")[0]["c"] == 0
    assert svc.store.rows("SELECT count(*) as c FROM jobs")[0]["c"] == 0
    assert svc.store.rows("SELECT count(*) as c FROM candidates")[0]["c"] == 0
    assert svc.store.rows("SELECT count(*) as c FROM exports")[0]["c"] == 0


def test_3_known_is_identified_without_persistence(tmp_path, monkeypatch):
    """3. KNOWN é identificado sem persistência."""
    svc = Service(ROOT, tmp_path / "data")
    # Cadastra previamente uma VOD no banco
    vod, _ = svc.create_vod("joaopichau", "https://www.youtube.com/watch?v=vid11111111", {
        "url": "https://www.youtube.com/watch?v=vid11111111",
        "provider_vod_id": "vid11111111",
        "platform": "YouTube",
        "title": "Vídeo Já Conhecido",
    })
    initial_vod_count = svc.store.rows("SELECT count(*) as c FROM vods")[0]["c"]
    assert initial_vod_count == 1

    monkeypatch.setattr(svc.provider, "execute", lambda *a, **kw: json.dumps({
        "entries": [
            {"id": "vid11111111", "title": "Vídeo Já Conhecido", "upload_date": "20260910"},
        ]
    }))

    result = svc.discover("joaopichau", "@joaopichau")
    assert result["count"] == 1
    assert result["items"][0]["status"] == "KNOWN"
    assert result["summary"]["known"] == 1

    # Comprova que o banco não sofreu nenhuma nova inserção
    assert svc.store.rows("SELECT count(*) as c FROM vods")[0]["c"] == initial_vod_count


def test_4_new_continues_without_persistence(tmp_path, monkeypatch):
    """4. NEW continua sem persistência."""
    svc = Service(ROOT, tmp_path / "data")
    monkeypatch.setattr(svc.provider, "execute", lambda *a, **kw: json.dumps({
        "entries": [
            {"id": "vid33333333", "title": "Vídeo Totalmente Novo", "upload_date": "20260915"},
        ]
    }))

    result = svc.discover("joaopichau", "@joaopichau")
    assert result["items"][0]["status"] == "NEW"
    assert result["summary"]["new"] == 1

    # Banco permanece limpo
    assert svc.store.rows("SELECT count(*) as c FROM vods")[0]["c"] == 0


def test_5_out_of_period(tmp_path, monkeypatch):
    """5. OUT_OF_PERIOD para datas anteriores ao início da campanha."""
    svc = Service(ROOT, tmp_path / "data")
    # joaopichau exige conteúdo >= 2026-09-01
    monkeypatch.setattr(svc.provider, "execute", lambda *a, **kw: json.dumps({
        "entries": [
            {"id": "vidold00001", "title": "Vídeo Antigo de Agosto", "upload_date": "20260831"},
            {"id": "vidvalid001", "title": "Vídeo Válido de Setembro", "upload_date": "20260901"},
        ]
    }))

    result = svc.discover("joaopichau", "@joaopichau")
    assert result["count"] == 2
    assert result["items"][0]["status"] == "OUT_OF_PERIOD"
    assert "anterior à data mínima" in result["items"][0]["status_reason"]
    assert result["items"][1]["status"] == "NEW"
    assert result["summary"]["out_of_period"] == 1
    assert result["summary"]["new"] == 1


def test_6_needs_review(tmp_path, monkeypatch):
    """6. NEEDS_REVIEW quando a data é ausente ou a campanha não define data mínima."""
    svc = Service(ROOT, tmp_path / "data")

    # Caso A: joaopichau com vídeo sem data confirmada na listagem
    monkeypatch.setattr(svc.provider, "execute", lambda *a, **kw: json.dumps({
        "entries": [
            {"id": "vidnodate01", "title": "Vídeo Sem Data"},
        ]
    }))
    result = svc.discover("joaopichau", "@joaopichau")
    assert result["items"][0]["status"] == "NEEDS_REVIEW"
    assert "Data não confirmada" in result["items"][0]["status_reason"]

    # Caso B: juninhomanella possui min_date = null (depende de revisão humana)
    monkeypatch.setattr(svc.provider, "execute", lambda *a, **kw: json.dumps({
        "entries": [
            {"id": "vidjuninho1", "title": "Vídeo do Juninho", "upload_date": "20260910"},
        ]
    }))
    result_j = svc.discover("juninhomanella", "@juninhomanella")
    assert result_j["items"][0]["status"] == "NEEDS_REVIEW"
    assert "sem data mínima definida" in result_j["items"][0]["status_reason"]


def test_7_upcoming_and_live_now(tmp_path, monkeypatch):
    """7. UPCOMING e LIVE_NOW identificados com segurança."""
    svc = Service(ROOT, tmp_path / "data")
    monkeypatch.setattr(svc.provider, "execute", lambda *a, **kw: json.dumps({
        "entries": [
            {"id": "vidlive0001", "title": "Live Agora", "is_live": True, "live_status": "is_live"},
            {"id": "vidupcom001", "title": "Live Amanhã", "live_status": "is_upcoming"},
        ]
    }))

    result = svc.discover("joaopichau", "@joaopichau")
    assert result["count"] == 2
    assert result["items"][0]["status"] == "LIVE_NOW"
    assert result["items"][1]["status"] == "UPCOMING"
    assert result["summary"]["live_now"] == 1
    assert result["summary"]["upcoming"] == 1


def test_8_and_9_import_requires_explicit_action_and_reuses_pipeline(tmp_path, monkeypatch):
    """8. Importar exige ação explícita; 9. Importar reutiliza pipeline existente."""
    svc = Service(ROOT, tmp_path / "data")

    # 1. Simula descoberta
    monkeypatch.setattr(svc.provider, "execute", lambda *a, **kw: json.dumps({
        "entries": [
            {"id": "vidimport01", "title": "Vídeo Para Importar", "upload_date": "20260915"},
        ]
    }))
    discovered = svc.discover("joaopichau", "@joaopichau")
    assert discovered["items"][0]["status"] == "NEW"
    target_url = discovered["items"][0]["url"]

    # Comprova que a descoberta NÃO importou
    assert svc.store.rows("SELECT count(*) as c FROM vods")[0]["c"] == 0

    # 2. Simula ação explícita do operador clicando em Importar VOD
    # Intercepta ytdlp_cli.extract_info do pipeline existente de import_url
    from miner import ytdlp_cli
    monkeypatch.setattr(ytdlp_cli, "extract_info", lambda *a, **kw: {
        "id": "vidimport01", "title": "Vídeo Para Importar", "upload_date": "20260915",
        "duration": 600, "channel": "Canal Pichau", "channel_id": "UC1234567890123456789012",
        "is_live": False, "was_live": False
    })

    import_result = svc.import_url("joaopichau", target_url)
    assert import_result["vod"]["id"] is not None
    assert import_result["known"] is False
    assert import_result["job"] is not None

    # Comprova que o pipeline existente cadastrou a VOD
    assert svc.store.rows("SELECT count(*) as c FROM vods")[0]["c"] == 1
    saved_vod = svc.store.get_vod(import_result["vod"]["id"])
    assert saved_vod["campaign"] == "joaopichau"

    # 3. Nova descoberta agora reconhece esse vídeo como KNOWN
    rediscovered = svc.discover("joaopichau", "@joaopichau")
    assert rediscovered["items"][0]["status"] == "KNOWN"
    assert rediscovered["summary"]["known"] == 1


def test_10_discovery_never_downloads_media(tmp_path, monkeypatch):
    """10. Discovery nunca baixa mídia (garante flags --skip-download e --flat-playlist)."""
    p = Provider(tmp_path)
    captured_args = []

    def mock_exec(args, *a, **kw):
        captured_args.append(args)
        return json.dumps({"entries": [{"id": "vidtest0001", "upload_date": "20260920"}]})

    monkeypatch.setattr(p, "execute", mock_exec)
    svc = Service(ROOT, tmp_path / "data")
    svc.provider = p

    # Executa descoberta de canal
    svc.discover("joaopichau", "https://youtube.com/@canal", limit=25)
    assert len(captured_args) == 1
    cmd = captured_args[0]
    assert "--skip-download" in cmd
    assert "--flat-playlist" in cmd
    assert "--dump-single-json" in cmd
    assert "--ignore-config" in cmd
    assert cmd[cmd.index("--playlist-end") + 1] == "25"

    # Executa descoberta de vídeo individual
    captured_args.clear()
    svc.discover("joaopichau", "https://www.youtube.com/watch?v=vidtest0001")
    assert len(captured_args) == 1
    cmd_single = captured_args[0]
    assert "--skip-download" in cmd_single
    assert "--dump-single-json" in cmd_single
    assert "--no-playlist" in cmd_single


def test_11_catalog_api_contract_and_summary(tmp_path, monkeypatch):
    """11. Contrato da API /api/discover e resposta do catálogo."""
    app = create_app(tmp_path / "data")
    client = app.test_client()

    fake_entries = [
        {"id": "vid00000001", "title": "Vídeo 1", "upload_date": "20260902", "duration": 100},
        {"id": "vid00000002", "title": "Vídeo 2", "upload_date": "20260820", "duration": 200},
    ]

    monkeypatch.setattr(app.extensions["miner"].provider, "execute",
                        lambda *a, **kw: json.dumps({"entries": fake_entries}))

    # Sem token -> 403
    res_no_token = client.post("/api/discover", json={"campaign": "joaopichau", "url": "@pichau"})
    assert res_no_token.status_code == 403

    # Obtém token do index
    token = None
    index_html = client.get("/").get_data(as_text=True)
    import re
    match = re.search(r'name="miner-token" content="([^"]+)"', index_html)
    assert match is not None
    token = match.group(1)

    # Com token válido
    headers = {"X-Miner-Token": token, "Content-Type": "application/json"}
    res = client.post("/api/discover", json={"campaign": "joaopichau", "url": "@pichau", "limit": 20}, headers=headers)
    assert res.status_code == 200
    data = res.get_json()

    assert data["campaign"] == "joaopichau"
    assert data["count"] == 2
    assert "summary" in data
    assert data["summary"]["new"] == 1
    assert data["summary"]["out_of_period"] == 1
    item = data["items"][0]
    assert item["source_id"] == "youtube:vid00000001"
    assert item["video_id"] == "vid00000001"
    assert item["url"] == "https://www.youtube.com/watch?v=vid00000001"
    assert item["status"] == "NEW"
    assert item["duration_formatted"] == "01:40"


def test_12_existing_campaigns_unaffected(tmp_path):
    """12. Campanhas existentes continuam carregando e funcionando."""
    svc = Service(ROOT, tmp_path / "data")
    assert set(svc.campaigns.keys()) >= {"gabepeixe", "brkk", "brabox", "joaopichau", "juninhomanella"}
    joao = svc.campaign("joaopichau")
    assert joao["min_date"] == "2026-09-01"
    juninho = svc.campaign("juninhomanella")
    assert juninho["min_date"] is None
    brabox = svc.campaign("brabox")
    assert "Brabox" in brabox["streamer"]


def test_collector_sync_decoupled_from_youtube(tmp_path, monkeypatch):
    """Comprova que Collector.sync não auto-registra VODs do YouTube."""
    from test_remote import collector  # noqa: F401
    from miner.collector import Collector
    svc = Service(ROOT, tmp_path / "data")
    c = Collector(svc)
    rid = c.configure(dict(creator="joaopichau", provider="YouTube", channel="https://youtube.com/@creator/streams", start="2026-09-15", end="2026-09-17"))["id"]

    msg = c.sync(rid, lambda: None, lambda *a: None)
    assert "desacoplada" in msg
    # Nenhum VOD adicionado
    assert len(c.members(rid)) == 0
