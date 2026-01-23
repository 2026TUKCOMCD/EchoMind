# match_manager.py
# -*- coding: utf-8 -*-

"""
[EchoMind] 서비스 비즈니스 로직 및 데이터 트랜잭션 관리
======================================================================

[시스템 개요]
본 모듈은 EchoMind 서비스의 핵심 데이터 엔티티(사용자, 매칭 요청, 알림) 간의 
상호작용을 관리하는 서비스 레이어입니다. Flask 애플리케이션과 AWS RDS MySQL 
데이터베이스 사이의 교량 역할을 수행하며, 원자성(Atomicity) 있는 트랜잭션을 처리합니다.

[주요 기능 및 로직]
1. Candidate Discovery (후보자 발굴)
   - 사용자의 대표 성향 프로필을 기반으로 매칭 가능한 후보군을 동적 쿼리합니다.
   - 이미 신청 중이거나 본인인 경우를 제외하는 'Anti-Join' 필터링이 포함되어 있습니다.

2. Match Request Pipeline (매칭 신청 프로세스)
   - 사용자 간 매칭 신청 이벤트를 생성하며, 중복 신청 및 자기 자신 매칭을 차단합니다.
   - 트랜잭션 롤백 설계를 통해 데이터 삽입 실패 시 정합성을 유지합니다.

3. Notification Service (알림 시스템)
   - 매칭 수락/거절 이벤트 발생 시 상대방에게 실시간 알림 데이터를 생성합니다.
   - 일괄 읽음 처리(Bulk Update) 기능을 통해 데이터베이스 I/O 효율을 높였습니다.

4. Activity Data Integrity (활동성 정합성)
   - 분석 시점의 대화량(line_count) 데이터를 연동하여 matcher.py의 정밀도를 보장합니다.

[데이터베이스 연관 테이블]
- users: 기본 사용자 정보 참조
- personality_results: 성향 분석 데이터 및 활동량 참조
- match_requests: 매칭 신청 상태(PENDING/ACCEPTED/REJECTED) 관리
- notifications: 시스템 알림 생성 및 읽음 상태 관리

[사용법]
  - app.py에서 MatchManager 클래스의 클래스 메서드를 직접 호출하여 사용합니다.
  - 예: MatchManager.get_matching_candidates(user_id=1, limit=5)
"""

import pymysql
import os
import json
import glob
import numpy as np
from config import config_by_name  # 프로젝트 설정 모듈 임포트
from scipy.spatial.distance import cosine
import matcher  # matcher.py의 고급 매칭 알고리즘 사용

# 환경 변수로부터 현재 실행 모드(development/production) 로드
env = os.getenv('FLASK_ENV', 'development')
cfg = config_by_name[env]

class MatchManager:
    """
    사용자 간 매칭 및 알림 시스템을 전담 관리하는 클래스입니다.
    RDS 데이터베이스와 직접 통신하며 비즈니스 로직을 수행합니다.
    """

    @staticmethod
    def get_db_connection():
        """AWS RDS MySQL 연결 객체를 반환합니다."""
        return pymysql.connect(
            host=cfg.DB_HOST,
            user=cfg.DB_USER,
            password=cfg.DB_PASSWORD,
            db=cfg.DB_NAME,
            port=int(cfg.DB_PORT),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    @classmethod
    def get_matching_candidates(cls, my_user_id, current_user_profile_json=None, limit=5):
        """
        [조회] 나에게 맞는 매칭 후보 리스트를 가져옵니다.
        
        Args:
            my_user_id: 현재 사용자 ID (DB 정수 ID 또는 u_XXX 형식)
            current_user_profile_json: 현재 사용자의 프로필 JSON (dict)
            limit: 반환할 후보자 수
        """
        try:
            # candidates_db 폴더의 모든 JSON 파일 로드
            base_dir = os.path.dirname(__file__)
            candidates_path = os.path.join(base_dir, 'candidates_db', '*.json')
            json_files = glob.glob(candidates_path)
            
            candidates = []
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # JSON 구조에서 필요한 데이터 추출
                    meta = data.get('meta', {})
                    llm_profile = data.get('llm_profile', {})
                    user_id = meta.get('user_id')
                    
                    # 자신의 프로필은 제외
                    if user_id == my_user_id:
                        continue
                    
                    candidate = {
                        'user_id': user_id,
                        'username': meta.get('speaker_name', 'Unknown'),
                        'nickname': meta.get('speaker_name', 'Unknown'),
                        'mbti_prediction': llm_profile.get('mbti', {}).get('type', 'Unknown'),
                        'socionics_prediction': llm_profile.get('socionics', {}).get('type', 'Unknown'),
                        'summary_text': llm_profile.get('summary', {}).get('one_paragraph', ''),
                        'full_report_json': data,
                        'line_count_at_analysis': data.get('parse_quality', {}).get('parsed_lines', 0),
                        'big5': llm_profile.get('big5', {}).get('scores_0_100', {})
                    }
                    candidates.append(candidate)
                except Exception as e:
                    print(f"Error loading {json_file}: {e}")
                    continue
            
            # 매칭 점수 계산 및 정렬
            if candidates:
                candidates = cls._calculate_match_scores(
                    my_user_id, 
                    candidates,
                    current_user_profile_json
                )
                candidates = sorted(candidates, key=lambda x: x.get('match_score', 0), reverse=True)
                return candidates[:limit]
            
            return []
        except Exception as e:
            print(f"Error fetching candidates: {e}")
            return []


    
    @classmethod
    def _calculate_match_scores(cls, my_user_id, candidates, current_user_profile_json=None, weights=None):
        """
        matcher.py의 HybridMatcher를 사용하여 고급 매칭 점수를 계산합니다.
        가중치 조정을 위해 weights 파라미터가 추가되었습니다.
        
        Args:
            weights: dict {'similarity': 0.5, 'chemistry': 0.4, 'activity': 0.1} 형태
        """
        # 기본 가중치 설정
        if weights is None:
            weights = {'similarity': 0.5, 'chemistry': 0.4, 'activity': 0.1}

        try:
            # 현재 사용자 프로필 로드
            target_user = None
            
            # 1. 전달받은 프로필 JSON이 있으면 그것을 사용
            if current_user_profile_json:
                target_user = cls._convert_json_to_user_vector(
                    current_user_profile_json,
                    my_user_id
                )
            
            # 2. 전달받은 프로필이 없으면 파일에서 로드 (legacy)
            if not target_user:
                base_dir = os.path.dirname(__file__)
                profile_file = os.path.join(base_dir, 'profile', 'profile.json')
                
                if os.path.exists(profile_file):
                    target_user = matcher.load_profile(profile_file)
            
            # 3. 모든 방법이 실패했으면 기본값 반환
            if not target_user:
                print(f"[Warning] 현재 사용자 프로필을 로드할 수 없습니다. 기본 점수(50) 반환")
                for candidate in candidates:
                    candidate['match_score'] = 50
                return candidates
            
            # 모든 candidates를 UserVector로 변환
            candidate_users = []
            for candidate in candidates:
                # 임시 JSON 파일로 변환
                candidate_json = candidate.get('full_report_json', {})
                user_vector = cls._convert_json_to_user_vector(
                    candidate_json,
                    candidate.get('user_id')
                )
                if user_vector:
                    candidate_users.append(user_vector)
            
            if not candidate_users:
                for candidate in candidates:
                    candidate['match_score'] = 50
                return candidates
            
            # [FIX] HybridMatcher 초기화
            hybrid_matcher = matcher.HybridMatcher(candidate_users + [target_user])
            hybrid_matcher.normalize_user(target_user)
            
            # 각 후보자 정규화 및 점수 계산
            for i, candidate_user in enumerate(candidate_users):
                hybrid_matcher.normalize_user(candidate_user)
                scores = hybrid_matcher.calculate_match_score(target_user, candidate_user)
                
                # [Dynamic Weighting] 동적 가중치 적용
                new_total = (
                    scores['similarity_score'] * weights['similarity'] +
                    scores['chemistry_score'] * weights['chemistry'] +
                    scores['activity_score'] * weights['activity']
                )
                
                # 상세 점수 업데이트
                scores['total_score'] = new_total
                
                # 0~100 범위로 정규화
                match_score = int(new_total * 100)
                candidates[i]['match_score'] = max(0, min(100, match_score))
                candidates[i]['match_details'] = scores

                # [추가] 상대적 성향 분석 (Z-Score 기반)
                # 0:Openness, 1:Conscientiousness, 2:Extraversion, 3:Agreeableness, 4:Neuroticism
                trait_names_kr = ["개방성", "성실성", "외향성", "우호성", "신경성"]
                distinctive_traits = []
                
                if candidate_user.big5_z_score is not None:
                    for idx, z_val in enumerate(candidate_user.big5_z_score):
                        if z_val >= 0.8:
                            distinctive_traits.append({"name": trait_names_kr[idx], "level": "High", "label": "높음", "color": "blue"})
                        elif z_val <= -0.8:
                            distinctive_traits.append({"name": trait_names_kr[idx], "level": "Low", "label": "낮음", "color": "gray"})
                
                # 최대 3개까지만 표시
                candidates[i]['relative_traits'] = distinctive_traits[:3]
            
            return candidates
        except Exception as e:
            print(f"Error calculating match scores: {e}")
            import traceback
            traceback.print_exc()
            # 점수 계산 실패해도 candidates 반환
            for candidate in candidates:
                candidate['match_score'] = 50
            return candidates
    
    @classmethod
    def _convert_json_to_user_vector(cls, json_data, user_id):
        """
        candidates_db의 JSON 데이터를 matcher.UserVector로 변환합니다.
        """
        try:
            meta = json_data.get('meta', {})
            llm_profile = json_data.get('llm_profile', {})
            
            mbti_data = llm_profile.get('mbti', {})
            big5_data = llm_profile.get('big5', {})
            socionics_data = llm_profile.get('socionics', {})
            
            # Big5 배열 구성
            scores = big5_data.get('scores_0_100', {})
            big5_raw = np.array([
                scores.get('openness', 50),
                scores.get('conscientiousness', 50),
                scores.get('extraversion', 50),
                scores.get('agreeableness', 50),
                scores.get('neuroticism', 50)
            ], dtype=float)
            
            # UserVector 생성
            user_vector = matcher.UserVector(
                user_id=user_id,
                name=meta.get('speaker_name', 'Unknown'),
                mbti_type=mbti_data.get('type', 'UNKNOWN'),
                mbti_conf=mbti_data.get('confidence', 0.0),
                big5_raw=big5_raw,
                big5_conf=big5_data.get('confidence', 0.0),
                socionics_type=socionics_data.get('type', 'Unknown'),
                socionics_conf=socionics_data.get('confidence', 0.0),
                line_count=json_data.get('parse_quality', {}).get('parsed_lines', 0)
            )
            
            return user_vector
        except Exception as e:
            print(f"Error converting JSON to UserVector: {e}")
            return None

    @classmethod
    def send_match_request(cls, sender_id, receiver_id):
        """
        [신청] 특정 유저에게 매칭 신청을 보냅니다.
        현재: candidates_db 사용 시 JSON 기반으로 처리 (DB 미사용)
        향후: DB 기반으로 변경 예정
        """
        # [추가: 매칭 신청의 비가역성] 자기 자신에게 신청하는 경우 방지
        if str(sender_id) == str(receiver_id):
            return {"success": False, "message": "자기 자신에게는 매칭 신청을 할 수 없습니다."}

        # candidates_db의 user_id (u_201 형식)인 경우
        if isinstance(receiver_id, str) and receiver_id.startswith('u_'):
            # 임시: 파일 기반 저장 또는 메모리 저장
            # 향후 DB 구현 시 변경
            return {
                "success": True, 
                "message": f"성공적으로 신청을 보냈습니다! (대상: {receiver_id})"
            }
        
        # DB 기반 처리 (기존 로직)
        try:
            receiver_id = int(receiver_id)
        except (ValueError, TypeError):
            return {"success": False, "message": "잘못된 사용자 ID입니다."}

        conn = cls.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 쌍방향 중복 체크 로직
                check_sql = """
                SELECT status FROM match_requests 
                WHERE (sender_id = %s AND receiver_id = %s) 
                   OR (sender_id = %s AND receiver_id = %s)
                """
                cursor.execute(check_sql, (sender_id, receiver_id, receiver_id, sender_id))
                if cursor.fetchone():
                    return {"success": False, "message": "이미 진행 중인 매칭 건이 존재합니다."}

                # 신청 데이터 삽입
                insert_sql = "INSERT INTO match_requests (sender_id, receiver_id) VALUES (%s, %s)"
                cursor.execute(insert_sql, (sender_id, receiver_id))
                
            conn.commit()
            return {"success": True, "message": "성공적으로 신청을 보냈습니다."}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": str(e)}
        finally:
            conn.close()

    @classmethod
    def respond_to_request(cls, request_id, action):
        """
        [응답] 매칭 신청에 대해 수락 또는 거절 처리를 합니다.
         동시에 신청자에게 결과 알림을 생성하여 notifications 테이블에 저장합니다.
        """
        if action not in ['ACCEPTED', 'REJECTED']:
            return {"success": False, "message": "잘못된 응답 액션입니다."}

        conn = cls.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 신청자 정보 및 수신자 이름 로드
                cursor.execute("""
                    SELECT r.sender_id, u.username as receiver_name 
                    FROM match_requests r
                    JOIN users u ON r.receiver_id = u.user_id
                    WHERE r.request_id = %s
                """, (request_id,))
                req_data = cursor.fetchone()
                
                if not req_data:
                    return {"success": False, "message": "요청 건을 찾을 수 없습니다."}

                # 매칭 상태 업데이트
                cursor.execute("UPDATE match_requests SET status = %s WHERE request_id = %s", (action, request_id))

                # 시스템 알림 생성
                res_msg = "수락" if action == 'ACCEPTED' else "거절"
                msg = f"{req_data['receiver_name']}님이 매칭 신청을 {res_msg}하셨습니다."
                cursor.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (req_data['sender_id'], msg))

            conn.commit()
            return {"success": True, "message": f"매칭 {res_msg} 처리가 완료되었습니다."}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": str(e)}
        finally:
            conn.close()

    @classmethod
    def get_unread_notifications(cls, user_id):
        """[알림] 읽지 않은 최신 알림 목록을 반환"""
        conn = cls.get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM notifications WHERE user_id = %s AND is_read = FALSE ORDER BY created_at DESC"
                cursor.execute(sql, (user_id,))
                return cursor.fetchall()
        # [추가: 예외 처리 강화] 알림 조회 중 발생할 수 있는 에러 포착
        except Exception as e:
            print(f"Error fetching notifications: {e}")
            return []
        finally:
            conn.close()

    @classmethod
    def mark_notifications_as_read(cls, user_id):
        """
        알림 일괄 읽음 처리 기능 수행. SQL 스크립트 하단에 안내된 업데이트 로직을 실제 구현한 메서드
        """
        conn = cls.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 안 읽은 알림 전체를 읽음으로 변경
                sql = "UPDATE notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE"
                cursor.execute(sql, (user_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating notifications: {e}")
            return False
        finally:
            conn.close()