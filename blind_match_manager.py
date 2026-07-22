# blind_match_manager.py
# -*- coding: utf-8 -*-

"""
[EchoMind] 블라인드 매칭 및 매칭 큐 비즈니스 로직 관리
======================================================================

[시스템 개요]
본 모듈은 EchoMind 서비스의 '블라인드 매칭' 기능을 전담하는 서비스 레이어입니다.
사용자가 '매칭 큐'에 참여하면, 시스템이 대기 중인 다른 사용자와 자동으로 1:1 익명 매칭을 생성해줍니다.
이 과정에서 상대방의 정보는 일체 제공되지 않으며, 오직 순수한 '만남'의 경험에 집중합니다.

본 모듈은 Flask 애플리케이션 컨텍스트와 SQLAlchemy ORM을 활용하여,
블라인드 매칭의 전체 라이프사이클(후보 탐색, 요청, 수락, 익명 대화, 프로필 공개, 종료)을
안전하고 정합성 있게 관리합니다.
"""

import os
import json
import logging
import numpy as np
from datetime import datetime, timedelta

from config import config_by_name
from extensions import (
    db, User, PersonalityResult, BlindMatch, BlindMatchMessage,
    Notification, MatchRequest, BlindMatchStatus, BlindMatchAnalytics,
    BlindMatchQueue, BlindQueueStatus
)
from match_manager import MatchManager
from sqlalchemy import or_, and_

# --- 로거 설정 ---
logger = logging.getLogger(__name__)

# --- 환경 설정 ---
env = os.getenv('FLASK_ENV', 'development')
cfg = config_by_name[env]


class BlindMatchConfig:
    """블라인드 매칭 기능의 모든 설정을 관리하는 클래스"""
    # 시간 관련 설정 (단위: 시간)
    REQUEST_EXPIRATION_HOURS = 72  # 매칭 요청 유효 시간 (3일)
    INACTIVITY_TIMEOUT_HOURS = 168  # 비활성 매칭 자동 종료 시간 (7일)

    # 제한 관련 설정
    MAX_ACTIVE_BLIND_MATCHES_PER_USER = 3  # 사용자당 동시에 진행할 수 있는 최대 블라인드 매칭 수
    MAX_DAILY_REQUESTS_PER_USER = 5  # 하루에 보낼 수 있는 최대 블라인드 매칭 요청 수

    # 매칭 알고리즘 가중치
    CANDIDATE_SCORE_WEIGHTS = {
        'similarity': 0.5,
        'chemistry': 0.4,
        'activity': 0.1
    }

    # 알림 메시지 템플릿
    NOTIFICATION_TEMPLATES = {
        'new_request': "새로운 블라인드 매칭 요청이 도착했어요.",
        'request_accepted': "상대방이 블라인드 매칭을 수락했어요. 지금 바로 대화를 시작해보세요.",
        'request_rejected': "상대방이 블라인드 매칭 요청을 거절했어요.",
        'reveal_request': "상대방이 당신을 더 알고 싶어해요!  프로필 공개 요청을 확인해보세요.",
        'match_revealed': "서로의 프로필이 공개되었습니다. 이제부터는 일반 채팅으로 대화를 이어가세요.",
        'match_ended': "블라인드 매칭이 종료되었습니다. 이번 경험이 좋은 기억으로 남았기를 바랍니다."
    }

    # 기능 플래그
    ENABLE_AUTO_SUGGESTIONS = True  # 매일 자동으로 블라인드 매칭을 추천하는 기능 활성화 여부


class BlindMatchManager:
    """
    블라인드 매칭 관련 비즈니스 로직을 전담하는 클래스.
    모든 메서드는 클래스 메서드로 구현되어 상태 없이 호출 가능합니다.
    """

    @classmethod
    def get_blind_match_candidates(cls, user_id, mode='balanced', limit=5):
        """
        [후보 탐색 - 레거시] 지정된 사용자를 위한 블라인드 매칭 후보를 추천합니다.
        **참고: 이 메서드는 새로운 큐 기반 매칭 시스템에서는 직접 사용되지 않습니다.**

        [후보 탐색] 지정된 사용자를 위한 블라인드 매칭 후보를 추천합니다.

        다양한 매칭 전략(mode)을 지원하여 사용자에게 다채로운 추천 경험을 제공합니다.
        - 'similar': 유사성이 높은 사용자 (편안한 대화 상대)
        - 'complementary': 보완성이 높은 사용자 (새로운 관점의 상대)
        - 'balanced': 유사성과 보완성을 균형 있게 고려한 상대 (기본값)

        Args:
            user_id (int): 추천을 받을 사용자의 ID
            mode (str): 매칭 전략 ('similar', 'complementary', 'balanced')
            limit (int): 추천할 후보의 최대 수

        Returns:
            list: 추천된 후보자 정보가 담긴 딕셔너리 리스트.
                  점수 계산이 불가능하거나 후보가 없는 경우 빈 리스트를 반환합니다.
        """
        logger.info(f"블라인드 매칭 후보 탐색 시작 - User ID: {user_id}, Mode: {mode}, Limit: {limit}")

        try:
            # 1. 현재 사용자 프로필 로드
            my_profile = PersonalityResult.query.filter_by(user_id=user_id, is_representative=True).first()
            if not my_profile:
                logger.warning(f"User ID {user_id}의 대표 프로필이 없어 후보 탐색을 중단합니다.")
                return []

            # 2. 제외할 사용자 ID 목록 필터링
            excluded_user_ids = cls._get_excluded_user_ids(user_id)

            # 3. 잠재적 후보군 전체 조회 (DB 최적화)
            potential_candidates_query = db.session.query(PersonalityResult, User)\
                .join(User, PersonalityResult.user_id == User.user_id)\
                .filter(
                    PersonalityResult.is_representative == True,
                    User.user_id != user_id,
                    ~User.user_id.in_(excluded_user_ids),
                    User.is_banned == False
                )

            all_candidates_from_db = potential_candidates_query.all()
            
            candidates = []
            for p_result, user in all_candidates_from_db:
                full_report = p_result.full_report_json
                if isinstance(full_report, str): data = json.loads(full_report)
                else: data = full_report
                
                if not data: continue
                
                candidate = {
                    'user_id': user.user_id,
                    'full_report_json': data,
                    'birth_date': user.birth_date,
                    'created_at': user.created_at
                }
                candidates.append(candidate)

            if not candidates:
                logger.info(f"User ID {user_id}에 대한 유효한 후보가 없습니다.")
                return []

            # 4. 매칭 점수 계산 (기존 MatchManager 로직 재활용)
            weights = cls._get_weights_for_mode(mode)
            
            scored_candidates = MatchManager._calculate_match_scores(
                my_user_id=user_id,
                candidates=candidates,
                current_user_profile_json=my_profile.full_report_json,
                weights=weights
            )

            # 5. 최종 정렬 및 필터링
            sorted_candidates = sorted(
                scored_candidates, 
                key=lambda x: (-x.get('match_score', 0), x.get('created_at', datetime.utcnow()))
            )

            # 최종 후보에서 민감 정보 제거
            final_candidates = []
            for cand in sorted_candidates[:limit]:
                final_candidates.append({
                    'user_id': cand['user_id'],
                    'match_score': cand.get('match_score', 0),
                    'match_details': cand.get('match_details', {}),
                    'relative_traits': cand.get('relative_traits', [])
                })

            logger.info(f"블라인드 매칭 후보 {len(final_candidates)}명 탐색 완료 for User ID: {user_id}")
            return final_candidates

        except Exception as e:
            logger.exception(f"블라인드 매칭 후보 탐색 중 예외 발생 - User ID: {user_id}")
            return []

    @classmethod
    def _get_weights_for_mode(cls, mode):
        """매칭 모드에 따른 가중치를 반환합니다."""
        if mode == 'similar':
            return {'similarity': 0.8, 'chemistry': 0.1, 'activity': 0.1}
        elif mode == 'complementary':
            return {'similarity': 0.1, 'chemistry': 0.8, 'activity': 0.1}
        else:  # balanced
            return BlindMatchConfig.CANDIDATE_SCORE_WEIGHTS

    @classmethod
    def _get_excluded_user_ids(cls, user_id):
        """
        [Helper] 매칭 후보에서 제외되어야 할 사용자 ID 목록을 반환합니다.
        """
        excluded_ids = {user_id}

        # 1. 블라인드 매칭 관련 제외
        blind_matches = BlindMatch.query.filter(
            or_(BlindMatch.user1_id == user_id, BlindMatch.user2_id == user_id),
            # PENDING, ACTIVE, REVEAL_REQUESTED, REVEALED 상태는 모두 재매칭에서 제외합니다.
            # REVEALED는 영구 제외 대상입니다.
            BlindMatch.status.in_([
                BlindMatchStatus.PENDING,
                BlindMatchStatus.ACTIVE,
                BlindMatchStatus.REVEAL_REQUESTED_BY_1,
                BlindMatchStatus.REVEAL_REQUESTED_BY_2,
                BlindMatchStatus.REVEALED
            ])
        ).all()

        for match in blind_matches:
            excluded_ids.add(match.user1_id)
            excluded_ids.add(match.user2_id)

        # 2. 일반 매칭 관련 제외
        general_matches = MatchRequest.query.filter(
            or_(MatchRequest.sender_id == user_id, MatchRequest.receiver_id == user_id),
            MatchRequest.status.in_(['PENDING', 'ACCEPTED', 'CANCEL_REQ_SENDER', 'CANCEL_REQ_RECEIVER'])
        ).all()

        for req in general_matches:
            excluded_ids.add(req.sender_id)
            excluded_ids.add(req.receiver_id)

        logger.debug(f"Excluded user IDs for user {user_id}: {excluded_ids}")
        return excluded_ids

    @classmethod
    def create_blind_match_request(cls, sender_id, receiver_id):
        """
        [매칭 시작] 블라인드 매칭 요청을 생성합니다.
        """
        logger.info(f"블라인드 매칭 요청 생성 시도: Sender={sender_id}, Receiver={receiver_id}")

        if int(sender_id) == int(receiver_id):
            return {"success": False, "message": "자기 자신에게는 블라인드 매칭을 신청할 수 없습니다."}

        # 제약 조건 검사
        if not cls._check_request_constraints(sender_id, receiver_id):
            return {"success": False, "message": "매칭을 신청할 수 없는 상태입니다. (일일 요청 수 초과, 중복 요청 등)"}

        try:
            # 새로운 블라인드 매칭 레코드 생성
            new_blind_match = BlindMatch(
                user1_id=sender_id,
                user2_id=receiver_id,
                status=BlindMatchStatus.PENDING,
                status_by_user_id=sender_id
            )
            db.session.add(new_blind_match)
            db.session.flush() # ID 확보
            
            # 수신자에게 알림 생성
            notification = Notification(
                user_id=receiver_id,
                message=BlindMatchConfig.NOTIFICATION_TEMPLATES['new_request'],
                related_entity_type='blind_match',
                related_entity_id=new_blind_match.id
            )
            db.session.add(notification)

            db.session.commit()
            logger.info(f"블라인드 매칭 요청(ID: {new_blind_match.id}) 생성 성공.")
            return {"success": True, "message": "블라인드 매칭 요청을 성공적으로 보냈습니다."}

        except Exception as e:
            db.session.rollback()
            logger.exception("블라인드 매칭 요청 생성 중 DB 오류 발생")
            return {"success": False, "message": "서버 오류로 인해 요청을 보내지 못했습니다."}

    @classmethod
    def _check_request_constraints(cls, sender_id, receiver_id):
        """[Helper] 매칭 요청 시 제약 조건을 검사합니다."""
        # 1. 동시 진행 가능한 매칭 수 초과 여부
        active_count = BlindMatch.query.filter(
            or_(BlindMatch.user1_id == sender_id, BlindMatch.user2_id == sender_id),
            BlindMatch.status == BlindMatchStatus.ACTIVE
        ).count()
        if active_count >= BlindMatchConfig.MAX_ACTIVE_BLIND_MATCHES_PER_USER:
            logger.warning(f"User {sender_id}의 활성 블라인드 매칭 수가 최대치({active_count})에 도달했습니다.")
            return False

        # 2. 일일 요청 수 초과 여부
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_sent_count = BlindMatch.query.filter(
            BlindMatch.user1_id == sender_id,
            BlindMatch.created_at >= today_start
        ).count()
        if daily_sent_count >= BlindMatchConfig.MAX_DAILY_REQUESTS_PER_USER:
            logger.warning(f"User {sender_id}의 일일 요청 수가 최대치({daily_sent_count})에 도달했습니다.")
            return False

        # 3. 동일 상대에게 진행 중인(PENDING) 요청 존재 여부
        existing_pending = BlindMatch.query.filter(
            or_(
                (BlindMatch.user1_id == sender_id) & (BlindMatch.user2_id == receiver_id),
                (BlindMatch.user1_id == receiver_id) & (BlindMatch.user2_id == sender_id)
            ),
            BlindMatch.status == BlindMatchStatus.PENDING
        ).first()
        if existing_pending:
            logger.warning(f"User {sender_id}와 {receiver_id} 사이에 이미 PENDING 상태의 요청이 존재합니다.")
            return False

        return True

    @classmethod
    def respond_to_blind_match_request(cls, request_id, responding_user_id, action):
        """
        [매칭 응답] 블라인드 매칭 요청에 대해 수락 또는 거절합니다.
        """
        logger.info(f"블라인드 매칭 응답 처리: RequestID={request_id}, User={responding_user_id}, Action={action}")

        if action not in ['accept', 'reject']:
            return {"success": False, "message": "잘못된 요청입니다."}

        try:
            match = BlindMatch.query.get(request_id)

            # 유효성 검사
            if not match:
                return {"success": False, "message": "존재하지 않는 요청입니다."}
            if match.status != BlindMatchStatus.PENDING:
                return {"success": False, "message": "이미 처리된 요청입니다."}
            if match.user2_id != responding_user_id:
                return {"success": False, "message": "요청에 응답할 권한이 없습니다."}

            sender_id = match.user1_id
            
            if action == 'accept':
                match.status = BlindMatchStatus.ACTIVE
                match.status_by_user_id = responding_user_id
                match.activated_at = datetime.utcnow()
                noti_msg = BlindMatchConfig.NOTIFICATION_TEMPLATES['request_accepted']
                response_msg = "매칭을 수락했습니다. 즐거운 대화를 나눠보세요!"
            else: # reject
                match.status = BlindMatchStatus.REJECTED
                match.status_by_user_id = responding_user_id
                noti_msg = BlindMatchConfig.NOTIFICATION_TEMPLATES['request_rejected']
                response_msg = "매칭 요청을 거절했습니다."

            # 알림 생성
            notification = Notification(
                user_id=sender_id,
                message=noti_msg,
                related_entity_type='blind_match',
                related_entity_id=match.id
            )
            db.session.add(notification)
            db.session.commit()

            logger.info(f"블라인드 매칭(ID: {request_id}) 상태 변경 -> {match.status.value}")
            return {"success": True, "message": response_msg}

        except Exception as e:
            db.session.rollback()
            logger.exception(f"블라인드 매칭 응답 처리 중 DB 오류 발생 (Request ID: {request_id})")
            return {"success": False, "message": "서버 오류로 인해 처리하지 못했습니다."}

    @classmethod
    def get_user_blind_matches(cls, user_id):
        """
        [목록 조회] 특정 사용자의 모든 블라인드 매칭 목록을 상태별로 분류하여 반환합니다.
        (최적화: 마지막 메시지, 안 읽은 메시지 수 포함)
        """
        logger.debug(f"User {user_id}의 블라인드 매칭 목록 조회")

        try:
            # 1. 사용자와 관련된 모든 매칭 조회
            matches_with_partner = db.session.query(
                BlindMatch,
                User.nickname.label('partner_nickname')
            ).outerjoin(
                User,
                or_(
                    (BlindMatch.user1_id == user_id) & (BlindMatch.user2_id == User.user_id),
                    (BlindMatch.user2_id == user_id) & (BlindMatch.user1_id == User.user_id)
                )
            ).filter(
                or_(BlindMatch.user1_id == user_id, BlindMatch.user2_id == user_id)
            ).order_by(BlindMatch.updated_at.desc()).all()

            if not matches_with_partner:
                return {"success": True, "data": {'active': [], 'completed': []}}

            match_ids = [match.id for match, _ in matches_with_partner]

            # 2. 마지막 메시지 일괄 조회 (최적화)
            last_message_subquery = db.session.query(
                BlindMatchMessage.match_id,
                db.func.max(BlindMatchMessage.created_at).label('max_created_at')
            ).filter(BlindMatchMessage.match_id.in_(match_ids)).group_by(BlindMatchMessage.match_id).subquery()

            last_messages_q = db.session.query(
                BlindMatchMessage.match_id,
                BlindMatchMessage.content
            ).join(
                last_message_subquery,
                (BlindMatchMessage.match_id == last_message_subquery.c.match_id) &
                (BlindMatchMessage.created_at == last_message_subquery.c.max_created_at)
            ).all()
            last_messages_map = {match_id: content for match_id, content in last_messages_q}

            # 3. 안 읽은 메시지 수 일괄 조회 (최적화)
            unread_counts_q = db.session.query(
                BlindMatchMessage.match_id,
                db.func.count(BlindMatchMessage.id)
            ).filter(
                BlindMatchMessage.match_id.in_(match_ids),
                BlindMatchMessage.sender_id != user_id,
                BlindMatchMessage.is_read == False
            ).group_by(BlindMatchMessage.match_id).all()
            unread_counts_map = {match_id: count for match_id, count in unread_counts_q}

            # 4. 결과 데이터 구조화
            result = {
                'active': [],
                'completed': []
            }

            for match, partner_nickname in matches_with_partner:
                partner_id = match.user1_id if match.user2_id == user_id else match.user2_id

                match_data = {
                    'match_id': match.id,
                    'match_code': match.match_code,
                    'partner_id': partner_id,
                    'partner_nickname': partner_nickname if match.status == BlindMatchStatus.REVEALED else "블라인드 사용자",
                    'status': match.status.value,
                    'updated_at': match.updated_at.isoformat(),
                    'last_message': last_messages_map.get(match.id, "대화를 시작해보세요."),
                    'unread_count': unread_counts_map.get(match.id, 0)
                }

                if match.status in [BlindMatchStatus.ACTIVE, BlindMatchStatus.REVEAL_REQUESTED_BY_1, BlindMatchStatus.REVEAL_REQUESTED_BY_2]:
                    result['active'].append(match_data)
                else:
                    result['completed'].append(match_data)
            
            return {"success": True, "data": result}
        except Exception as e:
            logger.exception(f"User {user_id}의 블라인드 매칭 목록 조회 중 오류 발생")
            return {"success": False, "message": "데이터를 불러오는 데 실패했습니다."}

    @classmethod
    def send_profile_and_create_match_request(cls, match_id, sender_id):
        """
        [프로필 전송] 블라인드 매칭에서 한 사용자가 자신의 프로필을 보내 일반 매칭을 신청합니다.
        """
        logger.info(f"프로필 전송 및 일반 매칭 전환 시도: MatchID={match_id}, SenderID={sender_id}")

        try:
            match = BlindMatch.query.get(match_id)

            if not match or sender_id not in [match.user1_id, match.user2_id]:
                return {"success": False, "message": "잘못된 접근입니다."}

            # ACTIVE 상태에서만 프로필 전송 가능
            if match.status != BlindMatchStatus.ACTIVE:
                return {"success": False, "message": "활성 상태의 매칭에서만 프로필을 보낼 수 있습니다."}

            receiver_id = match.user1_id if match.user2_id == sender_id else match.user2_id
            is_user1 = (sender_id == match.user1_id)

            # 1. 일반 매칭 요청 생성 (MatchManager 재사용)
            match_request_result = MatchManager.send_match_request(sender_id, receiver_id)
            
            if not match_request_result.get('success'):
                # 이미 진행 중인 매칭이 있다는 메시지 등을 그대로 반환
                return match_request_result

            # 2. 블라인드 매칭 상태 변경
            # REVEAL_REQUESTED_BY_1/2 상태를 "프로필 전송됨" 상태로 재사용합니다.
            # 이 상태가 되면 블라인드 채팅방에서는 더 이상 상호작용이 불가하고 인박스로 유도됩니다.
            new_status = BlindMatchStatus.REVEAL_REQUESTED_BY_1 if is_user1 else BlindMatchStatus.REVEAL_REQUESTED_BY_2
            match.status = new_status
            match.status_by_user_id = sender_id

            # 3. 상대방에게 알림 생성
            # send_match_request에서 기본 알림은 생성되지만, 블라인드 매칭에서 왔다는 것을 명시하기 위해 추가 알림을 보냅니다.
            sender_user = User.query.get(sender_id)
            notification = Notification(
                user_id=receiver_id,
                message=f"'{sender_user.nickname}'님이 블라인드 매칭에서 프로필을 보냈습니다. 인박스를 확인해주세요.",
                related_entity_type='match_request',
                related_entity_id=match_request_result.get('request_id')
            )
            db.session.add(notification)

            db.session.commit()
            logger.info(f"블라인드 매칭(ID: {match_id})에서 일반 매칭 요청(ID: {match_request_result.get('request_id')})으로 전환 성공.")

            return {"success": True, "message": "프로필을 성공적으로 보냈습니다. 상대방의 응답을 기다려주세요."}

        except Exception as e:
            db.session.rollback()
            logger.exception(f"프로필 전송 처리 중 DB 오류 발생 (Match ID: {match_id})")
            return {"success": False, "message": "서버 오류로 인해 처리하지 못했습니다."}

    @classmethod
    def end_blind_match(cls, match_id, user_id):
        """
        [매칭 종료] 사용자가 직접 블라인드 매칭을 종료합니다.
        """
        logger.info(f"블라인드 매칭 종료 시도: MatchID={match_id}, UserID={user_id}")

        try:
            match = BlindMatch.query.get(match_id)

            if not match or user_id not in [match.user1_id, match.user2_id]:
                return {"success": False, "message": "잘못된 접근입니다."}

            if match.status not in [BlindMatchStatus.ACTIVE, BlindMatchStatus.REVEAL_REQUESTED_BY_1, BlindMatchStatus.REVEAL_REQUESTED_BY_2]:
                return {"success": False, "message": "종료할 수 있는 상태의 매칭이 아닙니다."}

            match.status = BlindMatchStatus.ENDED_BY_USER
            match.status_by_user_id = user_id

            partner_id = match.user1_id if match.user2_id == user_id else match.user2_id
            notification = Notification(
                user_id=partner_id,
                message=BlindMatchConfig.NOTIFICATION_TEMPLATES['match_ended'],
                related_entity_type='blind_match',
                related_entity_id=match.id
            )
            db.session.add(notification)

            db.session.commit()

            cls.analyze_completed_match(match.id)

            logger.info(f"블라인드 매칭(ID: {match_id})이 사용자 {user_id}에 의해 종료됨.")
            return {"success": True, "message": "블라인드 매칭이 종료되었습니다."}

        except Exception as e:
            db.session.rollback()
            logger.exception(f"블라인드 매칭 종료 처리 중 DB 오류 발생 (Match ID: {match_id})")
            return {"success": False, "message": "서버 오류로 인해 처리하지 못했습니다."}

    @classmethod
    def get_unread_blind_count(cls, user_id):
        """
        [Helper] 사용자의 읽지 않은 블라인드 매칭 관련 알림 수를 집계합니다.
        (받은 요청 + 활성 대화의 안 읽은 메시지)
        """
        try:
            # 1. 받은 요청 수 (내가 user2_id이고 상태가 PENDING)
            pending_received_count = db.session.query(BlindMatch.id).filter(
                BlindMatch.user2_id == user_id,
                BlindMatch.status == BlindMatchStatus.PENDING
            ).count()

            # 2. 활성 대화의 안 읽은 메시지 총합
            # 먼저 내가 참여중인 활성 대화 ID 목록을 가져옴
            active_match_ids_q = db.session.query(BlindMatch.id).filter(
                or_(BlindMatch.user1_id == user_id, BlindMatch.user2_id == user_id),
                BlindMatch.status.in_([
                    BlindMatchStatus.ACTIVE, 
                    BlindMatchStatus.REVEAL_REQUESTED_BY_1, 
                    BlindMatchStatus.REVEAL_REQUESTED_BY_2
                ])
            )
            
            active_match_ids = [m[0] for m in active_match_ids_q.all()]
            
            unread_message_count = 0
            if active_match_ids:
                # 해당 대화들에서 내가 받기만 한(sender가 내가 아닌) 안 읽은 메시지 수
                unread_message_count = db.session.query(BlindMatchMessage.id).filter(
                    BlindMatchMessage.match_id.in_(active_match_ids),
                    BlindMatchMessage.sender_id != user_id,
                    BlindMatchMessage.is_read == False
                ).count()

            return pending_received_count + unread_message_count
        except Exception as e:
            logger.exception(f"사용자 {user_id}의 안 읽은 블라인드 매칭 카운트 조회 중 오류 발생")
            return 0

    # --- 블라인드 매칭 큐 (신규 기능) ---

    @classmethod
    def enter_blind_match_queue(cls, user_id):
        """
        [매칭 큐] 사용자를 블라인드 매칭 대기열에 추가하고 매칭을 시도합니다.
        app.py의 /api/blind-match/queue/enter 엔드포인트에서 호출됩니다.
        """
        logger.info(f"User {user_id}가 블라인드 매칭 큐에 참여 시도.")
        try:
            # 이미 활성/대기중인 블라인드 매치가 있는지 확인
            existing_match = BlindMatch.query.filter(
                or_(BlindMatch.user1_id == user_id, BlindMatch.user2_id == user_id),
                BlindMatch.status.in_([BlindMatchStatus.ACTIVE, BlindMatchStatus.PENDING])
            ).first()
            if existing_match:
                return {"success": False, "message": "이미 진행 중이거나 대기 중인 블라인드 매칭이 있습니다."}

            # 이미 큐에 있는지 확인
            in_queue = BlindMatchQueue.query.filter_by(user_id=user_id).first()
            if in_queue:
                if in_queue.status == BlindQueueStatus.WAITING:
                    logger.info(f"User {user_id}는 이미 큐에서 대기 중입니다.")
                    return {"success": True, "message": "이미 대기열에 참여 중입니다."}
                elif in_queue.status == BlindQueueStatus.MATCHED:
                    return {"success": False, "message": "이미 매칭이 완료되었습니다. 대화방을 확인해주세요."}
            
            # 큐에 추가
            new_entry = BlindMatchQueue(user_id=user_id, status=BlindQueueStatus.WAITING)
            db.session.add(new_entry)
            db.session.commit()

            # 매칭 시도
            cls._process_match_queue(user_id)

            return {"success": True, "message": "매칭 대기열에 참여했습니다."}

        except Exception as e:
            db.session.rollback()
            logger.exception(f"User {user_id}의 매칭 큐 참여 처리 중 오류 발생")
            return {"success": False, "message": "서버 오류로 대기열에 참여하지 못했습니다."}

    @classmethod
    def leave_blind_match_queue(cls, user_id):
        """
        [매칭 큐] 사용자를 대기열에서 제거합니다.
        app.py의 /api/blind-match/queue/leave 엔드포인트에서 호출됩니다.
        """
        logger.info(f"User {user_id}가 블라인드 매칭 큐에서 나가기 시도.")
        try:
            entry = BlindMatchQueue.query.filter_by(user_id=user_id, status=BlindQueueStatus.WAITING).first()
            if entry:
                db.session.delete(entry)
                db.session.commit()
                return {"success": True, "message": "매칭 대기열에서 나왔습니다."}
            return {"success": False, "message": "대기열에 참여 중인 상태가 아닙니다."}
        except Exception as e:
            db.session.rollback()
            logger.exception(f"User {user_id}의 매칭 큐 나가기 처리 중 오류 발생")
            return {"success": False, "message": "서버 오류로 처리하지 못했습니다."}

    @classmethod
    def get_queue_status(cls, user_id):
        """
        [매칭 큐] 사용자의 대기열 상태를 확인합니다.
        app.py의 /api/blind-match/queue/status 엔드포인트에서 호출됩니다.
        """
        entry = BlindMatchQueue.query.filter_by(user_id=user_id).first()

        if not entry:
            return {"status": "IDLE"}

        if entry.status == BlindQueueStatus.MATCHED:
            match = BlindMatch.query.get(entry.blind_match_id)
            if match:
                # 매칭 확인 후 큐에서 제거
                db.session.delete(entry)
                db.session.commit()
                return {"status": "MATCHED", "match_code": match.match_code}
        
        if entry.status == BlindQueueStatus.WAITING:
            elapsed = (datetime.utcnow() - entry.entered_at).total_seconds()
            return {"status": "WAITING", "elapsed_seconds": int(elapsed)}

        return {"status": "IDLE"}

    @classmethod
    def _process_match_queue(cls, new_user_id):
        """
        [Helper] 새 사용자가 큐에 들어왔을 때, 매칭 가능한 다른 사용자가 있는지 확인하고 매칭을 실행합니다.
        """
        # 락을 거는 대신, 한 번에 한 쌍만 처리하여 동시성 문제를 최소화합니다.
        with db.session.begin_nested():
            # 1. 나를 제외한 모든 대기자 조회
            potential_partners = BlindMatchQueue.query.filter(
                BlindMatchQueue.user_id != new_user_id,
                BlindMatchQueue.status == BlindQueueStatus.WAITING
            ).all()

            if not potential_partners:
                logger.info(f"User {new_user_id} 큐 진입, 하지만 다른 대기자가 없음.")
                return

            # 2. 현재 사용자와 이미 관계가 있는 사용자 ID 목록 조회
            excluded_user_ids = cls._get_excluded_user_ids(new_user_id)

            # 3. 유효한 파트너 필터링
            valid_partners = [p for p in potential_partners if p.user_id not in excluded_user_ids]

            if not valid_partners:
                logger.info(f"User {new_user_id} 큐 진입, 대기자는 있으나 모두 제외 대상임.")
                return

            # 4. 최종 파트너 선택 (여기서는 첫 번째 사용자를 선택, 랜덤 선택도 가능)
            partner_entry = valid_partners[0]

            logger.info(f"매칭 성공! User {new_user_id}와 User {partner_entry.user_id}를 매칭합니다.")
            my_entry = BlindMatchQueue.query.filter_by(user_id=new_user_id).one()

            # 새 블라인드 매치 생성 (즉시 ACTIVE)
            new_match = BlindMatch(user1_id=new_user_id, user2_id=partner_entry.user_id, status=BlindMatchStatus.ACTIVE, activated_at=datetime.utcnow())
            db.session.add(new_match)
            db.session.flush()

            # 두 사용자 모두 큐 상태 변경
            my_entry.status = BlindQueueStatus.MATCHED
            my_entry.blind_match_id = new_match.id
            partner_entry.status = BlindQueueStatus.MATCHED
            partner_entry.blind_match_id = new_match.id
        db.session.commit()

    # --- 시스템 자동화 작업 (스케줄러 연동) ---

    @classmethod
    def cleanup_expired_requests(cls, app):
        """
        [시스템 작업] 만료된 `PENDING` 상태의 블라인드 매칭 요청을 `ENDED_BY_TIMEOUT`으로 변경합니다.
        """
        with app.app_context():
            expiration_time = datetime.utcnow() - timedelta(hours=BlindMatchConfig.REQUEST_EXPIRATION_HOURS)
            
            expired_requests = BlindMatch.query.filter(
                BlindMatch.status == BlindMatchStatus.PENDING,
                BlindMatch.created_at < expiration_time
            ).all()

            if not expired_requests:
                logger.info("만료된 블라인드 매칭 요청이 없습니다.")
                return 0

            try:
                for req in expired_requests:
                    req.status = BlindMatchStatus.ENDED_BY_TIMEOUT
                    req.status_by_user_id = 0
                
                db.session.commit()
                logger.info(f"만료된 블라인드 매칭 요청 {len(expired_requests)}건을 정리했습니다.")
                return len(expired_requests)

            except Exception as e:
                db.session.rollback()
                logger.exception("만료된 블라인드 매칭 요청 정리 중 오류 발생")
                return -1

    @classmethod
    def timeout_inactive_matches(cls, app):
        """
        [시스템 작업] 장기간 활동이 없는 `ACTIVE` 상태의 매칭을 `ENDED_BY_TIMEOUT`으로 변경합니다.
        """
        with app.app_context():
            timeout_threshold = datetime.utcnow() - timedelta(hours=BlindMatchConfig.INACTIVITY_TIMEOUT_HOURS)

            last_message_subquery = db.session.query(
                BlindMatchMessage.match_id,
                db.func.max(BlindMatchMessage.created_at).label('last_message_time')
            ).group_by(BlindMatchMessage.match_id).subquery()

            inactive_matches = db.session.query(BlindMatch)\
                .outerjoin(last_message_subquery, BlindMatch.id == last_message_subquery.c.match_id)\
                .filter(
                    BlindMatch.status == BlindMatchStatus.ACTIVE,
                    or_(
                        (last_message_subquery.c.last_message_time == None) & (BlindMatch.activated_at < timeout_threshold),
                        (last_message_subquery.c.last_message_time < timeout_threshold)
                    )
                ).all()

            if not inactive_matches:
                logger.info("비활성으로 타임아웃 처리할 블라인드 매칭이 없습니다.")
                return 0

            try:
                for match in inactive_matches:
                    match.status = BlindMatchStatus.ENDED_BY_TIMEOUT
                    match.status_by_user_id = 0
                
                db.session.commit()
                logger.info(f"비활성 블라인드 매칭 {len(inactive_matches)}건을 타임아웃 처리했습니다.")
                return len(inactive_matches)

            except Exception as e:
                db.session.rollback()
                logger.exception("비활성 블라인드 매칭 타임아웃 처리 중 오류 발생")
                return -1

    # --- 분석 및 리포팅 ---

    @classmethod
    def analyze_completed_match(cls, match_id):
        """
        [분석] 종료된 블라인드 매칭 건에 대한 통계 데이터를 분석하고 저장합니다.
        """
        logger.info(f"블라인드 매칭 분석 시작: MatchID={match_id}")

        try:
            match = BlindMatch.query.get(match_id)
            if not match:
                logger.error(f"분석 대상 블라인드 매칭(ID: {match_id})을 찾을 수 없습니다.")
                return None

            duration = match.updated_at - (match.activated_at or match.created_at)

            messages = BlindMatchMessage.query.filter_by(match_id=match_id).order_by(BlindMatchMessage.created_at).all()
            total_messages = len(messages)
            user1_messages = sum(1 for m in messages if m.sender_id == match.user1_id)
            user2_messages = total_messages - user1_messages

            analytics_data = BlindMatchAnalytics.query.filter_by(match_id=match_id).first()
            if not analytics_data:
                analytics_data = BlindMatchAnalytics(match_id=match_id)
                db.session.add(analytics_data)

            analytics_data.duration_seconds = duration.total_seconds()
            analytics_data.total_messages = total_messages
            analytics_data.user1_message_count = user1_messages
            analytics_data.user2_message_count = user2_messages
            analytics_data.final_status = match.status.value
            analytics_data.ended_by_user_id = match.status_by_user_id if match.status == BlindMatchStatus.ENDED_BY_USER else None
            analytics_data.analysis_completed_at = datetime.utcnow()

            db.session.commit()
            logger.info(f"블라인드 매칭(ID: {match_id}) 분석 완료 및 저장 성공.")
            return analytics_data

        except Exception as e:
            db.session.rollback()
            logger.exception(f"블라인드 매칭 분석 중 오류 발생 (Match ID: {match_id})")
            return None