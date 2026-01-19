# app.py
import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# [Custom Modules] 기존 분석 모듈 임포트
import parse
import main as analyzer
import reporter
from matcher import AdvancedMatcher
from config import Config

# --- 앱 초기화 ---
app = Flask(__name__)
app.config.from_object(Config)

# 파일 저장소 생성
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

# --- DB 모델 정의 (SQLAlchemy) ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.BigInteger, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatUpload(db.Model):
    __tablename__ = 'chat_uploads'
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    process_status = db.Column(db.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'), default='PENDING')
    error_message = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class AnalysisProfile(db.Model):
    __tablename__ = 'analysis_profiles'
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False)
    chat_upload_id = db.Column(db.BigInteger, db.ForeignKey('chat_uploads.id'), nullable=False)
    is_representative = db.Column(db.Boolean, default=False)
    
    # 7대 지표 (감성도, 야간활동, 답장속도 삭제됨)
    activity_score = db.Column(db.Float, default=0.0)
    politeness_score = db.Column(db.Float, default=0.0)
    impact_score = db.Column(db.Float, default=0.0)
    # avg_reply_gap 삭제됨
    initiation_ratio = db.Column(db.Float, default=0.0)
    vocab_ttr = db.Column(db.Float, default=0.0)
    data_entropy = db.Column(db.Float, default=0.0)
    toxicity_score = db.Column(db.Float, default=0.0)
    
    full_report_json = db.Column(db.JSON)
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 매칭용 벡터 반환 헬퍼
    def to_vector(self):
        return {
            "activity_score": self.activity_score,
            "politeness_score": self.politeness_score,
            "impact_score": self.impact_score,
            "initiation_ratio": self.initiation_ratio,
            "vocab_ttr": self.vocab_ttr,
            "data_entropy": self.data_entropy,
            "toxicity_score": self.toxicity_score
        }

# --- 라우트 및 컨트롤러 ---

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = db.session.get(User, user_id)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if g.user:
        return redirect(url_for('upload_file'))
    return redirect(url_for('login'))

# 1. 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('비밀번호가 일치하지 않습니다.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('이미 존재하는 이메일입니다.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        new_user = User(name=name, email=email, password_hash=hashed_pw)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('회원가입이 완료되었습니다. 로그인해주세요.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('회원가입 중 오류가 발생했습니다.', 'danger')
            print(f"Error: {e}")

    return render_template('register.html')

# 2. 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session['user_id'] = user.id
            session['user_name'] = user.name
            return redirect(url_for('upload_file'))
        
        flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 3. 파일 업로드 및 분석 실행 (핵심 로직)
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('파일이 없습니다.', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        target_name = request.form['target_name'] # 분석 대상 이름

        if file.filename == '':
            flash('선택된 파일이 없습니다.', 'danger')
            return redirect(request.url)

        if file and file.filename.endswith('.txt'):
            try:
                # A. 파일 저장
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(save_path)

                # DB에 업로드 기록
                upload_rec = ChatUpload(
                    user_id=g.user.id,
                    original_filename=filename,
                    stored_filename=unique_filename,
                    file_path=save_path,
                    process_status='PROCESSING'
                )
                db.session.add(upload_rec)
                db.session.commit()

                # --- 분석 파이프라인 시작 ---
                
                # B. 전처리 (Parse) - 임시 파일 생성
                clean_path = save_path + ".clean"
                parse.parse_and_save(save_path, target_name, clean_path)

                # C. 본석 (Main Analysis)
                # 원본 파일에서 timestamp 파싱 등을 위해 다시 로드 (main.py 로직 활용)
                target_msgs, full_logs, stats = analyzer.load_chat_data(save_path, target_name)
                
                if len(target_msgs) < 10:
                    raise ValueError("대화 데이터가 너무 적습니다. (10건 미만)")

                # 벡터 분석
                basic_vec = analyzer.analyze_basic_features(target_msgs)
                time_vec = analyzer.analyze_time_and_initiative(full_logs)
                vocab_vec = analyzer.analyze_vocabulary_and_reliability(target_msgs)
                
                # 독성 분석 (사전 로드)
                bad_words = analyzer.load_bad_words("korean_bad_words_formatted.json")
                tox_score = analyzer.calculate_toxicity(target_msgs, bad_words)

                final_vector = {**basic_vec, **time_vec, **vocab_vec, "toxicity_score": round(tox_score, 4)}

                # D. 리포트 생성 (Reporter)
                stat_engine = reporter.StatEngine()
                identity_engine = reporter.IdentityEngine()
                
                # 리포트 JSON 구성
                identity = identity_engine.analyze_core_identity(final_vector)
                
                # 리포트 객체 생성 (임시)
                mock_reporter = reporter.EchoMindDeepReporter("dummy")
                mock_reporter.vector = final_vector
                mock_reporter.meta = {"target_name": target_name}
                
                full_report = mock_reporter.generate_comprehensive_report()

                # E. DB 저장 (AnalysisProfile)
                
                # 1. 기존 대표 프로필 해제
                AnalysisProfile.query.filter_by(user_id=g.user.id).update({'is_representative': False})
                
                # 2. 새 프로필 저장
                new_profile = AnalysisProfile(
                    user_id=g.user.id,
                    chat_upload_id=upload_rec.id,
                    is_representative=True, # 최신이므로 대표 설정
                    
                    # 벡터 매핑 (삭제된 키 제외)
                    activity_score=final_vector['activity_score'],
                    politeness_score=final_vector['politeness_score'],
                    impact_score=final_vector['impact_score'],
                    initiation_ratio=final_vector['initiation_ratio'],
                    vocab_ttr=final_vector['vocab_ttr'],
                    data_entropy=final_vector['data_entropy'],
                    toxicity_score=final_vector['toxicity_score'],
                    
                    full_report_json=full_report
                )
                
                db.session.add(new_profile)
                upload_rec.process_status = 'COMPLETED'
                db.session.commit()

                # 임시 파일 정리
                if os.path.exists(clean_path): os.remove(clean_path)

                flash('분석이 완료되었습니다!', 'success')
                return redirect(url_for('show_result'))

            except Exception as e:
                db.session.rollback()
                if 'upload_rec' in locals():
                    upload_rec.process_status = 'FAILED'
                    upload_rec.error_message = str(e)
                    db.session.commit()
                flash(f'분석 중 오류가 발생했습니다: {str(e)}', 'danger')
                print(f"Analysis Error: {e}")

    return render_template('upload.html')

# 4. 결과 확인
@app.route('/result')
@login_required
def show_result():
    # 현재 유저의 '대표 프로필' 조회
    profile = AnalysisProfile.query.filter_by(user_id=g.user.id, is_representative=True).first()
    
    if not profile:
        flash('아직 분석된 프로필이 없습니다. 대화를 업로드해주세요.', 'warning')
        return redirect(url_for('upload_file'))
        
    # DB의 JSON 데이터를 그대로 템플릿에 전달
    return render_template('result.html', profile_data=profile.full_report_json)

# 5. 매칭 (핵심 기능)
@app.route('/matching')
@login_required
def matching():
    # 1. 내 프로필 가져오기
    my_profile = AnalysisProfile.query.filter_by(user_id=g.user.id, is_representative=True).first()
    if not my_profile:
        flash('매칭을 하려면 먼저 대화 분석을 진행해야 합니다.', 'warning')
        return redirect(url_for('upload_file'))

    # 2. 후보군 가져오기 (DB에서 조회)
    # 조건: 나를 제외하고, 대표 프로필이며, 독성 점수가 0.2 미만인 사용자
    candidates = AnalysisProfile.query.filter(
        AnalysisProfile.user_id != g.user.id,
        AnalysisProfile.is_representative == True,
        AnalysisProfile.toxicity_score < 0.2
    ).all()

    matcher = AdvancedMatcher()
    results = []

    my_vector = my_profile.to_vector()

    for cand in candidates:
        cand_user = db.session.get(User, cand.user_id) # 사용자 이름 조회
        cand_vector = cand.to_vector()
        
        # 매칭 점수 계산
        match_info = matcher.calculate_match(my_vector, cand_vector)
        comment = matcher.generate_comment(match_info)
        
        results.append({
            "user_id": cand_user.name, # 화면엔 이름 표시
            "info": match_info,
            "comment": comment
        })

    # 점수순 정렬
    results.sort(key=lambda x: x['info']['total'], reverse=True)

    return render_template('matching.html', results=results)

if __name__ == '__main__':
    # DB 테이블 생성 (최초 1회)
    with app.app_context():
        db.create_all()
    
    app.run(debug=os.environ.get('FLASK_ENV') != 'production')