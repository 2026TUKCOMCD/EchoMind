# main.py
# -*- coding: utf-8 -*-

"""
EchoMind core (KakaoTalk TXT -> LLM structured profile) / Korean-first
- No HTML, No DB
- Input: KakaoTalk export .txt, target speaker name
- Output: JSON (structured via JSON Schema / Structured Outputs)

Install:
  pip install openai python-dotenv

Env:
  export OPENAI_API_KEY="..."
  (optional) export OPENAI_MODEL="gpt-5-mini"   # or any model your account supports


Run:
    python main.py --file "KakaoTalk_Chat.txt" --name "User" --out "profile.json" --dict "korean_bad_words.json"
"""

import os
import re
import json
import argparse
import sys
import time
import logging
from typing import List, Dict
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

# ----------------------------
# 0) Config & Setup
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("EchoMindCore")

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

MAX_MESSAGES_FOR_LLM = 140
MAX_CHARS_PER_MESSAGE = 200
MAX_TOTAL_INPUT_CHARS = 28_000

SYSTEM_SKIP_SUBSTR = [
    "사진", "이모티콘", "동영상", "삭제된 메시지입니다", "파일", "보이스톡", "통화", "송금", "입금", "출금"
]

# ----------------------------
# 1) Parsing & Logic
# ----------------------------
LINE_PATTERNS = [
    re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.+?)\]\s+(?P<msg>.+)$"),
    re.compile(r"^(?P<time>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.+)$"),
]

def parse_kakao_txt(filepath: str) -> List[Dict[str, str]]:
    rows = []
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line.strip(): continue
                m = None
                for pat in LINE_PATTERNS:
                    m = pat.match(line)
                    if m: break
                if m:
                    rows.append({"speaker": m.group("name").strip(), "text": m.group("msg").strip()})
    except Exception as e:
        logger.error(f"Failed to parse: {e}")
        return []
    return rows

def clean_text_ko(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[ㅋㅎ]{2,}", " ", text)
    text = re.sub(r"[ㅠㅜ]{2,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_target_messages(rows: List[Dict[str, str]], target_name: str, limit: int) -> List[str]:
    msgs = []
    for r in rows:
        if r["speaker"] != target_name: continue
        t = r.get("text", "")
        if not t or any(s in t for s in SYSTEM_SKIP_SUBSTR): continue
        t = clean_text_ko(t)
        if t: msgs.append(t)
    
    seen = set()
    uniq = []
    for m in msgs:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq[-limit:]

# ----------------------------
# 2) Toxicity (Rule-based)
# ----------------------------
def load_bad_words(filepath: str) -> List[str]:
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    return [item.get("text", "") for item in data if "text" in item]
                elif data and isinstance(data[0], str):
                    return data
            return []
    except: return []

def calculate_toxicity_score(messages: List[str], bad_words: List[str]) -> float:
    if not messages or not bad_words: return 0.0
    cnt = 0
    for m in messages:
        for b in bad_words:
            if b in m:
                cnt += 1
                break
    return round(cnt / len(messages), 4)

# ----------------------------
# 3) LLM Schema (Pure Vector)
# ----------------------------
# 텍스트 필드: main.py가 아닌 reporter.py에서, main.py에서는 수치 벡터만 남김
PROFILE_SCHEMA = {
    "name": "kakao_chat_vector_only",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "communication_vector": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "directness_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "0(완곡)~1(직설)"},
                    "emotion_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "0(이성)~1(감성)"},
                    "empathy_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "0(낮음)~1(높음)"},
                    "initiative_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "0(수동)~1(주도)"},
                    "tone_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "0(공격)~1(친근)"},
                    "conflict_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "0(회피)~1(직면)"},
                    # 독성은 Python에서 계산하지만 스키마 일관성을 위해 둠 (LLM은 0으로 출력 유도)
                    "toxicity_score": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["directness_score", "emotion_score", "empathy_score", "initiative_score", "tone_score", "conflict_score", "toxicity_score"]
            }
        },
        "required": ["communication_vector"]
    }
}

def build_prompt(target_name: str, messages: List[str]) -> str:
    trimmed = []
    total = 0
    for m in messages:
        if total + len(m) > MAX_TOTAL_INPUT_CHARS: break
        trimmed.append(m)
        total += len(m)
    
    bullets = "\n".join([f"- {x}" for x in trimmed])
    
    return f"""
    당신은 데이터 분석가입니다. 아래 대화 데이터를 바탕으로 화자의 성향을 0.0~1.0 사이 수치로 추출하세요.
    
    [규칙]
    - 텍스트 설명은 일절 포함하지 마세요. 오직 JSON 데이터만 출력하세요.
    - 'toxicity_score'는 0.0으로 출력하세요.
    
    [대상]: {target_name}
    [데이터]:
    {bullets}
    """.strip()

def call_llm(prompt: str, model: str) -> dict:
    client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_schema", "json_schema": PROFILE_SCHEMA},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logger.error(f"API Error: {e}")
        raise

# ----------------------------
# 4) Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", default="profile.json")
    ap.add_argument("--dict", default="korean_bad_words_formatted.json")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    # 1. Parse & Extract
    rows = parse_kakao_txt(args.file)
    msgs = extract_target_messages(rows, args.name, args.limit)
    if len(msgs) < 10:
        logger.error("Not enough messages.")
        sys.exit(1)

    # 2. Toxicity Calculation (Local)
    bad_words = load_bad_words(args.dict)
    tox_val = calculate_toxicity_score(msgs, bad_words)
    logger.info(f"Calculated Toxicity: {tox_val}")

    # 3. LLM Analysis (Vector Only)
    logger.info("Requesting Vector Analysis...")
    prompt = build_prompt(args.name, msgs)
    profile = call_llm(prompt, OPENAI_MODEL)

    # 4. Data Merge
    # LLM이 0.0으로 뱉은 toxicity_score를 실제 계산값으로 덮어씌움
    profile["communication_vector"]["toxicity_score"] = tox_val

    # 5. Metadata (Minimal)
    final_output = {
        "user_id": args.name,
        "communication_vector": profile["communication_vector"],
        "_meta": {
            "msg_count": len(msgs),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_file": os.path.basename(args.file)
        }
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved optimized profile to {args.out}")

if __name__ == "__main__":
    main()