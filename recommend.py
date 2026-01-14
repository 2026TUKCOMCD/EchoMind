import json
import os
import argparse
import glob
import math
from typing import Dict, List, Any, Set
from config import LEGACY_TO_SCORE_MAP

# -------------------------------------------------------------------------
# 1. Scoring Configuration (가중치 설정)
# -------------------------------------------------------------------------
WEIGHT_BIG5  = 35   # 성격적 궁합 (35점) - NEW
WEIGHT_STYLE = 35   # 커뮤니케이션 스타일 유사도 (35점)
WEIGHT_STATS = 20   # 대화 패턴 조화 (20점)
WEIGHT_TOPIC = 10   # 관심사 일치 (10점)

# -------------------------------------------------------------------------
# 2. Helper Functions
# -------------------------------------------------------------------------
def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_keywords(profile: Dict[str, Any]) -> Set[str]:
    """
    프로필에서 관심사 키워드 추출 (topics)
    """
    keywords = set()
    if "topics" in profile:
        for t in profile["topics"]:
            keywords.add(t.replace(" ", "")) # 공백제거 비교
    return keywords

def normalize_value(val: Any) -> float:
    """
    값을 0.0 ~ 1.0 실수로 강제 변환
    """
    if isinstance(val, (int, float)):
        return max(0.0, min(1.0, float(val)))
    return 0.5

def euclidean_distance(v1: List[float], v2: List[float]) -> float:
    """
    두 벡터 간의 유클리드 거리 계산
    """
    sum_sq = sum((a - b) ** 2 for a, b in zip(v1, v2))
    return math.sqrt(sum_sq)

def calculate_big5_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    Big5 성격 매칭 점수 (유클리드 거리 기반)
    거리가 가까울수록(0) 점수가 높음(1.0).
    최대 거리는 sqrt(5) ≈ 2.236
    """
    b1 = p1.get("big5", {})
    b2 = p2.get("big5", {})
    
    traits = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
    vec1 = [normalize_value(b1.get(t)) for t in traits]
    vec2 = [normalize_value(b2.get(t)) for t in traits]
    
    dist = euclidean_distance(vec1, vec2)
    max_dist = math.sqrt(len(traits)) # sqrt(5)
    
    # 거리 역산 (1.0 - 정규화된 거리)
    score = 1.0 - (dist / max_dist)
    return max(0.0, score)

def calculate_style_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    스타일 유사도 계산 (만점 1.0)
    """
    s1 = p1.get("communication_style", {})
    s2 = p2.get("communication_style", {})
    
    metrics = ["tone", "directness", "emotion_expression", "empathy_signals", "initiative", "conflict_style"]
    
    total_sim = 0.0
    valid_metrics = 0
    
    for key in metrics:
        v1 = normalize_value(s1.get(key))
        v2 = normalize_value(s2.get(key))
        
        dist = abs(v1 - v2)
        sim = 1.0 - dist
        total_sim += sim
        valid_metrics += 1

    return total_sim / valid_metrics if valid_metrics > 0 else 0.5

def calculate_statistics_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    통계 기반 매칭 점수 (만점 1.0)
    """
    st1 = p1.get("stats", {})
    st2 = p2.get("stats", {})
    
    if not st1 or not st2:
        return 0.5
        
    score = 0.0
    items = 0
    
    # 1. Share (Complementarity: 합쳐서 100에 가까우면 좋음?? -> 아니면 50:50이 이상적?)
    # 여기서는 "비슷한 대화 점유율 성향"보다는 "티키타카"를 위해 양쪽 평균이 적절한지를 봄
    # 단순히 '답장 속도' 유사성에 가중치
    
    # 2. Latency (Similarity: 답장 텀이 비슷한 사람끼리 편함)
    lat1 = st1.get("avg_reply_latency", 0.0)
    lat2 = st2.get("avg_reply_latency", 0.0)
    # 60분 차이까지는 허용, 그 이상 차이나면 점수 깎임
    lat_diff = abs(lat1 - lat2)
    score += max(0.0, 1.0 - (lat_diff / 60.0))
    items += 1
    
    # 3. Question (유사성)
    q1 = st1.get("question_ratio", 0.0)
    q2 = st2.get("question_ratio", 0.0)
    q_diff = abs(q1 - q2)
    score += max(0.0, 1.0 - (q_diff / 0.2)) # 0.2 차이면 0점
    items += 1
    
    return score / items if items > 0 else 0.5

def calculate_topic_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    k1 = get_keywords(p1)
    k2 = get_keywords(p2)
    
    if not k1 or not k2:
        return 0.0
        
    overlap = len(k1.intersection(k2))
    # 공통 관심사가 1개라도 있으면 기본 점수, 3개 이상이면 만점
    return min(1.0, overlap / 3.0)

# -------------------------------------------------------------------------
# 3. Main Logic
# -------------------------------------------------------------------------
def get_recommendations(my_profile: Dict[str, Any], candidates_dir: str) -> List[Dict[str, Any]]:
    my_name = my_profile.get("_meta", {}).get("target_name", "나")
    
    cand_files = glob.glob(os.path.join(candidates_dir, "*.json"))
    results = []
    
    print(f"[*] '{my_name}' 님의 베스트 파트너를 찾는 중... (후보: {len(cand_files)}명)")
    
    for cf in cand_files:
        try:
            cand_profile = load_json(cf)
        except Exception as e:
            continue
            
        # 내 파일은 제외 (파일 경로 비교 대신 내용/이름으로 체크)
        # (간단히 이름이 같으면 제외하는 로직도 가능하지만, 동명이인 고려 시 파일 경로가 확실. 
        #  UI에서는 파일 경로가 없을 수 있으므로 여기서는 이름+메타데이터로 체크하거나 스킵)
        cand_name = cand_profile.get("_meta", {}).get("target_name", "이름미상")
        if cand_name == my_name: 
            continue

        # Calculate Scores
        s_big5  = calculate_big5_score(my_profile, cand_profile)
        s_style = calculate_style_score(my_profile, cand_profile)
        s_stats = calculate_statistics_score(my_profile, cand_profile)
        s_topic = calculate_topic_score(my_profile, cand_profile)
        
        total = (s_big5 * WEIGHT_BIG5) + \
                (s_style * WEIGHT_STYLE) + \
                (s_stats * WEIGHT_STATS) + \
                (s_topic * WEIGHT_TOPIC)
                
        results.append({
            "name": cand_name,
            "total_score": round(total, 1),
            "details": {
                "big5":  round(s_big5 * WEIGHT_BIG5, 1),
                "style": round(s_style * WEIGHT_STYLE, 1),
                "stats": round(s_stats * WEIGHT_STATS, 1),
                "topic": round(s_topic * WEIGHT_TOPIC, 1)
            },
            "topics": list(get_keywords(my_profile).intersection(get_keywords(cand_profile)))
        })
        
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results

def recommend_best_match(my_file: str, candidates_dir: str):
    if not os.path.exists(my_file):
        print(f"[Error] 내 프로필 파일을 찾을 수 없습니다: {my_file}")
        return

    my_profile = load_json(my_file)
    results = get_recommendations(my_profile, candidates_dir)
    
    my_name = my_profile.get("_meta", {}).get("target_name", "나")
    print("\n" + "="*60)
    print(f"   MATCHING RESULTS FOR [{my_name}]")
    print("="*60)
    
    for rank, res in enumerate(results[:5], 1): # Top 5
        print(f"\n[{rank}위] {res['name']} (점수: {res['total_score']}점)")
        print(f"  - 성격 궁합(Big5) : {res['details']['big5']} / {WEIGHT_BIG5}")
        print(f"  - 대화 성향(Style): {res['details']['style']} / {WEIGHT_STYLE}")
        print(f"  - 패턴 조화(Stats): {res['details']['stats']} / {WEIGHT_STATS}")
        print(f"  - 관심사(Topic)   : {res['details']['topic']} / {WEIGHT_TOPIC} {res['topics']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EchoMind Recommendation System")
    parser.add_argument("--my", required=True, help="Path to my profile JSON")
    parser.add_argument("--dir", required=True, help="Directory containing candidate JSONs")
    
    args = parser.parse_args()
    
    recommend_best_match(args.my, args.dir)
