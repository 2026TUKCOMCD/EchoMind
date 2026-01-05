
import pymysql

# Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def create_database():
    # Connect without selecting a database first
    conn = pymysql.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        charset=db_config['charset']
    )
    
    try:
        with conn.cursor() as cursor:
            print("Creating database 'echomind_db' if it doesn't exist...")
            cursor.execute("CREATE DATABASE IF NOT EXISTS echomind_db")
            cursor.execute("USE echomind_db")
            
            print("Creating table 'users'...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    username VARCHAR(100),
                    nickname VARCHAR(100),
                    gender VARCHAR(10),
                    birth_date VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            print("Creating table 'chat_logs'...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_logs (
                    log_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    file_name VARCHAR(255),
                    file_path VARCHAR(255),
                    target_name VARCHAR(100),
                    process_status VARCHAR(50) DEFAULT 'COMPLETED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            print("Creating table 'personality_results'...")
            cursor.execute("""
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
                )
            """)
            
            conn.commit()
            print("Database setup completed successfully.")
            
    except Exception as e:
        print(f"Error during database setup: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    create_database()
