# matcher.py
# -*- coding: utf-8 -*-

"""
[EchoMind] 다차원 성격 분석 및 하이브리드 매칭 시스템
========================================================================================

[시스템 개요]
본 시스템은 '기질(Big5)', '관계 상성(소시오닉스)', '행동 패턴(Activity)'을 
종합적으로 분석하여 최적의 파트너를 찾아주는 하이브리드 매칭 엔진입니다.

[핵심 알고리즘 및 가중치]
1. 유사성 (Temperamental Similarity) - 50%
   - Big5(OCEAN) 5차원 벡터의 코사인 유사도를 계산합니다.
   - 모집단 통계 기반의 Z-Score 정규화를 적용하여 수치적 편향을 제거합니다.

2. 케미스트리 (Relational Chemistry) - 40%
   - MBTI 4지표와 소시오닉스(Socionics) 이론을 결합하여 관계 역학을 평가합니다.
   - 16가지 관계 유형(Intertype Relations)을 적용하여, 
     상호 보완적인 듀얼(Dual), 활동(Activity) 관계 등에 높은 가산점을 부여합니다.
   - 쿼드라(Quadra) 분석을 통해 삶의 가치관이 일치하는지 확인합니다.

3. 활동성 (Communication Activity) - 10%
   - 파싱된 대화 라인 수의 로그 비율을 분석하여, 
     비슷한 에너지 레벨(수다쟁이/과묵함)을 가진 유저끼리 매칭합니다.

[데이터 무결성 및 안전장치]
- Zero Vector Protection: 데이터가 비어있을 경우 NaN 오류를 방지합니다.
- 결측치 처리: MBTI 정보가 없을 때 잘못된 듀얼(Phantom Duality) 매칭을 방지합니다.
- 희소 데이터 보정: 대화량이 극도로 적은 경우(10줄 미만) 활동성 점수 왜곡을 방지합니다.

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
import logging

logger = logging.getLogger(__name__)

# ----------------------------
# 1. 데이터 구조 (Data Structures)
# ----------------------------
@dataclass
class UserVector:
    user_id: str
    name: str
    
    # 원본 데이터 (LLM 추출)
    mbti_type: str        # 예: INTJ
    mbti_conf: float      # 신뢰도 (0.0 ~ 1.0)
    big5_raw: np.array    # [O, C, E, A, N] (0~100)
    big5_conf: float
    socionics_type: str   # 예: LII, SLE
    socionics_conf: float
    
    # 정규화된 데이터 (통계 보정)
    big5_z_score: Optional[np.array] = None
    
    # 활동성 데이터
    line_count: int = 0

# ----------------------------
# 2. 관계 분석 브레인 (Relationship Brain)
# ----------------------------
class RelationshipBrain:
    """
    MBTI 4글자 조합을 분석하여 소시오닉스의 '16가지 관계 유형'을 도출하고,
    정밀한 케미스트리 점수를 산출합니다.
    """

    # 소시오닉스 4 쿼드라 (가치관 공유 그룹)
    QUADRAS = {
        "Alpha (개방/아이디어)": ["ILE", "SEI", "ESE", "LII"],
        "Beta (열정/규율)":     ["EIE", "LSI", "SLE", "IEI"],
        "Gamma (실리/독립)":    ["SEE", "ILI", "LIE", "ESI"],
        "Delta (평화/성실)":    ["LSE", "EII", "IEE", "SLI"]
    }

    @staticmethod
    def get_socionics_score(type_a: str, type_b: str) -> float:
        """
        [소시오닉스 쿼드라 로직]
        같은 쿼드라(Quadra)에 속하면 대화 코드가 통하고 가치관이 비슷하므로 높은 점수(1.0)를 부여합니다.
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
                return 1.0  # 같은 쿼드라 (최상의 가치관 매칭)
            else:
                return 0.4  # 다른 쿼드라
        
        return 0.5

    @staticmethod
    def analyze_relationship(type_a: str, type_b: str) -> Dict[str, any]:
        """
        [MBTI 기반 관계 분석]
        두 MBTI 유형 간의 관계를 분석하여 점수와 라벨을 반환합니다.
        """
        a = type_a.upper()
        b = type_b.upper()

        if len(a) != 4 or len(b) != 4:
            return {"score": 0.5, "label": "Unknown"}

        # [CRITICAL CHECK] 결측치가 있을 경우 엉뚱한 듀얼 매칭 방지
        if 'X' in a or 'X' in b:
            return {"score": 0.5, "label": "Unknown"}

        # 지표별 비교
        same_EI = a[0] == b[0]
        same_NS = a[1] == b[1]
        same_TF = a[2] == b[2]
        same_JP = a[3] == b[3]

        diff_count = sum([not same_EI, not same_NS, not same_TF, not same_JP])

        # ------------------------------------------------------------
        # [A-Tier] 영혼의 파트너 (상호 보완 & 시너지)
        # ------------------------------------------------------------
        
        # 1. 이원 관계 (Duality) - 점수: 1.0 (MAX)
        # 조건: 4글자가 모두 다름 (예: INTJ <-> ESFP)
        if diff_count == 4:
            return {"score": 1.0, "label": "Dual (이원 관계)"}

        # 2. 활동 관계 (Activity) - 점수: 0.9
        # 조건: E/I는 같고 나머지 3글자는 다름
        # 예: ENTP <-> ESFJ
        if same_EI and not same_NS and not same_TF and not same_JP:
            return {"score": 0.9, "label": "Activity (활동 관계)"}
        
        # 3. 거울 관계 (Mirror) - 점수: 0.8
        # 조건: E/I만 다르고 N/S, T/F, J/P는 같음
        if not same_EI and same_NS and same_TF and same_JP:
            return {"score": 0.8, "label": "Mirror (거울 관계)"}

        # ------------------------------------------------------------
        # [B-Tier] 좋은 동료 (유사성 & 이해)
        # ------------------------------------------------------------

        # 4. 유사 관계 (Kindred / Look-alike) - 점수: 0.75
        # 조건: E/I와 J/P는 같고, 가운데 기능만 다름
        if same_EI and same_JP and diff_count == 1:
             return {"score": 0.75, "label": "Kindred (유사 관계)"}

        # 6. 수혜/감독 관계 (비대칭) - 점수: 0.65
        # 예: 기능은 비슷하나 J/P가 다른 경우 등
        if (same_NS or same_TF) and not same_JP:
             return {"score": 0.65, "label": "Asymmetric (비대칭)"}
        
        # 5. 동일 관계 (Identical) - 점수: 0.6
        # 완벽한 이해는 가능하지만, 약점도 공유하여 상호 보완이 어려움
        if diff_count == 0:
            return {"score": 0.6, "label": "Identical (동일 관계)"}

        # ------------------------------------------------------------
        # [C-Tier] 갈등 및 주의 (스트레스 유발)
        # ------------------------------------------------------------

        # 7. 초자아 관계 (Super-Ego) - 점수: 0.3
        # 조건: E/I, J/P는 같지만 기능(N/S, T/F)이 다름
        # 겉보기엔 비슷해 보이지만 가치관 충돌 발생
        if same_EI and same_JP and not same_NS and not same_TF:
            return {"score": 0.3, "label": "Super-Ego (초자아)"}
        
        # 8. 갈등 관계 (Conflict) - 점수: 0.1 (MIN)
        # 조건: J/P만 같고 나머지는 다름
        if not same_EI and not same_NS and not same_TF and same_JP:
             return {"score": 0.1, "label": "Conflict (갈등 관계)"}

        # 9. 그 외 (중립)
        return {"score": 0.5, "label": "Neutral"}

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
        [활동성 점수]
        - 파싱된 라인 수(parsed_lines)가 비슷할수록 높은 점수.
        - 데이터가 너무 적을 경우(10줄 미만) 중립 점수(0.5) 반환.
        """
        if count_a is None: count_a = 0
        if count_b is None: count_b = 0
        
        if count_a < 10 or count_b < 10:
            return 0.5

        a = max(count_a, 10)
        b = max(count_b, 10)
        
        # 로그 비율 (Log Ratio) 사용
        ratio = max(a, b) / min(a, b) 
        
        # 공식: 1 / log2(비율 + 1)
        # 비율이 1이면(동일하면) 1.0, 비율이 3배 차이나면 약 0.5
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
                cos_sim = 0.0
            else:
                cos_sim = 1 - dist
        except:
            cos_sim = 0.0

        similarity_score = (cos_sim + 1) / 2
        
        # --- [B] Chemistry Score (40%) ---
        # B-1. MBTI 궁합
        mbti_chem = RelationshipBrain.get_chemistry_score(target.mbti_type, candidate.mbti_type)
        # B-2. 소시오닉스 쿼드라 궁합
        socio_chem = RelationshipBrain.get_socionics_score(target.socionics_type, candidate.socionics_type)
        
        # 신뢰도 가중 평균
        w_m = (target.mbti_conf * candidate.mbti_conf) ** 0.5
        w_s = (target.socionics_conf * candidate.socionics_conf) ** 0.5
        
        weight_sum = w_m + w_s + 1e-9
        chemistry_score = ((mbti_chem * w_m) + (socio_chem * w_s)) / weight_sum

        # --- [C] Activity Score (10%) ---
        activity_score = self.calculate_activity_score(target.line_count, candidate.line_count)

        # --- [D] 최종 합산 ---
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
# 4. 실행 및 리포트 (Execution)
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
        logger.warning(f"[Warn] Load failed ({filepath}): {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="EchoMind 하이브리드 매처")
    parser.add_argument("--target", required=True, help="타겟 프로필 JSON 경로")
    parser.add_argument("--db", required=True, help="후보군 폴더 경로")
    parser.add_argument("--output", help="결과 JSON 저장 경로", default=None)
    args = parser.parse_args()

    # 1. 로드
    logging.basicConfig(level=logging.INFO)
    target_user = load_profile(args.target)
    if not target_user:
        print("타겟 프로필 로드 실패")
        return

    candidate_files = glob.glob(os.path.join(args.db, "*.json"))
    candidates = []
    for cf in candidate_files:
        if os.path.abspath(cf) == os.path.abspath(args.target): continue
        c = load_profile(cf)
        if c and c.user_id != target_user.user_id: 
            candidates.append(c)

    if not candidates:
        print("후보군이 없습니다.")
        return

    # 2. 매칭 엔진 가동
    matcher = HybridMatcher(candidates + [target_user])
    # 통계 계산 후 타겟 정규화
    matcher.normalize_user(target_user)
    for c in candidates: matcher.normalize_user(c)

    # 3. 결과 산출
    results = []
    
    json_output = {
        "target_user": {
            "name": target_user.name,
            "mbti": target_user.mbti_type,
            "socionics": target_user.socionics_type,
            "line_count": target_user.line_count
        },
        "matches": []
    }

    print(f"\n[EchoMind] 매칭 리포트 - 유저: {target_user.name} ({target_user.mbti_type}) | 활동성: {target_user.line_count} lines")
    print("=" * 115)
    print(f"{'Rank':<4} {'Name':<8} {'MBTI':<6} {'Relationship (Chemistry)':<25} {'Total':<7} | {'Sim(50%)':<9} {'Chem(40%)':<9} {'Act(10%)':<9}")
    print("-" * 115)

    for c in candidates:
        res = matcher.calculate_match_score(target_user, c)
        results.append({"cand": c, "res": res})

    results.sort(key=lambda x: x['res']['total_score'], reverse=True)

    for idx, r in enumerate(results):
        c = r['cand']
        d = r['res']
        
        # 라벨링
        rel_label = RelationshipBrain.get_label(target_user.mbti_type, c.mbti_type)
        if d['socio_detail'] > 0.8: rel_label += " (Quadra)"

        # 출력
        print(f"{idx+1:<4} {c.name:<8} {c.mbti_type:<6} {rel_label:<25} {d['total_score']:.3f}   | {d['similarity_score']:.3f}     {d['chemistry_score']:.3f}     {d['activity_score']:.3f}")

        # JSON 데이터 구성
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
    print(f"* 산출 공식: (Sim x 0.5) + (Chem x 0.4) + (Act x 0.1)")

    # 파일 저장
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, indent=4, ensure_ascii=False)
            print(f"\n[System] 매칭 결과가 '{args.output}'에 저장되었습니다.")
        except Exception as e:
            print(f"\n[Error] 결과 저장 실패: {e}")

if __name__ == "__main__":
    main()