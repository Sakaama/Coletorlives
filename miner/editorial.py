"""Local, explainable relational review over cached speech. No model or candidate quota."""
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter

VERSION = "editorial-relations-1"
CLASSES = ("RECOMENDADO", "BOM", "TALVEZ", "FRACO")


def norm(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def has(pattern, text):
    return bool(re.search(pattern, norm(text)))


def relations(rows, candidate):
    """Link a premise to a consequence/obstacle in nearby speech, anchored in this candidate."""
    result = []
    for i, a in enumerate(rows):
        for b in rows[max(0, i-16):i+17]:
            if abs(b["start"] - a["start"]) > 40:
                continue
            if not (candidate["start"]-2 <= a["start"] <= candidate["end"]):
                continue
            ta, tb = a["text"], b["text"]
            rule = None
            # Experience/underdog -> concrete achievement, including preceding context.
            experience = has(r"(?<!\d)(?:[0-3]|um|dois|tres)\s+anos|iniciante|primeira vez|pouca experiencia|comec(?:ei|ou) a jogar", ta) and has(r"jog|experiencia|iniciante|comec|pratica", ta)
            experience = experience and has(r"\b(?:joga|jogando|tem|tenho|ha|comec\w*|iniciante|primeira vez|pouca experiencia)\b", ta)
            achievement = has(r"(?:cheg|est|tav|no|na|pra|para).{0,22}\bfinal\b|campeao|classific(?:ou|ado)|consegui(?:u)? vencer", tb)
            achievement = achievement and not has(r"nao (?:cheg|foi|est|consegui)|nunca (?:cheg|foi|consegui)", tb)
            if experience and achievement:
                rule = (94, "COMPETITIVO", "Pouca experiência ligada a uma conquista competitiva.", "POUCA EXPERIÊNCIA, UMA GRANDE CONQUISTA")
            role = has(r"\b(?:armador|capitao|lider|treinador|responsavel|organizador)\b", ta) and has(r"\b(?:era|sou|fui|e|como|nosso|meu)\b", ta)
            obstacle = has(r"sem (?:call|comunicacao|apoio|treino)|nao (?:tinha|consegui|conseguia|conseguiu)|falt(?:ou|ava) (?:call|comunicacao|apoio)", tb)
            if role and obstacle:
                rule = (92, "BASTIDOR", "Responsabilidade na equipe ligada a uma dificuldade concreta; bastidor com contexto próprio.", "A RESPONSABILIDADE E O PROBLEMA DENTRO DO TIME")
            if has(r"(?:perdendo|perdia|desvantagem|ia perder|quase perdi)", ta) and has(r"(?:viramos|virou|virei|ganhei|vencemos|venci|conseguimos)", tb) and b["start"] >= a["start"]:
                rule = (92, "COMPETITIVO", "Desvantagem seguida de virada/conquista, com progressão temporal.", "DA DESVANTAGEM À VIRADA")
            if has(r"(?:perdemos|perdi|ganhamos|ganhei|derrota|vitoria|nao consegui)", ta) and has(r"(?:porque|por causa|faltou|sem comunicacao|a estrategia)", tb):
                rule = rule or (85, "BASTIDOR", "Resultado ligado à sua causa ou estratégia, em falas próximas.", "O QUE EXPLICA ESSE RESULTADO")
            if has(r"(?:confesso|nunca contei|ninguem sabe|a verdade e|nos bastidores)", ta) and len(tb.split()) >= 8 and b["start"] >= a["start"]:
                rule = rule or (84, "STORYTELLING", "Revelação acompanhada de desenvolvimento; não exige punchline.", "A HISTÓRIA POR TRÁS DO MOMENTO")
            if has(r"(?:minha opiniao|eu acho|eu discordo|e um absurdo)", ta) and has(r"(?:porque|por isso|o problema|por exemplo)", tb) and len(tb.split()) >= 7:
                rule = rule or (79, "OPINIÃO", "Posicionamento acompanhado de argumento, além de reação isolada.", "A OPINIÃO E O MOTIVO")
            if b["start"] >= a["start"]:
                if has(r"(?:vou tentar|tentei|desafio|essa jogada)", ta) and has(r"(?:consegui|ganhei|venci|errei|falhei|perdi)", tb):
                    failed = has(r"(?:errei|falhei|perdi)", tb)
                    rule = rule or (86, "FAIL" if failed else "GAMEPLAY", "Tentativa seguida de resultado concreto na ação.", "A TENTATIVA E O RESULTADO")
                if has(r"(?:abri|abrindo|abrir).{0,20}(?:pack|pacote|carta|caixa)", ta) and has(r"(?:veio|saiu|tirei|raro|lendario)", tb):
                    rule = rule or (87, "REVEAL", "Abertura ligada ao item revelado, com progressão compreensível.", "O QUE SAIU DESSA ABERTURA")
                if has(r"(?:assistindo (?:esse |o |um )?video|reagindo|react)", ta) and has(r"(?:nao acredito|meu deus|olha isso)", tb):
                    rule = rule or (78, "REACT", "Conteúdo assistido seguido de reação explícita; conferir a imagem.", "A REAÇÃO AO VÍDEO")
            if rule:
                result.append({"strength": rule[0], "type": rule[1], "reason": rule[2], "title": rule[3],
                               "start": min(a["start"], b["start"]), "end": max(a["end"], b["end"]),
                               "evidence": [a, b] if a != b else [a]})
    return sorted(result, key=lambda r: (-r["strength"], r["end"]-r["start"]))


def review(candidate, segments, duration):
    original_start, original_end = candidate["start"], candidate["end"]
    rows = [s for s in segments if s["end"] > original_start-40 and s["start"] < original_end+15]
    own = [s for s in rows if s["end"] > original_start and s["start"] < original_end]
    text = " ".join(s["text"] for s in own) or candidate.get("summary", "")
    words = norm(text).split()
    repetition = 1 - len(set(words)) / max(1, len(words))
    links = relations(rows, candidate)
    best = links[0] if links else None
    visual = candidate.get("visual_activity_score") or 0
    coverage = min(1, sum(max(0, min(s["end"], original_end)-max(s["start"], original_start)) for s in own) / max(1, original_end-original_start))
    payoff = 80 if has(r"(?:ganhei|(?<!nao )\bconsegui\b|deu certo|no final|por isso|resolvi)", text) else 25
    context = 85 if best else 55 if len(words) >= 25 else 25
    story = best["strength"] if best else 45 if len(words) >= 30 else 20
    hook = 85 if best else 60 if has(r"(?:olha isso|meu deus|nao acredito|sabe o que)", text) else 35
    standalone = max(15, context - (10 if repetition > .68 else 0))
    editability = min(100, 45 + visual*.35 + (15 if best else 0))
    score = (best["strength"]-8 + visual*.05 if best else
             18 + context*.2 + hook*.15 + payoff*.1 + editability*.1 + candidate.get("score", 0)*.08)
    if not own:
        score = min(55, score)
    if coverage < .25 and own and not best:
        score -= 10
    # ASR repetition is a warning, not a veto over a grounded semantic relationship.
    if repetition > .7:
        score -= 5 if best else 12
    score = round(max(0, min(100, score)))
    classification = "RECOMENDADO" if score >= 82 else "BOM" if score >= 68 else "TALVEZ" if score >= 48 else "FRACO"
    start, end = original_start, original_end
    if best:
        start, end = max(0, best["start"]-2), min(duration, best["end"]+4)
        if end-start < 20:
            end = min(duration, start+20)
        # Finish the current spoken sentence; never enforce a hard 60s cut.
        crossing = [s for s in rows if s["start"] < end < s["end"]]
        if crossing:
            end = min(duration, max(s["end"] for s in crossing))
    elif original_end-original_start > 60 and own:
        # No reliable narrative core: preserve the original instead of arbitrary shortening.
        start, end = original_start, original_end
    content_type = best["type"] if best else "RAGE" if has(r"\b(?:porra|caralho|absurdo)\b", text) else "REAÇÃO" if hook >= 60 else "TALKING"
    warnings = []
    if not own:
        warnings.append("Sem transcrição contextual em cache; avaliação limitada ao resumo.")
    if repetition > .6:
        warnings.append("Transcrição repetitiva/possivelmente imprecisa; conferir áudio.")
    if not best:
        warnings.append("Não foi possível comprovar uma relação narrativa forte no texto disponível.")
    return {"version": VERSION, "editorial_score": score, "classification": classification, "content_type": content_type,
            "hook_score": hook, "story_score": story, "visual_score": round(visual), "context_score": context,
            "payoff_score": payoff, "editability_score": round(editability), "standalone_score": standalone,
            "original_start": original_start, "original_end": original_end, "suggested_start": round(start, 3),
            "suggested_end": round(end, 3), "suggested_duration": round(end-start, 3),
            "title": best["title"] if best else "", "title_alt": ('“'+best["evidence"][0]["text"][:100]+'”') if best else "",
            "hook": best["evidence"][0]["text"] if best else (own[0]["text"] if own else text[:160]),
            "reason": best["reason"] if best else "Sinais isolados ainda precisam de avaliação humana; score antigo não basta.",
            "evidence": best["evidence"] if best else [], "warnings": warnings,
            "layout": "VISUAL" if visual >= 40 else "TALKING", "difficulty": "FÁCIL" if visual >= 40 and best else "MÉDIA" if visual >= 40 else "MAIOR — pode exigir apoio visual"}


def cached_segments(store, vod):
    directory = store.root / "campaigns" / vod["campaign"] / "transcripts" / vod["id"]
    roots = list((directory / "remote").glob("*/result.json")) if vod.get("remote") else list((directory / "long").glob("*/result.json"))
    model = vod.get("transcript_model") or "base"
    if roots:
        root = max(roots, key=lambda p: p.stat().st_mtime_ns).parent
        chunks = []
        for path in root.glob(f"speech_*/{model}/transcript.json"):
            _, a, b = path.parent.parent.name.split("_")
            chunks.append((float(b)-float(a), float(a), path))
        rows, covered = [], []
        for length, offset, path in sorted(chunks, reverse=True):
            for row in json.loads(path.read_text(encoding="utf-8")):
                s = {**row, "start": row["start"]+offset, "end": row["end"]+offset}
                if not any(a <= (s["start"]+s["end"])/2 < b for a,b in covered):
                    rows.append(s)
            covered.append((offset, offset+length))
        return sorted(rows, key=lambda s: s["start"])
    path = directory / model / "transcript.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def group_refined(candidates, tolerance=3.0):
    """Presentation-only grouping of candidates whose editorial suggestions converge to the same moment.

    Two NOVO candidates from the same VOD are considered editorially redundant when their
    ``editorial_review.suggested_start`` and ``suggested_end`` both fall within *tolerance* seconds
    of each other — meaning the reviewer would point them to the same cut.

    Args:
        candidates: list of candidate dicts as returned by ``store.candidates()``.
        tolerance:  seconds within which suggested_start and suggested_end are considered
                    identical editorial suggestions.  Default 3.0 s covers minor Whisper
                    boundary variation.  Pass 0.5 to restore the original strict behaviour
                    (only candidates with essentially the same suggestion are merged).

    Returns:
        New list (originals are never mutated) with ``refined_duplicate_of`` and
        ``refined_alternatives`` annotation fields added for presentation only.
    """
    rows = [{**c, "refined_alternatives": [], "refined_duplicate_of": None} for c in candidates]
    representatives = []
    for c in sorted(rows, key=lambda r: (-r.get("editorial_review", {}).get("editorial_score", r.get("score", 0)), r["start"], r["id"])):
        review = c.get("editorial_review", {})
        if (c.get("archived") or c.get("status", "NOVO") != "NOVO" or c.get("editorial_package")
                or review.get("classification") not in ("RECOMENDADO", "BOM")
                or "suggested_start" not in review or "suggested_end" not in review):
            continue
        match = next((old for old in representatives if old["vod_id"] == c["vod_id"] and
                      abs(old["editorial_review"]["suggested_start"] - review["suggested_start"]) <= tolerance and
                      abs(old["editorial_review"]["suggested_end"] - review["suggested_end"]) <= tolerance), None)
        if match:
            c["refined_duplicate_of"] = match["id"]
            match["refined_alternatives"].append({k: c[k] for k in ("id", "start", "end")})
        else:
            representatives.append(c)
    return rows


def review_vod(store, vid, check=lambda: None):
    started = time.perf_counter()
    vod = store.get_vod(vid)
    segments = cached_segments(store, vod)
    candidates = store.candidates(vid)
    updates, counts = [], Counter()
    for candidate in candidates:
        check()
        relevant = [s for s in segments if s["end"] > candidate["start"]-40 and s["start"] < candidate["end"]+15]
        signature = hashlib.sha256(json.dumps([VERSION, relevant, candidate["start"], candidate["end"], candidate["score"], candidate.get("visual_activity_score"), candidate.get("summary")], sort_keys=True).encode()).hexdigest()
        value = candidate.get("editorial_review", {})
        if value.get("signature") != signature:
            value = {**review(candidate, relevant, vod["duration"]), "signature": signature}
            updates.append((candidate["id"], value))
        counts[value["classification"]] += 1
    check()
    with store.connect() as db:
        for cid, value in updates:
            data = json.loads(db.execute("SELECT data FROM candidates WHERE id=?", (cid,)).fetchone()[0])
            data["editorial_review"] = value
            db.execute("UPDATE candidates SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), cid))
    elapsed = time.perf_counter()-started
    store.update_vod(vid, reviewer_metrics={"seconds": elapsed, "reviewed": len(candidates), "cached": len(candidates)-len(updates), "counts": dict(counts), "version": VERSION})
    return {"seconds": elapsed, "counts": dict(counts), "cached": len(candidates)-len(updates)}
