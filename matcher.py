# matcher.py
# -*- coding: utf-8 -*-

"""
[EchoMind Matcher v4.5] 다차원 성향 분석 및 하이브리드 매칭 시스템
================================================================

[시스템 개요]
본 시스템은 단순한 성격 유형의 일치를 넘어, 사용자의 '기질적 성향(Big5)', 
'관계적 상호보완성(Socionics)', '행동 패턴(Activity)'을 입체적으로 분석하여 
최적의 파트너를 산출하는 하이브리드 매칭 엔진입니다.

[핵심 알고리즘 및 가중치]
1. Similarity (기질적 유사성) - 50%
   - Big5(OCEAN) 5차원 벡터의 코사인 유사도(Cosine Similarity)를 계산합니다.
   - 모집단 통계 기반 Z-Score 정규화를 통해 수치 편향을 제거하고 순수한 기질 일치도를 측정합니다.

2. Chemistry (관계적 화학작용) - 40%
   - MBTI 4지표와 소시오닉스(Socionics) 이론을 결합하여 관계의 역동성을 평가합니다.
   - 16가지 관계론(Intertype Relations) 적용: 
     이원(Dual), 활동(Activity), 거울(Mirror) 등 시너지 관계에 높은 가산점을 부여하고,
     갈등(Conflict)이나 초자아(Super-Ego) 관계는 감점 요인으로 반영합니다.
   - 쿼드라(Quadra) 분석을 통해 삶의 가치관 공유 여부를 판단합니다.

3. Activity (커뮤니케이션 활동성) - 10%
   - 파싱된 대화량(Parsed Lines)의 로그 비율을 분석하여 
     의사소통의 에너지 레벨(수다스러움/과묵함)이 유사한 사용자를 매칭합니다.

[데이터 무결성 및 안전장치 (Integrity & Safety)]
- Zero Vector Protection: 데이터 부족으로 인한 0 벡터 연산 시 수학적 오류(NaN) 방지.
- Missing Data Handling: MBTI 결측값('XXXX') 발생 시 왜곡된 매칭 결과(Phantom Duality) 차단.
- Sparse Data Correction: 극소량의 데이터(10줄 미만) 매칭 시 활동성 점수 왜곡 방지.

[사용법]
  python matcher.py --target "profile.json" --db "./candidates_db" --output "result.json"
"""

import argparse
import json
import os
import glob
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from scipy.spatial.distance import cosine

# ----------------------------
# 1. 데이터 구조 정의 (Data Structures)
# ----------------------------
@dataclass
class UserVector:
    user_id: str
    name: str
    
    # Raw Data (LLM 추출 값)
    mbti_type: str        # 예: INTJ
    mbti_conf: float      # 신뢰도 (0.0 ~ 1.0)
    big5_raw: np.array    # [O, C, E, A, N] (0~100)
    big5_conf: float
    socionics_type: str   # 예: LII, SLE
    socionics_conf: float
    
    # Normalized Data (통계적 보정 값)
    big5_z_score: Optional[np.array] = None
    
    # Activity Data
    line_count: int = 0

# ----------------------------
# 2. 관계 분석 두뇌 (Relationship Brain)
# ----------------------------
class RelationshipBrain:
    """
    MBTI 4글자 조합을 분석하여 소시오닉스의 '16가지 관계론'을 도출하고, 
    이에 따른 정교한 화학작용(Chemistry) 점수를 부여합니다.
    """

    # 소시오닉스 4대 쿼드라 (가치관 공유 그룹)
    QUADRAS = {
        "Alpha (개방/아이디어)": ["ILE", "SEI", "ESE", "LII"],
        "Beta (열정/규율)":     ["EIE", "LSI", "SLE", "IEI"],
        "Gamma (실용/독립)":    ["SEE", "ILI", "LIE", "ESI"],
        "Delta (평화/성실)":    ["LSE", "EII", "IEE", "SLI"]
    }

    @staticmethod
    def get_socionics_score(type_a: str, type_b: str) -> float:
        """
        [소시오닉스 쿼드라 로직]
        같은 쿼드라일 경우 대화의 결이 맞고 가치관 충돌이 적어 높은 점수(1.0)를 줍니다.
        """
        if not type_a or not type_b or type_a == "UNK" or type_b == "UNK":
            return 0.5 

        quadra_a = None
        quadra_b = None

        for q_name, types in RelationshipBrain.QUADRAS.items():
            if type_a in types: quadra_a = q_name
            if type_b in types: quadra_b = q_name
        
        if quadra_a and quadra_b:
            if quadra_a == quadra_b:
                return 1.0  # 같은 쿼드라 (Best Value Match)
            else:
                return 0.4  # 다른 쿼드라
        
        return 0.5

    @staticmethod
    def analyze_relationship(type_a: str, type_b: str) -> Dict[str, any]:
        """
        [MBTI 기반 관계 정밀 분석]
        두 MBTI 유형 간의 관계를 분석하여 점수와 구체적인 관계명(Label)을 반환합니다.
        """
        a = type_a.upper()
        b = type_b.upper()

        if len(a) != 4 or len(b) != 4:
            return {"score": 0.5, "label": "Unknown"}

        # [CRITICAL CHECK] 데이터 누락('XXXX') 시 Dual로 오판되는 것을 방지
        if 'X' in a or 'X' in b:
            return {"score": 0.5, "label": "Unknown"}

        # 지표별 비교
        same_EI = a[0] == b[0]
        same_NS = a[1] == b[1]
        same_TF = a[2] == b[2]
        same_JP = a[3] == b[3]

        diff_count = sum([not same_EI, not same_NS, not same_TF, not same_JP])

        # ------------------------------------------------------------
        # [A-Tier] 영혼의 파트너 (상호보완 & 시너지)
        # ------------------------------------------------------------
        
        # 1. 이원 관계 (Duality) - Score: 1.0 (MAX)
        # 조건: 4글자가 모두 다름 (예: INTJ <-> ESFP)
        if diff_count == 4:
            return {"score": 1.0, "label": "Dual (이원)"}

        # 2. 활동 관계 (Activity) - Score: 0.9
        # 조건: E/I 동일 + 나머지 3개 모두 다름
        # 예: ENTP <-> ESFJ
        if same_EI and not same_NS and not same_TF and not same_JP:
            return {"score": 0.9, "label": "Activity (활동)"}
        
        # 3. 거울 관계 (Mirror) - Score: 0.8
        # 조건: E/I 다름 + N/S, T/F, J/P 같음
        if not same_EI and same_NS and same_TF and same_JP:
            return {"score": 0.8, "label": "Mirror (거울)"}

        # ------------------------------------------------------------
        # [B-Tier] 좋은 동료 (유사성 & 이해)
        # ------------------------------------------------------------

        # 4. 유사/비즈니스 관계 (Kindred / Look-alike) - Score: 0.75
        # 조건: E/I와 J/P는 같고, 가운데 기능 하나만 다름
        # 예: ENTP <-> ENFP (Kindred), ENTP <-> ESTP (Look-alike)
        if same_EI and same_JP and diff_count == 1:
             return {"score": 0.75, "label": "Kindred/Biz (유사)"}

        # 6. 수혜/감독 등 비대칭 협력 - Score: 0.65
        # 예: 기능적 유사성은 있으나 J/P가 다른 경우
        if (same_NS or same_TF) and not same_JP:
             return {"score": 0.65, "label": "Asymmetric (협력)"}
        
        # 5. 동일 관계 (Identical) - Score: 0.6
        # 서로를 완벽히 이해하지만, 같은 약점을 공유하여 상호보완이 어려움
        if diff_count == 0:
            return {"score": 0.6, "label": "Identical (동일)"}

        # ------------------------------------------------------------
        # [C-Tier] 갈등 및 주의 (스트레스)
        # ------------------------------------------------------------

        # 7. 초자아 관계 (Super-Ego) - Score: 0.3
        # 조건: E/I, J/P는 같으나 기능(N/S, T/F)이 다름 (예: ENTP <-> ESFP)
        # 겉보기엔 비슷하나 가치관이 안 맞음
        if same_EI and same_JP and not same_NS and not same_TF:
            return {"score": 0.3, "label": "Super-Ego (초자아)"}
        
        # 8. 갈등 관계 (Conflict) - Score: 0.1 (MIN)
        # 조건: J/P만 같고 나머지는 다 다름 (예: INTP <-> ESFP)
        if not same_EI and not same_NS and not same_TF and same_JP:
             return {"score": 0.1, "label": "Conflict (갈등)"}

        # 9. 그 외 중립
        return {"score": 0.5, "label": "Neutral (보통)"}

    @staticmethod
    def get_chemistry_score(type_a: str, type_b: str) -> float:
        return RelationshipBrain.analyze_relationship(type_a, type_b)["score"]
    
    @staticmethod
    def get_label(type_a: str, type_b: str) -> str:
        return RelationshipBrain.analyze_relationship(type_a, type_b)["label"]

# ----------------------------
# 3. 매칭 엔진 (Matching Engine)
# ----------------------------
class HybridMatcher:
    def __init__(self, candidates: List[UserVector]):
        self.candidates = candidates
        self.stats_mean = np.array([50.0]*5)
        self.stats_std = np.array([15.0]*5)
        self._calculate_population_stats()

    def _calculate_population_stats(self):
        """전체 후보군의 Big5 분포(평균, 표준편차) 계산"""
        if not self.candidates: return
        
        all_big5 = np.array([u.big5_raw for u in self.candidates])
        count = len(self.candidates)
        weight_real = min(1.0, count / 10.0) # 데이터 적을 땐 기본값 보정
        
        real_mean = np.mean(all_big5, axis=0)
        real_std = np.std(all_big5, axis=0) + 1e-6

        self.stats_mean = (real_mean * weight_real) + (np.array([50.0]*5) * (1 - weight_real))
        self.stats_std = (real_std * weight_real) + (np.array([15.0]*5) * (1 - weight_real))

    def normalize_user(self, user: UserVector):
        """Z-Score 정규화"""
        z_scores = (user.big5_raw - self.stats_mean) / self.stats_std
        user.big5_z_score = np.clip(z_scores, -3.0, 3.0)

    def calculate_activity_score(self, count_a: int, count_b: int) -> float:
        """
        [Activity Score] 활동성 유사도 계산
        - 대화량(parsed_lines)의 차이가 적을수록 높은 점수
        - 데이터 부족(10줄 미만) 시 중립 점수(0.5) 반환하여 왜곡 방지
        """
        if count_a < 10 or count_b < 10:
            return 0.5

        a = max(count_a, 10)
        b = max(count_b, 10)
        
        # 로그 비율 계산 (큰 수 / 작은 수) -> 1.0에 가까울수록 비슷함
        ratio = max(a, b) / min(a, b) 
        
        # 공식: 1 / log2(ratio + 1)
        score = 1.0 / (np.log2(ratio) + 1.0)
        
        return max(0.0, min(1.0, score))

    def calculate_match_score(self, target: UserVector, candidate: UserVector) -> Dict[str, float]:
        """
        [최종 매칭 점수 산출]
        공식: Score = (Similarity * 0.5) + (Chemistry * 0.4) + (Activity * 0.1)
        """
        
        # --- [A] Similarity Score (50%) ---
        # Big5 Z-Score 기반 코사인 유사도
        # Zero Vector (모든 값이 평균이라 0인 경우) 예외 처리
        try:
            dist = cosine(target.big5_z_score, candidate.big5_z_score)
            if np.isnan(dist):
                cos_sim = 0.0 # 계산 불가 시 0점 처리
            else:
                cos_sim = 1 - dist
        except:
            cos_sim = 0.0 # 안전장치

        similarity_score = (cos_sim + 1) / 2
        
        # --- [B] Chemistry Score (40%) ---
        # B-1. MBTI 상호보완성
        mbti_chem = RelationshipBrain.get_chemistry_score(target.mbti_type, candidate.mbti_type)
        # B-2. 소시오닉스 쿼드라 매칭
        socio_chem = RelationshipBrain.get_socionics_score(target.socionics_type, candidate.socionics_type)
        
        # 신뢰도 기반 가중 평균 (점수 깎지 않음, 비중만 조절)
        w_m = (target.mbti_conf * candidate.mbti_conf) ** 0.5
        w_s = (target.socionics_conf * candidate.socionics_conf) ** 0.5
        
        weight_sum = w_m + w_s + 1e-9
        chemistry_score = ((mbti_chem * w_m) + (socio_chem * w_s)) / weight_sum

        # --- [C] Activity Score (10%) ---
        activity_score = self.calculate_activity_score(target.line_count, candidate.line_count)

        # --- [D] Final Score ---
        # 순수 점수 합산 (가중치: 50 : 40 : 10)
        final_score = (similarity_score * 0.5) + (chemistry_score * 0.4) + (activity_score * 0.1)
        
        return {
            "total_score": final_score,
            "similarity_score": similarity_score,
            "chemistry_score": chemistry_score,
            "activity_score": activity_score,
            "mbti_detail": mbti_chem,
            "socio_detail": socio_chem
        }

# ----------------------------
# 4. 파일 입출력 및 메인 실행
# ----------------------------
def load_profile(filepath: str) -> Optional[UserVector]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        meta = data.get('meta', {})
        prof = data.get('llm_profile', {})
        parse_q = data.get('parse_quality', {}) 

        b5 = prof.get('big5', {})
        scores = b5.get('scores_0_100', {})
        
        big5_vec = np.array([
            scores.get('openness', 50),
            scores.get('conscientiousness', 50),
            scores.get('extraversion', 50),
            scores.get('agreeableness', 50),
            scores.get('neuroticism', 50)
        ], dtype=float)

        return UserVector(
            user_id=meta.get('user_id', 'unknown'),
            name=meta.get('speaker_name', 'unknown'),
            mbti_type=prof.get('mbti', {}).get('type', 'XXXX'),
            mbti_conf=float(prof.get('mbti', {}).get('confidence', 0.5)),
            big5_raw=big5_vec,
            big5_conf=float(b5.get('confidence', 0.5)),
            socionics_type=prof.get('socionics', {}).get('type', 'UNK'),
            socionics_conf=float(prof.get('socionics', {}).get('confidence', 0.5)),
            line_count=parse_q.get('parsed_lines', 0)
        )
    except Exception as e:
        print(f"[Warn] 파일 로드 실패 ({filepath}): {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="EchoMind Hybrid Matcher")
    parser.add_argument("--target", required=True, help="타겟 프로필 JSON 경로")
    parser.add_argument("--db", required=True, help="후보군 폴더 경로")
    parser.add_argument("--output", help="매칭 결과 저장 경로 (.json)", default=None) # [New] JSON 출력 옵션 추가
    args = parser.parse_args()

    # 1. 로드
    target_user = load_profile(args.target)
    if not target_user:
        print("타겟 프로필 오류")
        return

    candidate_files = glob.glob(os.path.join(args.db, "*.json"))
    candidates = []
    for cf in candidate_files:
        if os.path.abspath(cf) == os.path.abspath(args.target): continue
        c = load_profile(cf)
        if c and c.user_id != target_user.user_id: 
            candidates.append(c)

    if not candidates:
        print("후보자가 없습니다.")
        return

    # 2. 매칭 엔진
    matcher = HybridMatcher(candidates + [target_user])
    matcher.normalize_user(target_user)
    for c in candidates: matcher.normalize_user(c)

    # 3. 결과 출력 및 JSON 저장 준비
    results = []
    
    # [New] JSON 저장을 위한 데이터 구조 초기화
    json_output = {
        "target_user": {
            "name": target_user.name,
            "mbti": target_user.mbti_type,
            "socionics": target_user.socionics_type,
            "line_count": target_user.line_count
        },
        "matches": []
    }

    print(f"\n[EchoMind] 매칭 결과 리포트 - 사용자: {target_user.name} ({target_user.mbti_type}) | 활동량: {target_user.line_count} lines")
    print("=" * 115)
    print(f"{'순위':<4} {'이름':<8} {'MBTI':<6} {'관계 유형 (Chemistry)':<25} {'총점':<7} | {'성향(50%)':<9} {'궁합(40%)':<9} {'활동(10%)':<9}")
    print("-" * 115)

    for c in candidates:
        res = matcher.calculate_match_score(target_user, c)
        results.append({"cand": c, "res": res})

    results.sort(key=lambda x: x['res']['total_score'], reverse=True)

    for idx, r in enumerate(results):
        c = r['cand']
        d = r['res']
        
        # RelationshipBrain에서 직접 관계 레이블 가져오기
        rel_label = RelationshipBrain.get_label(target_user.mbti_type, c.mbti_type)
        if d['socio_detail'] > 0.8: rel_label += " (Quadra)"

        # 콘솔 출력 (기존 유지)
        print(f"{idx+1:<4} {c.name:<8} {c.mbti_type:<6} {rel_label:<25} {d['total_score']:.3f}   | {d['similarity_score']:.3f}     {d['chemistry_score']:.3f}     {d['activity_score']:.3f}")

        # [New] JSON 데이터 구성
        if args.output:
            json_output["matches"].append({
                "rank": idx + 1,
                "name": c.name,
                "user_id": c.user_id,
                "mbti": c.mbti_type,
                "socionics": c.socionics_type,
                "relationship_label": rel_label,
                "scores": {
                    "total": round(d['total_score'], 4),
                    "similarity": round(d['similarity_score'], 4),
                    "chemistry": round(d['chemistry_score'], 4),
                    "activity": round(d['activity_score'], 4)
                }
            })

    print("=" * 115)
    print(f"* 총점 공식: (성향 x 0.5) + (궁합 x 0.4) + (활동 x 0.1)")
    print(f"* 화학작용 상세: {RelationshipBrain.get_label(target_user.mbti_type, target_user.mbti_type)} 등 16가지 관계론 적용")

    # [New] JSON 파일 저장
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, indent=4, ensure_ascii=False)
            print(f"\n[System] 매칭 결과가 '{args.output}' 파일로 저장되었습니다.")
        except Exception as e:
            print(f"\n[Error] 결과 파일 저장 중 오류 발생: {e}")

if __name__ == "__main__":
    main()