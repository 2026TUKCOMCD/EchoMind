# extensions.py
# -*- coding: utf-8 -*-

"""
[EchoMind] Flask 확장 및 데이터베이스 모델
======================================================================
SQLAlchemy 인스턴스 및 모든 ORM 모델을 정의합니다.
이를 통해 순환 참조(circular import) 문제를 방지합니다.
"""

from datetime import datetime
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

class MatchRequest(db.Model):
    __tablename__ = 'match_requests'
    request_id = db.Column(db.Integer, primary_key=True)
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
