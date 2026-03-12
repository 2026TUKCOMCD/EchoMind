# main.py
# -*- coding: utf-8 -*-

"""
Single output: LLM-based profile only (summary -> MBTI/Big5/Socionics)
- Compatible with OpenAI Python SDKs that do NOT support response_format=json_schema.

Input:
- KakaoTalk exported .txt
- --name: the user's speaker name in the export
- --user_id: your internal id (DB PK or uuid)

Output:
- One JSON object:
  - meta
  - parse_quality
  - llm_profile (summary + MBTI/Big5/Socionics + reasons + caveats)

Install:
  pip install openai python-dotenv

Env (.env):
  OPENAI_API_KEY=...
  OPENAI_MODEL=...

Usage:
  python main.py --file sample_chat.txt --name "홍길동" --user_id "u_123" --out profile.json
"""

import argparse
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI


# ----------------------------
# Kakao parsing patterns
# ----------------------------
LINE_PATTERNS = [
    re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.+?)\]\s+(?P<msg>.+)$"),
    re.compile(r"^(?P<time>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.*)$"),
    re.compile(r"^(?P<time>\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*(?:오전|오후)\s*\d{1,2}:\d{1,2}),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.*)$"),
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

RE_QUESTION = re.compile(r"\?")
RE_EMO = re.compile(r"(?:\:\)|\:\(|\^\^|ㅎㅎ|ㅋ|ㅠ|ㅜ|😄|😂|😭|🙂|🙃|😅|😢)")


# ----------------------------
# Data structures
# ----------------------------
@dataclass
class ParseQuality:
    total_lines: int
    parsed_lines: int
    parse_failed_lines: int
    filtered_system_lines: int
    empty_text_lines: int
    pii_masked_hits: int


# ----------------------------
# Helpers
# ----------------------------
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


def mask_pii(text: str) -> Tuple[str, int]:
    hits = 0

    new = RE_PHONE.sub("[전화번호]", text)
    if new != text:
        hits += 1
    text = new

    new = RE_EMAIL.sub("[이메일]", text)
    if new != text:
        hits += 1
    text = new

    new = RE_KR_ID.sub("[주민번호]", text)
    if new != text:
        hits += 1
    text = new

    return text, hits


# ----------------------------
# Parse TXT and filter only target user
# ----------------------------
def parse_target_rows(filepath: str, target_name: str) -> Tuple[List[Dict[str, str]], ParseQuality]:
    total_lines = parsed = failed = filtered_system = empty_text = pii_hits_total = 0
    rows: List[Dict[str, str]] = []

    # [NEW] Case-insensitive comparison target
    norm_target = target_name.strip().lower()

    current_speaker = None
    current_msg = []

    def flush_msg():
        nonlocal parsed, filtered_system, empty_text, pii_hits_total
        # [NEW] Check speaker name case-insensitively
        if current_speaker and current_speaker.strip().lower() == norm_target and current_msg:
            full_text = "\n".join(current_msg).strip()
            if not full_text:
                empty_text += 1
                return
            if looks_like_system_message(full_text):
                filtered_system += 1
                return
            
            cleaned = clean_text_ko(full_text)
            if not cleaned:
                empty_text += 1
                return
                
            masked, hits = mask_pii(cleaned)
            pii_hits_total += hits

            rows.append({"text": masked})
            parsed += 1

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            total_lines += 1
            line = raw.rstrip("\n")
            
            # Allow empty lines within multiline message, otherwise mark failed
            if not line.strip():
                if current_speaker is not None:
                    current_msg.append("") 
                else:
                    failed += 1
                continue

            # Check if this line starts a new message
            m = None
            for pat in LINE_PATTERNS:
                m = pat.match(line)
                if m:
                    break

            if m:
                # Append the previous accumulated message
                flush_msg()
                
                # Start recording a new message
                speaker = m.group("name").strip()
                text = m.group("msg")
                
                current_speaker = speaker
                current_msg = [text]
            else:
                # Ignore top info metadata or pure date dividers from Kakao
                is_meta = line.startswith("저장한 날짜 :") or "카카오톡 대화" in line
                # e.g., "2025년 12월 2일 화요일" (Kakao daily divider string format roughly)
                is_divider = bool(re.match(r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*.*$", line))
                
                if is_meta or is_divider:
                    failed += 1
                    continue
                
                # If we have an active speaker, treat as a multiline continuation
                if current_speaker is not None:
                    current_msg.append(line)
                else:
                    failed += 1

    # Catch the very last message in the file
    flush_msg()

    quality = ParseQuality(
        total_lines=total_lines,
        parsed_lines=parsed,
        parse_failed_lines=failed,
        filtered_system_lines=filtered_system,
        empty_text_lines=empty_text,
        pii_masked_hits=pii_hits_total,
    )
    return rows, quality


# ----------------------------
# Numeric signals (minimal)
# ----------------------------
def compute_numeric_signals(rows: List[Dict[str, str]]) -> Dict[str, float]:
    texts = [r["text"] for r in rows]
    n = max(len(texts), 1)

    avg_msg_len = sum(len(t) for t in texts) / n
    question_ratio = sum(1 for t in texts if RE_QUESTION.search(t)) / n
    emoji_ratio = sum(1 for t in texts if RE_EMO.search(t)) / n

    return {
        "message_count": float(len(rows)),
        "avg_msg_len": float(avg_msg_len),
        "question_ratio": float(question_ratio),
        "emoji_ratio": float(emoji_ratio),
    }


def sample_texts_for_llm(rows: List[Dict[str, str]], max_msgs: int, max_chars: int) -> List[str]:
    if not rows:
        return []

    n = len(rows)
    if n <= max_msgs:
        pick = rows
    else:
        step = max(1, n // max_msgs)
        pick = [rows[i] for i in range(0, n, step)][:max_msgs]

    out: List[str] = []
    total = 0
    for r in pick:
        t = r["text"].strip()
        if not t:
            continue
        if len(t) > 180:
            t = t[:180] + "…"
        if total + len(t) + 1 > max_chars:
            break
        out.append(t)
        total += len(t) + 1
    return out


# ----------------------------
# LLM call (SDK-compatible, no response_format)
# ----------------------------
def _extract_responses_text(resp) -> str:
    """
    OpenAI 응답 객체에서 텍스트를 안전하게 추출합니다.
    (ChatCompletion의 'choices'와 Responses API의 'output_text'를 모두 지원)
    """
    # 1. 표준 ChatCompletion (gpt-4o, gpt-3.5 등) 구조 처리
    if hasattr(resp, "choices") and resp.choices:
        return resp.choices[0].message.content or ""
    
    # 2. Responses API (gpt-5-mini 등 커스텀/구형) 구조 처리
    if hasattr(resp, "output_text") and resp.output_text:
        return resp.output_text

    texts = []
    
    # 객체의 속성이나 딕셔너리 키로 'output'이 있는지 확인
    out = getattr(resp, "output", []) or []
    if not out and isinstance(resp, dict):
        out = resp.get("output", [])

    for item in out:
        # item이 객체인지 딕셔너리인지 확인하여 content 추출
        content_list = getattr(item, "content", []) if not isinstance(item, dict) else item.get("content", [])
        if not content_list: continue

        for c in content_list:
            if hasattr(c, "text"):
                texts.append(c.text)
            elif isinstance(c, dict):
                t = c.get("text")
                if t: texts.append(t)

    return "\n".join(texts).strip()


def _extract_json_object(raw: str) -> Dict[str, object]:
    raw = (raw or "").strip()
    if not raw:
        raise RuntimeError("LLM 응답이 비어 있습니다.")

    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise RuntimeError("LLM이 JSON 객체(dict)가 아닌 값을 반환했습니다.")
        return obj
    except json.JSONDecodeError:
        pass

    l = raw.find("{")
    r = raw.rfind("}")
    if l != -1 and r != -1 and r > l:
        candidate = raw[l:r + 1]
        try:
            obj = json.loads(candidate)
            if not isinstance(obj, dict):
                raise RuntimeError("LLM이 JSON 객체(dict)가 아닌 값을 반환했습니다.")
            return obj
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        "LLM이 JSON으로 파싱 불가능한 응답을 반환했습니다.\n"
        "--- RAW START ---\n" + raw + "\n--- RAW END ---"
    )


def call_llm_profile(client: OpenAI, model: str, llm_input: Dict[str, object]) -> Dict[str, object]:
    """
    response_format(json_schema)을 지원하지 않는 SDK에서도 동작하는 버전.
    - JSON Schema 강제 대신: 프롬프트로 'JSON만' 반환하도록 강제
    - 출력 텍스트를 추출 후 json.loads 파싱
    """

    json_contract = {
        "summary": {
            "one_paragraph": "string",
            "communication_style_bullets": ["string", "..."]
        },
        "mbti": {
            "type": "I/E + N/S + F/T + J/P (예: INTJ)",
            "confidence": "0~1 number",
            "reasons": ["string", "..."]
        },
        "big5": {
            "scores_0_100": {
                "openness": "0~100",
                "conscientiousness": "0~100",
                "extraversion": "0~100",
                "agreeableness": "0~100",
                "neuroticism": "0~100"
            },
            "confidence": "0~1 number",
            "reasons": ["Trait: reason string...", "..."]
        },
        "socionics": {
            "type": "string (예: LII, EII, SLE 등)",
            "confidence": "0~1 number",
            "reasons": ["string", "..."]
        },
        "caveats": ["string", "..."]
    }

    system = (
        "당신은 대화 요약/성향 추정 도우미입니다.\n"
        "중요:\n"
        "- 원문 대화 문장을 직접 인용(따옴표 포함)하지 마십시오.\n"
        "- 개인정보/식별정보를 생성하거나 추측하지 마십시오.\n"
        "- 대화방 규범에 따라 달라질 수 있는 말투(존댓말/반말/완곡 표현 등)를 근거로 삼지 마십시오.\n"
        "- 제공된 샘플(정제·마스킹됨)과 수치 신호(평균 길이/질문비율/이모지비율 등)만으로 "
        "MBTI, Big5, 소시오니크를 '추정'하고 이유를 한국어로 제시하십시오.\n"
        "- 한계와 오차 가능성을 caveats에 반드시 포함하십시오.\n\n"
        "Big5 이유 (reasons) 작성:\n"
        "- 각 특성(Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)마다 "
        "'특성명: 구체적인 이유' 형식의 문장을 작성하십시오.\n"
        "- 예시: 'Openness: 새로운 표현과 실험적인 언어 사용이 빈번함', "
        "'Conscientiousness: 계획적이고 시간 약속을 엄격히 지키는 언어 패턴'\n"
        "- 최소 3~5개의 명확한 이유를 reasons 배열에 포함하십시오.\n\n"
        "출력 형식 요구사항:\n"
        "- 반드시 JSON '객체' 하나만 출력하십시오.\n"
        "- 설명 문장/마크다운/코드블록/여분 텍스트를 절대 포함하지 마십시오.\n"
        "- 키 이름은 아래 계약(json_contract)과 동일해야 합니다."
    )

    user = {
        "task": "Infer MBTI/Big5/Socionics from chat samples + numeric signals.",
        "json_contract": json_contract,
        "input": llm_input
    }

    # IMPORTANT: response_format 제거 (SDK 호환)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)}
        ]
    )

    raw = _extract_responses_text(resp)
    obj = _extract_json_object(raw)

    required = ["summary", "mbti", "big5", "socionics", "caveats"]
    for k in required:
        if k not in obj:
            raise RuntimeError(f"LLM JSON 결과에 필수 키가 없습니다: {k}")

    return obj


# ----------------------------
# CLI
# ----------------------------
def main():
    ap = argparse.ArgumentParser(description="Single-output LLM profiling from KakaoTalk TXT")
    ap.add_argument("--file", required=True, help="KakaoTalk exported .txt file path")
    ap.add_argument("--name", required=True, help="Target speaker name in the export (the uploader)")
    ap.add_argument("--user_id", required=True, help="Your internal user id (DB PK/UUID)")
    ap.add_argument("--out", default="", help="Output JSON path (optional)")
    ap.add_argument("--min_msgs", type=int, default=30, help="Minimum messages required (default: 30)")
    ap.add_argument("--openai_model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    ap.add_argument("--max_msgs_for_llm", type=int, default=120)
    ap.add_argument("--max_chars_for_llm", type=int, default=18000)

    args = ap.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY가 설정되지 않았습니다. .env 또는 환경변수로 설정하세요.")

    rows, quality = parse_target_rows(args.file, args.name)
    if len(rows) < args.min_msgs:
        raise SystemExit(
            f"분석 가능한 발화가 부족합니다: {len(rows)}개 (< {args.min_msgs}). "
            f"--name(대화명) 또는 --min_msgs를 확인하세요."
        )

    signals = compute_numeric_signals(rows)
    samples = sample_texts_for_llm(rows, max_msgs=args.max_msgs_for_llm, max_chars=args.max_chars_for_llm)

    llm_input = {
        "samples": samples,
        "numeric_signals": signals,
        "constraints": {
            "no_quotes": True,
            "no_pii": True,
            "avoid_room_dependent_style": True
        }
    }

    client = OpenAI(api_key=api_key)
    profile = call_llm_profile(client=client, model=args.openai_model, llm_input=llm_input)

    out_obj = {
        "meta": {
            "source": "kakao_export_txt",
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
            "file": args.file,
            "speaker_name": args.name,
            "user_id": args.user_id,
            "model": args.openai_model
        },
        "parse_quality": asdict(quality),
        "llm_profile": profile
    }

    text = json.dumps(out_obj, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[OK] Saved: {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()