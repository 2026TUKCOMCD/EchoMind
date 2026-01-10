# match.py
# -*- coding: utf-8 -*-

"""
DB-style matching (LLM-free): 1 target vs N candidates

Inputs:
- --target: JSON output from main.py (single user vector)
- --candidates: JSON with {"candidates":[...]} from DB export

Output:
- Top-K candidate matches with scores

Usage:
  python match.py --target target.json --candidates candidates.json --out matches.json --topk 10
  python match.py --target target.json --candidates candidates.json --min_score 0.3
"""

import argparse
import json
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple


def safe_log1p(x: Optional[float]) -> float:
    if x is None or x < 0:
        return 0.0
    return math.log1p(x)


def mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 1.0
    m = sum(values) / len(values)
    var = sum((v - m) ** 2 for v in values) / max(1, len(values) - 1)
    sd = math.sqrt(var) if var > 1e-12 else 1.0
    return m, sd


def zscore(x: float, m: float, sd: float) -> float:
    return (x - m) / sd if sd != 0 else 0.0


def cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def build_raw_vector(u: Dict) -> List[float]:
    r = u["rhythm"]
    l = u["language"]
    return [
        float(r.get("avg_msg_len", 0.0)),
        float(r.get("question_ratio", 0.0)),
        float(l.get("honorific_ratio", 0.0)),
        float(l.get("casual_ratio", 0.0)),
        float(l.get("emoji_ratio", 0.0)),
        float(l.get("hedge_ratio", 0.0)),
        safe_log1p(r.get("avg_gap_sec", None)),
    ]


def standardize_with_population(target_vec: List[float], cand_vecs: List[List[float]]) -> Tuple[List[float], List[List[float]]]:
    # z-score using population = candidates + target (stability)
    all_vecs = cand_vecs + [target_vec]
    cols = list(zip(*all_vecs))
    stats = [mean_std(list(col)) for col in cols]

    def z(v: List[float]) -> List[float]:
        return [zscore(v[i], stats[i][0], stats[i][1]) for i in range(len(v))]

    return z(target_vec), [z(v) for v in cand_vecs]


def friction_rules(target: Dict, cand: Dict) -> float:
    la = target["language"]
    lb = cand["language"]
    ra = target["rhythm"]
    rb = cand["rhythm"]

    score = 0.0

    if abs(float(la.get("honorific_ratio", 0.0)) - float(lb.get("honorific_ratio", 0.0))) > 0.45:
        score -= 0.04

    if (float(la.get("casual_ratio", 0.0)) > 0.35 and float(lb.get("casual_ratio", 0.0)) < 0.10) or \
       (float(lb.get("casual_ratio", 0.0)) > 0.35 and float(la.get("casual_ratio", 0.0)) < 0.10):
        score -= 0.04

    if abs(float(la.get("emoji_ratio", 0.0)) - float(lb.get("emoji_ratio", 0.0))) > 0.35:
        score -= 0.02

    ga = ra.get("avg_gap_sec", None)
    gb = rb.get("avg_gap_sec", None)
    if ga is not None and gb is not None:
        if abs(safe_log1p(ga) - safe_log1p(gb)) > 2.0:
            score -= 0.03

    if abs(float(ra.get("question_ratio", 0.0)) - float(rb.get("question_ratio", 0.0))) < 0.10:
        score += 0.02

    return score


def final_score(target: Dict, cand: Dict, zt: List[float], zc: List[float]) -> float:
    base = cosine(zt, zc)          # [-1, 1]
    adj = friction_rules(target, cand)

    s = (base + 1.0) / 2.0 + adj   # roughly [0, 1]
    ct = float(target.get("confidence", 0.5))
    cc = float(cand.get("confidence", 0.5))
    conf = (ct + cc) / 2.0
    s = s * (0.6 + 0.4 * conf)

    return max(0.0, min(1.0, s))


def main():
    ap = argparse.ArgumentParser(description="Match 1 target user vs DB candidates (LLM-free)")
    ap.add_argument("--target", required=True, help="target.json from main.py")
    ap.add_argument("--candidates", required=True, help="candidates.json from DB export")
    ap.add_argument("--out", default="", help="Output JSON path (optional)")
    ap.add_argument("--topk", type=int, default=10, help="Top-K matches (default: 10)")
    ap.add_argument("--min_score", type=float, default=0.0, help="Filter matches below this score (default: 0.0)")
    args = ap.parse_args()

    with open(args.target, "r", encoding="utf-8") as f:
        target_doc = json.load(f)
    target = target_doc.get("user")
    if not target:
        raise SystemExit("target.json 형식이 올바르지 않습니다. main.py 출력인지 확인하세요.")

    with open(args.candidates, "r", encoding="utf-8") as f:
        cand_doc = json.load(f)
    candidates: List[Dict] = cand_doc.get("candidates", [])
    if not candidates:
        raise SystemExit("candidates.json에 candidates 배열이 비어 있습니다.")

    # remove self if present
    target_id = str(target.get("user_id", ""))
    candidates = [c for c in candidates if str(c.get("user_id", "")) != target_id]
    if not candidates:
        raise SystemExit("후보군에서 자기 자신을 제외한 결과가 0명입니다.")

    t_raw = build_raw_vector(target)
    c_raw = [build_raw_vector(c) for c in candidates]
    t_z, c_zs = standardize_with_population(t_raw, c_raw)

    scored = []
    for c, cz in zip(candidates, c_zs):
        s = final_score(target, c, t_z, cz)
        if s < args.min_score:
            continue
        scored.append({
            "candidate_user_id": c.get("user_id"),
            "score": round(s, 6),
            "candidate_message_count": c.get("message_count", 0),
            "candidate_confidence": round(float(c.get("confidence", 0.0)), 6),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    scored = scored[: max(0, args.topk)]

    out = {
        "meta": {
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
            "target_user_id": target.get("user_id"),
            "topk": args.topk,
            "min_score": args.min_score,
            "scoring": {
                "base": "z-scored features (candidates + target) + cosine similarity",
                "adjustments": "small deterministic friction/bonus rules",
                "confidence_blend": "score *= (0.6 + 0.4 * avg_confidence)",
            },
        },
        "target": {
            "user_id": target.get("user_id"),
            "display_name": target.get("display_name"),
            "message_count": target.get("message_count"),
            "confidence": target.get("confidence"),
        },
        "matches": scored,
    }

    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[OK] Saved: {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
