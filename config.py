import os
from datetime import timedelta
from dotenv import load_dotenv

# 1. 경로 설정 (Path Anchor)
# 실행 위치와 상관없이 프로젝트 루트를 정확히 찾기 위해 사용
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# .env 파일 로드 (명시적 경로 지정)
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    """기본 설정 (Base Configuration)"""
    
    # --- 보안 (Security) ---
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("CRITICAL: SECRET_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    # --- 데이터베이스 (Database) ---
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST')
    DB_NAME = os.environ.get('DB_NAME')
    DB_PORT = os.environ.get('DB_PORT', 3306) # 포트 기본값 추가

    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
        raise ValueError("CRITICAL: 데이터베이스 연결 정보 중 일부가 누락되었습니다.")

    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 커넥션 풀링 최적화 (대용량 트래픽 대비)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,       # 기본 유지 연결 수
        'max_overflow': 20,    # 트래픽 폭주 시 최대 허용 연결 수
        'pool_recycle': 1800,  # 연결 재사용 주기 (초) - MySQL 타임아웃 방지
        'pool_pre_ping': True, # 연결 유효성 자동 체크 (끊긴 연결 재사용 방지)
    }

    # --- 파일 업로드 (File Upload) ---
    # 절대 경로를 사용하여 폴더 생성 오류 방지
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 최대 16MB
    ALLOWED_EXTENSIONS = {'txt'}           # 허용 확장자 명시

    # --- 응답 설정 (Response) ---
    # JSON 응답 시 한글 깨짐 방지 (매우 중요)
    JSON_AS_ASCII = False 

    # --- 세션 및 쿠키 (Session & Cookie) ---
    SESSION_COOKIE_HTTPONLY = True  # XSS 방지 (JS로 쿠키 접근 불가)
    SESSION_COOKIE_SAMESITE = 'Lax' # CSRF 방지
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60) # 세션 만료 시간 설정 (1시간)


class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    # 개발 시에는 HTTPS를 강제하지 않음
    SESSION_COOKIE_SECURE = False
    # SQL 쿼리 로그 출력 (디버깅용)
    SQLALCHEMY_ECHO = False 


class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    # HTTPS 필수 적용
    SESSION_COOKIE_SECURE = True
    
    # 운영 환경 추가 보안
    # SESSION_COOKIE_DOMAIN = 'yourdomain.com' # 도메인 확정 시 주석 해제


class TestingConfig(Config):
    """테스트 환경 설정"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:' # 인메모리 DB 사용
    WTF_CSRF_ENABLED = False


# 환경 설정 딕셔너리 (app.py에서 쉽게 호출하기 위함)
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}