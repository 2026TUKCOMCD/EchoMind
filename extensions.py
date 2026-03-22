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

# SQLAlchemy 인스턴스 생성 (app 없이)
# app.py에서 db.init_app(app)으로 나중에 연결됩니다
db = SQLAlchemy()

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    target_name = db.Column(db.String(100), nullable=False) # 분석 대상자 이름
    process_status = db.Column(db.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='process_status_enum'), default='PENDING')
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

class PersonalityResult(db.Model):
    __tablename__ = 'personality_results'
    result_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
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
