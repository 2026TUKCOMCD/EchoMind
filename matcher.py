# matcher.py
# -*- coding: utf-8 -*-

"""
[EchoMind] 다차원 성격 분석 및 하이브리드 매칭 시스템

[시스템 개요]
본 시스템은 '기질(Big5)', 'MBTI의 8기능 심리기능 위계(Si, Se, Ni, Ne, Ti, Te, Fi, Fe)', 
그리고 '활동성(Activity)'을 종합적으로 분석하여 최적의 파트너를 찾아주는 하이브리드 매칭 엔진입니다.

[핵심 알고리즘 및 가중치]
1. 유사성 (Temperamental Similarity) - 50%
   - Big5(OCEAN) 5차원 벡터의 코사인 유사도를 계산하고, 모집단 통계 기반의 Z-Score 정규화를 적용하여 수치적 편향을 제거합니다.

2. 케미스트리 (Relational Chemistry) - 40%
   - MBTI의 8가지 심리기능(주기능, 부기능, 3차기능, 열등기능) 상호작용을 기반으로 평가합니다.
   - 한쪽의 주기능이 상대의 열등기능을 보완하는 '상호 보완성' 구조에 가산점을 부여합니다. 
   - 또한, 주기능과 부기능이 맞물리는 '시너지 협업' 관계 역시 평가에 반영합니다.
   - 외부 이론(소시오닉스 등)을 배제하고 오직 심리기능 위계 간의 교차 특성에 근거하여 관계 역학을 산출합니다.

3. 활동성 (Communication Activity) - 10%
   - 파싱된 대화 라인 수의 로그 비율을 분석하여, 비슷한 에너지 레벨(수다쟁이/과묵함)을 가진 유저끼리 매칭합니다.

[데이터 무결성 및 안전장치]
- Zero Vector Protection: 데이터가 비어있을 경우 NaN 오류를 방지합니다.

[사용법]
  python matcher.py --target "profile.json" --db "./candidates_db" --output "result.json"
"""

import argparse
import json
import os
import glob
import numpy as np
from dataclasses import dataclass
from datetime import date, datetime
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

    # 나이 계산을 위한 생년월일
    birth_date: Optional[date] = None

    # 가입일 (3차 정렬 기준)
    created_at: Optional[datetime] = None

# ----------------------------
# 2. 관계 분석 브레인 (Relationship Brain)
# ----------------------------

class RelationshipBrain:
    """
    8가지 심리기능(주기능, 부기능, 3차기능, 열등기능)의 상호작용과 위계적 특성만을 근거로
    매칭 점수와 관계를 도출하는 정통 심리기능 엔진.
    """

    # 소시오닉스 쿼드라 그룹 (가치관 공유)
    QUADRAS = {
        "Alpha": ["ILE", "SEI", "ESE", "LII"],
        "Beta": ["EIE", "LSI", "SLE", "IEI"],
        "Gamma": ["SEE", "ILI", "LIE", "ESI"],
        "Delta": ["LSE", "EII", "IEE", "SLI"]
    }

    OPPOSITES = {
        "Si": "Se", "Se": "Si", "Ni": "Ne", "Ne": "Ni",
        "Ti": "Te", "Te": "Ti", "Fi": "Fe", "Fe": "Fi"
    }

    FUNCTION_STACKS = {
        "ISTJ": ("Si", "Te", "Fi", "Ne"),
        "ISFJ": ("Si", "Fe", "Ti", "Ne"),
        "INFJ": ("Ni", "Fe", "Ti", "Se"),
        "INTJ": ("Ni", "Te", "Fi", "Se"),
        "ISTP": ("Ti", "Se", "Ni", "Fe"),
        "ISFP": ("Fi", "Se", "Ni", "Te"),
        "INFP": ("Fi", "Ne", "Si", "Te"),
        "INTP": ("Ti", "Ne", "Si", "Fe"),
        "ESTP": ("Se", "Ti", "Fe", "Ni"),
        "ESFP": ("Se", "Fi", "Te", "Ni"),
        "ENFP": ("Ne", "Fi", "Te", "Si"),
        "ENTP": ("Ne", "Ti", "Fe", "Si"),
        "ESTJ": ("Te", "Si", "Ne", "Fi"),
        "ESFJ": ("Fe", "Si", "Ne", "Ti"),
        "ENFJ": ("Fe", "Ni", "Se", "Ti"),
        "ENTJ": ("Te", "Ni", "Se", "Fi"),
    }

    FUNCTION_DESCRIPTIONS = {
        "Si": {"dominant": "정보 데이터를 조직하고 활용함",
               "auxiliary": "현실 가능성 타진",
               "inferior": "감각의 왜곡 및 비현실성"},

        "Se": {"dominant": "적극적 감각과 경험 추구",
               "auxiliary": "신체 운동 기능 활용",
               "inferior": "과민 또는 쾌락 집착"},

        "Ni": {"dominant": "통찰력으로 존재 이해",
               "auxiliary": "미래 비전 제시",
               "inferior": "도덕적 맹종 및 미신 현혹"},

        "Ne": {"dominant": "창조적 아이디어 적용",
               "auxiliary": "가치와 논리의 표현",
               "inferior": "비관주의 및 불안"},

        "Ti": {"dominant": "객관적이고 날카로운 논리",
               "auxiliary": "논리적 설득",
               "inferior": "냉혹한 태도 합리화"},

        "Te": {"dominant": "상식과 이론에 따른 조직",
               "auxiliary": "신뢰 구축",
               "inferior": "인습 집착 및 고집"},

        "Fi": {"dominant": "감정과 가치 중심 이해",
               "auxiliary": "주관적 감정 표현",
               "inferior": "충동적 분노 및 아집"},

        "Fe": {"dominant": "보편적 유대감 형성",
               "auxiliary": "공감과 친밀함",
               "inferior": "피암시성과 비판적 성향"}
    }

    @staticmethod
    def _calculate_dynamic_score(stack_a: tuple, stack_b: tuple) -> float:
        """
        두 유형의 기능 스택(주, 부, 3차, 열등) 간의 교차 관계를 분석하여 
        -1.0 ~ 1.0 범위의 궁합 점수를 산출합니다.
        """
        P1, A1, T1, I1 = stack_a
        P2, A2, T2, I2 = stack_b
        # 1. 인지적 상호작용
        score = 0.0

        # 2. 상호 보완성 평가 (주기능 ↔ 열등기능 교차)
        # 한쪽의 강점(주기능)이 상대의 무의식적 약점(열등기능)을 보완하는 구조
        if (P1 == I2) or (P2 == I1):
            score += 0.5

        # 3. 협업 및 시너지 평가 (주기능 ↔ 부기능 교차)
        if (P1 == A2) or (P2 == A1):
            score += 0.4

        # 4. 가치관 및 소통 방식 공조 평가 (주기능 일치 또는 동일 축 공유)
        if P1 == P2:
            score += 0.3  # 동일한 핵심 인식/판단 기준 공유
        elif P1[1] == P2[1]:
            score += 0.2  # 동일한 기질 축(감각/직관/사고/감정) 공유

        # 5. 인지적 마찰 평가 (대립 기능 충돌 시 미세 감점)
        if RelationshipBrain.OPPOSITES.get(P1) == P2:
            score -= 0.15

        return np.clip(score, -1.0, 1.0)

    @staticmethod
    def _get_dynamic_relationship_type(stack_a: tuple, stack_b: tuple) -> str:
        """
        기능 스택의 교차 상태를 기반으로 순수 심리기능 기반의 관계 명칭을 부여합니다.
        """
        P1, A1, T1, I1 = stack_a
        P2, A2, T2, I2 = stack_b

        # 1. 완벽한 상호 보완 관계 (주기능과 열등기능이 상호 교차)
        if (P1 == I2) and (P2 == I1):
            return "Complete_Balance (완벽보완)"
        
        # 2. 능동적 협업 관계 (주기능과 부기능이 맞물림)
        if (P1 == A2) or (P2 == A1):
            return "Active_Synergy (시너지협업)"

        # 3. 동질적 공감 관계 (핵심 주기능 일치)
        if P1 == P2:
            return "Core_Alignment (핵심일치)"

        # 4. 기능 축 기반 조화 관계
        if P1[1] == P2[1]:
            return "Functional_Harmonious (기질조화)"
        
        # 5. 기능 대립 관계
        if RelationshipBrain.OPPOSITES.get(P1) == P2:
            return "Functional_Opposition (기능대립)"

        return "Cognitive_Complement (인지적상호작용)"

    @staticmethod
    def get_chemistry_score(type_a: str, type_b: str) -> float:
        a = type_a.upper(); b = type_b.upper()
        if len(a) != 4 or len(b) != 4 or 'X' in a or 'X' in b: return 0.5
        stack_a = RelationshipBrain.FUNCTION_STACKS.get(a)
        stack_b = RelationshipBrain.FUNCTION_STACKS.get(b)
        if not stack_a or not stack_b: return 0.5
        raw_score = RelationshipBrain._calculate_dynamic_score(stack_a, stack_b)
        return (raw_score + 1) / 2

    @staticmethod
    def get_socionics_details(type_a: str, type_b: str) -> dict:
        """소시오닉스 쿼드라를 분석하여 점수와 상세 정보를 반환합니다."""
        if not type_a or not type_b or type_a == "UNK" or type_b == "UNK":
            return {"score": 0.5, "quadra_a": None, "quadra_b": None, "is_same": False}

        quadra_a = None
        quadra_b = None
        type_a_upper = type_a.upper()
        type_b_upper = type_b.upper()

        for q_name, types in RelationshipBrain.QUADRAS.items(): # noqa
            if type_a_upper in types:
                quadra_a = q_name
            if type_b_upper in types:
                quadra_b = q_name

        score = 0.5
        if quadra_a and quadra_a == quadra_b:
            score = 1.0
        elif quadra_a and quadra_b:
            score = 0.4

        return {"score": score, "quadra_a": quadra_a, "quadra_b": quadra_b, "is_same": (quadra_a is not None and quadra_a == quadra_b)}


    @staticmethod
    def get_relationship_label(type_a: str, type_b: str) -> str:
        a = type_a.upper(); b = type_b.upper()
        if len(a) != 4 or len(b) != 4 or 'X' in a or 'X' in b: return "Unknown (Unknown)"
        stack_a = RelationshipBrain.FUNCTION_STACKS.get(a)
        stack_b = RelationshipBrain.FUNCTION_STACKS.get(b)
        if not stack_a or not stack_b: return "Unknown (Unknown)"

        relation_key = RelationshipBrain._get_dynamic_relationship_type(stack_a, stack_b)
        return relation_key

    @staticmethod
    def get_relationship_analysis(type_a: str, type_b: str) -> dict:
        a = type_a.upper(); b = type_b.upper()
        if len(a) != 4 or len(b) != 4 or 'X' in a or 'X' in b: return {}
        stack_a = RelationshipBrain.FUNCTION_STACKS.get(a)
        stack_b = RelationshipBrain.FUNCTION_STACKS.get(b)
        if not stack_a or not stack_b: return {}

        relation_type = RelationshipBrain._get_dynamic_relationship_type(stack_a, stack_b)
        P1, A1, T1, I1 = stack_a
        P2, A2, T2, I2 = stack_b

        return {
            "type": relation_type,
            "summary": f"{a}와 {b} 유형 간의 8가지 심리기능 위계(주·부·열등기능) 상호작용 분석 결과입니다.",
            "dynamics": [
                {"interaction": f"{a}의 주기능({P1}) ↔ {b}의 열등기능({I2})",
                 "description": RelationshipBrain.FUNCTION_DESCRIPTIONS.get(P1, {}).get("dominant", "")},
                {"interaction": f"{b}의 주기능({P2}) ↔ {a}의 열등기능({I1})",
                 "description": RelationshipBrain.FUNCTION_DESCRIPTIONS.get(P2, {}).get("dominant", "")}
            ]
        }

    @staticmethod
    def get_function_stack_details(mbti_type: str) -> Optional[List[Dict[str, str]]]:
        mbti = mbti_type.upper()
        if mbti not in RelationshipBrain.FUNCTION_STACKS:
            return None
        stack = RelationshipBrain.FUNCTION_STACKS[mbti]
        func_P, func_A, func_T, func_I = stack

        return [
            {"role": "주기능 (Dominant)",
             "function": func_P,
             "description": RelationshipBrain.FUNCTION_DESCRIPTIONS.get(func_P, {}).get("dominant", "")},

            {"role": "부기능 (Auxiliary)",
             "function": func_A,
             "description": RelationshipBrain.FUNCTION_DESCRIPTIONS.get(func_A, {}).get("auxiliary", "")},

            {"role": "3차기능 (Tertiary)",
             "function": func_T,
             "description": "상대적으로 미개발된 균형 기능입니다."},

            {"role": "열등기능 (Inferior)",
             "function": func_I,
             "description": RelationshipBrain.FUNCTION_DESCRIPTIONS.get(func_I, {}).get("inferior", "")}
        ]
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
        except Exception:
            cos_sim = 0.0

        similarity_score = (cos_sim + 1) / 2

        # --- [B] Chemistry Score (40%) ---
        # B-1. MBTI 궁합
        mbti_chem = RelationshipBrain.get_chemistry_score(target.mbti_type, candidate.mbti_type) # 새로운 엔진 호출
        mbti_label = RelationshipBrain.get_relationship_label(target.mbti_type, candidate.mbti_type)

        # B-2. 소시오닉스 쿼드라 궁합
        socio_details = RelationshipBrain.get_socionics_details(target.socionics_type, candidate.socionics_type)
        socio_chem = socio_details["score"]
        target_quadra = socio_details["quadra_a"]
        candidate_quadra = socio_details["quadra_b"]
        socio_quadra_same = socio_details["is_same"]
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
            "socio_detail": socio_chem,

            # 확장 패널용 추가 데이터
            "mbti_label": mbti_label,
            "target_mbti": target.mbti_type,
            "candidate_mbti": candidate.mbti_type,
            "relationship_analysis": RelationshipBrain.get_relationship_analysis(target.mbti_type, candidate.mbti_type),
            "socio_quadra_same": socio_quadra_same,
            "target_quadra": target_quadra,
            "candidate_quadra": candidate_quadra,
            "target_socio": target.socionics_type,
            "candidate_socio": candidate.socionics_type,
            "mbti_weight": float(w_m),
            "socio_weight": float(w_s),
            "cos_sim_raw": float(cos_sim),
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

        # 생년월일 정보 로드
        birth_date_str = meta.get('birth_date')
        birth_date_obj = None
        if birth_date_str:
            try:
                birth_date_obj = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass # 날짜 형식이 아니면 무시

        # 가입일 정보 로드
        created_at_str = meta.get('created_at')
        created_at_obj = None
        if created_at_str:
            try:
                # ISO 형식 (e.g., "2024-01-01T12:00:00Z") 처리
                if created_at_str.endswith('Z'):
                    created_at_str = created_at_str[:-1] + '+00:00'
                created_at_obj = datetime.fromisoformat(created_at_str)
            except (ValueError, TypeError):
                pass # 날짜 형식이 아니면 무시

        return UserVector(
            user_id=meta.get('user_id', 'unknown'),
            name=meta.get('speaker_name', 'unknown'),
            mbti_type=prof.get('mbti', {}).get('type', 'XXXX'),
            mbti_conf=float(prof.get('mbti', {}).get('confidence', 0.5)),
            big5_raw=big5_vec,
            big5_conf=float(b5.get('confidence', 0.5)),
            socionics_type=prof.get('socionics', {}).get('type', 'UNK'),
            socionics_conf=float(prof.get('socionics', {}).get('confidence', 0.5)),
            line_count=parse_q.get('parsed_lines', 0),
            birth_date=birth_date_obj,
            created_at=created_at_obj
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

    print(
        f"\n[EchoMind] 매칭 리포트 - 유저: {target_user.name} "
        f"({target_user.mbti_type}) | 활동성: {target_user.line_count} lines"
    )
    print("=" * 115)
    print(
        f"{'Rank':<4} {'Name':<8} {'MBTI':<6} "
        f"{'Relationship (Chemistry)':<25} {'Total':<7} | "
        f"{'Sim(50%)':<9} {'Chem(40%)':<9} {'Act(10%)':<9}"
    )
    print("-" * 115)

    for c in candidates:
        res = matcher.calculate_match_score(target_user, c)

        # 나이 차이 계산 (단위: 일)
        age_diff = 999999  # 날짜 정보 없을 시 후순위로 밀기 위한 큰 값
        if target_user.birth_date and c.birth_date:
            delta = target_user.birth_date - c.birth_date
            age_diff = abs(delta.days)
        res['age_difference'] = age_diff

        results.append({"cand": c, "res": res})

    # 점수 동일 시 나이 차이 적은 순, 그 다음 가입일 순으로 정렬
    # (점수 내림차순, 나이차 오름차순, 가입일 오름차순)
    results.sort(key=lambda x: (
        -x['res']['total_score'], 
        x['res']['age_difference'],
        x['cand'].created_at or datetime.max # 가입일 없으면 맨 뒤로
    ))

    for idx, r in enumerate(results):
        c = r['cand']
        d = r['res']

        # 라벨링
        rel_label = RelationshipBrain.get_relationship_label(target_user.mbti_type, c.mbti_type)
        if d['socio_detail'] > 0.8: rel_label += " (Quadra)"

        # 출력
        print(
            f"{idx+1:<4} {c.name:<8} {c.mbti_type:<6} "
            f"{rel_label:<25} {d['total_score']:.3f}   | "
            f"{d['similarity_score']:.3f}    "
            f"{d['chemistry_score']:.3f}    "
            f"{d['activity_score']:.3f}"
        )
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