import json
import os
import argparse
import glob
from typing import Dict, List, Any, Set

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
    # CPU에서도 무난하게 돌아가는 'paraphrase-multilingual-MiniLM-L12-v2' (470MB)
    # 혹은 더 가벼운 'distiluse-base-multilingual-cased-v2'
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
    
    # 5개 이상 겹치면 만점 처리 (변별력 강화: 3 -> 5)
    score = min(1.0, overlap / 5.0)
    return score

def calculate_semantic_similarity(text1: str, text2: str) -> float:
    """
    SBERT를 이용한 문장 의미 유사도 (0.0 ~ 1.0)
    """
    if not USE_SBERT or not text1 or not text2:
        return 0.0
        
    # Encode both texts
    emb1 = sbert_model.encode(text1, convert_to_tensor=True)
    emb2 = sbert_model.encode(text2, convert_to_tensor=True)
    
    # Cosine Similarity
    score = util.cos_sim(emb1, emb2).item()
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
        matched = False
        
        # 1. SBERT Semantic Match (Prioritized)
        if USE_SBERT:
            sim = calculate_semantic_similarity(w, cand_summary)
            # 유사도가 일정 수준(0.4) 이상이면 매칭 간주
            if sim > 0.4:  
                score += 0.5 * min(1.0, sim * 1.5) # 유사도가 높을수록 점수 더 줌
                matched = True
                
        # 2. Kiwi Keyword Match (Fallback / Complementary)
        if not matched and USE_KIWI:
            w_keywords = extract_meaningful_words(w)
            cand_keywords = extract_meaningful_words(cand_summary)
            if w_keywords & cand_keywords:
                score += 0.5
                matched = True
        
        # 3. Simple String Match (Last Resort)
        if not matched and not USE_KIWI and not USE_SBERT:
             if w in cand_summary:
                score += 0.5

    # 부정 힌트 찾기
    for c in clash:
        matched = False
        
        # 1. SBERT
        if USE_SBERT:
            sim = calculate_semantic_similarity(c, cand_summary)
            if sim > 0.45: # 부정 매칭은 좀 더 엄격하게(오탐 방지)
                score -= 0.5 * min(1.0, sim * 1.5)
                matched = True
                
        # 2. Kiwi
        if not matched and USE_KIWI:
            c_keywords = extract_meaningful_words(c)
            cand_keywords = extract_meaningful_words(cand_summary)
            # 부정 키워드 매칭 시, 단순 키워드 겹침은 오해의 소지가 큼(예: '감정'적 vs '감정' 표현 낮음)
            # 따라서 SBERT가 켜져있으면 Kiwi 부정 매칭은 스킵하거나 보수적으로 적용
            if c_keywords & cand_keywords:
                score -= 0.5
                matched = True
                
        # 3. String
        if not matched and not USE_KIWI and not USE_SBERT:
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
            
        try:
            cand_profile = load_json(cf)
        except Exception as e:
            print(f"[Skip] 파일 로드 실패 ({os.path.basename(cf)}): {e}")
            continue

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
