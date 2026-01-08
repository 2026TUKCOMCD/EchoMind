# matcher.py
# -*- coding: utf-8 -*-

"""
EchoMind 매칭 시스템 (콘솔 출력 버전)
-----------------------------------------
[목적]
    타겟 사용자의 프로필 벡터를 데이터베이스(후보군)와 비교 분석합니다.
    분석된 매칭 결과를 시각적인 순위표(Leaderboard) 형태로 콘솔 창에 즉시 출력합니다.

[주요 기능]
    - CLI를 통한 매칭 알고리즘 가중치(Weight) 사용자 정의 및 튜닝 가능
    - 가시성 높은 리더보드 출력 (외부 라이브러리 의존성 없음)
    - 예외 처리가 강화된 안정적인 벡터 비교 로직
"""

import os
import json
import math
import glob
import argparse
import logging
from typing import List, Dict, Tuple

# 로깅 설정 (결과는 print로, 시스템 로그는 logging으로 분리)
logging.basicConfig(level=logging.WARNING, format="[LOG] %(message)s")
logger = logging.getLogger("Matcher")

class MatchEngine:
    def __init__(self, w_sim=0.7, w_dist=0.3, w_tox=2.0):
        # CLI에서 받은 가중치 적용
        self.w_sim = w_sim    # 성향 방향성 (Cosine)
        self.w_dist = w_dist  # 성향 강도 (Distance)
        self.w_tox = w_tox    # 독성 패널티 (Penalty)

    def _load_json(self, path: str) -> Dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "communication_vector" not in data:
                    return None
                return data
        except:
            return None

    def _cosine_similarity(self, v1: Dict, v2: Dict, keys: List[str]) -> float:
        dot = sum(v1[k] * v2[k] for k in keys)
        norm1 = math.sqrt(sum(v1[k]**2 for k in keys))
        norm2 = math.sqrt(sum(v2[k]**2 for k in keys))
        if norm1 == 0 or norm2 == 0: return 0.0
        return dot / (norm1 * norm2)

    def _euclidean_score(self, v1: Dict, v2: Dict, keys: List[str]) -> float:
        dist_sq = sum((v1[k] - v2[k])**2 for k in keys)
        dist = math.sqrt(dist_sq)
        # 거리 0이면 1점, 거리 멀어질수록 0점에 수렴
        return 1 / (1 + dist)

    def calculate(self, target: Dict, candidate: Dict) -> Dict:
        v1 = target["communication_vector"]
        v2 = candidate["communication_vector"]
        
        # 공통 키 추출 (안전성 확보)
        common_keys = [k for k in v1 if k in v2 and k != "toxicity_score"]
        
        # 1. 성향 점수
        sim = self._cosine_similarity(v1, v2, common_keys)
        dist = self._euclidean_score(v1, v2, common_keys)
        base_score = (sim * self.w_sim) + (dist * self.w_dist)
        
        # 2. 독성 패널티 (Gap이 클수록 감점)
        t1 = v1.get("toxicity_score", 0.0)
        t2 = v2.get("toxicity_score", 0.0)
        tox_diff = abs(t1 - t2)
        penalty = tox_diff * self.w_tox
        
        final_score = base_score - penalty
        
        # 3. 매칭 코멘트 생성
        if penalty > 0.3: comment = "독성 차이 큼"
        elif sim > 0.9: comment = "영혼의 단짝"
        elif sim > 0.7: comment = "좋은 파트너"
        else: comment = "평범한 관계"

        return {
            "score": round(final_score * 100, 1), # 100점 만점 환산
            "sim": round(sim, 2),
            "tox_gap": round(tox_diff, 2),
            "comment": comment
        }

def print_leaderboard(target_name: str, results: List[Dict]):
    """콘솔에 예쁜 표를 출력하는 함수"""
    print(f"\n[EchoMind] '{target_name}'님을 위한 매칭 리포트")
    print("=" * 65)
    print(f"| {'Rank':^4} | {'User ID':^12} | {'Score':^6} | {'Sim':^4} | {'ToxGap':^6} | {'Note':^12} |")
    print("-" * 65)
    
    for res in results:
        rank = res['rank']
        uid = res['user_id'][:12] # 이름 길면 자름
        score = res['match_info']['score']
        sim = res['match_info']['sim']
        tox = res['match_info']['tox_gap']
        note = res['match_info']['comment']
        
        # [수정됨] 메달 이모지 삭제 -> 단순 숫자로 변경
        print(f"| {rank:^4} | {uid:<12} | {score:>6} | {sim:>4} | {tox:>6} | {note:<12} |")
    
    print("=" * 65)
    print(f"* Sim: 성향 유사도 (1.0=완벽일치)")
    print(f"* ToxGap: 독성 점수 차이 (클수록 위험)")
    print("\n")

def main():
    parser = argparse.ArgumentParser(description="EchoMind Matcher (Console Output)")
    parser.add_argument("--target", required=True, help="Path to profile.json")
    parser.add_argument("--db", required=True, help="Folder containing candidate jsons")
    # 가중치 튜닝 옵션 추가
    parser.add_argument("--w_sim", type=float, default=0.7, help="Similarity Weight (default: 0.7)")
    parser.add_argument("--w_tox", type=float, default=2.0, help="Toxicity Penalty Weight (default: 2.0)")
    
    args = parser.parse_args()
    
    engine = MatchEngine(w_sim=args.w_sim, w_tox=args.w_tox)
    
    # 1. 타겟 로드
    target_data = engine._load_json(args.target)
    if not target_data:
        print("❌ Error: Target profile invalid.")
        return
    
    target_name = target_data.get("user_id", "Unknown")

    # 2. 후보군 스캔
    search_path = os.path.join(args.db, "*.json")
    files = glob.glob(search_path)
    
    results = []
    
    # 3. 매칭 실행
    for fpath in files:
        if os.path.abspath(fpath) == os.path.abspath(args.target): continue # 본인 제외
        
        cand = engine._load_json(fpath)
        if not cand: continue
        
        cand_name = cand.get("user_id", os.path.basename(fpath))
        if cand_name == target_name: continue # ID 같으면 제외
        
        info = engine.calculate(target_data, cand)
        
        results.append({
            "user_id": cand_name,
            "match_info": info
        })
        
    # 4. 정렬 및 출력
    results.sort(key=lambda x: x['match_info']['score'], reverse=True)
    
    # 순위 할당
    for i, item in enumerate(results):
        item['rank'] = i + 1
        
    # 결과 출력
    if not results:
        print("매칭 가능한 후보가 없습니다.")
    else:
        print_leaderboard(target_name, results)

if __name__ == "__main__":
    main()