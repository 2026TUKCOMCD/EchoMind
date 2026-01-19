# reporter.py
# -*- coding: utf-8 -*-

"""
[EchoMind Reporter] Rule-based Deep Analysis (Advanced Version)
---------------------------------------------------------------
main.py에서 생성된 고도화된 프로필 벡터(시간, 어휘, 주도성 포함)를 입력받아
심층적인 심리 분석 리포트와 행동 예측 결과를 제공합니다.
"""

import json
import os
import sys
import argparse
import logging
from scipy.stats import norm
from datetime import datetime
from typing import Dict, Any, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] REPORT: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("DeepReporter")

# ----------------------------
# 1. Statistical Engine
# ----------------------------
class StatEngine:
    def __init__(self, mean=0.5, std=0.15):
        self.mean = mean
        self.std = std

    def get_percentile(self, score: float) -> str:
        z_score = (score - self.mean) / self.std
        percentile = norm.cdf(z_score) * 100
        
        if percentile >= 90: return "최상위권 (Top 10%)"
        elif percentile >= 75: return "상위권 (Top 25%)"
        elif percentile >= 40: return "평균 범위 (Middle)"
        elif percentile >= 20: return "하위권 (Bottom 25%)"
        else: return "최하위권 (Bottom 10%)"

    def get_deviation_msg(self, score: float, label: str) -> str:
        if score > 0.8: intensity = "매우 높은"
        elif score > 0.6: intensity = "다소 높은"
        elif score < 0.2: intensity = "매우 낮은"
        elif score < 0.4: intensity = "다소 낮은"
        else: return f"평균적인 {label} 수치를 보입니다."
        return f"일반 사용자 대비 {intensity} {label} 경향이 있습니다."

# ----------------------------
# 2. Identity Engine
# ----------------------------
class IdentityEngine:
    def analyze_core_identity(self, vec: Dict[str, float]) -> Dict[str, Any]:
        tags = []
        descriptions = []
        
        # 1. 활동 패턴 (답장 속도, 야간활동 로직 삭제됨)
        # 속도 관련 분석 로직 삭제
            
        # 2. 지적 수준 (감성도 제거됨)
        vocab = vec.get("vocab_ttr", 0.5)
        
        if vocab > 0.7:
            tags.append("#뇌섹남녀")
            style_desc = "다양한 어휘를 구사하며 지적인 대화를 이끌어가는 스타일입니다."
        else:
            style_desc = "핵심만 간결하게 전달하는 효율적인 대화 스타일입니다."
            
        # 3. 주도성
        initiation = vec.get("initiation_ratio", 0.0)
        if initiation > 0.6:
            tags.append("#적극적리더")
            
        full_desc = f"당신은 {' '.join(descriptions)} {style_desc}"
        
        if not tags: tags = ["#밸런스형"]

        return {
            "keywords": tags[:4],
            "description": full_desc,
            "short_title": f"{tags[0]} 스타일의 {tags[-1]}"
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
        
        self.stat_engine = StatEngine()
        self.identity_engine = IdentityEngine()

    def _load_data(self) -> Dict[str, Any]:
        if self.profile_path == "dummy":
            return {}

        if not os.path.exists(self.profile_path):
            logger.error(f"Profile not found: {self.profile_path}")
            return {} 
            
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            return {}

    def analyze_deep_metrics(self) -> Dict[str, Any]:
        metrics = {}
        # 감성도, 야간활동성, 답장속도 제거됨
        labels = {
            "activity_score": "활동성", 
            "politeness_score": "정중함",
            "impact_score": "직설성",
            "initiation_ratio": "주도성(선톡)",
            "vocab_ttr": "어휘다양성"
        }
        
        for key, label_kr in labels.items():
            val = self.vector.get(key, 0.0)
            metrics[key] = {
                "raw_score": val,
                "percentile": self.stat_engine.get_percentile(val),
                "analysis": self.stat_engine.get_deviation_msg(val, label_kr)
            }
        return metrics

    def simulate_scenarios(self) -> List[Dict[str, str]]:
        scenarios = []
        vec = self.vector
        
        if vec.get("initiation_ratio", 0) > 0.6:
            reaction = "참지 않고 먼저 '잘 지내?'라며 자연스럽게 선톡을 보냄"
        else:
            reaction = "각자의 시간이 중요하다고 생각하며 묵묵히 기다림"
        scenarios.append({"situation": "썸이나 친구 관계에서 연락이 뜸해졌을 때", "prediction": reaction})
        
        # 야간활동, 답장속도 시나리오 제거됨
        
        if vec.get("impact_score", 0) > 0.7 and vec.get("vocab_ttr", 0) > 0.6:
            reaction = "논리정연하고 다양한 어휘를 사용해 상대를 팩트로 압도함"
        else:
            reaction = "갈등을 회피하고 화제를 돌리거나 단답으로 일관함"
        scenarios.append({"situation": "의견 충돌로 논쟁이 발생했을 때", "prediction": reaction})
        
        return scenarios

    def generate_coaching_advice(self) -> List[str]:
        advice = []
        vec = self.vector
        
        entropy = vec.get("data_entropy", 0.0)
        if entropy < 0.3:
            advice.append("[Warning] 대화 패턴이 너무 단순하거나 반복적입니다.")
        
        if vec.get("toxicity_score", 0) > 0.1:
            advice.append("[Critical] 비속어 사용이 감지되었습니다. 매칭 점수가 하락할 수 있습니다.")

        # 답장 속도 조언 삭제됨
        
        if vec.get("vocab_ttr", 0) < 0.4 and vec.get("activity_score", 0) > 0.7:
            advice.append("말수는 많지만 어휘가 반복적입니다. 다양한 표현을 써보세요.")

        if not advice:
            advice.append("아주 훌륭한 대화 매너와 패턴을 가지고 계십니다!")

        return advice

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        if not self.vector:
            logger.warning("Vector data is empty. Using default values.")
            # 삭제된 키 제거
            self.vector = {k: 0.5 for k in ["activity_score", "politeness_score", "impact_score", "initiation_ratio", "vocab_ttr", "data_entropy", "toxicity_score"]}

        identity = self.identity_engine.analyze_core_identity(self.vector)
        metrics = self.analyze_deep_metrics()
        scenarios = self.simulate_scenarios()
        coaching = self.generate_coaching_advice()
        
        radar_data = {
            "labels": ["적극성", "정중함", "직설성", "어휘력"],
            "user_data": [
                self.vector.get("activity_score", 0),
                self.vector.get("politeness_score", 0),
                self.vector.get("impact_score", 0),
                self.vector.get("vocab_ttr", 0)
            ],
            "average_data": [0.5] * 4
        }

        return {
            "_meta": {
                "user_id": self.meta.get("target_name") or self.data.get("user_id", "Unknown"),
                "generated_at": datetime.now().isoformat(),
                "algorithm": self.meta.get("algorithm", "rule_based_scientific_v5")
            },
            "communication_dna": {
                "summary_title": identity["short_title"],
                "full_description": identity["description"],
                "keywords": identity["keywords"]
            },
            "statistical_analysis": metrics,
            "behavioral_prediction": scenarios,
            "ai_coaching": coaching,
            "visualization_data": radar_data,
            "communication_vector": self.vector 
        }

    def save(self, output_path: str):
        report = self.generate_comprehensive_report()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Deep analysis report saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Path to profile.json")
    parser.add_argument("--out", default="report_deep.json", help="Output report path")
    args = parser.parse_args()
    
    reporter = EchoMindDeepReporter(args.profile)
    reporter.save(args.out)