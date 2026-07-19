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

# ----------------------------
# 2. 관계 분석 브레인 (Relationship Brain)
# ----------------------------
class RelationshipBrain:
    """
    소시오닉스 16관계 이론에 기반한 MBTI 궁합 매트릭스.
    모든 16x16 조합에 대해 1위부터 16위까지의 순위를 정하고,
    1.0 ~ 0.1까지의 고정 점수를 부여하는 '정공법' 매칭 시스템입니다.
    소시오닉스 16관계 이론에 기반하여 MBTI 유형 간의 관계를 동적으로 분석하고
    점수를 계산하는 클래스입니다.
    """
    # 소시오닉스 쿼드라 그룹 (가치관 공유)
    QUADRAS = {
        "Alpha (개방/아이디어)": ["ILE", "SEI", "ESE", "LII"],
        "Beta (열정/규율)":     ["EIE", "LSI", "SLE", "IEI"],
        "Gamma (실리/독립)":    ["SEE", "ILI", "LIE", "ESI"],
        "Delta (평화/성실)":    ["LSE", "EII", "IEE", "SLI"]
    }

    # 심리기능에 따른 유형별 특성: MBTI 8기능 스택 (주기능, 부기능, 3차기능, 열등기능)
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

    # 심리기능에 따른 유형별 특성: 정의
    FUNCTION_DESCRIPTIONS = {
        "Si": {
            "dominant": "최대한 많은 정보데이터를 수집하여 조직하고 활용하는 것을 즐깁니다.",
            "auxiliary": "주기능의 판단이 현실 가능한지 타진하고자 정보데이터를 효율적으로 수집합니다.",
            "inferior": "감각의 주관적 왜곡, 객관적 정보의 무시로 인한 지나친 비현실성으로 표현됩니다."
        },

        "Se": {
            "dominant": "적극적 활동을 통해 얻는 강한 신체적 감각을 즐기고 인생을 기꺼이 경험하며 즐기고자 합니다.",
            "auxiliary": "신체운동기능을 잘 사용하여 인정을 얻습니다.",
            "inferior": "지나치게 과민하거나 둔감한 감각, 천박한 감각적 향락에 빠질 수 있습니다."
        },

        "Ni": {
            "dominant": "통찰력을 사용하여 세상과 인간, 존재를 이해하고자 합니다.",
            "auxiliary": "통찰력 있는 미래비전을 제시하여 타인을 통솔하고 성장시킵니다.",
            "inferior": "도덕적 맹종, 종교적 광신 또는 미신에 현혹될 수 있습니다."
        },

        "Ne": {
            "dominant": "창조적인 아이디어를 모든 상황에 적용하는 것을 즐깁니다.",
            "auxiliary": "자신의 가치와 논리를 창의적 아이디어로 표현합니다.",
            "inferior": "부정적 예견(비관주의), 편집적 사고(지나친 의심), 지나친 공포와 불안에 시달릴 수 있습니다."
        },

        "Ti": {
            "dominant": "세상과 상황을 매우 객관적으로 분석하는 날카로운 논리가 있습니다.",
            "auxiliary": "자신의 주장을 논리적으로 설파하여 상대를 설득합니다. 어떤 상황에서도 변명이 가능합니다.",
            "inferior": "특정 대상을 향한 무자비하고 냉혹한 태도를 합리화할 수 있습니다."
        },

        "Te": {
            "dominant": "보편적인 상식과 논리, 이론에 맞게 상황을 조직합니다.",
            "auxiliary": "상식적인 언행을 통해 타인에게 신뢰를 얻습니다.",
            "inferior": "인습에 대한 집착을 보이거나 사회적 합의를 무시할 수 있습니다. 원시적인 논리를 내세우며 고집을  부리기도 합니다."
        },

        "Fi": {
            "dominant": "자신의 감정과 가치를 바탕으로 세상과 사람을 이해합니다.",
            "auxiliary": "상황에 따른 주관적 감정을 자유롭게 표현하여 편안함을 줍니다.",
            "inferior": "충동적 감정에 압도되거나 (예: 갑작스런 분노), 자신만의 아집을 꺾지 않을 수 있습니다."
        },

        "Fe": {
            "dominant": "다양한 관계를 형성하고 조직하여 보편적 유대감을 형성합니다.",
            "auxiliary": "타인의 감정을 이해하고 공감하며 깊고 친밀한 관계를 맺습니다.",
            "inferior": "높은 피암시성을 보이거나 모든 비판에 대한 분노를 표출할 수 있습니다. 보편성에 집착하여 타인의  감정을 비판하기도 합니다."
        }
    }

    @staticmethod
    def _calculate_dynamic_score(stack_a: tuple, stack_b: tuple) -> float:
        """기능 스택을 직접 비교하여 -1.0 ~ 1.0 범위의 동적 점수를 계산합니다."""
        score = 0.0
        P1, A1, T1, I1 = stack_a  # Dominant, Auxiliary, Tertiary, Inferior
        P2, A2, T2, I2 = stack_b

        # 기능 태도(내향/외향) 변환 헬퍼
        opposites = {"Si": "Se", "Se": "Si",
                     "Ni": "Ne", "Ne": "Ni",
                     "Ti": "Te", "Te": "Ti",
                     "Fi": "Fe", "Fe": "Fi"}

        # --- 점수 계산: 계층적 규칙 적용 ---

        # 1. 최상위/최하위 관계는 즉시 점수 확정 (가장 영향력이 큼)
        if P1 == I2 and P2 == I1: return 1.0  # Duality (이원)
        if P1 == A2 and P2 == A1: return 0.8  # Activity (활동)
        if opposites.get(I1) == P2 and opposites.get(I2) == P1: return -1.0 # Conflict (갈등) [FIXED]

        # Supervision(감독)은 비대칭이므로 별도 체크
        is_supervision_A_B = (P1 == T2 and A1 == I2)
        is_supervision_B_A = (P2 == T1 and A2 == I1)
        if is_supervision_A_B or is_supervision_B_A: return -0.7

        # 2. 나머지 관계들은 점수를 누적하여 계산
        # 긍정적 관계
        if A1 == I2 and A2 == I1: score += 0.7  # Semi-Duality (준이원)
        if A1 == A2 and P1 != P2: score += 0.5  # Mirror (거울)
        if P1 == T2 and P2 == T1: score += 0.4  # Mirage (신기루)

        # 유사 관계
        if P1 == P2:
            if I1 == I2: score += 0.3  # Identical (동일)
            else: score += 0.1 # Kindred (유사)

        # Business 관계: 3차 기능이 상대의 주기능, 열등 기능이 상대의 부기능이 되는 관계
        if T1 == P2 and I1 == A2:
            score += 0.1 # Business (비즈니스)

        if opposites.get(P1) == P2 and opposites.get(A1) == A2: score += 0.2 # Quasi-Identical (준동일)

        # 부정적 및 비대칭 관계
        if opposites.get(P1) == T2 and opposites.get(A1) == I2: score -= 0.6 # Super-Ego (초자아)

        # Contrary (소멸): 주기능과 열등기능이 서로 교차되나, 기능의 내/외향성이 같아 오해를 유발.
        if P1 == I2 and I1 == P2:
            score -= 0.5

        # Benefit (시혜): 비대칭 관계. 한쪽이 도움을 주지만 부담을 느끼기 쉬움.
        is_benefit_A_B = (A1 == T2 and T1 == I2) # A가 B에게 시혜
        is_benefit_B_A = (A2 == T1 and T2 == I1) # B가 A에게 시혜
        if is_benefit_A_B or is_benefit_B_A:
            score -= 0.2

        return np.clip(score, -1.0, 1.0) # 최종 점수를 -1.0 ~ 1.0 범위로 제한

    @staticmethod
    def _get_dynamic_relationship_type(stack_a: tuple, stack_b: tuple) -> Optional[str]:
        """기능 스택을 직접 비교하여 관계 유형의 '키'를 동적으로 반환합니다."""
        P1, A1, T1, I1 = stack_a
        P2, A2, T2, I2 = stack_b
        opposites = {"Si": "Se", "Se": "Si",
                     "Ni": "Ne", "Ne": "Ni",
                     "Ti": "Te", "Te": "Ti",
                     "Fi": "Fe", "Fe": "Fi"}

        # 순서가 중요 (가장 명확한 관계부터)
        if P1 == I2 and P2 == I1: return "Duality"
        if P1 == A2 and P2 == A1: return "Activity"
        if opposites.get(I1) == P2 and opposites.get(I2) == P1: return "Conflict"

        # 비대칭 관계
        if P1 == T2 and A1 == I2: return "Supervision_Supervisor" # A가 B를 감독
        if P2 == T1 and A2 == I1: return "Supervision_Supervisee" # A가 B에게 감독받음

        if A1 == I2 and A2 == I1: return "Semi-Duality"
        if P1 == T2 and P2 == T1: return "Mirage"
        if opposites.get(P1) == T2 and opposites.get(A1) == I2: return "Super-Ego"

        if A1 == T2 and T1 == I2: return "Benefit_Giver" # A가 B에게 시혜
        if A2 == T1 and T2 == I1: return "Benefit_Receiver" # A가 B에게 수혜

        if P1 == I2 and I1 == P2: return "Contrary"

        # 유사 관계
        if P1 == P2:
            if A1 == A2: return "Identical"
            else: return "Kindred"

        if A1 == A2: # P1 != P2는 위에서 걸러짐
            return "Mirror"

        if T1 == P2 and I1 == A2: return "Business"
        if opposites.get(P1) == P2 and opposites.get(A1) == A2: return "Quasi-Identical"

        return "Unknown"


    @staticmethod
    def get_chemistry_score(type_a: str, type_b: str) -> float:
        """기능 역학 분석을 통해 동적으로 MBTI 궁합 점수를 계산합니다."""
        a = type_a.upper()
        b = type_b.upper()

        if len(a) != 4 or len(b) != 4 or 'X' in a or 'X' in b:
            return 0.5

        stack_a = RelationshipBrain.FUNCTION_STACKS.get(a)
        stack_b = RelationshipBrain.FUNCTION_STACKS.get(b)

        if not stack_a or not stack_b:
            return 0.5

        raw_score = RelationshipBrain._calculate_dynamic_score(stack_a, stack_b)
        return (raw_score + 1) / 2 # 0.0 ~ 1.0 범위로 정규화

    @staticmethod
    def get_socionics_score(type_a: str, type_b: str) -> float:
        """소시오닉스 쿼드라(가치관) 점수"""
        if not type_a or not type_b or type_a == "UNK" or type_b == "UNK": return 0.5
        quadra_a = next((q for q, types in RelationshipBrain.QUADRAS.items() if type_a in types), None)
        quadra_b = next((q for q, types in RelationshipBrain.QUADRAS.items() if type_b in types), None)
        return 1.0 if quadra_a and quadra_a == quadra_b else 0.4

    @staticmethod
    def get_relationship_label(type_a: str, type_b: str) -> str:
        """두 유형의 대표적인 관계 라벨을 반환합니다."""
        a = type_a.upper()
        b = type_b.upper()
        if len(a) != 4 or len(b) != 4 or 'X' in a or 'X' in b:
            return "Unknown"

        stack_a = RelationshipBrain.FUNCTION_STACKS.get(a)
        stack_b = RelationshipBrain.FUNCTION_STACKS.get(b)

        if not stack_a or not stack_b:
            return "Unknown"

        # [REFACTORED] 동적 분석 함수 호출
        relation_key = RelationshipBrain._get_dynamic_relationship_type(stack_a, stack_b)

        # 비대칭 관계 라벨 처리
        if relation_key == "Benefit_Giver":
            return "Benefit (시혜자)"
        if relation_key == "Benefit_Receiver":
            return "Benefit (수혜자)"
        if relation_key == "Supervision_Supervisor":
            return "Supervision (감독자)"
        if relation_key == "Supervision_Supervisee":
            return "Supervision (피감자)"

        # 대칭 관계 라벨 처리
        korean_map = {"Duality": "이원",
                      "Activity": "활동",
                      "Identical": "동일",
                      "Mirror": "거울",
                      "Mirage": "신기루",
                      "Semi-Duality": "준이원",
                      "Kindred": "유사",
                      "Business": "비즈니스",
                      "Quasi-Identical": "준동일",
                      "Contrary": "소멸",
                      "Super-Ego": "초자아",
                      "Conflict": "갈등"}

        korean_label = korean_map.get(relation_key, relation_key)
        return f"{relation_key} ({korean_label})"

    @staticmethod
    def get_relationship_analysis(type_a: str, type_b: str) -> dict:
        """두 유형의 기능적 상호작용을 상세히 분석하여 텍스트 리포트를 생성합니다."""
        a = type_a.upper(); b = type_b.upper()
        if len(a) != 4 or len(b) != 4 or 'X' in a or 'X' in b: return {}

        stack_a = RelationshipBrain.FUNCTION_STACKS.get(a)
        stack_b = RelationshipBrain.FUNCTION_STACKS.get(b)
        if not stack_a or not stack_b: return {}

        # [REFACTORED] 동적 분석 함수 호출
        relation_type = RelationshipBrain._get_dynamic_relationship_type(stack_a, stack_b)
        if not relation_type: return {}

        # 비대칭 관계의 경우, 분석을 위해 대표 키로 통일 (예: Supervision_Supervisor -> Supervision)
        if "Supervision" in relation_type: relation_type = "Supervision"
        if "Benefit" in relation_type: relation_type = "Benefit"

        P1, A1, T1, I1 = stack_a
        P2, A2, T2, I2 = stack_b

        analysis = {
            "type": relation_type,
            "summary": "",
            "dynamics": []
        }

        # 관계별 핵심 상호작용 분석 (예시: 이원관계)
        if "Duality" in relation_type:
            analysis["summary"] = "서로의 강점이 상대방의 약점을 완벽하게 보완해주는 최상의 궁합입니다."
            # 분석 1: A의 주기능 -> B의 열등기능
            desc1 = f"{a}의 강점인 '{RelationshipBrain.FUNCTION_DESCRIPTIONS[P1]['dominant']}' 특성은, {b}가 어려움을 겪는 '{RelationshipBrain.FUNCTION_DESCRIPTIONS[I2]['inferior']}' 영역에 안정감과 해결책을 제시합니다."
            analysis["dynamics"].append({"interaction": f"{a}(주기능) ↔ {b}(열등기능)", "description": desc1})
            # 분석 2: B의 주기능 -> A의 열등기능
            desc2 = f"{b}의 강점인 '{RelationshipBrain.FUNCTION_DESCRIPTIONS[P2]['dominant']}' 특성은, {a}가 불안해하는 '{RelationshipBrain.FUNCTION_DESCRIPTIONS[I1]['inferior']}' 영역에 새로운 가능성과 활력을 불어넣습니다."
            analysis["dynamics"].append({"interaction": f"{b}(주기능) ↔ {a}(열등기능)", "description": desc2})

        # 'Activity' 관계 분석 로직
        elif "Activity" in relation_type:
            analysis["summary"] = "함께 있으면 즐겁고 활력이 넘치는, 최고의 파트너 관계입니다. 서로를 쉽게 이해하고 지지해줍니다."
            # 분석 1: A의 주기능 -> B의 부기능
            desc1 = f"{a}가 가장 자신있는 '{RelationshipBrain.FUNCTION_DESCRIPTIONS[P1]['dominant']}' 방식은, {b}가 유능하게 사용하는 '{RelationshipBrain.FUNCTION_DESCRIPTIONS[A2]['auxiliary']}' 방식과 일치하여 서로에게 큰 영감과 에너지를  줍니다."
            analysis["dynamics"].append({"interaction": f"{a}(주기능) ↔ {b}(부기능)", "description": desc1})
            # 분석 2: B의 주기능 -> A의 부기능
            desc2 = f"마찬가지로, {b}의 주된 접근 방식인 '{RelationshipBrain.FUNCTION_DESCRIPTIONS[P2]['dominant']}' 특 성은 {a}의 부기능과 통해, 두 사람의 협업과 소통을 매우 원활하게 만듭니다."
            analysis["dynamics"].append({"interaction": f"{b}(주기능) ↔ {a}(부기능)", "description": desc2})

        return analysis

    @staticmethod
    def get_function_stack_details(mbti_type: str) -> Optional[List[Dict[str, str]]]:
        """MBTI 유형의 8기능 스택과 설명을 반환합니다."""
        mbti = mbti_type.upper()
        if mbti not in RelationshipBrain.FUNCTION_STACKS:
            return None

        stack = RelationshipBrain.FUNCTION_STACKS[mbti]
        func_P, func_A, func_T, func_I = stack

        detailed_stack = [
            {
                "role": "주기능 (Dominant)",
                "function": func_P,
                "description": RelationshipBrain.FUNCTION_DESCRIPTIONS.get(func_P, {}).get("dominant", "핵심적인 강점 기능입니다.")
            },

            {
                "role": "부기능 (Auxiliary)",
                "function": func_A,
                "description": RelationshipBrain.FUNCTION_DESCRIPTIONS.get(func_A, {}).get("auxiliary", "주기능을 보조하는 균형 기능입니다.")
            },

            {
                "role": "3차기능 (Tertiary)",
                "function": func_T,
                "description": "상대적으로 미개발된 기능으로, 스트레스 상황에서 나타나거나 성장 가능성을 보입니다."
            },

            {
                "role": "열등기능 (Inferior)",
                "function": func_I,
                "description": RelationshipBrain.FUNCTION_DESCRIPTIONS.get(func_I, {}).get("inferior", "가장 약하고 무의식적인 기능으로, 큰 스트레스 상황에서 미숙하게 표출될 수 있습니다.")
            }
        ]
        return detailed_stack
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
        socio_chem = RelationshipBrain.get_socionics_score(target.socionics_type, candidate.socionics_type)

        # 소시오닉스 쿼드라 정보 추출
        target_quadra = None
        candidate_quadra = None
        for q_name, types in RelationshipBrain.QUADRAS.items():
            if target.socionics_type in types:
                target_quadra = q_name
            if candidate.socionics_type in types:
                candidate_quadra = q_name
        socio_quadra_same = (target_quadra is not None and target_quadra == candidate_quadra)

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
            birth_date=birth_date_obj
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

        # 나이 차이 계산 (단위: 일)
        age_diff = 999999  # 날짜 정보 없을 시 후순위로 밀기 위한 큰 값
        if target_user.birth_date and c.birth_date:
            delta = target_user.birth_date - c.birth_date
            age_diff = abs(delta.days)
        res['age_difference'] = age_diff

        results.append({"cand": c, "res": res})

    # 점수 동일 시 나이 차이 적은 순으로 정렬 (점수 내림차순, 나이차 오름차순)
    results.sort(key=lambda x: (-x['res']['total_score'], x['res']['age_difference']))
    results.sort(key=lambda x: x['res']['total_score'], reverse=True)

    for idx, r in enumerate(results):
        c = r['cand']
        d = r['res']

        # 라벨링
        rel_label = RelationshipBrain.get_relationship_label(target_user.mbti_type, c.mbti_type)
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
