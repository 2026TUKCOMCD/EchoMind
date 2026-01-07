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
  (optional) export OPENAI_MODEL="gpt-5"   # or any model your account supports

Run:
  python main.py --file "KakaoTalkChat.txt" --name "홍길동" --out "profile.json"
"""

import os
import re
import json
import argparse
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI


# ----------------------------
# 0) Config
# ----------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")  # account-dependent

# 비용/지연 제어(한국어 대화는 길어지기 쉬움)
MAX_MESSAGES_FOR_LLM = 140
MAX_CHARS_PER_MESSAGE = 200
MAX_TOTAL_INPUT_CHARS = 28_000

SYSTEM_SKIP_SUBSTR = [
    "사진", "이모티콘", "동영상", "삭제된 메시지입니다", "파일", "보이스톡", "통화", "송금", "입금", "출금"
]

# ----------------------------
# 1) KakaoTalk TXT parsing
# ----------------------------
# 다양한 내보내기 포맷을 최대한 흡수(완벽 파서는 아님)
LINE_PATTERNS = [
    # [Name] [YYYY.MM.DD. 오후 1:23] message
    re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.+?)\]\s+(?P<msg>.+)$"),
    # 2025. 1. 1. 오후 1:23, Name : message
    re.compile(r"^(?P<time>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.+)$"),
]

def parse_kakao_txt(filepath: str) -> List[Dict[str, str]]:
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
                # 멀티라인 메시지(줄바꿈 이어지는 경우)까지 완전히 처리하려면
                # 이전 메시지에 붙이는 로직이 필요합니다.
                continue

            rows.append({
                "speaker": m.group("name").strip(),
                "time": m.group("time").strip(),
                "text": m.group("msg").strip(),
            })
    return rows


# ----------------------------
# 2) Preprocess (Korean-first)
# ----------------------------
RE_URL = re.compile(r"https?://\S+")
RE_LAUGH = re.compile(r"[ㅋㅎ]{2,}")
RE_CRY = re.compile(r"[ㅠㅜ]{2,}")
RE_SPACES = re.compile(r"\s+")

def looks_like_system_message(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    for s in SYSTEM_SKIP_SUBSTR:
        if s in t:
            return True
    return False

def clean_text_ko(text: str) -> str:
    text = RE_URL.sub(" ", text)
    text = RE_LAUGH.sub(" ", text)
    text = RE_CRY.sub(" ", text)
    text = RE_SPACES.sub(" ", text).strip()
    return text

# PII 마스킹(오탐 가능성은 존재. 보수적으로 적용)
RE_PHONE = re.compile(r"(01[016789])[-.\s]?\d{3,4}[-.\s]?\d{4}")
RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
RE_KR_ID = re.compile(r"\b\d{6}[-\s]?\d{7}\b")  # 주민번호 형태(단순)

def mask_pii(text: str) -> str:
    text = RE_PHONE.sub("[전화번호]", text)
    text = RE_EMAIL.sub("[이메일]", text)
    text = RE_KR_ID.sub("[주민번호]", text)
    return text

def extract_target_messages(rows: List[Dict[str, str]], target_name: str, limit: int = MAX_MESSAGES_FOR_LLM) -> List[str]:
    msgs: List[str] = []
    for r in rows:
        if r["speaker"] != target_name:
            continue
        txt = r.get("text", "")
        if looks_like_system_message(txt):
            continue
        txt = clean_text_ko(txt)
        txt = mask_pii(txt)
        if not txt:
            continue
        msgs.append(txt)

    # 중복 제거(동일 문장 반복 API 비용 낭비 방지)
    seen = set()
    uniq = []
    for m in msgs:
        if m in seen:
            continue
        seen.add(m)
        uniq.append(m)

    # 최근 발화 위주(현재 스타일 반영)
    if len(uniq) > limit:
        uniq = uniq[-limit:]

    return uniq


# ----------------------------
# 3) LLM Structured Output (JSON Schema)
# ----------------------------
PROFILE_SCHEMA = {
    "name": "kakao_chat_profile_v1",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "language": {"type": "string", "enum": ["ko"]},
            "overall_summary": {"type": "string", "minLength": 20, "maxLength": 1200},

            # 1. 정성적 성향 지표 (사용자 리포트용)
            "communication_style": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tone": {"type": "string", "enum": ["친근함", "공손함", "중립적", "건조함", "공격적"]},
                    "directness": {"type": "string", "enum": ["직설적", "완곡적", "상황따라변함"]},
                    "emotion_expression": {"type": "string", "enum": ["낮음", "보통", "높음"]},
                    "empathy_signals": {"type": "string", "enum": ["낮음", "보통", "높음"]},
                    "initiative": {"type": "string", "enum": ["주도형", "반응형", "혼합형"]},
                    "conflict_style": {"type": "string", "enum": ["회피", "완화", "직면", "혼합"]},
                },
                "required": ["tone", "directness", "emotion_expression", "empathy_signals", "initiative", "conflict_style"],
            },

            # 2. 정량적 성향 벡터 (사용자 매칭 알고리즘용)
            "communication_vector": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "directness_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "완곡(0) ~ 직설(1)"},
                    "emotion_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "이성적(0) ~ 감정적(1)"},
                    "empathy_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "낮음(0) ~ 높음(1)"},
                    "initiative_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "반응형(0) ~ 주도형(1)"},
                    "tone_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "공격적(0) ~ 친근/공손(1)"},
                    "conflict_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "회피형(0) ~ 직면/해결형(1)"}
                },
                "required": ["directness_score", "emotion_score", "empathy_score", "initiative_score", "tone_score", "conflict_score"]
            },

            "notable_patterns": {
                "type": "array",
                "items": {"type": "string", "minLength": 5, "maxLength": 120},
                "minItems": 3,
                "maxItems": 10
            },

            "strengths": {
                "type": "array",
                "items": {"type": "string", "minLength": 5, "maxLength": 120},
                "minItems": 2,
                "maxItems": 6
            },

            "cautions": {
                "type": "array",
                "items": {"type": "string", "minLength": 5, "maxLength": 120},
                "minItems": 2,
                "maxItems": 6
            },

            "matching_tips": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "works_well_with": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 6},
                    "may_clash_with": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 6},
                },
                "required": ["works_well_with", "may_clash_with"]

            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "evidence_quotes": {
                "type": "array",
                "items": {"type": "string", "minLength": 5, "maxLength": 60},
                "minItems": 3,
                "maxItems": 8
            }

        },
        "required": [
            "language", "overall_summary", "communication_style", "communication_vector",
            "notable_patterns", "strengths", "cautions",
            "matching_tips", "confidence", "evidence_quotes"
        ]
    }
}

def build_prompt(target_name: str, messages: List[str]) -> str:
    # 입력 총량 제한
    trimmed: List[str] = []
    total = 0
    for m in messages:
        m2 = m[:MAX_CHARS_PER_MESSAGE]
        add = len(m2) + 3
        if total + add > MAX_TOTAL_INPUT_CHARS:
            break
        trimmed.append(m2)
        total += add

    bullets = "\n".join([f"- {x}" for x in trimmed])

    return f"""
당신은 한국어 카카오톡 대화 텍스트로부터 '대화 성향/커뮤니케이션 스타일'을 분석해 구조화 요약하는 분석가입니다.

규칙:
- 심리검사/의학적 진단처럼 단정하지 말고, 텍스트에서 관찰되는 경향만 기술하세요.
- 개인정보(전화번호/이메일/실명/계좌 등)를 출력에 포함하지 마세요.
- 출력하는 JSON의 모든 Value에는 \\u001b나 \\u001b[0m 같은 터미널 제어/색상 문자를 절대 포함하지 마세요.
- 원문을 길게 인용하지 말고, evidence_quotes는 25자 내외 의역/요약만 하세요.
- 출력은 반드시 제공된 JSON 스키마를 정확히 준수하세요.
- 언어는 반드시 ko로 출력하세요.

분석 대상(내 발화): {target_name}
아래는 발화 샘플입니다:
{bullets}
""".strip()

def call_llm_structured(prompt: str, model: str) -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Responses API에서 Structured Outputs 사용 (문서 기준: text.format 사용 권장)
    # SDK 버전에 따라 파라미터 형태가 다를 수 있어, 2가지 형태를 순차 시도합니다.
    # 1) text.format 방식
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": PROFILE_SCHEMA
            },
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        return data
    except Exception as e:
        # Fallback or re-raise
        raise RuntimeError(f"OpenAI API 호출 실패: {e}")


# ----------------------------
# 4) CLI
# ----------------------------
def main():
    ap = argparse.ArgumentParser(description="KakaoTalk TXT -> LLM structured profile (Korean-first)")
    ap.add_argument("--file", required=True, help="KakaoTalk exported .txt file path")
    ap.add_argument("--name", required=True, help="Target speaker name in the export (your name)")
    ap.add_argument("--out", default="", help="Output JSON path (optional)")
    ap.add_argument("--model", default=OPENAI_MODEL, help="OpenAI model name (optional)")
    ap.add_argument("--limit", type=int, default=200, help="Max messages to analyze (default: 200)")
    args = ap.parse_args()

    rows = parse_kakao_txt(args.file)
    if not rows:
        raise SystemExit("파싱 결과가 비어 있습니다. 내보내기 파일 형식이 예상과 다를 수 있습니다.")

    msgs = extract_target_messages(rows, args.name, limit=args.limit)
    if len(msgs) < 15:
        raise SystemExit(f"분석 가능한 발화가 너무 적습니다(현재 {len(msgs)}개). --name(대화명)을 확인하세요.")

    prompt = build_prompt(args.name, msgs)
    profile = call_llm_structured(prompt, args.model)

    # 안전장치: language 강제
    profile["language"] = "ko"
    profile["_meta"] = {
        "source": "kakao_export_txt",
        "target_name": args.name,
        "message_count_used": len(msgs),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model
    }

    out_text = json.dumps(profile, ensure_ascii=False, indent=2)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"[OK] Saved: {args.out}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
