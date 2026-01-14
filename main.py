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
  python main.py --file "KakaoTalkChats.txt" --name "홍길동" --out "profile.json"
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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")  # account-dependent

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
    # [Name] [YYYY.MM.DD. 오후 1:23] message (Or [Name] [오후 1:23] message)
    re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.+?)\]\s+(?P<msg>.+)$"),
    # 2025. 1. 1. 오후 1:23, Name : message (PC/CSV Export)
    re.compile(r"^(?P<time>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.+)$"),
    # 2025년 1월 1일 오후 1:23, Name : message (Android Export)
    re.compile(r"^(?P<time>\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.+)$"),
]

def parse_kakao_lines(lines_iter) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for raw in lines_iter:
        line = raw.rstrip("\n")
        if not line.strip():
            continue

        m = None
        for pat in LINE_PATTERNS:
            m = pat.match(line)
            if m:
                break
        if not m:
            # 멀티라인 메시지(줄바꿈 이어지는 경우) 처리
            # 이전 메시지에 붙이는 로직 (간단 구현)
            if rows and len(rows) > 0:
                rows[-1]["text"] += "\n" + line
            continue

        rows.append({
            "speaker": m.group("name").strip(),
            "time": m.group("time").strip(),
            "text": m.group("msg").strip(),
        })
    return rows

def parse_kakao_txt(filepath: str) -> List[Dict[str, str]]:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return parse_kakao_lines(f)


# -------------------------------------------------------------------------
# 2) Preprocess (Korean-first)
# -------------------------------------------------------------------------
RE_URL = re.compile(r"https?://\S+")
RE_LAUGH = re.compile(r"[ㅋㅎ]{2,}")
RE_CRY = re.compile(r"[ㅠㅜ]{2,}")
RE_SPACES = re.compile(r"\s+")

def looks_like_system_message(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    
    # Exact match for common placeholders
    exact_skips = {"사진", "이모티콘", "동영상", "파일", "보이스톡", "통화", "송금", "입금", "출금", "투표"}
    if t in exact_skips:
        return True

    # Substring match for longer phrases
    long_skips = ["삭제된 메시지입니다"]
    for s in long_skips:
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
from config import BAD_WORDS_FILE, SENTIMENT_DICT_FILE

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
    다양한 포맷의 날짜/시간 문자열에서 시간 정보(HH:MM)를 추출하여 datetime 변환
    날짜 정보는 무시하고, '오전/오후'와 'HH:MM' 패턴을 찾습니다.
    """
    try:
        # Regex to find HH:MM
        # 12:34
        time_pat = re.compile(r"(?P<hour>\d{1,2}):(?P<min>\d{2})")
        m = time_pat.search(t_str)
        if not m:
            return None
        
        hour = int(m.group("hour"))
        minute = int(m.group("min"))
        
        # Adjust for PM
        # "오전", "오후", "AM", "PM" check
        is_pm = "오후" in t_str or "PM" in t_str.upper()
        is_am = "오전" in t_str or "AM" in t_str.upper()

        if is_pm and hour < 12:
            hour += 12
        if is_am and hour == 12:
            hour = 0
            
        # If no AM/PM indicator found, assume 24-hour format logic if reasonable or just keep it?
        # Many PC exports just say "14:00". Android often says "오후 2:00".
        # If we found "오후" but hour is already > 12 (e.g. 14), that's ambiguous, but usually valid 24h.
        
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
    
    # Load Bad Words (Lazy load or load here)
    bad_words_list = []
    if os.path.exists(BAD_WORDS_FILE):
        try:
            with open(BAD_WORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 'abuse' flag가 1인 것만 필터링 (필요시 otherHate 등도 포함 가능)
                bad_words_list = [item["text"] for item in data if item.get("abuse") == 1]
            print(f"[*] 욕설 사전 로드 완료 ({len(bad_words_list)}개)")
        except Exception as e:
            print(f"[Warning] 욕설 사전 로드 실패: {e}")
            
    if bad_words_list:
        for m in messages:
            for bad in bad_words_list:
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
    "name": "kakao_chat_profile_v2",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "language": {"type": "string", "enum": ["ko"]},
            "big5": {
                "type": "object",
                "additionalProperties": False,
                "description": "Big5(OCEAN) 성격 특성 5가지를 0.00~1.00 사이의 수치로 평가",
                "properties": {
                    "openness": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "개방성: 새로운 경험, 상상력, 호기심"},
                    "conscientiousness": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "성실성: 계획성, 책임감, 체계성"},
                    "extraversion": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "외향성: 사교성, 활동성, 자기주장"},
                    "agreeableness": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "우호성: 협조성, 타인에 대한 배려, 신뢰"},
                    "neuroticism": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "신경성: 정서적 불안정, 예민함, 걱정"}
                },
                "required": ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
            },
            "communication_style": {
                "type": "object",
                "additionalProperties": False,
                "description": "커뮤니케이션 스타일을 0.00~1.00 사이의 수치로 평가",
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
            "topics": {
                "type": "array",
                "description": "대화에서 드러나는 핵심 관심사 키워드 (최대 5개)",
                "items": {"type": "string", "minLength": 1, "maxLength": 10},
                "minItems": 1,
                "maxItems": 5
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        },
        "required": [
            "language", "big5", "communication_style", "topics", "confidence"
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
당신은 카카오톡 대화 데이터를 분석하여 화자의 성격과 스타일을 수치화하는 정밀 분석가입니다.
텍스트 설명보다는 **수치(Numerical Score)**와 **핵심 키워드** 추출에 집중하세요.

규칙:
1. **Big5 (OCEAN)**: 5대 성격 특성을 대화 내용에 근거하여 0.0~1.0 사이로 평가하세요.
2. **Communication Style**: 대화 스타일을 주어진 척도에 맞춰 0.0~1.0 사이로 평가하세요.
3. **Topics**: 관심사 키워드는 명사 중심으로 최대 5개만 추출하세요. (예: 주식, 야구, 연애)
4. 개인정보는 절대 포함하지 마세요.
5. 출력은 JSON Schema를 엄격히 준수하세요.

분석 대상: {target_name}
발화 샘플:
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
# 4) Orchestration & CLI
# ----------------------------
def analyze_kakao_data(rows: List[Dict[str, str]], target_name: str, model: str, limit: int = MAX_MESSAGES_FOR_LLM) -> dict:
    msgs = extract_target_messages(rows, target_name, limit=limit)
    if len(msgs) < 30:
        raise ValueError(f"분석 가능한 발화가 너무 적습니다(현재 {len(msgs)}개). --name(대화명)을 확인하세요.")

    prompt = build_prompt(target_name, msgs)
    
    # [NEW] Statistical & Dict Analysis
    stats = analyze_statistics(rows, target_name)
    senti_db = load_sentiment_dict()
    dict_analysis = analyze_dictionary_based(msgs, senti_db)
    
    profile = call_llm_structured(prompt, model)
    
    # Merge Stats & Dict
    profile["stats"] = stats
    profile["dictionary_analysis"] = dict_analysis

    # 안전장치: language 강제
    profile["language"] = "ko"
    profile["_meta"] = {
        "source": "kakao_export_txt",
        "target_name": target_name,
        "message_count_used": len(msgs),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model": model
    }
    return profile

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

    try:
        profile = analyze_kakao_data(rows, args.name, args.model, args.limit)
    except ValueError as e:
        raise SystemExit(str(e))

    out_text = json.dumps(profile, ensure_ascii=False, indent=2)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"[OK] Saved: {args.out}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
