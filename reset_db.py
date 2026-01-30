# reset_db.py
# -*- coding: utf-8 -*-

"""
[DB 초기화 스크립트]
이 스크립트는 extensions.py에 정의된 SQLAlchemy 모델을 기반으로
데이터베이스 테이블을 모두 삭제(DROP)하고 다시 생성(CREATE)합니다.

사용법:
    python reset_db.py
"""

from app import app
from extensions import db

def reset_database():
    print("WARNING: This will delete ALL data in the database.")
    confirm = input("Are you sure you want to proceed? (y/n): ")
    
    if confirm.lower() == 'y':
        with app.app_context():
            print("dropping all tables...")
            db.drop_all()  # 모든 테이블 삭제
            
            print("Creating all tables from extensions.py...")
            db.create_all() # 모델 정의대로 테이블 생성
            
            print("Database has been reset successfully!")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    reset_database()
