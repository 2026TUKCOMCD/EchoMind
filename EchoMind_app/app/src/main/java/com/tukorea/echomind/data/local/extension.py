# extensions.py
# -*- coding: utf-8 -*-

"""
[EchoMind] Flask 확장 및 데이터베이스 모델
======================================================================
SQLAlchemy 인스턴스 및 모든 ORM 모델을 정의합니다.
이를 통해 순환 참조(circular import) 문제를 방지합니다.
"""

from datetime import datetime
import random
from flask_sqlalchemy import SQLAlchemy
from enum import Enum

# SQLAlchemy 인스턴스 생성 (app 없이)
# app.py에서 db.init_app(app)으로 나중에 연결됩니다
db = SQLAlchemy()

# --- 모델용 Enum ---
class BlindMatchStatus(Enum):
    """블라인드 매칭의 생명주기를 정의하는 Enum 클래스"""
    PENDING = "PENDING"  # 요청이 보내졌으나 상대방이 아직 응답하지 않은 상태
    ACTIVE = "ACTIVE"  # 양측이 수락하여 익명 대화가 진행 중인 상태
    REVEAL_REQUESTED_BY_1 = "REVEAL_REQUESTED_BY_1"  # 사용자 1이 프로필 공개를 요청한 상태
    REVEAL_REQUESTED_BY_2 = "REVEAL_REQUESTED_BY_2"  # 사용자 2가 프로필 공개를 요청한 상태
    REVEALED = "REVEALED"  # 양측이 프로필 공개에 동의하여 일반 매칭으로 전환된 상태
    ENDED_BY_USER = "ENDED_BY_USER"  # 사용자 중 한 명이 대화를 종료한 상태
    ENDED_BY_TIMEOUT = "ENDED_BY_TIMEOUT"  # 비활성 기간이 길어져 시스템이 자동 종료한 상태
    REJECTED = "REJECTED"  # 상대방이 매칭 요청을 거절한 상태
    CANCELLED = "CANCELLED"  # 요청자가 매칭 요청을 취소한 상태

class BlindQueueStatus(Enum):
    """블라인드 매칭 대기열 상태"""
    WAITING = "WAITING"      # 매칭 대기 중
    PROCESSING = "PROCESSING"  # 매칭 처리 중 (락)
    MATCHED = "MATCHED"      # 매칭 성공
    CANCELLED = "CANCELLED"    # 사용자가 취소
    EXPIRED = "EXPIRED"      # 타임아웃


# --- 데이터베이스 모델 (Database Models) ---
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=True)  # 더미 사용자는 이메일 없음
    password_hash = db.Column(db.String(255), nullable=True)  # 더미 사용자는 비밀번호 없음
    username = db.Column(db.String(100), nullable=False) # 실명
    nickname = db.Column(db.String(100)) # 닉네임
    gender = db.Column(db.Enum('MALE', 'FEMALE', 'OTHER', name='gender_enum'))
    birth_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_banned = db.Column(db.Boolean, default=False) # 계정 정지 여부
    is_dummy = db.Column(db.Boolean, default=False)  # 더미 사용자 여부 (시뮬레이션용)

class ChatLog(db.Model):
    __tablename__ = 'chat_logs'
    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    target_name = db.Column(db.String(100), nullable=False) # 분석 대상자 이름
    process_status = db.Column(db.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='process_status_enum'), default='PENDING')
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

class PersonalityResult(db.Model):
    __tablename__ = 'personality_results'
    result_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=True)
    log_id = db.Column(db.Integer, db.ForeignKey('chat_logs.log_id', ondelete='SET NULL'), nullable=True)  # 더미 사용자는 ChatLog 없음
    is_representative = db.Column(db.Boolean, default=True) # 대표 결과 여부
    
    line_count_at_analysis = db.Column(db.Integer, default=0) # 분석 당시 대화 라인 수
    
    # Big5 점수 (0~100)
    openness = db.Column(db.Float, nullable=False)
    conscientiousness = db.Column(db.Float, nullable=False)
    extraversion = db.Column(db.Float, nullable=False)
    agreeableness = db.Column(db.Float, nullable=False)
    neuroticism = db.Column(db.Float, nullable=False)
    big5_confidence = db.Column(db.Float, default=0.0)
    
    # MBTI & Socionics
    mbti_prediction = db.Column(db.String(10))
    mbti_confidence = db.Column(db.Float, default=0.0)
    socionics_prediction = db.Column(db.String(10))
    socionics_confidence = db.Column(db.Float, default=0.0)
    
    summary_text = db.Column(db.Text)
    reasoning_text = db.Column(db.Text)
    full_report_json = db.Column(db.JSON) # 전체 JSON 원본 저장
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def generate_match_code():
    # 1:1 매칭 채팅방 10자리 난수 코드 생성
    return str(random.randint(1000000000, 9999999999))

class MatchRequest(db.Model):
    __tablename__ = 'match_requests'
    request_id = db.Column(db.Integer, primary_key=True)
    match_code = db.Column(db.String(20), unique=True, nullable=False, default=generate_match_code)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(30), default='PENDING')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_entity_type = db.Column(db.String(50), nullable=True) # e.g., 'blind_match'
    related_entity_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('match_requests.request_id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

def generate_room_code():
    # 10자리 난수 생성 (예: 4928103945)
    return str(random.randint(1000000000, 9999999999))

# --- 그룹 채팅 시스템 (Group Chat) ---
class GroupChatRoom(db.Model):
    __tablename__ = 'group_chat_rooms'
    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(20), unique=True, nullable=False, default=generate_room_code)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    max_participants = db.Column(db.Integer, default=10)
    
    # 입장 조건 (JSON 구조로 저장하여 확장성을 확보합니다)
    # 예: {"genders": ["MALE", "FEMALE"], "min_age": 20, "max_age": 29, "mbtis": ["INTJ", "INTP"], "big5": {"openness": {"min": 60, "max": 100}}}
    conditions = db.Column(db.JSON) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GroupChatParticipant(db.Model):
    __tablename__ = 'group_chat_participants'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('group_chat_rooms.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_read_message_id = db.Column(db.Integer, default=0)

class GroupChatMessage(db.Model):
    __tablename__ = 'group_chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('group_chat_rooms.id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GroupChatKickVote(db.Model):
    __tablename__ = 'group_chat_kick_votes'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('group_chat_rooms.id', ondelete='CASCADE'), nullable=False)
    voter_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- 블라인드 매칭 시스템 (Blind Matching) ---
def generate_blind_match_code():
    """블라인드 매칭용 10자리 난수 코드 생성 (접두사 'B' 추가)"""
    return 'B' + str(random.randint(100000000, 999999999))

class BlindMatchQueue(db.Model):
    __tablename__ = 'blind_match_queue'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, unique=True)
    status = db.Column(db.Enum(BlindQueueStatus), nullable=False, default=BlindQueueStatus.WAITING)
    entered_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 매칭이 성사된 경우, 해당 match_id를 기록할 수 있습니다.
    blind_match_id = db.Column(db.Integer, db.ForeignKey('blind_matches.id', ondelete='SET NULL'), nullable=True)


class BlindMatch(db.Model):
    __tablename__ = 'blind_matches'
    id = db.Column(db.Integer, primary_key=True)
    match_code = db.Column(db.String(20), unique=True, nullable=False, default=generate_blind_match_code)
    
    user1_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    
    status = db.Column(db.Enum(BlindMatchStatus), nullable=False, default=BlindMatchStatus.PENDING)
    status_by_user_id = db.Column(db.Integer, nullable=True) # 상태 변경을 유발한 사용자 ID (0은 시스템)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    activated_at = db.Column(db.DateTime, nullable=True) # ACTIVE 상태가 된 시간

    # Foreign key relationships
    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])

    def to_dict(self): # For admin API
        return {
            'id': self.id,
            'match_code': self.match_code,
            'user1_id': self.user1_id,
            'user2_id': self.user2_id,
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class BlindMatchMessage(db.Model):
    __tablename__ = 'blind_match_messages'
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('blind_matches.id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

class UserActivityLog(db.Model):
    __tablename__ = 'user_activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., 'LOGIN_SUCCESS', 'LOGIN_FAIL'
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.JSON)

    user = db.relationship('User', backref=db.backref('activity_logs', lazy=True))

    def __repr__(self):
        return f'<UserActivityLog {self.user_id} - {self.activity_type}>'

class BlindMatchAnalytics(db.Model):
    __tablename__ = 'blind_match_analytics'
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('blind_matches.id', ondelete='CASCADE'), nullable=False, unique=True)
    duration_seconds = db.Column(db.Integer)
    total_messages = db.Column(db.Integer)
    user1_message_count = db.Column(db.Integer)
    user2_message_count = db.Column(db.Integer)
    final_status = db.Column(db.String(50)) # Storing enum value as string
    ended_by_user_id = db.Column(db.Integer, nullable=True)
    analysis_completed_at = db.Column(db.DateTime, default=datetime.utcnow)