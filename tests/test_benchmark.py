import copy
import itertools
import json
import random
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from miner.benchmark import evaluate, temporal_metrics


ROOT = Path(__file__).resolve().parents[1]


def gold(cut_id="g1", start=10, end=20, **extra):
    return dict(gold_id=cut_id, vod_id="vod", campaign_id="campaign", creator="Pessoa",
                expected_start=start, expected_end=end, would_clip=True, **extra)


def pred(cut_id="p1", start=10, end=20, **extra):
    return dict(prediction_id=cut_id, vod_id="vod", campaign_id="campaign", start=start, end=end, **extra)


def documents(golds, predictions):
    return ({"schema_version": 1, "gold_cuts": golds}, {"schema_version": 1, "predictions": predictions})


def run(golds, predictions, **kwargs):
    return evaluate(*documents(golds, predictions), **kwargs)


def pair_ids(result):
    return [(m["gold_id"], m["prediction_id"]) for m in result["matches"]]


def test_perfect_match():
    result = run([gold()], [pred()])
    assert result["matched_count"] == result["gold_count"] == result["prediction_count"] == 1
    assert result["recall"] == result["precision"] == result["mean_temporal_iou"] == 1
    assert result["false_positive_count"] == result["false_negative_count"] == 0
    assert result["mean_start_error"] == result["mean_end_error"] == result["boundary_mae"] == 0
    assert result["boundary_both_within_tolerance_rate"] == 1


def test_acceptance_human_70_115_miner_72_113():
    result = run([gold(start=70, end=115)], [pred(start=72, end=113)])
    match = result["matches"][0]
    assert match["intersection"] == 41
    assert match["union"] == 45
    assert match["temporal_iou"] == pytest.approx(41 / 45)
    assert match["start_error"] == match["end_error"] == match["boundary_mae"] == 2
    assert match["both_within_tolerance"]
    assert result["precision"] == result["recall"] == 1
    assert result["precision_at_k"] == {"3": 1, "5": 1, "10": 1}


@pytest.mark.parametrize("start,end,count", [(15, 20, 1), (15.001, 20, 0), (30, 40, 0), (20, 30, 0)])
def test_threshold_and_no_overlap(start, end, count):
    assert run([gold()], [pred(start=start, end=end)])["matched_count"] == count


@pytest.mark.parametrize("start,end,start_ok,end_ok,mae", [
    (14, 20, False, True, 2), (10, 24, True, False, 2), (13, 23, True, True, 3),
])
def test_boundary_errors_are_separate_from_detection(start, end, start_ok, end_ok, mae):
    result = run([gold()], [pred(start=start, end=end)])
    assert result["matched_count"] == 1
    assert result["boundary_mae"] == mae
    assert result["mean_start_error"] == abs(start - 10)
    assert result["mean_end_error"] == abs(end - 20)
    assert result["boundary_start_within_tolerance_rate"] == float(start_ok)
    assert result["boundary_end_within_tolerance_rate"] == float(end_ok)
    assert result["boundary_both_within_tolerance_rate"] == float(start_ok and end_ok)


def test_duplicate_intervals_compete_and_best_iou_wins():
    result = run([gold()], [pred("weak", 11, 20), pred("z"), pred("a")])
    assert pair_ids(result) == [("g1", "a")]
    assert result["false_positive_count"] == 2
    assert result["precision"] == pytest.approx(1 / 3)


def test_two_golds_compete_for_one_prediction():
    result = run([gold("z"), gold("a")], [pred()])
    assert pair_ids(result) == [("a", "p1")]
    assert result["recall"] == 0.5
    assert result["false_negative_count"] == 1


def test_mae_breaks_equal_iou_before_id():
    # IoU 0.5 para ambos; a-enclosing tem MAE 5, z-inside tem MAE 2.5.
    result = run([gold()], [pred("a-enclosing", 5, 25), pred("z-inside", 10, 15)])
    assert pair_ids(result) == [("g1", "z-inside")]


def test_ambiguous_matching_prioritizes_cardinality_over_best_individual_iou():
    # A->p1 IoU1, A->p2 IoU.5, B->p1 IoU.6, B->p2 abaixo do limiar.
    result = run([gold("A", 10, 20), gold("B", 10, 16)],
                 [pred("p1", 10, 20), pred("p2", 15, 20)])
    assert pair_ids(result) == [("A", "p2"), ("B", "p1")]
    assert result["matched_count"] == 2


def test_determinism_under_permutations_and_exact_id_tie():
    golds, predictions = [gold("b"), gold("a")], [pred("z"), pred("x"), pred("y")]
    for gs in itertools.permutations(golds):
        for ps in itertools.permutations(predictions):
            result = run(list(gs), list(ps))
            assert pair_ids(result) == [("a", "x"), ("b", "y")]
            assert result["prediction_order"] == [p["prediction_id"] for p in ps]


def test_metrics_aggregate_only_matched_pairs():
    result = run([gold("a", 0, 10), gold("b", 20, 30), gold("c", 50, 60)],
                 [pred("x", 0, 10), pred("y", 24, 30), pred("z", 100, 110)])
    assert result["precision"] == result["recall"] == pytest.approx(2 / 3)
    assert result["false_positive_count"] == result["false_negative_count"] == 1
    assert result["mean_temporal_iou"] == 0.8
    assert result["mean_start_error"] == 2
    assert result["mean_end_error"] == 0
    assert result["boundary_mae"] == 1
    assert result["boundary_start_within_tolerance_rate"] == 0.5
    assert result["boundary_end_within_tolerance_rate"] == 1
    assert result["boundary_both_within_tolerance_rate"] == 0.5
    assert result["unmatched_gold_ids"] == ["c"]
    assert result["unmatched_prediction_ids"] == ["z"]


def test_precision_at_3_5_10_respects_order_not_metadata_score():
    predictions = [pred(str(i), i * 20, i * 20 + 10, metadata={"score": i}) for i in range(10)]
    golds = [gold(str(i), i * 20, i * 20 + 10) for i in (0, 2, 4, 9)]
    result = run(golds, predictions)
    assert result["precision_at_k"] == {"3": 2 / 3, "5": 3 / 5, "10": 4 / 10}
    assert result["prediction_order"] == [str(i) for i in range(10)]


def test_top_k_matches_prefix_independently_and_short_list_denominator():
    result = run([gold()], [pred("early", 11, 20), pred("later")], top_k=(1, 3, 5, 10))
    assert pair_ids(result) == [("g1", "later")]
    assert result["precision_at_k"] == {"1": 1, "3": 0.5, "5": 0.5, "10": 0.5}
    assert result["top_k_counts"]["10"] == {"matched_count": 1, "denominator": 2}


@pytest.mark.parametrize("ng,np,precision,recall", [(0, 1, 0, None), (1, 0, None, 0), (0, 0, None, None)])
def test_empty_sets(ng, np, precision, recall):
    result = run([gold()] * ng, [pred()] * np)
    assert result["matched_count"] == 0
    assert result["precision"] == precision
    assert result["recall"] == recall
    assert result["false_positive_count"] == np
    assert result["false_negative_count"] == ng
    for key in ("mean_temporal_iou", "mean_start_error", "mean_end_error", "boundary_mae",
                "boundary_start_within_tolerance_rate", "boundary_end_within_tolerance_rate",
                "boundary_both_within_tolerance_rate"):
        assert result[key] is None
    assert result["precision_at_k"] == {str(k): (0 if np else None) for k in (3, 5, 10)}


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), float("-inf"), "10", None, True])
@pytest.mark.parametrize("is_gold", [True, False])
def test_invalid_timestamp(bad, is_gold):
    g, p = gold(), pred()
    (g if is_gold else p)["expected_start" if is_gold else "start"] = bad
    with pytest.raises(ValueError):
        run([g], [p])


@pytest.mark.parametrize("start,end", [(20, 10), (10, 10)])
def test_inverted_or_empty_intervals(start, end):
    with pytest.raises(ValueError):
        run([gold(start=start, end=end)], [])
    with pytest.raises(ValueError):
        temporal_metrics(10, 20, start, end)


@pytest.mark.parametrize("golds,predictions", [([gold(), gold()], []), ([], [pred(), pred()])])
def test_duplicate_ids_rejected(golds, predictions):
    with pytest.raises(ValueError, match="ID duplicado"):
        run(golds, predictions)


@pytest.mark.parametrize("field", ["vod_id", "campaign_id"])
def test_no_match_across_vod_or_campaign(field):
    p = pred()
    p[field] = "different"
    assert run([gold()], [p])["matched_count"] == 0


def test_custom_configuration_and_zero_tolerance():
    result = run([gold()], [pred(start=16)], iou_threshold=0.4, boundary_tolerance=6, top_k=(1, 2))
    assert result["matched_count"] == 1
    assert result["boundary_both_within_tolerance_rate"] == 1
    assert run([gold()], [pred(start=16)], iou_threshold=0.41)["matched_count"] == 0
    assert run([gold()], [pred(start=10.01)], boundary_tolerance=0)["boundary_both_within_tolerance_rate"] == 0


@pytest.mark.parametrize("kwargs", [
    {"iou_threshold": 0}, {"iou_threshold": 1.01}, {"iou_threshold": float("nan")},
    {"boundary_tolerance": -1}, {"boundary_tolerance": True}, {"top_k": (0,)},
    {"top_k": (True,)}, {"top_k": (1, 1)}, {"top_k": (1.5,)}, {"metadata_filter": []},
])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        run([], [], **kwargs)


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(schema_version=True), lambda d: d.update(schema_version=2),
    lambda d: d.update(gold_cuts={}), lambda d: d.update(unknown=1),
    lambda d: d["gold_cuts"][0].update(would_clip=False),
    lambda d: d["gold_cuts"][0].update(gold_id=" "),
    lambda d: d["gold_cuts"][0].pop("creator"),
    lambda d: d["gold_cuts"][0].update(metadata=[]),
    lambda d: d["gold_cuts"][0].update(unknown=True),
])
def test_invalid_gold_contract(mutation):
    g, p = documents([gold()], [pred()])
    mutation(g)
    with pytest.raises(ValueError):
        evaluate(g, p)


def test_metadata_filter_prepares_future_priority_without_inventing_it():
    g, p = documents([gold()], [pred("b", metadata={"priority": "B"}),
                               pred("a", metadata={"priority": "A", "other": [1, 2]}), pred("unknown")])
    before = copy.deepcopy((g, p))
    result = evaluate(g, p, metadata_filter={"priority": "A"})
    assert result["input_prediction_count"] == 3
    assert result["prediction_count"] == 1
    assert result["prediction_order"] == ["a"]
    assert result["precision"] == 1
    assert (g, p) == before
    assert "publicable_rate" not in result
    assert evaluate(g, p, metadata_filter={"missing": None})["prediction_count"] == 0


def test_optimal_matching_against_exhaustive_oracle():
    # Independente do algoritmo de fluxo: enumera todas as associações de casos pequenos.
    rng = random.Random(42)
    for _ in range(35):
        gs = [gold(str(i), start := rng.randint(0, 12), start + rng.randint(5, 15)) for i in range(3)]
        ps = [pred(str(i), start := rng.randint(0, 12), start + rng.randint(5, 15)) for i in range(3)]
        edges = {}
        for i, g in enumerate(gs):
            for j, p in enumerate(ps):
                a, b, c, d = g["expected_start"], g["expected_end"], p["start"], p["end"]
                intersection = max(0, min(b, d) - max(a, c))
                iou = Fraction(intersection, b - a + d - c - intersection)
                if iou >= Fraction(1, 2):
                    edges[i, j] = (iou, Fraction(abs(a - c) + abs(b - d), 2))
        objectives = []
        for assignment in itertools.product((-1, 0, 1, 2), repeat=3):
            pairs = tuple((i, j) for i, j in enumerate(assignment) if j >= 0)
            if len({j for _, j in pairs}) != len(pairs) or any(pair not in edges for pair in pairs):
                continue
            objectives.append((-len(pairs), -sum(edges[p][0] for p in pairs),
                               sum(edges[p][1] for p in pairs), pairs))
        expected = min(objectives)[3]
        assert pair_ids(run(gs, ps, top_k=())) == [(str(i), str(j)) for i, j in expected]


def test_sample_cli_is_offline_deterministic_and_read_only(tmp_path):
    # Executa sem site-packages, fora do diretório do produto, sem importar infraestrutura.
    import shutil
    package = tmp_path / "miner"
    package.mkdir()
    for name in ("__init__.py", "benchmark.py"):
        shutil.copy2(ROOT / "miner" / name, package / name)
    samples = ROOT / "benchmarks/gold/samples"
    command = [sys.executable, "-S", "-m", "miner.benchmark", "--gold", str(samples / "gold.json"),
               "--predictions", str(samples / "predictions.json")]
    before = {p.name: p.read_bytes() for p in samples.glob("*.json")}
    outputs = [subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True).stdout
               for _ in range(2)]
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["mean_temporal_iou"] == pytest.approx(41 / 45)
    assert {p.name: p.read_bytes() for p in samples.glob("*.json")} == before
    assert not (tmp_path / "data").exists()
    invalid = subprocess.run(command + ["--iou-threshold", "0"], cwd=tmp_path, capture_output=True, text=True)
    assert invalid.returncode == 2
    assert not invalid.stdout


def test_schema_and_sample_contract():
    schema = json.loads((ROOT / "benchmarks/gold/schema.json").read_text(encoding="utf-8"))
    samples = ROOT / "benchmarks/gold/samples"
    g = json.loads((samples / "gold.json").read_text(encoding="utf-8"))
    p = json.loads((samples / "predictions.json").read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == g["schema_version"] == 1
    assert set(schema["required"]) == set(g)
    cut_schema = schema["properties"]["gold_cuts"]["items"]
    assert set(cut_schema["required"]) <= set(g["gold_cuts"][0])
    assert cut_schema["properties"]["would_clip"]["const"] is True
    assert evaluate(g, p)["matched_count"] == 1
