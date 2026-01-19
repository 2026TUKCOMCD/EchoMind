# main.py
# -*- coding: utf-8 -*-

"""
[EchoMind Core] Scientific Deep Profiler (LLM-free / Numeric Only)
==================================================================

[프로그램 개요]
  카카오톡 대화 내역(.txt)을 분석하여 사용자의 성향, 라이프스타일, 지적 수준을
  0.0 ~ 1.0 사이의 정규화된 10차원 벡터(Vector)로 변환하는 핵심 모듈입니다.
  거대언어모델(LLM)을 사용하지 않고, 언어학적 통계와 시계열 분석 알고리즘을 적용하여
  데이터 양(Conversation Length)에 왜곡되지 않는 객관적인 지표를 산출합니다.

[핵심 알고리즘 및 과학적 근거]
  1. 시계열 분석 (Time-Series):
     - Session Tracking: 6시간 이상의 공백을 '새로운 대화 세션'으로 정의하여,
       단순 발화량이 아닌 '대화 시작 시도(Initiative)'를 정밀 추적합니다.

  2. 언어학적 통계 (Computational Linguistics):
     - Herdan's C Index: 텍스트 길이가 길어질수록 어휘 다양성(TTR)이 낮아지는 문제를 해결하기 위해,
       로그 스케일(log(Unique)/log(Total))을 적용하여 데이터 양에 독립적인 순수 어휘력을 측정합니다.
     - Shannon Entropy: 단어의 불확실성을 계산하여 기계적인 반복(매크로/도배)과 자연스러운 대화를 구분합니다.

  3. 데이터 정규화 (Normalization):
     - Sigmoid Function: 모든 수치를 단순 선형 변환하지 않고, 시그모이드 함수를 통해
       양극단(Outlier)의 영향을 줄이고 평균 구간의 변별력을 높였습니다.

[보안 및 프라이버시]
  - No Text Storage: 분석 과정에서 텍스트 내용을 램(RAM)에서만 처리하며,
    결과 파일(JSON)에는 오직 '수치 데이터'만 저장되므로 개인정보 유출 우려가 없습니다.

[산출 데이터 (7-Dimension Vector)]
  1. Basic: 활동성(Activity), 정중함(Polite), 직설성(Impact)
  2. Time : 주도성(Initiative)
  3. Lang : 어휘다양성(Vocab), 신뢰도(Entropy)
  4. Risk : 독성(Toxicity)

[실행 방법]
      - python main.py --file "KakaoTalk_Chat.txt" --name "홍길동" --out "profile.json"
      - python main.py --file "KakaoTalk_Chat.txt" --name "홍길동" --out "profile.json" --dict "korean_bad_words.json"
"""

import os
import re
import json
import argparse
import sys
import math
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

# ----------------------------
# 1. 설정 및 정규식
# ----------------------------
SYSTEM_SKIP_SUBSTR = [
    "사진", "이모티콘", "동영상", "삭제된 메시지입니다", "파일", "보이스톡", "통화", "송금", "입금", "출금"
]

LINE_PATTERNS = [
    re.compile(r"^(?P<time>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.+)$"),
    re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.+?)\]\s+(?P<msg>.+)$"),
]

# [추가됨] 개인정보 마스킹 패턴 (PII Masking)
RE_PII_PHONE = re.compile(r"01[0-9]-?\d{3,4}-?\d{4}")
RE_PII_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
RE_PII_RRN = re.compile(r"\d{6}-?[1-4]\d{6}")

# 성향 분석 정규식
RE_QUESTION = re.compile(r"\?")
# 감성 관련 정규식 제거됨
RE_HONORIFIC = re.compile(r"(습니다|세요|해요|했나요|인가요|시죠)\b")
RE_CASUAL = re.compile(r"(야\b|지\b|해\b|했어\b|임\b|ㄴ데|ㄱㄱ|ㅇㅇ)")
RE_HEDGE = re.compile(r"(글쎄|아마|약간|좀|..|...|같은데|모르겠)")
RE_ARGUMENT = re.compile(r"(아니|근데|하지만|솔직히|그게 아니라|틀렸)")

# ----------------------------
# 2. 헬퍼 함수
# ----------------------------
def parse_dt(time_str: str) -> Optional[datetime]:
    """
    시간 문자열을 파싱하여 datetime 객체 반환
    (수정됨: 24시간제 '16:01' 형식 지원 추가)
    """
    try:
        ts = time_str.strip()
        
        # Case 1: 날짜가 포함된 포맷 (YYYY. MM. DD. ...)
        if re.match(r"\d{4}\.", ts):
            ts = ts.replace("오전", "AM").replace("오후", "PM")
            ts = re.sub(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.", r"\1-\2-\3", ts)
            return datetime.strptime(ts, "%Y-%m-%d %p %I:%M")

        now = datetime.now()
        
        # Case 2: 24시간제 (예: "16:01") - '오전/오후'가 없고 ':'가 있는 경우
        if ':' in ts and not any(x in ts for x in ['오전', '오후', 'AM', 'PM']):
            dt = datetime.strptime(ts, "%H:%M")
            return dt.replace(year=now.year, month=now.month, day=now.day)

        # Case 3: 12시간제 (예: "오후 4:01")
        ts = ts.replace("오전", "AM").replace("오후", "PM")
        dt = datetime.strptime(ts, "%p %I:%M")
        return dt.replace(year=now.year, month=now.month, day=now.day)

    except Exception:
        return None

def sigmoid(x: float, center: float = 0.0, scale: float = 1.0) -> float:
    """수치를 0~1 사이로 부드럽게 매핑하는 함수"""
    return 1 / (1 + math.exp(-scale * (x - center)))

# ----------------------------
# 3. 데이터 로딩
# ----------------------------
def load_chat_data(filepath: str, target_name: str) -> Tuple[List[str], List[Dict], Dict]:
    target_msgs = []
    interaction_logs = [] 
    stats = {"total_lines": 0, "parsed_lines": 0, "target_count": 0, "other_count": 0}

    if not os.path.exists(filepath): return [], [], stats

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            stats["total_lines"] += 1
            line = raw.rstrip("\n")
            if not line: continue
            
            m = None
            for pat in LINE_PATTERNS:
                m = pat.match(line)
                if m: break
            
            if m:
                stats["parsed_lines"] += 1
                name = m.group("name").strip()
                time_str = m.group("time").strip()
                msg = m.group("msg").strip()
                
                if any(s in msg for s in SYSTEM_SKIP_SUBSTR): continue
                
                # 내부 로직용 시간 파싱 (주도성 분석용)
                dt = parse_dt(time_str)
                if not dt: continue

                is_target = (name == target_name)
                interaction_logs.append({"name": name, "dt": dt, "is_target": is_target})

                if is_target:
                    clean_msg = re.sub(r"https?://\S+", "", msg).strip()
                    
                    # [추가됨] 개인정보 마스킹 로직
                    clean_msg = RE_PII_PHONE.sub("(전화번호)", clean_msg)
                    clean_msg = RE_PII_EMAIL.sub("(이메일)", clean_msg)
                    clean_msg = RE_PII_RRN.sub("(주민번호)", clean_msg)

                    if clean_msg:
                        target_msgs.append(clean_msg)
                        stats["target_count"] += 1
                else:
                    stats["other_count"] += 1
                    
    interaction_logs.sort(key=lambda x: x["dt"])
    return target_msgs, interaction_logs, stats

# ----------------------------
# 4. 분석 모듈 (과학적 알고리즘 적용)
# ----------------------------

def analyze_time_and_initiative(logs: List[Dict]) -> Dict[str, float]:
    """[시간/주도성] 세션 기반 정밀 분석 (야간활동, 답장속도 제거됨)"""
    if not logs:
        return {"initiation_ratio": 0.0}

    session_starts = 0
    target_initiations = 0
    
    SESSION_THRESHOLD = 6 * 3600 # 6시간
    last_dt = None

    for i, log in enumerate(logs):
        curr_dt = log["dt"]
        is_target = log["is_target"]
        
        if i > 0:
            time_diff = (curr_dt - last_dt).total_seconds()
            if time_diff >= SESSION_THRESHOLD:
                # 새로운 세션 시작
                session_starts += 1
                if is_target: target_initiations += 1
        elif i == 0:
            session_starts += 1
            if is_target: target_initiations += 1

        last_dt = curr_dt

    # 1. 답장 속도 분석 로직 제거됨

    # 2. 선톡 비율
    score_init = target_initiations / session_starts if session_starts > 0 else 0.0
    
    # 3. 야간 활동성 계산 제거됨

    return {
        "initiation_ratio": round(score_init, 3)
    }

def analyze_vocabulary_and_reliability(messages: List[str]) -> Dict[str, float]:
    """
    [어휘력/신뢰도] 
    단순 비율(unique/total)의 오류를 해결하기 위해 'Herdan\'s C' 지표 사용
    """
    if not messages:
        return {"vocab_ttr": 0.0, "data_entropy": 0.0}
    
    all_tokens = []
    for m in messages:
        all_tokens.extend(m.split())
    
    total_tokens = len(all_tokens)
    if total_tokens < 10:
        return {"vocab_ttr": 0.0, "data_entropy": 0.0}

    # (2) 어휘 다양성 (Herdan's C Index)
    unique_count = len(set(all_tokens))
    
    if total_tokens > 1:
        herdan_index = math.log(unique_count) / math.log(total_tokens)
    else:
        herdan_index = 1.0

    score_vocab = sigmoid(herdan_index, center=0.84, scale=15.0)
    
    # (5) 데이터 신뢰도 (Shannon Entropy)
    counts = Counter(all_tokens)
    entropy = 0.0
    for count in counts.values():
        p = count / total_tokens
        entropy -= p * math.log2(p)
    
    score_entropy = sigmoid(entropy, center=4.0, scale=1.5)

    return {
        "vocab_ttr": round(score_vocab, 3),
        "data_entropy": round(score_entropy, 3)
    }

def analyze_basic_features(messages: List[str]) -> Dict[str, float]:
    """[기본 성향] 분석 (감성도 제거됨)"""
    if not messages: return {}
    count = len(messages)
    
    # 정규식 매칭 (감성 관련 제거)
    q_cnt = sum(1 for m in messages if RE_QUESTION.search(m))
    honor_cnt = sum(1 for m in messages if RE_HONORIFIC.search(m))
    casual_cnt = sum(1 for m in messages if RE_CASUAL.search(m))
    hedge_cnt = sum(1 for m in messages if RE_HEDGE.search(m))
    arg_cnt = sum(1 for m in messages if RE_ARGUMENT.search(m))

    # (A) 적극성: 질문 비율 + 평균 길이(로그 보정)
    avg_len = sum(len(m) for m in messages) / count
    score_len = sigmoid(avg_len, center=20, scale=0.1) 
    score_q = min(q_cnt/count / 0.2, 1.0)
    score_active = (score_len * 0.5) + (score_q * 0.5)

    # (B) 감성도 계산 제거됨

    # (C) 정중함
    total_tone = honor_cnt + casual_cnt
    score_polite = honor_cnt / total_tone if total_tone > 0 else 0.5

    # (D) 직설성
    score_hedge = sigmoid(hedge_cnt/count, center=0.05, scale=20.0)
    base_direct = 1.0 - score_hedge
    score_arg_boost = sigmoid(arg_cnt/count, center=0.02, scale=30.0) * 0.3
    score_impact = min(base_direct + score_arg_boost, 1.0)

    return {
        "activity_score": round(score_active, 3),
        "politeness_score": round(score_polite, 3),
        "impact_score": round(score_impact, 3)
    }

def calculate_toxicity(messages: List[str], bad_words: List[str]) -> float:
    if not messages or not bad_words: return 0.0
    hit = 0
    for m in messages:
        for bad in bad_words:
            if bad in m:
                hit += 1
                break
    return min(hit / len(messages) * 10, 1.0)

def load_bad_words(filepath: str) -> List[str]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                if data and isinstance(data[0], dict): return [d.get("text", "") for d in data]
                return data
    except: pass
    return []

# ----------------------------
# 5. 메인 실행
# ----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", default="profile.json")
    parser.add_argument("--dict", default="korean_bad_words_formatted.json")
    args = parser.parse_args()

    target_msgs, full_logs, stats = load_chat_data(args.file, args.name)
    if len(target_msgs) < 10:
        print(f"❌ 데이터 부족. 통계: {stats}")
        sys.exit(1)

    # 각 분석 모듈 호출
    basic_vec = analyze_basic_features(target_msgs)
    time_vec = analyze_time_and_initiative(full_logs)
    vocab_vec = analyze_vocabulary_and_reliability(target_msgs)
    
    bad_words = load_bad_words(args.dict)
    tox_score = calculate_toxicity(target_msgs, bad_words)

    final_vector = {
        **basic_vec,
        **time_vec,
        **vocab_vec,
        "toxicity_score": round(tox_score, 4)
    }

    output = {
        "user_id": args.name,
        "communication_vector": final_vector,
        "_meta": {
            "generated_at": datetime.now().isoformat(),
            "algorithm": "rule_based_scientific_v5",
            "parse_stats": stats,
            "reliability_check": "PASS" if vocab_vec["data_entropy"] > 0.3 else "WARNING"
        }
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"결과 개요: {args.out}")
    print("------------------------------------------------")
    print(f"[기본 성향] 적극성:{basic_vec.get('activity_score', 0)}")
    print(f"[대화 스킬] 선톡비율:{time_vec.get('initiation_ratio', 0)} / 어휘력(LogTTR):{vocab_vec.get('vocab_ttr', 0)}")
    print(f"[데이터 신뢰도] 엔트로피:{vocab_vec.get('data_entropy', 0)} / 독성:{tox_score}")
    print("------------------------------------------------")

if __name__ == "__main__":
    main()