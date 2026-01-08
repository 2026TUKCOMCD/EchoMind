import json
import os
import argparse
import glob
from typing import Dict, List, Any, Set
from config import LEGACY_TO_SCORE_MAP

try:
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    STOP_WORDS = {"사람", "성격", "성향", "분", "편", "것", "점", "수", "등", "나", "저"}
    USE_KIWI = True
except ImportError:
    kiwi = None
    STOP_WORDS = set()
    USE_KIWI = False
    print("[Warning] kiwipiepy(Kiwi)가 없습니다. 단순 텍스트 매칭만 수행합니다.")

try:
    from sentence_transformers import SentenceTransformer, util
    # 한국어 성능이 좋은 경량화 모델 사용 (최초 실행 시 자동 다운로드)
    print("[*] SBERT 모델 로딩 중... (최초 실행 시 시간이 걸릴 수 있습니다)")
    sbert_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    USE_SBERT = True
    print("[OK] SBERT 모델 로드 완료!")
except ImportError:
    sbert_model = None
    USE_SBERT = False
    print("[Warning] sentence-transformers가 없습니다. 의미 기반 매칭(Semantic Matching)을 건너뜁니다.")


# -------------------------------------------------------------------------
# 1. Scoring Configuration (가중치 설정)
# -------------------------------------------------------------------------
WEIGHT_STYLE = 35   # 스타일 유사도 (35점)
WEIGHT_STATS = 40   # 통계적 조화 (40점) - NEW
WEIGHT_TOPIC = 20   # 관심사 일치도 (20점)
WEIGHT_LLM   = 5    # AI 매칭 힌트 (5점)


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
    return keywords

def extract_meaningful_words(text: str) -> Set[str]:
    """
    텍스트에서 의미 있는 단어(명사, 어근)만 추출 (2글자 이상)
    """
    if not text: return set()
    
    # Kiwi가 없으면 띄어쓰기 단위로 대충 분리
    if not USE_KIWI:
        return set(text.split())

    words = set()
    try:
        # 형태소 분석
        tokens = kiwi.tokenize(text)
        for t in tokens:
            # 명사(N..) 또는 어근(XR)이면서, 한 글자가 아닌 것
            if (t.tag.startswith('N') or t.tag.startswith('XR')) and len(t.form) > 1:
                if t.form not in STOP_WORDS:
                    words.add(t.form)
    except Exception as e:
        print(f"[NLP Error] {e}")
        pass
        
    return words

def normalize_style_value(key: str, val: Any) -> float:
    """
    스타일 값을 0.0 ~ 1.0 실수로 변환
    """
    if isinstance(val, (int, float)):
        return max(0.0, min(1.0, float(val)))
        
    if isinstance(val, str):
        if val in LEGACY_TO_SCORE_MAP:
            return LEGACY_TO_SCORE_MAP[val]
        return 0.5
    return 0.5

def calculate_style_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    연속형 스타일 유사도 계산 (만점 1.0)
    """
    s1 = p1.get("communication_style", {})
    s2 = p2.get("communication_style", {})
    
    metrics = ["tone", "directness", "emotion_expression", "empathy_signals", "initiative", "conflict_style"]
    
    total_sim = 0.0
    
    for key in metrics:
        v1 = normalize_style_value(key, s1.get(key))
        v2 = normalize_style_value(key, s2.get(key))
        
        dist = abs(v1 - v2)
        sim = 1.0 - dist
        total_sim += sim

    return total_sim / len(metrics)

def calculate_statistics_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    통계 기반 매칭 점수 (만점 1.0)
    """
    st1 = p1.get("stats", {})
    st2 = p2.get("stats", {})
    dic1 = p1.get("dictionary_analysis", {})
    dic2 = p2.get("dictionary_analysis", {})
    
    if not st1 or not st2:
        return 0.5
        
    score = 0.0
    items = 0
    
    # 1. Share (Complementarity)
    sh1 = st1.get("msg_share", 50.0)
    sh2 = st2.get("msg_share", 50.0)
    share_sum = sh1 + sh2
    share_diff = abs(share_sum - 100.0)
    score += max(0.0, 1.0 - (share_diff / 80.0))
    items += 1
    
    # 2. Latency (Similarity)
    lat1 = st1.get("avg_reply_latency", 0.0)
    lat2 = st2.get("avg_reply_latency", 0.0)
    lat_diff = abs(lat1 - lat2)
    score += max(0.0, 1.0 - (lat_diff / 60.0))
    items += 1
    
    # 3. Question (Complementarity)
    q1 = st1.get("question_ratio", 0.0)
    q2 = st2.get("question_ratio", 0.0)
    q_diff = abs(q1 - q2)
    score += min(1.0, q_diff / 0.15)
    items += 1
    
    # 4. Toxicity (Penalty)
    tox1 = dic1.get("toxicity_score", 0.0)
    tox2 = dic2.get("toxicity_score", 0.0)
    avg_tox = (tox1 + tox2) / 2.0
    score += max(0.0, 1.0 - (avg_tox * 5))
    items += 1
    
    return score / items if items > 0 else 0.5

def calculate_topic_score(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    k1 = get_keywords(p1)
    k2 = get_keywords(p2)
    
    if not k1 or not k2:
        return 0.0
        
    overlap = len(k1.intersection(k2))
    return min(1.0, overlap / 5.0)

def calculate_semantic_similarity(text1: str, text2: str) -> float:
    if not USE_SBERT or not text1 or not text2:
        return 0.0
    emb1 = sbert_model.encode(text1, convert_to_tensor=True)
    emb2 = sbert_model.encode(text2, convert_to_tensor=True)
    return util.cos_sim(emb1, emb2).item()

def calculate_llm_hint_score(me: Dict[str, Any], candidate: Dict[str, Any]) -> float:
    tips = me.get("matching_tips", {})
    works = tips.get("works_well_with", [])
    clash = tips.get("may_clash_with", [])
    
    cand_summary = candidate.get("overall_summary", "") + " " + \
                   " ".join(candidate.get("strengths", [])) + " " + \
                   " ".join(candidate.get("notable_patterns", []))
                   
    score = 0.0
    
    for w in works:
        matched = False
        if USE_SBERT:
            sim = calculate_semantic_similarity(w, cand_summary)
            if sim > 0.4:  
                score += 0.5 * min(1.0, sim * 1.5)
                matched = True
        if not matched and USE_KIWI:
            w_keywords = extract_meaningful_words(w)
            cand_keywords = extract_meaningful_words(cand_summary)
            if w_keywords & cand_keywords:
                score += 0.5
                matched = True
        if not matched and not USE_KIWI and not USE_SBERT:
             if w in cand_summary:
                score += 0.5

    for c in clash:
        matched = False
        if USE_SBERT:
            sim = calculate_semantic_similarity(c, cand_summary)
            if sim > 0.45: 
                score -= 0.5 * min(1.0, sim * 1.5)
                matched = True
        if not matched and USE_KIWI:
            c_keywords = extract_meaningful_words(c)
            cand_keywords = extract_meaningful_words(cand_summary)
            if c_keywords & cand_keywords:
                score -= 0.5
                matched = True
        if not matched and not USE_KIWI and not USE_SBERT:
            if c in cand_summary:
                score -= 0.5
            
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
        if os.path.abspath(cf) == os.path.abspath(my_file):
            continue
            
        try:
            cand_profile = load_json(cf)
        except Exception as e:
            print(f"[Skip] 파일 로드 실패 ({os.path.basename(cf)}): {e}")
            continue

        cand_name = cand_profile.get("_meta", {}).get("target_name", "이름미상")
        
        # Calculate Scores
        s_style = calculate_style_score(my_profile, cand_profile)
        s_stats = calculate_statistics_score(my_profile, cand_profile)
        s_topic = calculate_topic_score(my_profile, cand_profile)
        s_llm   = calculate_llm_hint_score(my_profile, cand_profile)
        
        llm_mapped = (s_llm + 1.0) / 2.0
        
        total = (s_style * WEIGHT_STYLE) + \
                (s_stats * WEIGHT_STATS) + \
                (s_topic * WEIGHT_TOPIC) + \
                (llm_mapped * WEIGHT_LLM)
                
        results.append({
            "name": cand_name,
            "file": cf,
            "total_score": round(total, 1),
            "details": {
                "style": round(s_style * WEIGHT_STYLE, 1),
                "stats": round(s_stats * WEIGHT_STATS, 1),
                "topic": round(s_topic * WEIGHT_TOPIC, 1),
                "llm":   round(llm_mapped * WEIGHT_LLM, 1)
            },
            "topics": list(get_keywords(my_profile).intersection(get_keywords(cand_profile)))
        })
        
    results.sort(key=lambda x: x["total_score"], reverse=True)
    
    print("\n" + "="*60)
    print(f"   MATCHING RESULTS FOR [{my_name}]")
    print("="*60)
    
    for rank, res in enumerate(results[:5], 1): # Top 5
        print(f"\n[{rank}위] {res['name']} (점수: {res['total_score']}점)")
        print(f"  - 대화 성향(Style): {res['details']['style']} / {WEIGHT_STYLE}")
        print(f"  - 통계 데이터(Stats): {res['details']['stats']} / {WEIGHT_STATS}")
        print(f"  - 관심사 일치(Topic): {res['details']['topic']} / {WEIGHT_TOPIC} {res['topics']}")
        print(f"  - AI 분석매칭(Hint):  {res['details']['llm']} / {WEIGHT_LLM}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EchoMind Recommendation System")
    parser.add_argument("--my", required=True, help="Path to my profile JSON")
    parser.add_argument("--dir", required=True, help="Directory containing candidate JSONs")
    
    args = parser.parse_args()
    
    recommend_best_match(args.my, args.dir)
