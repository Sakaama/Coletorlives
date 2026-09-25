"""Benchmark temporal offline. Não importa nem modifica o pipeline operacional."""

import argparse
import json
import math
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


SCHEMA_VERSION = 1
DEFAULT_IOU_THRESHOLD = 0.50
DEFAULT_BOUNDARY_TOLERANCE = 3.0
DEFAULT_TOP_K = (3, 5, 10)


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: esperado número finito não negativo em segundos")
    if value < 0 or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError(f"{label}: esperado número finito não negativo")
    return Fraction(str(value))


def _interval(start, end):
    start, end = _number(start, "start"), _number(end, "end")
    if end <= start:
        raise ValueError("Intervalo inválido: end deve ser maior que start")
    return start, end


def _measure(g_start, g_end, p_start, p_end):
    intersection = max(Fraction(0), min(g_end, p_end) - max(g_start, p_start))
    union = g_end - g_start + p_end - p_start - intersection
    start_error, end_error = abs(g_start - p_start), abs(g_end - p_end)
    return dict(intersection=intersection, union=union, temporal_iou=intersection / union,
                start_error=start_error, end_error=end_error, boundary_mae=(start_error + end_error) / 2)


def temporal_metrics(g_start, g_end, p_start, p_end):
    """Métricas de dois intervalos absolutos; entradas inválidas geram ValueError."""
    values = _measure(*_interval(g_start, g_end), *_interval(p_start, p_end))
    return {key: float(value) for key, value in values.items()}


@dataclass(frozen=True)
class _Cut:
    id: str
    vod_id: str
    campaign_id: str
    start: Fraction
    end: Fraction
    metadata: dict


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: esperado texto não vazio")
    return value


def _load_document(document, gold):
    key = "gold_cuts" if gold else "predictions"
    if not isinstance(document, dict) or set(document) != {"schema_version", key}:
        raise ValueError(f"Documento deve conter somente schema_version e {key}")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("schema_version não suportada (esperado 1)")
    if not isinstance(document[key], list):
        raise ValueError(f"{key}: esperado array")
    id_key = "gold_id" if gold else "prediction_id"
    start_key, end_key = ("expected_start", "expected_end") if gold else ("start", "end")
    required = {id_key, "vod_id", "campaign_id", start_key, end_key}
    allowed = required | {"metadata", "creator"}
    if gold:
        required |= {"creator", "would_clip"}
        allowed |= {"would_clip", "content_type", "priority", "notes"}
    cuts, ids = [], set()
    for entry in document[key]:
        if not isinstance(entry, dict) or not required <= set(entry) or set(entry) - allowed:
            raise ValueError(f"Campos inválidos em {key}; obrigatórios: {sorted(required)}")
        cut_id = _text(entry[id_key], id_key)
        if cut_id in ids:
            raise ValueError(f"ID duplicado: {cut_id}")
        ids.add(cut_id)
        for field in ("creator", "content_type", "priority", "notes"):
            if field in entry:
                _text(entry[field], field)
        if gold and entry["would_clip"] is not True:
            raise ValueError("Gold exige would_clip: true (EU CORTARIA ESTE TRECHO)")
        metadata = entry.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("metadata deve ser objeto")
        cuts.append(_Cut(cut_id, _text(entry["vod_id"], "vod_id"),
                         _text(entry["campaign_id"], "campaign_id"),
                         *_interval(entry[start_key], entry[end_key]), metadata))
    return cuts


@dataclass
class _Edge:
    target: int
    reverse: int
    capacity: int
    cost: tuple


def _optimal_matches(golds, predictions, threshold):
    """Fluxo máximo de custo mínimo, com custos lexicográficos exatos.

    Prioridades: cardinalidade, soma IoU, soma MAE, conjunto de pares por ID.
    Bellman-Ford também permite desfazer associações anteriores na rede residual.
    """
    golds = sorted(golds, key=lambda cut: cut.id)
    predictions = sorted(predictions, key=lambda cut: cut.id)
    pairs = []
    for gi, gold in enumerate(golds):
        for pi, pred in enumerate(predictions):
            if (gold.vod_id, gold.campaign_id) != (pred.vod_id, pred.campaign_id):
                continue
            metrics = _measure(gold.start, gold.end, pred.start, pred.end)
            if metrics["temporal_iou"] >= threshold:
                pairs.append((gi, pi, metrics))
    source, pred_offset = 0, 1 + len(golds)
    sink = pred_offset + len(predictions)
    graph = [[] for _ in range(sink + 1)]
    zero = (Fraction(0), Fraction(0), 0)

    def add_edge(a, b, cost):
        forward = _Edge(b, len(graph[b]), 1, cost)
        graph[a].append(forward)
        graph[b].append(_Edge(a, len(graph[a]) - 1, 0, tuple(-c for c in cost)))
        return forward

    for gi in range(len(golds)):
        add_edge(source, gi + 1, zero)
    for pi in range(len(predictions)):
        add_edge(pred_offset + pi, sink, zero)
    tracked = []
    for index, (gi, pi, metrics) in enumerate(pairs):
        # Um bit por aresta: em empate exato, prefere o primeiro par por IDs.
        cost = (-metrics["temporal_iou"], metrics["boundary_mae"], -(1 << (len(pairs) - index - 1)))
        edge = add_edge(gi + 1, pred_offset + pi, cost)
        tracked.append((edge, golds[gi], predictions[pi], metrics))
    while True:
        distances, previous = [None] * len(graph), [None] * len(graph)
        distances[source] = zero
        for _ in range(len(graph) - 1):
            changed = False
            for node, edges in enumerate(graph):
                if distances[node] is None:
                    continue
                for ei, edge in enumerate(edges):
                    if not edge.capacity:
                        continue
                    cost = tuple(a + b for a, b in zip(distances[node], edge.cost, strict=True))
                    if distances[edge.target] is None or cost < distances[edge.target]:
                        distances[edge.target] = cost
                        previous[edge.target] = (node, ei)
                        changed = True
            if not changed:
                break
        if previous[sink] is None:
            break
        node = sink
        while node != source:
            parent, ei = previous[node]
            edge = graph[parent][ei]
            edge.capacity -= 1
            graph[node][edge.reverse].capacity += 1
            node = parent
    return [(g, p, m) for edge, g, p, m in tracked if edge.capacity == 0]


def evaluate(gold_document, prediction_document, *, iou_threshold=DEFAULT_IOU_THRESHOLD,
             boundary_tolerance=DEFAULT_BOUNDARY_TOLERANCE, top_k=DEFAULT_TOP_K, metadata_filter=None):
    """Compara documentos sem efeitos colaterais; ordem de predictions define Top-K.

    metadata_filter faz igualdade exata por campo (AND), sem reclassificar/reranquear.
    Valores indefinidos (denominador zero ou nenhum match) são None no Python/null no JSON.
    """
    threshold = _number(iou_threshold, "iou_threshold")
    if not 0 < threshold <= 1:
        raise ValueError("iou_threshold deve estar em (0, 1]")
    tolerance = _number(boundary_tolerance, "boundary_tolerance")
    top_k = tuple(top_k)
    if any(type(k) is not int or k <= 0 for k in top_k) or len(top_k) != len(set(top_k)):
        raise ValueError("top_k deve conter inteiros positivos distintos")
    if metadata_filter is not None and not isinstance(metadata_filter, dict):
        raise ValueError("metadata_filter deve ser objeto")
    golds = _load_document(gold_document, True)
    predictions = _load_document(prediction_document, False)
    input_count = len(predictions)
    if metadata_filter is not None:
        predictions = [p for p in predictions if all(k in p.metadata and p.metadata[k] == v
                                                     for k, v in metadata_filter.items())]
    matched = _optimal_matches(golds, predictions, threshold)
    n, ng, np = len(matched), len(golds), len(predictions)

    def ratio(numerator, denominator):
        return numerator / denominator if denominator else None

    def mean(key):
        return float(sum(m[key] for _, _, m in matched) / n) if n else None

    matches = []
    for g, p, m in matched:
        start_ok, end_ok = m["start_error"] <= tolerance, m["end_error"] <= tolerance
        matches.append(dict(gold_id=g.id, prediction_id=p.id,
                            **{key: float(value) for key, value in m.items()},
                            start_within_tolerance=start_ok, end_within_tolerance=end_ok,
                            both_within_tolerance=start_ok and end_ok))
    matched_g = {g.id for g, _, _ in matched}
    matched_p = {p.id for _, p, _ in matched}
    top_counts = {str(k): len(_optimal_matches(golds, predictions[:k], threshold)) for k in top_k}
    return dict(
        schema_version=SCHEMA_VERSION,
        config=dict(iou_threshold=float(threshold), boundary_tolerance=float(tolerance),
                    top_k=list(top_k), metadata_filter=metadata_filter),
        input_prediction_count=input_count, gold_count=ng, prediction_count=np, matched_count=n,
        recall=ratio(n, ng), precision=ratio(n, np), false_positive_count=np - n, false_negative_count=ng - n,
        mean_temporal_iou=mean("temporal_iou"), mean_start_error=mean("start_error"),
        mean_end_error=mean("end_error"), boundary_mae=mean("boundary_mae"),
        boundary_start_within_tolerance_rate=ratio(sum(m["start_within_tolerance"] for m in matches), n),
        boundary_end_within_tolerance_rate=ratio(sum(m["end_within_tolerance"] for m in matches), n),
        boundary_both_within_tolerance_rate=ratio(sum(m["both_within_tolerance"] for m in matches), n),
        precision_at_k={str(k): ratio(top_counts[str(k)], min(k, np)) for k in top_k},
        top_k_counts={str(k): dict(matched_count=top_counts[str(k)], denominator=min(k, np)) for k in top_k},
        matches=matches, unmatched_gold_ids=sorted(g.id for g in golds if g.id not in matched_g),
        unmatched_prediction_ids=[p.id for p in predictions if p.id not in matched_p],
        prediction_order=[p.id for p in predictions],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--iou-threshold", type=float, default=DEFAULT_IOU_THRESHOLD)
    parser.add_argument("--boundary-tolerance", type=float, default=DEFAULT_BOUNDARY_TOLERANCE)
    parser.add_argument("--top-k", nargs="+", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--metadata-filter", type=json.loads, help='Objeto JSON, ex.: {"priority":"A"}')
    args = parser.parse_args(argv)
    try:
        gold = json.loads(args.gold.read_text(encoding="utf-8-sig"))
        predictions = json.loads(args.predictions.read_text(encoding="utf-8-sig"))
        result = evaluate(gold, predictions, iou_threshold=args.iou_threshold,
                          boundary_tolerance=args.boundary_tolerance, top_k=args.top_k,
                          metadata_filter=args.metadata_filter)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
