# llm_style.py
# -*- coding: utf-8 -*-

"""
LLM explanation generator (explanation-only; DOES NOT affect matching score)
Aligned with match.py output format.

Inputs (required):
- --matches: matches.json from match.py
- --target_json: target.json from main.py (single user vector doc)
- --candidates_json: candidates.json (DB export; {"candidates":[...]})

Optional (for message samples to improve explanations):
- --target_file: target user's original KakaoTalk .txt
- --target_name: target speaker name inside target_file
- --candidate_dir: folder containing candidate txt files named by user_id (e.g., u_456.txt)
- --candidate_name_map: JSON mapping {"u_456":"김철수", ...}

Output:
- explanations.json with Top-N explanations

Usage:
  pip install openai python-dotenv
  export OPENAI_API_KEY="..."
  export OPENAI_MODEL="gpt-5-mini"   # optional

  # Metrics-only explanation (no txt needed)
  python llm_style.py --matches matches.json --target_json target.json --candidates_json candidates.json --out explanations.json --topn 3

  # Metrics + sample messages explanation (recommended)
  python llm_style.py --matches matches.json --target_json target.json --candidates_json candidates.json \
    --target_file my.txt --target_name "홍길동" --candidate_dir ./candidate_txts --candidate_name_map name_map.json \
    --out explanations.json --topn 3
"""

import argparse
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI


# ----------------------------
# (Optional) TXT parsing for samples
# ----------------------------
LINE_PATTERNS = [
    re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.+?)\]\s+(?P<msg>.+)$"),
    re.compile(r"^(?P<time>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.+)$"),
]

SYSTEM_SKIP_SUBSTR = [
    "사진", "이모티콘", "동영상", "삭제된 메시지입니다", "파일", "보이스톡", "통화",
    "송금", "입금", "출금",
]

RE_URL = re.compile(r"https?://\S+")
RE_LAUGH = re.compile(r"[ㅋㅎ]{2,}")
RE_CRY = re.compile(r"[ㅠㅜ]{2,}")
RE_SPACES = re.compile(r"\s+")

RE_PHONE = re.compile(r"(01[016789])[-.\s]?\d{3,4}[-.\s]?\d{4}")
RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
RE_KR_ID = re.compile(r"\b\d{6}[-\s]?\d{7}\b")


def looks_like_system_message(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    return any(s in t for s in SYSTEM_SKIP_SUBSTR)


def clean_text_ko(text: str) -> str:
    text = RE_URL.sub(" ", text)
    text = RE_LAUGH.sub(" ", text)
    text = RE_CRY.sub(" ", text)
    text = RE_SPACES.sub(" ", text).strip()
    return text


def mask_pii(text: str) -> str:
    text = RE_PHONE.sub("[전화번호]", text)
    text = RE_EMAIL.sub("[이메일]", text)
    text = RE_KR_ID.sub("[주민번호]", text)
    return text


def parse_txt_rows(filepath: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            m = None
            for pat in LINE_PATTERNS:
                m = pat.match(line)
                if m:
                    break
            if not m:
                continue
            speaker = m.group("name").strip()
            time_str = m.group("time").strip()
            text = m.group("msg").strip()

            if looks_like_system_message(text):
                continue

            text = mask_pii(clean_text_ko(text))
            if not text:
                continue

            rows.append({"speaker": speaker, "time": time_str, "text": text})
    return rows


def sample_user_messages(rows: List[Dict[str, str]], user_name: str, limit: int = 40, max_chars: int = 140) -> List[str]:
    msgs = [r["text"] for r in rows if r["speaker"] == user_name]
    seen = set()
    uniq = []
    for m in msgs:
        m2 = m.strip()
        if not m2 or m2 in seen:
            continue
        seen.add(m2)
        uniq.append(m2)
    if len(uniq) > limit:
        uniq = uniq[-limit:]
    return [m[:max_chars] for m in uniq]


# ----------------------------
# Output schema (explanation-only)
# ----------------------------
EXPLAIN_SCHEMA = {
    "name": "match_explanation_v1",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "language": {"type": "string", "enum": ["ko"]},
            "pair": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "target_user_id": {"type": "string"},
                    "candidate_user_id": {"type": "string"},
                    "score": {"type": "number", "minimum": 0.0, "maximum": 1.0}
                },
                "required": ["target_user_id", "candidate_user_id", "score"]
            },
            "summary": {"type": "string", "minLength": 20, "maxLength": 400},
            "why_it_matches": {
                "type": "array",
                "items": {"type": "string", "minLength": 8, "maxLength": 120},
                "minItems": 3,
                "maxItems": 6
            },
            "possible_frictions": {
                "type": "array",
                "items": {"type": "string", "minLength": 8, "maxLength": 120},
                "minItems": 1,
                "maxItems": 5
            },
            "conversation_tips": {
                "type": "array",
                "items": {"type": "string", "minLength": 8, "maxLength": 120},
                "minItems": 3,
                "maxItems": 6
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        },
        "required": [
            "language",
            "pair",
            "summary",
            "why_it_matches",
            "possible_frictions",
            "conversation_tips",
            "confidence"
        ]
    }
}


def call_llm_json(prompt: str, model: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_schema", "json_schema": EXPLAIN_SCHEMA},
    )
    raw = resp.choices[0].message.content
    return json.loads(raw)


def minimal_metrics_from_target_doc(target_doc: Dict) -> Dict:
    u = target_doc.get("user", {})
    return {
        "user_id": str(u.get("user_id", "")),
        "message_count": u.get("message_count", 0),
        "rhythm": u.get("rhythm", {}),
        "language": u.get("language", {}),
        "confidence": u.get("confidence", 0.0),
    }


def minimal_metrics_from_candidate(c: Dict) -> Dict:
    return {
        "user_id": str(c.get("user_id", "")),
        "message_count": c.get("message_count", 0),
        "rhythm": c.get("rhythm", {}),
        "language": c.get("language", {}),
        "confidence": c.get("confidence", 0.0),
    }


def build_prompt(
    target_metrics: Dict,
    candidate_metrics: Dict,
    score: float,
    target_samples: Optional[List[str]],
    candidate_samples: Optional[List[str]],
) -> str:
    # Keep samples optional to support metrics-only mode
    if target_samples:
        bullets_a = "\n".join(f"- {x}" for x in target_samples)
    else:
        bullets_a = "(제공되지 않음)"

    if candidate_samples:
        bullets_b = "\n".join(f"- {x}" for x in candidate_samples)
    else:
        bullets_b = "(제공되지 않음)"

    return f"""
당신은 '매칭 결과 설명'을 작성하는 분석가입니다.

원칙:
- 심리검사/의학적 진단처럼 단정하지 말고, 관찰 가능한 경향만 기술하세요.
- 원문을 길게 인용하지 말고, 샘플 문장을 그대로 복사하지 마세요.
- 아래 수치 지표(리듬/언어 특징)와 (있다면) 메시지 샘플을 종합해 '설명'만 작성하세요.
- 출력은 반드시 제공된 JSON 스키마를 준수하세요. 언어는 ko.

매칭쌍:
- target_user_id: {target_metrics.get("user_id")}
- candidate_user_id: {candidate_metrics.get("user_id")}
- score(0~1): {score:.6f}

Target 지표:
{json.dumps(target_metrics, ensure_ascii=False)}

Candidate 지표:
{json.dumps(candidate_metrics, ensure_ascii=False)}

Target 메시지 샘플(참고용):
{bullets_a}

Candidate 메시지 샘플(참고용):
{bullets_b}
""".strip()


def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Generate LLM explanations aligned with match.py (explanation-only)")
    ap.add_argument("--matches", required=True, help="matches.json from match.py")
    ap.add_argument("--target_json", required=True, help="target.json from main.py (single user doc)")
    ap.add_argument("--candidates_json", required=True, help="candidates.json (DB export; {candidates:[...]})")

    # optional sample inputs
    ap.add_argument("--target_file", default="", help="(Optional) Target user's KakaoTalk .txt for sampling")
    ap.add_argument("--target_name", default="", help="(Optional) Target speaker name inside target_file")
    ap.add_argument("--candidate_dir", default="", help="(Optional) Directory with candidate txt files named by user_id")
    ap.add_argument("--candidate_name_map", default="", help='(Optional) JSON file: {"u_456":"김철수"}')

    ap.add_argument("--out", default="", help="Output JSON path (optional)")
    ap.add_argument("--topn", type=int, default=3, help="Explain top-N matches (default: 3)")
    ap.add_argument("--sample_msgs", type=int, default=40, help="Sample messages per user (default: 40)")
    ap.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"), help="OpenAI model (optional)")
    args = ap.parse_args()

    # Load match.py output
    with open(args.matches, "r", encoding="utf-8") as f:
        match_doc = json.load(f)

    target_user_id_in_matches = str(match_doc.get("target", {}).get("user_id", ""))
    top_matches = match_doc.get("matches", [])[: max(0, args.topn)]
    if not target_user_id_in_matches:
        raise SystemExit("matches.json에서 target.user_id를 찾을 수 없습니다.")
    if not top_matches:
        raise SystemExit("설명할 매칭 결과가 없습니다. match.py 결과를 확인하세요.")

    # Load target metrics (main.py output)
    with open(args.target_json, "r", encoding="utf-8") as f:
        target_doc = json.load(f)
    target_metrics = minimal_metrics_from_target_doc(target_doc)

    # Validate alignment
    if target_metrics.get("user_id") and target_metrics["user_id"] != target_user_id_in_matches:
        raise SystemExit(
            f"target_json의 user_id({target_metrics['user_id']})와 matches.json의 target_user_id({target_user_id_in_matches})가 다릅니다."
        )

    # Load candidates metrics map
    with open(args.candidates_json, "r", encoding="utf-8") as f:
        cand_doc = json.load(f)
    candidates_list: List[Dict] = cand_doc.get("candidates", [])
    cand_map: Dict[str, Dict] = {str(c.get("user_id")): minimal_metrics_from_candidate(c) for c in candidates_list}

    # Optional name map for candidate speaker names inside their txt
    name_map: Dict[str, str] = {}
    if args.candidate_name_map:
        with open(args.candidate_name_map, "r", encoding="utf-8") as f:
            name_map = json.load(f)

    # Optional target samples
    use_samples = bool(args.target_file and args.target_name and args.candidate_dir)
    target_samples: Optional[List[str]] = None
    target_rows: Optional[List[Dict[str, str]]] = None
    if use_samples:
        target_rows = parse_txt_rows(args.target_file)
        target_samples = sample_user_messages(target_rows, args.target_name, limit=args.sample_msgs)

    explanations = []
    for item in top_matches:
        cand_id = str(item.get("candidate_user_id", ""))
        score = float(item.get("score", 0.0))
        if not cand_id:
            continue

        candidate_metrics = cand_map.get(cand_id)
        if not candidate_metrics:
            # 후보 지표가 없으면 설명 생성 불가(지표 기반 설계)
            continue

        cand_samples: Optional[List[str]] = None
        if use_samples:
            cand_file = os.path.join(args.candidate_dir, f"{cand_id}.txt")
            if os.path.exists(cand_file):
                cand_rows = parse_txt_rows(cand_file)
                cand_name = name_map.get(cand_id, "")
                if cand_name:
                    cand_samples = sample_user_messages(cand_rows, cand_name, limit=args.sample_msgs)
                else:
                    cand_samples = None  # 이름 없으면 샘플 사용 안 함

        prompt = build_prompt(
            target_metrics=target_metrics,
            candidate_metrics=candidate_metrics,
            score=score,
            target_samples=target_samples,
            candidate_samples=cand_samples,
        )
        explanations.append(call_llm_json(prompt, args.model))

    out = {
        "meta": {
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
            "matches": args.matches,
            "target_json": args.target_json,
            "candidates_json": args.candidates_json,
            "topn": args.topn,
            "sample_msgs": args.sample_msgs,
            "model": args.model,
            "mode": "metrics_only" if not use_samples else "metrics_plus_samples",
            "note": "설명 전용이며 match.py 점수는 변경하지 않습니다."
        },
        "target_user_id": target_user_id_in_matches,
        "explanations": explanations
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
