SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS match_requests;
DROP TABLE IF EXISTS personality_results;
DROP TABLE IF EXISTS chat_logs;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS = 1;

-- 1. Users Table
CREATE TABLE users (
    user_id INTEGER AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    username VARCHAR(100) NOT NULL,
    nickname VARCHAR(100),
    gender ENUM('MALE', 'FEMALE', 'OTHER'),
    birth_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_banned BOOLEAN DEFAULT FALSE,
    is_dummy BOOLEAN DEFAULT FALSE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. Chat Logs Table
CREATE TABLE chat_logs (
    log_id INTEGER AUTO_INCREMENT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    target_name VARCHAR(100) NOT NULL,
    process_status ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED') DEFAULT 'PENDING',
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 3. Personality Results Table
CREATE TABLE personality_results (
    result_id INTEGER AUTO_INCREMENT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    log_id INTEGER,
    is_representative BOOLEAN DEFAULT TRUE,
    line_count_at_analysis INTEGER DEFAULT 0,
    openness FLOAT NOT NULL,
    conscientiousness FLOAT NOT NULL,
    extraversion FLOAT NOT NULL,
    agreeableness FLOAT NOT NULL,
    neuroticism FLOAT NOT NULL,
    big5_confidence FLOAT DEFAULT 0.0,
    mbti_prediction VARCHAR(10),
    mbti_confidence FLOAT DEFAULT 0.0,
    socionics_prediction VARCHAR(10),
    socionics_confidence FLOAT DEFAULT 0.0,
    summary_text TEXT,
    reasoning_text TEXT,
    full_report_json JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (log_id) REFERENCES chat_logs(log_id) ON DELETE SET NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 4. Match Requests Table
CREATE TABLE match_requests (
    request_id INTEGER AUTO_INCREMENT PRIMARY KEY,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(user_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 5. Notifications Table
CREATE TABLE notifications (
    notification_id INTEGER AUTO_INCREMENT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
