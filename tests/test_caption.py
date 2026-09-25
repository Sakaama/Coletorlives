from pathlib import Path
import pytest
from miner.caption import CaptionGenerator, load_campaign_config, load_creator_template


@pytest.fixture
def generator():
    root = Path(__file__).resolve().parent.parent
    return CaptionGenerator(root)


def test_load_campaign_config():
    root = Path(__file__).resolve().parent.parent
    camp = load_campaign_config(root, "gabepeixe")
    assert camp["id"] == "gabepeixe"
    assert "#gabepeixe" in camp["hashtags"]

    brkk = load_campaign_config(root, "brkk")
    assert brkk["id"] == "brkk"
    assert "#brkk" in brkk["hashtags"]


def test_load_creator_template():
    root = Path(__file__).resolve().parent.parent
    tmpl = load_creator_template(root, "gabepeixe")
    assert tmpl["has_template_file"] is True
    assert "1080x1920" in tmpl["canvas"]
    assert "Câmera em cima" in tmpl["layout_visual"]


def test_caption_generator_gabepeixe(generator):
    candidate = {
        "id": "cand_12345",
        "creator_key": "gabepeixe",
        "title": "Momento épico no Minecraft",
        "hook": "Gabe encontra Netherite no primeiro minuto",
        "transcript": "Gente eu não acredito nisso, achei!",
    }

    pkg = generator.generate(candidate, platform="TikTok", variation_seed=0)
    assert pkg["platform"] == "TikTok"
    assert pkg["streamer"] == "GabePeixe"
    assert "#gabepeixe" in pkg["mandatory_hashtags"]
    assert "#gabepeixe" in pkg["all_hashtags"]
    assert "@gabepeixe" in pkg["mentions"]
    assert "suggested_caption" in pkg
    assert "full_text" in pkg
    assert len(pkg["compliance"]) >= 5

    # Check checklist items
    comp_ids = [c["id"] for c in pkg["compliance"]]
    assert "lower" in comp_ids
    assert "hashtags" in comp_ids
    assert "mention" in comp_ids
    assert "human_curation" in comp_ids


def test_caption_variations(generator):
    candidate = {
        "id": "cand_var",
        "creator_key": "gabepeixe",
        "hook": "Jogada inacreditável",
    }
    pkg0 = generator.generate(candidate, platform="TikTok", variation_seed=0)
    pkg1 = generator.generate(candidate, platform="TikTok", variation_seed=1)
    pkg2 = generator.generate(candidate, platform="TikTok", variation_seed=2)

    assert pkg0["creative_text"] != pkg1["creative_text"]
    assert pkg1["creative_text"] != pkg2["creative_text"]
    # But mandatory hashtags stay identical and deterministic
    assert pkg0["mandatory_hashtags"] == pkg1["mandatory_hashtags"] == ["#gabepeixe"]


def test_caption_different_platforms(generator):
    candidate = {
        "id": "cand_plat",
        "creator_key": "brkk",
        "title": "Clutch 1v4 no Valorant",
    }
    pkg_yt = generator.generate(candidate, platform="YouTube Shorts")
    assert pkg_yt["platform"] == "YouTube Shorts"
    assert "#shorts" in pkg_yt["all_hashtags"]
    assert "#brkk" in pkg_yt["all_hashtags"]

    pkg_ig = generator.generate(candidate, platform="Instagram Reels")
    assert pkg_ig["platform"] == "Instagram Reels"
    assert "#reelsbrasil" in pkg_ig["all_hashtags"]
