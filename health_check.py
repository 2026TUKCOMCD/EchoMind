import os
import sys
import time
import psutil
import compileall
import traceback

# ANSI Colors for terminal
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_result(step, status, message=""):
    if status:
        print(f"{GREEN}[PASS]{RESET} {step} {message}")
    else:
        print(f"{RED}[FAIL]{RESET} {step} {message}")

def print_traceback(e):
    print(f"\n{RED}--- [ERROR TRACEBACK] ---{RESET}")
    traceback.print_exc()
    print(f"{RED}-------------------------{RESET}\n")

def check_env():
    if not os.path.exists('.env'):
        print_result("Environment", False, "- .env file is missing!")
        return False
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        required_keys = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME', 'SECRET_KEY', 'OPENAI_API_KEY']
        missing = [key for key in required_keys if not os.environ.get(key)]
        if missing:
            print_result("Environment", False, f"- Missing keys: {', '.join(missing)}")
            return False
        print_result("Environment", True, "- .env and required keys present")
        return True
    except Exception as e:
        print_result("Environment", False, f"- Exception loading .env")
        print_traceback(e)
        return False

def check_dependencies():
    critical_modules = ['flask', 'pymysql', 'flask_sqlalchemy', 'openai', 'numpy', 'scipy', 'cryptography', 'flask_migrate', 'dotenv', 'flask_compress']
    missing = []
    for mod in critical_modules:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print_result("Dependencies", False, f"- Missing Python packages: {', '.join(missing)}")
        return False
    print_result("Dependencies", True, "- All core Python packages are installed")
    return True

def check_db_connection():
    """DB 서버 연결 가능 여부를 사전에 검증 (Flask 로딩 전 경량 테스트)"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        import pymysql
        
        conn = pymysql.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            user=os.environ.get('DB_USER', ''),
            password=os.environ.get('DB_PASSWORD', ''),
            database=os.environ.get('DB_NAME', ''),
            connect_timeout=5
        )
        conn.ping(reconnect=False)
        conn.close()
        print_result("Database Connection", True, "- DB 서버 연결 및 Ping 응답 정상")
        return True
    except Exception as e:
        print_result("Database Connection", False, 
            f"- DB 서버에 연결할 수 없습니다. 호스트/인증 정보 또는 네트워크를 확인하세요.")
        print_traceback(e)
        return False

def check_flask_app():
    try:
        # 1. 최상위 설계 파일(app.py)만 가져오면 의존성 달린 모델들과 db가 전부 빨려옵니다. (앱 구동 테스트 1)
        from app import app, db
        import sqlalchemy
        from sqlalchemy import text
        
        print_result("Flask App Initialization", True, "- (app.py) loaded successfully without crashing")
        
        # 2. 하드코딩 제거: 파이썬 클래스 정보 기반 동적 스키마 비교
        with app.app_context():
            engine = db.engine
            inspector = sqlalchemy.inspect(engine)
            actual_tables = set(inspector.get_table_names())
            defined_tables = set(db.metadata.tables.keys())
            
            missing_tables = defined_tables - actual_tables
            if missing_tables:
                print_result("Database Schema", False, f"- Missing tables in DB: {', '.join(missing_tables)}")
                return False
            else:
                print_result("Database Schema", True, f"- Total {len(defined_tables)} tables automatically matched between Python Models and MySQL")
            
            # 2-1. Alembic 마이그레이션 적용 상태 확인 (경고만 출력, 차단하지 않음)
            # 주의: Health Check는 마이그레이션 전에 실행되므로, 첫 배포 시에는 아직 적용 전일 수 있음
            migration_ok = True
            if 'alembic_version' in actual_tables:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT version_num FROM alembic_version"))
                    current_rev = result.scalar()
                    
                    if current_rev is None:
                        print_result("Migration Status", False, 
                            "- [WARNING] alembic_version 테이블은 존재하나 적용된 마이그레이션이 없습니다. "
                            "'flask db upgrade'가 이후 단계에서 실행됩니다.")
                        migration_ok = False
                    else:
                        print_result("Migration Status", True, 
                            f"- Current applied migration: {current_rev}")
            else:
                print_result("Migration Status", False,
                    "- [WARNING] alembic_version 테이블이 없습니다. 마이그레이션 시스템 초기화가 필요합니다.")
                migration_ok = False
            
            # 2-2. 핵심 컬럼 속성 검증 (비회원 모드 필수 조건)
            # 마이그레이션 미적용 시에는 경고만 출력
            nullable_checks = [
                ('personality_results', 'user_id'),
                ('chat_logs', 'user_id'),
            ]
            for table_name, col_name in nullable_checks:
                columns = inspector.get_columns(table_name)
                for col in columns:
                    if col['name'] == col_name:
                        if not col.get('nullable', False):
                            if migration_ok:
                                # 마이그레이션이 적용되었는데도 NOT NULL이면 진짜 에러
                                print_result("Schema Drift Check", False,
                                    f"- {table_name}.{col_name}가 NOT NULL 상태입니다. "
                                    f"비회원 모드가 작동하지 않습니다. 마이그레이션 적용을 확인하세요.")
                                return False
                            else:
                                # 마이그레이션 미적용 상태 → 이후 단계에서 해결 예정
                                print(f"{YELLOW}[WARN]{RESET} Schema Drift Check "
                                    f"- {table_name}.{col_name}가 NOT NULL 상태입니다. "
                                    f"마이그레이션 적용 후 해결될 예정입니다.")
            
            if migration_ok:
                print_result("Schema Drift Check", True, 
                    "- 핵심 컬럼 속성(user_id nullable)이 모델 정의와 일치합니다.")
            
        # 3. 가상 HTTP 요청 테스트 (Flask test_client 앱 구동 테스트 2)
        client = app.test_client()
        response = client.get('/', follow_redirects=True)
        # 404여도 라우터가 응답했다는 의미이므로 정상입니다. 코드가 깨지면 500이 뜹니다.
        if response.status_code >= 500:
            print_result("Flask Routing System", False, f"- Simulated GET '/' returned {response.status_code} Internal Server Error")
            return False
        else:
            print_result("Flask Routing System", True, f"- Simulated GET '/' responded with HTTP {response.status_code}")
            
        return True
    except Exception as e:
        print_result("Flask & DB Check", False, "- Initialization crashed! Traceback below:")
        print_traceback(e)
        return False

def check_system():
    if not os.path.exists('uploads'):
        try:
            os.makedirs('uploads')
        except Exception as e:
            print_result("System Resources", False, f"- Cannot create uploads folder")
            print_traceback(e)
            return False
            
    if not os.access('uploads', os.W_OK):
        print_result("System Resources", False, "- 'uploads' folder lacks write permissions")
        return False
        
    memory = psutil.virtual_memory()
    available_mb = memory.available / (1024 * 1024)
    if available_mb < 50:
        print_result("System Resources", False, f"- Danger: Extremely low memory ({available_mb:.0f}MB available)")
        return False
        
    print_result("System Resources", True, f"- Memory OK ({available_mb:.0f}MB free), File IO OK")
    return True

def check_syntax():
    # 파이썬 전체 코드 컴파일 오류 스캔 (venv, .git 등 불필요한 폴더 제외)
    try:
        exclude_dirs = ['venv', '.git', '__pycache__', 'node_modules', '.pytest_cache', 'EchoMind_app']
        
        # 프로젝트 루트의 .py 파일과 하위 디렉토리를 선별적으로 컴파일
        all_ok = True
        for entry in os.listdir('.'):
            if entry in exclude_dirs or entry.startswith('.'):
                continue
            path = os.path.join('.', entry)
            if os.path.isfile(path) and path.endswith('.py'):
                if not compileall.compile_file(path, quiet=1):
                    all_ok = False
            elif os.path.isdir(path):
                if not compileall.compile_dir(path, maxlevels=10, quiet=1):
                    all_ok = False
        
        if not all_ok:
            print_result("Syntax Check", False, "- Python files contain syntax errors! Check standard output above.")
            return False
        print_result("Syntax Check", True, "- Passed static compilation check for all Python files")
        return True
    except Exception as e:
        print_result("Syntax Check", False, "- Compilation engine crashed")
        print_traceback(e)
        return False

if __name__ == "__main__":
    start_time = time.time()
    
    print(f"\n{YELLOW}{'='*50}")
    print(" ECHO-MIND SERVER HEALTH CHECK V1 (Production Mode)")
    print(f"{'='*50}{RESET}\n")
    
    # 버전 정보 출력
    print(f" Python  : {sys.version.split()[0]}")
    try:
        import flask
        print(f" Flask   : {flask.__version__}")
    except ImportError:
        print(f" Flask   : {RED}Not Installed{RESET}")
    try:
        import sqlalchemy
        print(f" SQLAlchemy: {sqlalchemy.__version__}")
    except ImportError:
        print(f" SQLAlchemy: {RED}Not Installed{RESET}")
    print()
    
    passed = True
    passed &= check_syntax()
    passed &= check_dependencies()
    passed &= check_env()
    
    if passed:
        passed &= check_system()
        passed &= check_db_connection()
    
    if passed:
        passed &= check_flask_app()
        
    elapsed = time.time() - start_time
    print(f"\n{YELLOW}{'='*50}{RESET}")
    if passed:
        print(f"{GREEN}[SUCCESS] All diagnostic checks passed. System is ready for deployment. (took {elapsed:.2f}s){RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}[ABORT] Critical failures detected. Deployment halted. (took {elapsed:.2f}s){RESET}\n")
        sys.exit(1)
