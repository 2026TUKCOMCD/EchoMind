import os
import sys
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
        required_keys = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME', 'SECRET_KEY']
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
    critical_modules = ['flask', 'pymysql', 'flask_sqlalchemy', 'openai', 'numpy', 'scipy', 'cryptography', 'flask_migrate', 'dotenv']
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

def check_flask_app():
    try:
        # 1. 최상위 설계 파일(app.py)만 가져오면 의존성 달린 모델들과 db가 전부 빨려옵니다. (앱 구동 테스트 1)
        from app import app, db
        import sqlalchemy
        
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
    # 파이썬 전체 코드 컴파일 오류 스캔
    try:
        result = compileall.compile_dir('.', maxlevels=10, quiet=1)
        if not result:
            print_result("Syntax Check", False, "- Python files contain syntax errors! Check standard output above.")
            return False
        print_result("Syntax Check", True, "- Passed static compilation check for all Python files")
        return True
    except Exception as e:
        print_result("Syntax Check", False, "- Compilation engine crashed")
        print_traceback(e)
        return False

if __name__ == "__main__":
    print(f"\n{YELLOW}{'='*50}")
    print(" ECHO-MIND SERVER HEALTH CHECK V2 (Production Mode)")
    print(f"{'='*50}{RESET}\n")
    
    passed = True
    passed &= check_syntax()
    passed &= check_dependencies()
    passed &= check_env()
    
    if passed:
        passed &= check_system()
        passed &= check_flask_app()
        
    print(f"\n{YELLOW}{'='*50}{RESET}")
    if passed:
        print(f"{GREEN}[SUCCESS] All diagnostic checks passed. System is ready for deployment.{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}[ABORT] Critical failures detected. Deployment halted. Check traceback above.{RESET}\n")
        sys.exit(1)
