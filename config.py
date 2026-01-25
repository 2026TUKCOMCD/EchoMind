# config.py
# -*- coding: utf-8 -*-

"""
[EchoMind] 환경 설정 관리 (Environment Configuration)
======================================================================

[시스템 개요]
이 모듈은 EchoMind 애플리케이션의 실행 환경(개발/운영) 설정을 관리합니다.
.env 파일에서 환경 변수를 로드하여 FLASK_ENV 설정에 따라 동적으로 주입합니다.

[주요 설정 항목]
1. 보안 키(Security Key): Flask 세션 보안을 위한 SECRET_KEY.
2. 서버 런타임(Server Runtime): 서버 실행 호스트 및 포트 설정.
3. 데이터베이스 엔진(Database Engine):
   - AWS RDS MySQL 연결 정보 설정.
   - SQLAlchemy를 위한 URI 생성.
4. 성능 튜닝(Performance Tuning): RDS 연결 풀(Connection Pool) 최적화 설정.
5. 정적 정책(Static Policy): 파일 업로드 최대 크기 제한 등.

[사용법]
- app.py에서 FLASK_ENV 환경변수에 따라 적절한 Config 클래스를 로드합니다.
- 예: app.config.from_object(config_by_name['development'])
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    """기본 설정 (Base Configuration)"""
    # .env 파일에서 로드
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    RUN_HOST = os.environ.get('RUN_HOST', '0.0.0.0')
    RUN_PORT = int(os.environ.get('RUN_PORT', 5000))
    
    # 데이터베이스 설정 (AWS RDS)
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST')
    DB_NAME = os.environ.get('DB_NAME')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))

    # Flask-SQLAlchemy DB 연결 URI
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 연결 풀 튜닝 (RDS 최적화)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 15,
        'max_overflow': 25,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
    }

    # 파일 업로드 설정
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB 제한
    ALLOWED_EXTENSIONS = {'txt', 'json'}
    JSON_AS_ASCII = False

    # 세션 및 쿠키 설정
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    # [REMOVED] ENABLE_DUMMY_SIMULATION 삭제됨 (더미 기능은 이제 DB 기반으로 통합됨)

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}