# reporter.py
# -*- coding: utf-8 -*-

"""
EchoMind 심층 분석 리포터 모듈 (통계 및 서술형 분석)
---------------------------------------------------
[목적]
    main.py에서 생성된 원시 커뮤니케이션 벡터(Raw Vector)를 입력받아,
    통계적 검증과 해석이 포함된 종합 심리 리포트로 변환합니다.
    단순 유형 분류(MBTI 등)를 지양하고, 데이터에 기반한 서술형 행동 분석에 초점을 둡니다.

[핵심 기능]
    1. 통계적 위치 분석 (Statistical Analysis):
       - 정규분포(Normal Distribution) 모델을 가정하여 사용자의 점수가 상위 몇 %인지 백분위(Percentile)를 산출합니다.
    
    2. 서술형 아이덴티티 도출 (Identity Synthesis):
       - 수치 데이터를 조합하여 사용자의 화법 특성을 설명하는 자연어 문장(Descriptive Sentences)을 생성합니다.
    
    3. 상황별 행동 시뮬레이션 (Situational Simulation):
       - 갈등 발생이나 팀 프로젝트 등 특정 상황에서 사용자가 보일 예상 행동 패턴을 예측합니다.
    
    4. 맞춤형 코칭 (Actionable Coaching):
       - 매칭 확률을 높이기 위해 개선해야 할 구체적인 커뮤니케이션 전략을 제안합니다.

[사용법]
    python reporter.py --profile profile.json --out report_deep.json
"""

import json
import os
import sys
import argparse
import logging
import numpy as np
from scipy.stats import norm
from datetime import datetime
from typing import Dict, Any, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] REPORT-ENG: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("DeepReporter")

# ----------------------------
# 1. Statistical Engine (통계 분석 엔진)
# ----------------------------
class StatEngine:
    """
    사용자의 점수가 전체 모집단(가정)에서 어디쯤 위치하는지 분석합니다.
    (정규분포 모델링: 평균 0.5, 표준편차 0.15 가정)
    """
    def __init__(self, mean=0.5, std=0.15):
        self.mean = mean
        self.std = std

    def get_percentile(self, score: float) -> str:
        """점수를 백분위 등급으로 변환 (예: 상위 10%)"""
        # Z-score 계산
        z_score = (score - self.mean) / self.std
        # 누적분포함수(CDF)를 통해 백분위 계산
        percentile = norm.cdf(z_score) * 100
        
        if percentile >= 90: return "최상위권 (Top 10%)"
        elif percentile >= 75: return "상위권 (Top 25%)"
        elif percentile >= 40: return "평균 범위 (Middle)"
        elif percentile >= 20: return "하위권 (Bottom 25%)"
        else: return "최하위권 (Bottom 10%)"

    def get_deviation_msg(self, score: float, label: str) -> str:
        """평균과의 편차를 분석하여 문장 생성"""
        diff = score - self.mean
        direction = "높은" if diff > 0 else "낮은"
        intensity = "압도적으로" if abs(diff) > 0.3 else "평균보다 다소"
        
        # 문맥에 따른 긍/부정 중립적 서술
        return f"일반 사용자 대비 {intensity} {direction} {label} 수치를 보입니다."

# ----------------------------
# 2. Identity Engine (성향 서술 엔진 - No MBTI)
# ----------------------------
class IdentityEngine:
    """
    벡터의 조합을 분석하여 사용자의 화법을 설명하는 '서술형 아이덴티티'를 생성합니다.
    MBTI 같은 고정된 유형(Type)이 아니라, 데이터에 기반한 '문장'을 만듭니다.
    """
    def analyze_core_identity(self, vec: Dict[str, float]) -> Dict[str, Any]:
        tags = []
        descriptions = []
        
        # 1. 이성 vs 감성 (판단 기준)
        emotion = vec.get("emotion_score", 0.5)
        if emotion < 0.4:
            tags.append("#이성적")
            descriptions.append("감정보다는 사실과 논리에 기반하여 판단하며")
        elif emotion > 0.6:
            tags.append("#감성적")
            descriptions.append("상대방의 감정과 분위기를 중요하게 고려하며")
        else:
            tags.append("#균형잡힌")
            descriptions.append("상황에 따라 이성과 감성을 적절히 조율하며")
            
        # 2. 주도성 (행동 양식)
        initiative = vec.get("initiative_score", 0.5)
        if initiative > 0.6:
            tags.append("#주도적")
            descriptions.append("대화의 흐름을 적극적으로 이끌어가는 편입니다.")
        elif initiative < 0.4:
            tags.append("#협조적")
            descriptions.append("상대의 의견을 경청하고 따라가는 것을 선호합니다.")
        else:
            descriptions.append("대화에 자연스럽게 참여하여 흐름을 맞춥니다.")

        # 3. 화법 (표현 방식)
        directness = vec.get("directness_score", 0.5)
        if directness > 0.7:
            tags.append("#직설화법")
            style_desc = "돌려 말하기보다 핵심을 찌르는 직설적인 화법이 특징입니다."
        elif directness < 0.3:
            tags.append("#완곡화법")
            style_desc = "상처 주지 않으려 조심스럽게 돌려 말하는 완곡한 화법이 특징입니다."
        else:
            style_desc = "상황에 맞춰 유연하게 의사를 표현하는 스타일입니다."

        # 종합 문장 생성
        full_desc = f"당신은 {' '.join(descriptions)} {style_desc}"
        
        return {
            "keywords": tags,
            "description": full_desc,
            "short_title": f"{tags[0]}이고 {tags[1]}인 대화 스타일"
        }

# ----------------------------
# 3. Main Reporter Class
# ----------------------------
class EchoMindDeepReporter:
    def __init__(self, profile_path: str):
        self.profile_path = profile_path
        self.data = self._load_data()
        self.vector = self.data.get("communication_vector", {})
        self.meta = self.data.get("_meta", {})
        
        # 엔진 초기화
        self.stat_engine = StatEngine()
        self.identity_engine = IdentityEngine()

    def _load_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.profile_path):
            logger.critical("Profile not found.")
            sys.exit(1)
        with open(self.profile_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def analyze_deep_metrics(self) -> Dict[str, Any]:
        """각 지표별 정밀 통계 분석 수행"""
        metrics = {}
        labels = {
            "directness_score": "직설성", "emotion_score": "감성도", 
            "empathy_score": "공감력", "initiative_score": "주도성",
            "conflict_score": "갈등직면"
        }
        
        for key, label_kr in labels.items():
            val = self.vector.get(key, 0.5)
            metrics[key] = {
                "raw_score": val,
                "percentile": self.stat_engine.get_percentile(val),
                "analysis": self.stat_engine.get_deviation_msg(val, label_kr)
            }
        return metrics

    def simulate_scenarios(self) -> List[Dict[str, str]]:
        """
        [New] 상황별 시뮬레이션: 이 사람은 특정 상황에서 어떻게 말할까?
        """
        scenarios = []
        vec = self.vector
        
        # Situation 1: 팀원의 실수를 발견했을 때
        if vec.get("directness_score") > 0.7:
            reaction = "즉시 지적하며 수정을 요구함 (예: '이거 틀렸는데 다시 확인해주세요.')"
        elif vec.get("empathy_score") > 0.7:
            reaction = "감정을 배려하며 우회적으로 표현함 (예: '혹시 이 부분 의도하신 건지 확인 가능할까요?')"
        else:
            reaction = "조용히 본인이 수정하거나 나중에 따로 말함"
            
        scenarios.append({"situation": "팀 프로젝트 중 동료의 실수를 발견했을 때", "prediction": reaction})
        
        # Situation 2: 의견 충돌 시
        if vec.get("conflict_score") > 0.6:
            reaction = "자신의 논리가 맞음을 끝까지 증명하려 함 (논쟁 불사)"
        else:
            reaction = "갈등을 피하기 위해 상대의 의견을 일단 수용하거나 화제를 돌림"
            
        scenarios.append({"situation": "회의 중 의견 충돌이 발생했을 때", "prediction": reaction})
        
        return scenarios

    def generate_coaching_advice(self) -> List[str]:
        """
        [New] 맞춤형 코칭 어드바이스 생성
        """
        advice = []
        vec = self.vector
        
        # 독성 피드백
        tox = vec.get("toxicity_score", 0.0)
        if tox > 0.15:
            advice.append("🚨 [Critical] 부정적인 단어 사용 빈도가 높습니다. 이는 매칭 알고리즘에서 큰 감점 요인입니다.")
        
        # 밸런스 피드백 (Cross-Analysis)
        if vec.get("directness_score") > 0.8 and vec.get("empathy_score") < 0.3:
            advice.append("💡 팩트 전달 능력은 탁월하지만, '쿠션어(괜찮으시다면, 혹시 등)'를 섞어 쓰면 설득력이 2배 높아질 것입니다.")
            
        if vec.get("initiative_score") < 0.3:
            advice.append("💡 너무 상대에게 맞추려 하지 마세요. 가끔은 본인의 의견을 먼저 제시하는 것이 매력적으로 보입니다.")
            
        if not advice:
            advice.append("✅ 전반적으로 균형 잡힌 대화 스타일을 가지고 있습니다. 현재의 스타일을 유지하세요.")

        return advice

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """최종 리포트 생성"""
        logger.info("Synthesizing comprehensive report...")
        
        # 1. 기본 분석 (통계 & 서술)
        identity = self.identity_engine.analyze_core_identity(self.vector)
        detailed_metrics = self.analyze_deep_metrics()
        
        # 2. 시뮬레이션 & 코칭
        scenarios = self.simulate_scenarios()
        coaching = self.generate_coaching_advice()
        
        # 3. 시각화 데이터 (레이더 차트용)
        radar_data = {
            "labels": ["직설성", "감성", "공감", "주도성", "갈등대처"],
            "user_data": [
                self.vector.get("directness_score", 0),
                self.vector.get("emotion_score", 0),
                self.vector.get("empathy_score", 0),
                self.vector.get("initiative_score", 0),
                self.vector.get("conflict_score", 0)
            ],
            "average_data": [0.5, 0.5, 0.5, 0.5, 0.5] # 전체 평균(가정)
        }

        # 4. 최종 JSON 구조 조립
        final_report = {
            "meta_info": {
                "user_id": self.meta.get("target_name"),
                "analyzed_at": datetime.now().isoformat(),
                "data_reliability": "High" if self.meta.get("message_count_used", 0) > 100 else "Low"
            },
            "communication_dna": {
                "summary_title": identity["short_title"],
                "full_description": identity["description"],
                "keywords": identity["keywords"]
            },
            "statistical_analysis": detailed_metrics, # 통계 분석 결과
            "behavioral_prediction": scenarios,       # 행동 예측
            "ai_coaching": coaching,                  # 개선 가이드
            "visualization_data": radar_data          # 차트 데이터
        }
        
        return final_report

    def save(self, output_path: str):
        report = self.generate_comprehensive_report()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Deep analysis report saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="profile.json")
    parser.add_argument("--out", default="report_deep.json")
    args = parser.parse_args()
    
    reporter = EchoMindDeepReporter(args.profile)
    reporter.save(args.out)