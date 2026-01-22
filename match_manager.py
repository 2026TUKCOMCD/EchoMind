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
from config import config_by_name  # 프로젝트 설정 모듈 임포트

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
    def get_matching_candidates(cls, my_user_id, limit=5):
        """
        [조회] 나에게 맞는 매칭 후보 리스트를 가져옵니다.
        개선사항 B 반영: 활동성 점수 계산을 위해 line_count_at_analysis를 포함합니다.
        """
        conn = cls.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 이미 신청했거나 결과가 나온 상대는 제외하는 필터링 포함
                sql = """
                SELECT 
                    u.user_id, u.username, u.nickname, 
                    p.mbti_prediction, p.socionics_prediction, 
                    p.summary_text, p.full_report_json,
                    p.line_count_at_analysis -- [활동량 데이터 정합성 보장]
                FROM personality_results p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.is_representative = TRUE 
                  AND p.user_id != %s
                  AND p.user_id NOT IN (
                      SELECT receiver_id FROM match_requests WHERE sender_id = %s
                  )
                ORDER BY p.created_at DESC 
                LIMIT %s;
                """
                cursor.execute(sql, (my_user_id, my_user_id, limit))
                return cursor.fetchall()
        # [추가: 예외 처리 강화] DB 조회 중 발생할 수 있는 에러 포착
        except Exception as e:
            print(f"Error fetching candidates: {e}")
            return []
        finally:
            conn.close()

    @classmethod
    def send_match_request(cls, sender_id, receiver_id):
        """
        [신청] 특정 유저에게 매칭 신청을 보냅니다.
        데이터 무결성: 중복 및 교차 신청 여부를 사전에 체크합니다.
        """
        # [추가: 매칭 신청의 비가역성] 자기 자신에게 신청하는 경우 방지
        if sender_id == receiver_id:
            return {"success": False, "message": "자기 자신에게는 매칭 신청을 할 수 없습니다."}

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