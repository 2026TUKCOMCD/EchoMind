# matcher.py
# -*- coding: utf-8 -*-

"""
[EchoMind Matcher] Multi-Dimensional Statistical Matching System
----------------------------------------------------------------
main.py에서 생성된 7가지 고도화 지표를 활용하여 최적의 상대를 찾습니다.
원본 벡터(0~1)를 직접 비교하여 소규모 데이터에서도 정확하게 작동합니다.

[매칭 알고리즘 구조]
 1. Style Score (70%): 성향 3대 지표 (Cosine Similarity) - 결이 비슷한가?
 2. Life Score  (30%): 시간/지능/습관 3대 지표 (Euclidean Distance) - 생활 패턴이 맞는가?
 3. Penalty    (Subtract): 독성 점수 절대값 패널티 (Weighted Penalty) - 위험 요소가 있는가?

[실행 방법]
   python matcher.py --target "profile.json" --db "./candidates_db"
"""

import os
import json
import glob
import argparse
import numpy as np
from typing import List, Dict, Tuple

class AdvancedMatcher:
    def __init__(self, w_style=0.7, w_life=0.3, w_tox=2.0):
        # 가중치 설정 (성향 70%, 라이프스타일 30%, 독성 패널티 가중치 2.0)
        self.w_style = w_style
        self.w_life = w_life
        self.w_tox = w_tox

    def load_data(self, target_path: str, db_folder: str) -> Tuple[Dict, List[Dict]]:
        """타겟 및 후보군 데이터 로드"""
        target = self._load(target_path)
        candidates = []
        
        if not target:
            raise ValueError("Target profile is invalid.")

        if not os.path.exists(db_folder):
            raise ValueError(f"DB folder not found: {db_folder}")

        for f in glob.glob(os.path.join(db_folder, "*.json")):
            if os.path.abspath(f) == os.path.abspath(target_path): continue
            
            cand = self._load(f)
            if cand and cand.get("user_id") != target.get("user_id"):
                vec = cand.get("communication_vector", {})
                if "initiation_ratio" in vec:
                    candidates.append(cand)
        
        return target, candidates

    def _load(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return None

    def calculate_match(self, target_vec: Dict, cand_vec: Dict) -> Dict:
        """
        개별 후보에 대한 매칭 점수 계산 (Raw Vector 사용 + 독성 절대값 패널티)
        """
        # 그룹별 키 정의 (감성도, 야간활동, 답장속도 제거됨)
        style_keys = ["activity_score", "politeness_score", "impact_score"]
        life_keys = ["initiation_ratio", "vocab_ttr", "data_entropy"]

        # 1. Style Match (Cosine Similarity)
        v1_s = np.array([target_vec.get(k, 0.5) for k in style_keys])
        v2_s = np.array([cand_vec.get(k, 0.5) for k in style_keys])
        
        dot = np.dot(v1_s, v2_s)
        norm = np.linalg.norm(v1_s) * np.linalg.norm(v2_s)
        
        if norm < 1e-9:
            style_sim = 0.5
        else:
            style_sim = (dot / norm + 1) / 2

        # 2. Life Match (Euclidean Distance)
        v1_l = np.array([target_vec.get(k, 0.5) for k in life_keys])
        v2_l = np.array([cand_vec.get(k, 0.5) for k in life_keys])
        
        dist = np.linalg.norm(v1_l - v2_l)
        life_sim = 1 / (1 + dist * 0.4) 

        # 3. Penalty (Absolute Toxicity)
        cand_tox = cand_vec.get("toxicity_score", 0.0)
        
        if cand_tox >= 0.2:
            tox_pen = cand_tox * self.w_tox
        else:
            tox_pen = 0.0

        # 4. 종합 점수
        final_score = (style_sim * self.w_style) + (life_sim * self.w_life) - tox_pen
        
        return {
            "total": max(0, final_score * 100),
            "style": style_sim,
            "life": life_sim,
            "penalty": tox_pen
        }

    def generate_comment(self, info: Dict) -> str:
        score = info["total"]
        if info["penalty"] > 0.4: return "위험: 언어습관 문제"
        if score >= 99: return "도플갱어 수준 (완벽)"
        if score >= 90: return "영혼의 단짝 (최고)"
        if score >= 80: return "찰떡 궁합 (강력 추천)"
        if score >= 70: return "좋은 인연 (잘 맞음)"
        if info["life"] < 0.4: return "생활 패턴 차이 있음"
        if info["style"] < 0.4: return "성격 유형이 다름"
        return "평범한 관계"

def print_leaderboard(target_name, results):
    print(f"\n[EchoMind 매칭 리포트] '{target_name}'님의 추천 파트너")
    print("=" * 80)
    print(f"| Rank | {'User ID':^12} | Total | {'Style':^5} | {'Life':^5} | {'Pen':^4} | {'Comment':^20} |")
    print("-" * 80)
    
    for i, res in enumerate(results[:10]):
        info = res['info']
        comment = res['comment']
        print(f"| {i+1:^4} | {res['user_id'][:12]:<12} | {info['total']:>5.1f} | "
              f"{info['style']:.2f}  | {info['life']:.2f}  | {info['penalty']:.2f} | {comment:<20} |")
    
    print("=" * 80)
    print(" * Style: 성격/화법 유사도 (Cosine)")
    print(" * Life : 주도성/지능 등 라이프스타일 일치도 (Euclidean)")
    print(" * Pen  : 비속어 사용 빈도에 따른 감점 (0.2 이상 시 적용)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="Path to profile.json")
    parser.add_argument("--db", required=True, help="Directory containing candidate profiles")
    args = parser.parse_args()

    try:
        matcher = AdvancedMatcher()
        
        # 1. 데이터 로드
        target, candidates = matcher.load_data(args.target, args.db)
        if not candidates:
            print("매칭할 후보군 데이터가 없습니다.")
            return

        # 2. 매칭 점수 계산
        results = []
        for cand in candidates:
            match_info = matcher.calculate_match(
                target["communication_vector"], 
                cand["communication_vector"]
            )
            comment = matcher.generate_comment(match_info)
            results.append({
                "user_id": cand["user_id"],
                "info": match_info,
                "comment": comment
            })
            
        # 3. 정렬
        results.sort(key=lambda x: x['info']['total'], reverse=True)
        
        # 4. 출력
        print_leaderboard(target["user_id"], results)

    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    main()