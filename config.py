# config.py
# -*- coding: utf-8 -*-

"""
[EchoMind] 보안 및 서버 환경 설정 관리
======================================================================

[시스템 개요]
본 모듈은 EchoMind 애플리케이션 전역에서 사용되는 민감 정보 및 구동 환경 변수를 
중앙 집중식으로 관리합니다. .env 파일을 통해 보안을 유지하며 환경(개발/운영)에 
따른 유연한 설정 전환을 지원합니다.

[주요 관리 항목]
1. Security Key: Flask 세션 및 CSRF 보호를 위한 SECRET_KEY 관리
2. Server Runtime: 서버가 바인딩할 Host 주소 및 Port 번호 정의
3. Database Engine: 
   - AWS RDS MySQL 연결 정보를 수집하고 정수형(Port) 변환을 수행합니다.
   - SQLAlchemy의 URI 포맷을 동적으로 생성합니다.
4. Performance Tuning: RDS 연결 해제 방지를 위한 커넥션 풀링(Pool Size, Recycle 등) 최적화
5. Static Policy: 파일 업로드 용량 제한(MAX_CONTENT) 및 허용 확장자 규정

[사용법]
- app.py에서 FLASK_ENV 값에 따라 특정 Config 클래스를 선택하여 로드합니다.
- 예: app.config.from_object(config_by_name['development'])
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    """기본 설정 (Base Configuration)"""
    # .env 파일에서 정보를 로드하여 하드코딩을 방지합니다.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    RUN_HOST = os.environ.get('RUN_HOST', '0.0.0.0')
    RUN_PORT = int(os.environ.get('RUN_PORT', 5000))
    
    # 데이터베이스 설정 (AWS RDS 연동 핵심)
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST')
    DB_NAME = os.environ.get('DB_NAME')
    # 파이썬 데이터 타입 안정성을 위해 int()로 변환 처리합니다.
    DB_PORT = int(os.environ.get('DB_PORT', 3306))

    # Flask-SQLAlchemy용 URI 생성
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 커넥션 풀링 최적화 (RDS 타임아웃 방지 및 트래픽 분산)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 15,
        'max_overflow': 25,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
    }

    # 파일 업로드 및 쿠키 설정
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'txt'}
    JSON_AS_ASCII = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    @staticmethod
    def init_app(app):
        # .env 신뢰를 바탕으로 추가 체크 로직은 제거 상태 유지
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True # 운영 환경 보안 강화

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}