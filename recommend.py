import json
import os
import argparse
import glob
from typing import Dict, List, Any, Set

# -------------------------------------------------------------------------
# 1. Scoring Configuration (가중치 설정)
# -------------------------------------------------------------------------
WEIGHT_STYLE = 50   # 스타일 유사도 (50점)
WEIGHT_TOPIC = 30   # 관심사 일치도 (30점)
WEIGHT_LLM   = 20   # AI 매칭 힌트 (20점)

# 스타일 점수 매핑 (거리 계산용)
STYLE_MAP = {
    "tone": {"친근함": 0, "공손함": 1, "중립적": 2, "건조함": 3, "공격적": 4},
    "directness": {"직설적": 0, "상황따라변함": 1, "완곡적": 2},
    "emotion_expression": {"높음": 2, "보통": 1, "낮음": 0},
    "empathy_signals": {"높음": 2, "보통": 1, "낮음": 0}
}

# -------------------------------------------------------------------------
# 2. Helper Functions
# -------------------------------------------------------------------------
def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_keywords(profile: Dict[str, Any]) -> Set[str]:
    """
    프로필에서 관심사 키워드 추출 (topics 우선, 없으면 notable_patterns 등 활용)
    """
    keywords = set()
    # 1. topics (신규 스키마)
    if "topics" in profile:
        for t in profile["topics"]:
            keywords.add(t.replace(" ", "")) # 공백제거 비교
            
    # 2. notable_patterns (보조)
    # 토픽이 너무 적으면 패턴에서도 일부 명사만 추출할 수 있으나, 
    # 여기서는 단순 문자열 매칭보다는 topics 필드 의존도를 높임.
    return keywords

def calculate_style_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    스타일 유사도 계산 (만점 1.0)
    """
    s1 = p1.get("communication_style", {})
    s2 = p2.get("communication_style", {})
    
    score_sum = 0
    max_sum = 0
    
    # A. 단순 유사도 (거리가 가까울수록 점수 높음)
    for key in ["tone", "directness", "emotion_expression", "empathy_signals"]:
        if key not in STYLE_MAP: continue
        
        val1 = s1.get(key)
        val2 = s2.get(key)
        
        if val1 not in STYLE_MAP[key] or val2 not in STYLE_MAP[key]:
            # 값이 없거나 모르는 값이면 중간 점수 부여
            score_sum += 0.5
        else:
            # Normalized Distance (0~1)
            v1 = STYLE_MAP[key][val1]
            v2 = STYLE_MAP[key][val2]
            max_dist = max(STYLE_MAP[key].values())
            dist = abs(v1 - v2)
            similarity = 1.0 - (dist / max_dist)
            score_sum += similarity
            
        max_sum += 1

    # B. 보완적 관계 (Initiative: 주도형+반응형=Good)
    # 주도+주도(충돌), 반응+반응(침묵) 보다는 섞인게 낫다고 가정 (기획 반영)
    i1 = s1.get("initiative")
    i2 = s2.get("initiative")
    
    initiative_score = 0.5 # 기본
    if i1 and i2:
        if i1 == i2:
            if i1 == "혼합형": initiative_score = 1.0
            else: initiative_score = 0.3 # 둘다 주도 혹은 둘다 반응 -> 감점
        else:
            # 서로 다르면 (주도+반응, 주도+혼합 등) -> 보완적 관계
            initiative_score = 1.0
            
    score_sum += initiative_score
    max_sum += 1
    
    # C. 갈등 해결 (Conflict: 직면+회피=Bad)
    c1 = s1.get("conflict_style")
    c2 = s2.get("conflict_style")
    conflict_score = 0.5
    if c1 and c2:
        if (c1 == "직면" and c2 == "회피") or (c1 == "회피" and c2 == "직면"):
            conflict_score = 0.0 # 최악의 상성
        elif c1 == c2:
            conflict_score = 1.0
        else:
            conflict_score = 0.8
            
    score_sum += conflict_score
    max_sum += 1

    return score_sum / max_sum if max_sum > 0 else 0

def calculate_topic_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    관심사 일치도 (만점 1.0)
    """
    k1 = get_keywords(p1)
    k2 = get_keywords(p2)
    
    if not k1 or not k2:
        return 0.0
        
    # 교집합 개수
    overlap = len(k1.intersection(k2))
    
    # 3개 이상 겹치면 만점 처리 (너무 엄격하지 않게)
    score = min(1.0, overlap / 3.0)
    return score

def calculate_llm_hint_score(me: Dict[str, Any], candidate: Dict[str, Any]) -> float:
    """
    LLM 힌트 매칭 (만점 1.0, 최저 -1.0)
    """
    tips = me.get("matching_tips", {})
    works = tips.get("works_well_with", [])
    clash = tips.get("may_clash_with", [])
    
    cand_summary = candidate.get("overall_summary", "") + " " + \
                   " ".join(candidate.get("strengths", [])) + " " + \
                   " ".join(candidate.get("notable_patterns", []))
                   
    score = 0.0
    
    # 긍정 힌트 찾기
    for w in works:
        if w in cand_summary:
            score += 0.5 # 하나라도 있으면 크게 가점
            
    # 부정 힌트 찾기
    for c in clash:
        if c in cand_summary:
            score -= 0.5
            
    # Range Clamping (-1.0 ~ 1.0) -> Normalize to 0.0 ~ 1.0 for weighted sum?
    # 여기서는 보너스 점수이므로 -점수도 허용하되, 최종 합산시 고려
    return max(-1.0, min(1.0, score))

# -------------------------------------------------------------------------
# 3. Main Logic
# -------------------------------------------------------------------------
def recommend_best_match(my_file: str, candidates_dir: str):
    if not os.path.exists(my_file):
        print(f"[Error] 내 프로필 파일을 찾을 수 없습니다: {my_file}")
        return

    my_profile = load_json(my_file)
    my_name = my_profile.get("_meta", {}).get("target_name", "나")
    
    cand_files = glob.glob(os.path.join(candidates_dir, "*.json"))
    results = []
    
    print(f"[*] '{my_name}' 님의 베스트 파트너를 찾는 중... (후보: {len(cand_files)}명)")
    
    for cf in cand_files:
        # 내 파일은 제외
        if os.path.abspath(cf) == os.path.abspath(my_file):
            continue
            
        cand_profile = load_json(cf)
        cand_name = cand_profile.get("_meta", {}).get("target_name", "이름미상")
        
        # 1. Calculate Scores
        s_style = calculate_style_score(my_profile, cand_profile)
        s_topic = calculate_topic_score(my_profile, cand_profile)
        s_llm   = calculate_llm_hint_score(my_profile, cand_profile)
        
        # 2. Weighted Sum
        # LLM Score는 -1~1 범위이므로, 0~1로 정규화하거나 그대로 보너스로 사용.
        # 여기서는 기본 100점 만점 구조에 더하는 식으로 계산
        # Style(50) + Topic(30) + LLM(20, but mapped from -1~1 to 0~1 ish)
        
        # LLM 점수 변환: -1(0점) ~ 0(10점) ~ 1(20점)
        llm_mapped = (s_llm + 1.0) / 2.0  # 0.0 ~ 1.0
        
        total = (s_style * WEIGHT_STYLE) + \
                (s_topic * WEIGHT_TOPIC) + \
                (llm_mapped * WEIGHT_LLM)
                
        results.append({
            "name": cand_name,
            "file": cf,
            "total_score": round(total, 1),
            "details": {
                "style": round(s_style * WEIGHT_STYLE, 1),
                "topic": round(s_topic * WEIGHT_TOPIC, 1),
                "llm":   round(llm_mapped * WEIGHT_LLM, 1)
            },
            "topics": list(get_keywords(my_profile).intersection(get_keywords(cand_profile)))
        })
        
    # 3. Rank
    results.sort(key=lambda x: x["total_score"], reverse=True)
    
    # 4. Output
    print("\n" + "="*60)
    print(f"   MATCHING RESULTS FOR [{my_name}]")
    print("="*60)
    
    for rank, res in enumerate(results[:5], 1): # Top 5
        print(f"\n[{rank}위] {res['name']} (점수: {res['total_score']}점)")
        print(f"  - 대화 스타일: {res['details']['style']} / {WEIGHT_STYLE}")
        print(f"  - 관심사 일치: {res['details']['topic']} / {WEIGHT_TOPIC} {res['topics']}")
        print(f"  - AI 분석매칭: {res['details']['llm']} / {WEIGHT_LLM}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EchoMind Recommendation System")
    parser.add_argument("--my", required=True, help="Path to my profile JSON")
    parser.add_argument("--dir", required=True, help="Directory containing candidate JSONs")
    
    args = parser.parse_args()
    
    recommend_best_match(args.my, args.dir)
