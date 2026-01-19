import pymysql
import os
from dotenv import load_dotenv

# .env 파일이 있다면 로드 (로컬 실행 시 유용)
load_dotenv()

# ==========================================
# [설정] RDS 정보 (직접 입력하거나 환경 변수 사용)
# ==========================================
# 로컬(윈도우)에서 실행할 경우, 여기에 직접 RDS 엔드포인트를 입력하거나 
# .env 파일에 DB_HOST=... 형식으로 저장해서 사용할 수 있습니다.
RDS_HOST = os.getenv("DB_HOST", "여기에_RDS_엔드포인트_입력") 
RDS_USER = os.getenv("DB_USER", "admin")
RDS_PASSWORD = os.getenv("DB_PASSWORD", "mypassword1234")
DB_NAME = "echomind"

print(f">>> 접속 시도: {RDS_HOST} ({RDS_USER})")

try:
    conn = pymysql.connect(
        host=RDS_HOST, 
        user=RDS_USER, 
        password=RDS_PASSWORD, 
        db=DB_NAME,
        charset='utf8mb4'
    )
    print(">>> DB 연결 성공!")

    # 테이블 생성 SQL 모음
    sql_users = """
    CREATE TABLE IF NOT EXISTS users (
        user_id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255),
        username VARCHAR(100),
        nickname VARCHAR(100),
        gender VARCHAR(50),
        birth_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    sql_chat_logs = """
    CREATE TABLE IF NOT EXISTS chat_logs (
        log_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        file_name VARCHAR(255),
        file_path VARCHAR(255),
        target_name VARCHAR(100),
        process_status VARCHAR(50),
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """

    sql_results = """
    CREATE TABLE IF NOT EXISTS personality_results (
        result_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        log_id INT,
        openness FLOAT,
        conscientiousness FLOAT,
        extraversion FLOAT,
        agreeableness FLOAT,
        neuroticism FLOAT,
        summary_text TEXT,
        mbti_prediction VARCHAR(10),
        reasoning_text TEXT,
        toxicity_score FLOAT,
        sentiment_pos_ratio FLOAT,
        sentiment_neg_ratio FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (log_id) REFERENCES chat_logs(log_id)
    );
    """

    # 실행 및 확인
    with conn.cursor() as cursor:
        print("1. Users 테이블 확인/생성 중...")
        cursor.execute(sql_users)
        
        print("2. Chat Logs 테이블 확인/생성 중...")
        cursor.execute(sql_chat_logs)
        
        print("3. Results 테이블 확인/생성 중...")
        cursor.execute(sql_results)
        
    conn.commit()
    print("\n>>> 모든 테이블 생성 완료! 성공적입니다.")

except Exception as e:
    print(f"\n>>> [오류 발생] {e}")
    print("팁: RDS의 '퍼블릭 액세스'가 '예'로 되어 있는지, 보안 그룹에서 내 IP(3306)가 허용되어 있는지 확인하세요.")

finally:
    if 'conn' in locals():
        conn.close()
