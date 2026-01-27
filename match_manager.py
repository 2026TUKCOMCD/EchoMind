# match_manager.py
# -*- coding: utf-8 -*-

"""
[EchoMind] 서비스 비즈니스 로직 및 데이터 트랜잭션 관리 (SQLAlchemy Refactored)
======================================================================

[시스템 개요]
본 모듈은 EchoMind 서비스의 핵심 데이터 엔티티(사용자, 매칭 요청, 알림) 간의 
상호작용을 관리하는 서비스 레이어입니다. Flask 애플리케이션과 AWS RDS MySQL 
데이터베이스 사이의 교량 역할을 수행하며, SQLAlchemy ORM을 사용하여 
안전하고 효율적인 트랜잭션을 처리합니다.

[주요 기능 및 로직]
1. Candidate Discovery (후보자 발굴)
   - 사용자의 대표 성향 프로필(is_representative=True)을 기반으로 매칭 가능한 
     후보군을 동적 쿼리합니다.
   - DB 기반 'Anti-Join' 필터링을 통해 이미 매칭 중이거나 본인인 경우를 제외합니다.

2. Match Request Pipeline (매칭 신청 프로세스)
   - 사용자 간 매칭 신청 이벤트를 생성하며, 중복 신청 및 자기 자신 매칭을 차단합니다.
   - 트랜잭션 관리(commit/rollback)를 통해 데이터 정합성을 유지합니다.

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
  - 예: MatchManager.get_matching_candidates(my_user_id=1, limit=5)
"""

import os
import json
import logging
import numpy as np

logger = logging.getLogger(__name__)
from config import config_by_name
import matcher

# 환경 변수로부터 현재 실행 모드(development/production) 로드
env = os.getenv('FLASK_ENV', 'development')
cfg = config_by_name[env]

class MatchManager:
    """
    사용자 간 매칭 및 알림 시스템을 전담 관리하는 클래스입니다.
    SQLAlchemy ORM을 사용하여 비즈니스 로직을 수행합니다.
    """

    @classmethod
    def get_matching_candidates(cls, my_user_id, current_user_profile_json=None, limit=5):
        """
        [조회] 나에게 맞는 매칭 후보 리스트를 가져옵니다.
        Hybrid Mode: candidates_db (File) + personality_results (DB) 병합
        """
        from extensions import db, User, PersonalityResult, MatchRequest
        from sqlalchemy import or_
        from utils_system import get_system_config
        
        sys_conf = get_system_config()
        hide_dummies = sys_conf.get('hide_dummies', False)
        
        candidates = []
        seen_user_ids = set()
        excluded_user_ids = {str(my_user_id)}

        try:
            # 0. 제외할 유저 ID 수집
            active_matches = MatchRequest.query.filter(
                or_(MatchRequest.sender_id == my_user_id, MatchRequest.receiver_id == my_user_id),
                ~MatchRequest.status.in_(['REJECTED', 'CANCELLED'])
            ).all()

            for req in active_matches:
                excluded_user_ids.add(str(req.sender_id))
                excluded_user_ids.add(str(req.receiver_id))

        except Exception as e:
            logger.exception("Error fetching excluded users")


        # 2. Database (personality_results) - SQLAlchemy ORM
        try:
            results = db.session.query(PersonalityResult, User)\
                .join(User, PersonalityResult.user_id == User.user_id)\
                .filter(PersonalityResult.is_representative == True)\
                .all()

            for p_result, user in results:
                uid_str = str(user.user_id)
                if uid_str in excluded_user_ids: continue
                if uid_str in seen_user_ids: continue
                if user.is_banned: continue
                
                # [System Config] 더미 숨김 처리
                if hide_dummies and user.is_dummy:
                    continue

                try:
                    full_report = p_result.full_report_json
                    
                    if isinstance(full_report, str):
                        data = json.loads(full_report)
                    else:
                        data = full_report
                    
                    if not data: continue

                    llm_profile = data.get('llm_profile', {})
                    
                    candidate = {
                        'user_id': user.user_id,
                        'username': user.username,
                        'nickname': user.nickname or user.username,
                        'mbti_prediction': p_result.mbti_prediction or 'Unknown',
                        'socionics_prediction': p_result.socionics_prediction or 'Unknown',
                        'summary_text': p_result.summary_text or '',
                        'full_report_json': data,
                        'line_count_at_analysis': p_result.line_count_at_analysis,
                        'big5': llm_profile.get('big5', {}).get('scores_0_100', {})
                    }
                    candidates.append(candidate)
                    seen_user_ids.add(uid_str)

                except Exception as e:
                    logger.exception(f"Error parsing db candidate {user.user_id}")
                    
        except Exception as e:
            logger.exception("Error in DB candidate fetching")

        # 3. Score & Sort
        if candidates:
            candidates = cls._calculate_match_scores(
                my_user_id, 
                candidates,
                current_user_profile_json
            )
            candidates = sorted(candidates, key=lambda x: x.get('match_score', 0), reverse=True)
            return candidates[:limit]
        
        return []

    @classmethod
    def get_successful_matches(cls, user_id):
        """
        [매칭 성사 목록] 나와 매칭이 성사(ACCEPTED)된 상대방 정보 조회
        (취소 요청 상태 포함)
        """
        from extensions import db, User, MatchRequest
        from sqlalchemy import or_

        try:
            # 내가 Sender이거나 Receiver인 경우 중 ACCEPTED/CANCEL_REQ 상태인 건 조회
            # JOIN으로 상대방 정보 가져오기
            
            # 1. 내가 Sender인 경우 (상대: Receiver)
            sent_matches = db.session.query(MatchRequest, User)\
                .join(User, MatchRequest.receiver_id == User.user_id)\
                .filter(
                    MatchRequest.sender_id == user_id,
                    MatchRequest.status.in_(['ACCEPTED', 'CANCEL_REQ_SENDER', 'CANCEL_REQ_RECEIVER'])
                ).all()

            # 2. 내가 Receiver인 경우 (상대: Sender)
            received_matches = db.session.query(MatchRequest, User)\
                .join(User, MatchRequest.sender_id == User.user_id)\
                .filter(
                    MatchRequest.receiver_id == user_id,
                    MatchRequest.status.in_(['ACCEPTED', 'CANCEL_REQ_SENDER', 'CANCEL_REQ_RECEIVER'])
                ).all()

            results = []
            
            # [Refactor] 두 리스트 병합 후 일괄 처리 (중복 코드 제거)
            all_matches = sent_matches + received_matches
            
            for req, partner in all_matches:
                results.append({
                    'user_id': partner.user_id,
                    'username': partner.username,
                    'nickname': partner.nickname,
                    'matched_at': req.updated_at,
                    'request_id': req.request_id,
                    'status': req.status,
                    'sender_id': req.sender_id,
                    'receiver_id': req.receiver_id
                })
            
            # 최신순 정렬
            results.sort(key=lambda x: x['matched_at'], reverse=True)
            return results

        except Exception as e:
            logger.exception("Error fetching successful matches")
            return []

    @classmethod
    def request_unmatch(cls, user_id, request_id):
        """
        [매칭 취소 요청]
        """
        from extensions import db, MatchRequest

        try:
            req = MatchRequest.query.get(request_id)
            if not req:
                return {"success": False, "message": "존재하지 않는 매칭입니다."}

            if req.status != 'ACCEPTED':
                return {"success": False, "message": "성사된 매칭 상태에서만 취소 요청이 가능합니다."}

            new_status = ''
            if req.sender_id == int(user_id):
                new_status = 'CANCEL_REQ_SENDER'
            elif req.receiver_id == int(user_id):
                new_status = 'CANCEL_REQ_RECEIVER'
            else:
                return {"success": False, "message": "권한이 없습니다."}

            req.status = new_status
            req.updated_at = db.func.now()
            db.session.commit()
            
            return {"success": True, "message": "매칭 취소를 요청했습니다. 상대방의 수락을 기다립니다."}
        
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": str(e)}

    @classmethod
    def cancel_match_request(cls, user_id, request_id):
        """
        [매칭 신청 취소] (PENDING 상태 회수)
        """
        from extensions import db, MatchRequest

        try:
            req = MatchRequest.query.get(request_id)
            if not req:
                return {"success": False, "message": "존재하지 않는 요청입니다."}

            if req.sender_id != int(user_id):
                return {"success": False, "message": "취소 권한이 없습니다."}

            if req.status != 'PENDING':
                return {"success": False, "message": "이미 처리되었거나 취소된 요청입니다."}

            # Soft Delete (CANCELLED)
            req.status = 'CANCELLED'
            req.updated_at = db.func.now()
            db.session.commit()

            return {"success": True, "message": "매칭 요청이 취소되었습니다."}

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": str(e)}

    @classmethod
    def respond_unmatch(cls, request_id, action):
        """
        [매칭 취소 응답] ACCEPT / REJECT
        """
        from extensions import db, MatchRequest

        try:
            if action not in ['ACCEPT', 'REJECT']:
                return {"success": False, "message": "잘못된 응답입니다."}

            req = MatchRequest.query.get(request_id)
            if not req:
                return {"success": False, "message": "존재하지 않는 요청입니다."}

            if action == 'ACCEPT':
                req.status = 'CANCELLED'
                msg = "매칭이 취소되었습니다."
            else:
                req.status = 'ACCEPTED' # 다시 원래대로 복구
                msg = "매칭 취소 요청을 거절했습니다."

            req.updated_at = db.func.now()
            db.session.commit()
            return {"success": True, "message": msg}

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": str(e)}

    @classmethod
    def reload_candidates(cls):
        """
        [관리자] 후보군 데이터 새로고침
        DB 모드에서는 크게 의미 없으나 호환성을 위해 유지 (DB 카운트 반환)
        """
        from extensions import PersonalityResult
        try:
            return PersonalityResult.query.filter_by(is_representative=True).count()
        except Exception as e:
            logger.exception("Error reloading candidates")
            return 0
    
    @classmethod
    def _calculate_match_scores(cls, my_user_id, candidates, current_user_profile_json=None, weights=None):
        """
        matcher.py의 HybridMatcher를 사용하여 고급 매칭 점수를 계산합니다.
        
        # ========================================================================
        # TODO [미래 변경 대비] - 매칭 알고리즘 Abstraction Layer
        # ------------------------------------------------------------------------
        # 본 함수는 매칭 점수 계산의 핵심 로직입니다. 다음 변경 시 수정 필요:
        #
        # 1. MBTI/소시오닉스가 수치(Numeric)로 변경되는 경우:
        #    - _convert_json_to_user_vector() 함수 내 타입 변환 로직 수정
        #    - matcher.py의 HybridMatcher 입력 형식 변경 대응
        #
        # 2. 매칭 알고리즘(matcher.py) 자체가 교체되는 경우:
        #    - HybridMatcher 호출부를 Adapter 패턴으로 추상화 권장
        #    - 예: matching_adapter.py 생성 후 calc_score(user_a, user_b, weights) 인터페이스로 통일
        #
        # 3. 가중치 체계가 변경되는 경우 (예: 4요소로 확장):
        #    - weights dict 구조 및 기본값 수정
        #    - 프론트엔드(dashboard.html) 슬라이더 UI도 동시 수정 필요
        # ========================================================================
        
        # 밑은 가중치 설정 부분
        """
        if weights is None:
            weights = {'similarity': 0.5, 'chemistry': 0.4, 'activity': 0.1}

        try:
            # 현재 사용자 프로필 로드
            target_user = None
            if current_user_profile_json:
                target_user = cls._convert_json_to_user_vector(current_user_profile_json, my_user_id)
            
            # Fallback: 파일 로드 (Legacy, 필요시 제거 가능)
            if not target_user:
                base_dir = os.path.dirname(__file__)
                profile_file = os.path.join(base_dir, 'profile', 'profile.json')
                if os.path.exists(profile_file):
                    target_user = matcher.load_profile(profile_file)
            
            if not target_user:
                return candidates # 점수 계산 불가 시 그대로 반환
            
            # Candidates 변환
            candidate_users = []
            valid_candidates_map = {} # user_id -> index

            for i, candidate in enumerate(candidates):
                candidate_json = candidate.get('full_report_json', {})
                user_vector = cls._convert_json_to_user_vector(candidate_json, candidate.get('user_id'))
                if user_vector:
                    candidate_users.append(user_vector)
                    valid_candidates_map[candidate.get('user_id')] = i
            
            if not candidate_users:
                return candidates
            
            # HybridMatcher 실행
            hybrid_matcher = matcher.HybridMatcher(candidate_users + [target_user])
            hybrid_matcher.normalize_user(target_user)
            
            for candidate_user in candidate_users:
                hybrid_matcher.normalize_user(candidate_user)
                scores = hybrid_matcher.calculate_match_score(target_user, candidate_user)
                
                new_total = (
                    scores['similarity_score'] * weights['similarity'] +
                    scores['chemistry_score'] * weights['chemistry'] +
                    scores['activity_score'] * weights['activity']
                )
                
                # 결과 업데이트
                idx = valid_candidates_map.get(candidate_user.user_id)
                if idx is not None:
                    candidates[idx]['match_score'] = int(max(0, min(100, new_total * 100)))
                    candidates[idx]['match_details'] = scores
                    
                    # 상대적 성향 분석 (Relative Traits)
                    trait_names_kr = ["개방성", "성실성", "외향성", "우호성", "신경성"]
                    distinctive = []
                    if candidate_user.big5_z_score is not None:
                        for z_idx, z_val in enumerate(candidate_user.big5_z_score):
                            if z_val >= 0.8:
                                distinctive.append({"name": trait_names_kr[z_idx], "level": "High", "label": "높음", "color": "blue"})
                            elif z_val <= -0.8:
                                distinctive.append({"name": trait_names_kr[z_idx], "level": "Low", "label": "낮음", "color": "gray"})
                    candidates[idx]['relative_traits'] = distinctive[:3]

            return candidates

        except Exception as e:
            logger.exception("Error calculating match scores")
            return candidates
    
    @classmethod
    def _convert_json_to_user_vector(cls, json_data, user_id):
        """
        JSON 데이터를 UserVector 객체로 변환 (기존 유지)
        """
        try:
            meta = json_data.get('meta', {})
            llm_profile = json_data.get('llm_profile', {})
            
            mbti_data = llm_profile.get('mbti', {})
            big5_data = llm_profile.get('big5', {})
            socionics_data = llm_profile.get('socionics', {})
            
            scores = big5_data.get('scores_0_100', {})
            big5_raw = np.array([
                scores.get('openness', 50),
                scores.get('conscientiousness', 50),
                scores.get('extraversion', 50),
                scores.get('agreeableness', 50),
                scores.get('neuroticism', 50)
            ], dtype=float)
            
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
            logger.exception("Error converting JSON to UserVector")
            return None

    @classmethod
    def send_match_request(cls, sender_id, receiver_id):
        """
        [신청] 매칭 신청 (DB Transaction)
        """
        from extensions import db, MatchRequest
        from sqlalchemy import or_

        # 자기 자신에게 신청 방지
        if int(sender_id) == int(receiver_id):
            return {"success": False, "message": "자기 자신에게는 매칭 신청을 할 수 없습니다."}

        try:
            # 중복 체크
            existing = MatchRequest.query.filter(
                or_(
                    (MatchRequest.sender_id == sender_id) & (MatchRequest.receiver_id == receiver_id),
                    (MatchRequest.sender_id == receiver_id) & (MatchRequest.receiver_id == sender_id)
                )
            ).first()

            if existing:
                if existing.status in ['PENDING', 'ACCEPTED', 'CANCEL_REQ_SENDER', 'CANCEL_REQ_RECEIVER']:
                    return {"success": False, "message": "이미 진행 중인 매칭 건이 존재합니다."}
                
                # 종료된 상태면 삭제 후 재신청
                db.session.delete(existing)
                db.session.commit() # 삭제 반영

            # 신청 생성
            new_req = MatchRequest(
                sender_id=sender_id, 
                receiver_id=receiver_id, 
                status='PENDING'
            )
            db.session.add(new_req)
            db.session.commit()
            
            return {"success": True, "message": "성공적으로 신청을 보냈습니다."}

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": str(e)}

    @classmethod
    def respond_to_request(cls, request_id, action):
        """
        [응답] ACCEPT / REJECT
        """
        from extensions import db, MatchRequest, Notification, User

        if action not in ['ACCEPTED', 'REJECTED']:
            return {"success": False, "message": "잘못된 응답 액션입니다."}

        try:
            req = MatchRequest.query.get(request_id)
            if not req:
                return {"success": False, "message": "요청 건을 찾을 수 없습니다."}

            req.status = action
            
            # 알림 생성
            receiver = User.query.get(req.receiver_id)
            res_msg = "수락" if action == 'ACCEPTED' else "거절"
            msg = f"{receiver.username}님이 매칭 신청을 {res_msg}하셨습니다."
            
            noti = Notification(user_id=req.sender_id, message=msg)
            db.session.add(noti)
            
            db.session.commit()
            return {"success": True, "message": f"매칭 {res_msg} 처리가 완료되었습니다."}

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": str(e)}

    @classmethod
    def get_unread_notifications(cls, user_id):
        """[알림] 읽지 않은 알림 목록"""
        from extensions import Notification
        try:
            return Notification.query.filter_by(user_id=user_id, is_read=False)\
                .order_by(Notification.created_at.desc()).all()
        except Exception as e:
            logger.exception("Error fetching notifications")
            return []

    @classmethod
    def mark_notifications_as_read(cls, user_id):
        """[알림] 일괄 읽음 처리"""
        from extensions import db, Notification
        try:
            Notification.query.filter_by(user_id=user_id, is_read=False)\
                .update({Notification.is_read: True})
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

    @classmethod
    def delete_match_by_admin(cls, request_id):
        """[관리자] 매칭 요청 삭제"""
        from extensions import db, MatchRequest
        try:
            req = MatchRequest.query.get(request_id)
            if not req:
                return {"success": False, "message": "존재하지 않는 매칭 ID입니다."}
            
            db.session.delete(req)
            db.session.commit()
            return {"success": True, "message": f"매칭(ID: {request_id})이 삭제되었습니다."}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": str(e)}