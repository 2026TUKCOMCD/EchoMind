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
from datetime import datetime, timedelta
import re
import json # Used for loading sentiment dict
from kiwipiepy import Kiwi # Reuse kiwi for consistent tokenization if needed, or simple split for basic dict check

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
# 2-1) Stat & Dictionary Helper
# ----------------------------
from config import BAD_WORDS, SENTIMENT_DICT_FILE

# Kiwi Init (Safe)
try:
    kiwi = Kiwi()
    print("[*] Kiwi(형태소 분석기) 로드 완료")
except Exception as e:
    kiwi = None
    print(f"[Warning] Kiwi 로드 실패: {e}")

def load_sentiment_dict():
    """KNU 감성사전 로드 (파일 없으면 빈 딕셔너리)"""
    senti_db = {}
    if os.path.exists(SENTIMENT_DICT_FILE):
        try:
            with open(SENTIMENT_DICT_FILE, encoding='utf-8-sig') as f:
                data = json.load(f)
            for entry in data:
                senti_db[entry['word_root']] = int(entry['polarity'])
                senti_db[entry['word']] = int(entry['polarity'])
            print(f"[*] 감성 사전 로드 완료 ({len(senti_db)}개)")
        except Exception as e:
            print(f"[Warning] 감성 사전 로드 실패: {e}")
    else:
        print("[Warning] 감성 사전 파일이 없습니다. (감성분석 건너뜀)")
    return senti_db

def parse_time_str(t_str: str) -> Optional[datetime]:
    """
    '오전 10:23', '오후 2:00' 같은 문자열을 datetime(오늘 날짜 기준)으로 변환
    날짜 정보가 없으므로 시간 차이 계산용으로만 사용 (하루 넘기는 경우 보정)
    """
    try:
        # Remove brackets if any
        t_str = t_str.replace("[", "").replace("]", "").strip()
        # Pattern: (오전|오후) HH:MM
        is_pm = "오후" in t_str
        t_str_clean = t_str.replace("오전", "").replace("오후", "").strip()
        
        parts = t_str_clean.split(":")
        if len(parts) != 2: return None
        
        hour = int(parts[0])
        minute = int(parts[1])
        
        if is_pm and hour != 12:
            hour += 12
        if not is_pm and hour == 12:
            hour = 0
            
        now = datetime.now()
        return datetime(now.year, now.month, now.day, hour, minute)
    except:
        return None

def analyze_statistics(rows: List[Dict[str, str]], target_name: str) -> dict:
    total_count = len(rows)
    my_msgs = [r for r in rows if r["speaker"] == target_name]
    my_count = len(my_msgs)
    
    # 1. Share
    share = (my_count / total_count * 100) if total_count > 0 else 0.0
    
    # 2. Latency (Reply Speed)
    latencies = []
    
    # 스피커가 달라지는 지점(상대 -> 나)을 찾아서 시간 차 계산
    last_speaker = None
    last_time_obj = None
    
    for r in rows:
        curr_speaker = r["speaker"]
        curr_time_str = r["time"]
        
        # Parse time
        curr_time_obj = parse_time_str(curr_time_str)
        if not curr_time_obj:
            continue
            
        if last_speaker and last_speaker != target_name and curr_speaker == target_name:
            # 상대방 -> 나 (답장 상황)
            if last_time_obj:
                diff = (curr_time_obj - last_time_obj).total_seconds() / 60.0 # minutes
                # 만약 날짜가 바뀌어서 음수가 나오면? (23:59 -> 00:01)
                # +24시간(1440분) 보정. 단, 대화가 끊겼다가 다음날 하는 경우일 수도 있으니
                # 12시간(720분) 이상 차이나면 계산에서 제외하거나 보정
                if diff < 0:
                    diff += 1440
                
                # 너무 긴 시간(예: 6시간 이상)은 답장이 아니라 새로운 대화 시작으로 간주하여 제외
                if 0 <= diff < 360: 
                    latencies.append(diff)
                    
        last_speaker = curr_speaker
        last_time_obj = curr_time_obj
        
    avg_latency = float(sum(latencies) / len(latencies)) if latencies else 0.0
    
    # 3. Question Ratio
    q_count = sum(1 for m in my_msgs if "?" in m["text"])
    q_ratio = q_count / my_count if my_count > 0 else 0.0
    
    return {
        "msg_share": round(share, 1),
        "avg_reply_latency": round(avg_latency, 1),
        "question_ratio": round(q_ratio, 2)
    }

def analyze_dictionary_based(messages: List[str], senti_db: dict) -> dict:
    """
    Toxicity & Sentiment Analysis (Local Dictionary + Kiwi)
    """
    # 1. Toxicity
    toxic_count = 0
    total = len(messages)
    for m in messages:
        for bad in BAD_WORDS:
            if bad in m:
                toxic_count += 1
                break
    tox_score = toxic_count / total if total > 0 else 0.0
    
    # 2. Sentiment
    pos_score_sum = 0
    neg_score_sum = 0
    total_sent_words = 0
    
    for m in messages:
        # Tokenization: Use Kiwi if available
        if kiwi:
            try:
                tokens = kiwi.tokenize(m)
                words = [t.form for t in tokens]
            except:
                words = m.split()
        else:
            words = m.split()

        for w in words:
            if w in senti_db:
                s = senti_db[w]
                if s >= 1:
                    pos_score_sum += s
                    total_sent_words += 1
                elif s <= -1:
                    neg_score_sum += abs(s)
                    total_sent_words += 1
                    
    if total_sent_words == 0:
        s_score = {"positive": 0.0, "negative": 0.0, "neutral": 1.0}
    else:
        tot = pos_score_sum + neg_score_sum + 0.001
        p = pos_score_sum / tot
        n = neg_score_sum / tot
        neu = 1.0 - (p + n)
        if neu < 0: neu = 0
        s_score = {"positive": round(p, 2), "negative": round(n, 2), "neutral": round(neu, 2)}
        
    return {
        "toxicity_score": round(tox_score, 3),
        "sentiment_score": s_score
    }


from config import STYLE_OPTIONS, STYLE_SCALES

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
            "communication_style": {
                "type": "object",
                "additionalProperties": False,
                "description": "각 스타일 항목을 0.00(최저/좌측) ~ 1.00(최고/우측) 사이의 소수점 값으로 평가",
                "properties": {
                    "tone": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": f"0.0({STYLE_SCALES['tone'][0]}) ~ 1.0({STYLE_SCALES['tone'][1]})"},
                    "directness": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": f"0.0({STYLE_SCALES['directness'][0]}) ~ 1.0({STYLE_SCALES['directness'][1]})"},
                    "emotion_expression": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": f"0.0({STYLE_SCALES['emotion_expression'][0]}) ~ 1.0({STYLE_SCALES['emotion_expression'][1]})"},
                    "empathy_signals": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": f"0.0({STYLE_SCALES['empathy_signals'][0]}) ~ 1.0({STYLE_SCALES['empathy_signals'][1]})"},
                    "initiative": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": f"0.0({STYLE_SCALES['initiative'][0]}) ~ 1.0({STYLE_SCALES['initiative'][1]})"},
                    "conflict_style": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": f"0.0({STYLE_SCALES['conflict_style'][0]}) ~ 1.0({STYLE_SCALES['conflict_style'][1]})"},
                },
                "required": ["tone", "directness", "emotion_expression", "empathy_signals", "initiative", "conflict_style"],
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
            "topics": {
                "type": "array",
                "description": "대화에서 드러나는 핵심 관심사/키워드 (예: 주식, 아이돌, 운동, 여행, 코딩)",
                "items": {"type": "string", "minLength": 2, "maxLength": 20},
                "minItems": 3,
                "maxItems": 10
            },
            "matching_tips": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "works_well_with": {"type": "array", "items": {"type": "string", "minLength": 5, "maxLength": 120}, "minItems": 2, "maxItems": 6},
                    "may_clash_with": {"type": "array", "items": {"type": "string", "minLength": 5, "maxLength": 120}, "minItems": 2, "maxItems": 6},
                },
                "required": ["works_well_with", "may_clash_with"]
            },
            "stats": {
                "type": "object",
                "properties": {
                    "msg_share": {"type": "number", "description": "전체 대화 중 내 메시지 점유율 (0~100%)"},
                    "avg_reply_latency": {"type": "number", "description": "평균 답장 시간 (분)"},
                    "question_ratio": {"type": "number", "description": "전체 내 발화 중 물음표(?) 포함 비율 (0.0~1.0)"}
                },
                "required": ["msg_share", "avg_reply_latency", "question_ratio"]
            },
            "dictionary_analysis": {
                "type": "object",
                "properties": {
                    "toxicity_score": {"type": "number", "description": "욕설/비속어 사용 비율 (0.0~1.0)"},
                    "sentiment_score": {"type": "object", "properties": {
                        "positive": {"type": "number"},
                        "negative": {"type": "number"},
                        "neutral": {"type": "number"}
                    }, "required": ["positive", "negative", "neutral"]}
                },
                "required": ["toxicity_score", "sentiment_score"]
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        },
        "required": [
            "language", "overall_summary", "communication_style",
            "topics", "notable_patterns", "strengths", "cautions",
            "matching_tips", "stats", "dictionary_analysis", "confidence"
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
- topics(관심사)는 대화에서 반복적으로 등장하거나 깊게 이야기한 주제를 명사 형태로 추출하세요.
- **communication_style**은 0.00(해당 성향이 매우 낮음) ~ 1.00(해당 성향이 매우 높음) 사이의 실수로 정밀하게 평가하세요.
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
    
    # [NEW] Statistical & Dict Analysis
    stats = analyze_statistics(rows, args.name)
    senti_db = load_sentiment_dict()
    dict_analysis = analyze_dictionary_based(msgs, senti_db)
    
    profile = call_llm_structured(prompt, args.model)
    
    # Merge Stats & Dict
    profile["stats"] = stats
    profile["dictionary_analysis"] = dict_analysis

    # 안전장치: language 강제
    profile["language"] = "ko"
    profile["_meta"] = {
        "source": "kakao_export_txt",
        "target_name": args.name,
        "message_count_used": len(msgs),
        "generated_at": datetime.utcnow().isoformat() + "Z",
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
