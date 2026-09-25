"""Deterministic, contextual VOD selection. No quotas or learned models."""

import re
import unicodedata

import numpy as np

from miner.rules import candidate_eligibility

MODES = {"conservador": 74, "equilibrado": 56, "agressivo": 38}
VERSION = "vod-context-1"
SIGNALS = {
    "hook": (18, ("olha isso", "olha so", "presta atencao", "sabe o que", "vou contar", "voces nao")),
    "reação": (18, ("meu deus", "nao acredito", "nao acreditei", "que isso", "impossivel", "foi loucura")),
    "humor": (20, ("haha", "kkkk", "risada", "engracado", "piada", "rindo", "zoeira")),
    "rage": (14, ("porra", "caralho", "deu ruim", "merda", "se fudeu", "muito ruim", "absurdo")),
    "storytelling": (
        18,
        ("vou contar", "aconteceu", "naquele dia", "historia", "eu falei", "eu fiquei", "eu apertei"),
    ),
    "opinião forte": (
        18,
        ("na minha opiniao", "eu discordo", "nao faz sentido", "ridiculo", "inaceitavel", "pior", "melhor"),
    ),
    "mudança emocional": (
        12,
        ("mas agora", "de repente", "do nada", "fiquei nervoso", "fiquei feliz", "tava tranquilo"),
    ),
    "conclusão / payoff": (
        18,
        (
            "no final",
            "foi por isso",
            "por isso que",
            "consegui",
            "ganhei",
            "deu certo",
            "moral da historia",
            "acabou",
            "resumindo",
        ),
    ),
}


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def tags(text):
    text = normalized(text)
    found = {
        key
        for key, (_, words) in SIGNALS.items()
        if any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words)
    }
    if "?" in text:
        found.add("pergunta")
    return found


def overlap(a, b):
    return max(0, min(a["end"], b["end"]) - max(a["start"], b["start"])) / max(
        0.01, min(a["end"] - a["start"], b["end"] - b["start"])
    )


def group_windows(windows):
    """Merge competing windows, without chaining an entire live into one clip."""
    selected = []
    for item in sorted(windows, key=lambda w: (w["start"], w["end"])):
        p = dict(item)
        if selected:
            last = selected[-1]
            same = overlap(last, p) >= 0.25
            nearby = (
                0 <= p["start"] - last["end"] <= 6
                and not last.get("closed")
                and bool(set(last.get("tags", [])) & set(p.get("tags", [])))
            )
            if same or nearby:
                if max(last["end"], p["end"]) - last["start"] <= 150:
                    last["end"] = max(last["end"], p["end"])
                    last["tags"] = set(last.get("tags", [])) | set(p.get("tags", []))
                    last["closed"] = p.get("closed", False) or last.get("closed", False)
                # Beyond the context safety limit, retain the earlier event rather than duplicate it.
                continue
        selected.append(p)
    return selected


def detect(segments, energies, duration, interval=None, mode="equilibrado"):
    # interval is accepted for older callers; periodic filler windows are no longer generated.
    if mode not in MODES:
        raise ValueError("Modo de garimpo inválido.")
    if duration <= 0:
        return []
    speech = []
    seen = set()
    for s in sorted(segments, key=lambda s: (s["start"], s["end"])):
        key = (s["start"], s["end"], normalized(s["text"]))
        if key in seen or s["end"] <= s["start"] or s["start"] >= duration:
            continue
        seen.add(key)
        speech.append(
            {**s, "start": max(0, s["start"]), "end": min(duration, s["end"]), "tags": tags(s["text"])}
        )
    windows = []
    anchors = [i for i, s in enumerate(speech) if s["tags"]]
    groups = []
    for i in anchors:
        if groups:
            first, last = speech[groups[-1][0]], speech[groups[-1][-1]]
            connected = speech[i]["start"] - last["end"] <= 18
            new_event = "conclusão / payoff" in last["tags"] and bool(
                speech[i]["tags"] & {"hook", "storytelling"}
            )
            if connected and not new_event and speech[i]["end"] - first["start"] <= 95:
                groups[-1].append(i)
                continue
        groups.append([i])
    for group in groups:
        left, right = group[0], group[-1]
        start = speech[left]["start"]
        # Carry enough preceding speech to avoid opening on a dangling reaction.
        while (
            left > 0
            and start - speech[left - 1]["start"] <= 14
            and speech[left]["start"] - speech[left - 1]["end"] <= 4
        ):
            if "conclusão / payoff" in speech[left - 1]["tags"]:
                break
            left -= 1
        closed = "conclusão / payoff" in speech[right]["tags"]
        end_anchor = speech[right]["end"]
        # Follow development to payoff, pause or completed utterance. Never force 35 seconds.
        while not closed and right + 1 < len(speech):
            nxt = speech[right + 1]
            if (
                nxt["start"] - speech[right]["end"] > 5
                or nxt["end"] - end_anchor > 35
                or nxt["end"] - speech[left]["start"] > 120
                or "hook" in nxt["tags"]
            ):
                break
            right += 1
            closed = "conclusão / payoff" in nxt["tags"]
            if nxt["text"].rstrip().endswith((".", "!")) and nxt["end"] - end_anchor >= 7:
                break
        windows.append(
            {
                "start": max(0, speech[left]["start"] - 1),
                "end": min(duration, speech[right]["end"] + 1.5),
                "tags": set().union(*(s["tags"] for s in speech[left : right + 1])),
                "closed": closed,
            }
        )
    values = np.asarray(energies, dtype=float)
    # Audio alone is a low-priority exploratory signal in Aggressive only.
    if mode == "agressivo" and len(values):
        threshold = max(0.03, float(np.median(values)) * 4, float(np.percentile(values, 97)))
        for index in np.flatnonzero(values > threshold):
            if any(s["start"] - 5 <= index <= s["end"] + 5 for s in speech):
                continue
            windows.append(
                {
                    "start": max(0, float(index) - 3),
                    "end": min(duration, float(index) + 5),
                    "tags": {"áudio isolado"},
                    "closed": False,
                }
            )
    result = []
    for p in group_windows(windows):
        rows = [s for s in speech if s["start"] < p["end"] and s["end"] > p["start"]]
        labels = set(p["tags"])
        if "pergunta" in labels:
            for a, b in zip(rows, rows[1:], strict=False):
                if (
                    "?" in a["text"]
                    and "?" not in b["text"]
                    and len(b["text"].split()) >= 4
                    and b["start"] - a["end"] <= 4
                ):
                    labels.add("possível pergunta/resposta")
                    break
        score = 12 + sum(SIGNALS[t][0] for t in labels if t in SIGNALS)
        reasons = [t for t in SIGNALS if t in labels]
        penalties = []
        if "possível pergunta/resposta" in labels:
            score += 18
            reasons.append("possível pergunta/resposta (falas consecutivas)")
        if "reação" in labels and labels & {"humor", "rage", "mudança emocional"}:
            score += 7
        text = " ".join(s["text"] for s in rows)
        words = normalized(text).split()
        spoken = sum(max(0, min(p["end"], s["end"]) - max(p["start"], s["start"])) for s in rows)
        span = p["end"] - p["start"]
        block = values[int(p["start"]) : int(p["end"])]
        if len(block) and max(block) > max(0.03, float(np.median(values)) * 2):
            score += 3
            reasons.append("energia reforça o contexto (+3 no máximo)")
        if not p["closed"]:
            score -= 10
            penalties.append("sem conclusão/payoff explícito")
        if len(words) < 9 or (
            rows and re.match(r"^(isso|ele|ela|ai|esse|essa)\b", normalized(rows[0]["text"]))
        ):
            score -= 10
            penalties.append("contexto limitado")
        if spoken / max(span, 1) < 0.35 or (len(block) and np.mean(block < 0.004) > 0.5):
            score -= 14
            penalties.append("silêncio ou pouca fala")
        unclear = any(
            w in normalized(text) for w in ("inaudivel", "incompreensivel", "[musica]", "[ruido]", "♪")
        )
        repeated = len(words) > 18 and len(set(words)) / len(words) < 0.32
        if unclear or repeated:
            score -= 24
            penalties.append("fala incerta/repetitiva ou possível música/ruído")
        if rows and any(s.get("avg_logprob", 0) < -1 or s.get("no_speech_prob", 0) > 0.7 for s in rows):
            score -= 18
            penalties.append("baixa confiança da transcrição")
        audio_only = labels == {"áudio isolado"}
        if audio_only:
            score = 12
            reasons = ["pico isolado: exploração de baixa prioridade; pode ser música/barulho"]
        elif score < MODES[mode]:
            continue
        result.append(
            {
                "start": round(p["start"], 2),
                "end": round(p["end"], 2),
                "score": min(100, max(0, round(score))),
                "reason": "; ".join(reasons)
                + (". Penalizações: " + "; ".join(penalties) if penalties else ""),
                "summary": text[:320] or "Sem fala transcrita. Revisar imagem e áudio.",
                "eligibility_review": candidate_eligibility(text),
                "mode": mode,
                "detector_version": VERSION,
            }
        )
    return sorted(result, key=lambda p: (-p["score"], p["start"]))
