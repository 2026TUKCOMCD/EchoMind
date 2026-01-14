
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import tempfile
from io import StringIO

# Import core logic from existing files
from main import parse_kakao_lines, analyze_kakao_data, MAX_MESSAGES_FOR_LLM
from recommend import get_recommendations, WEIGHT_BIG5, WEIGHT_STYLE, WEIGHT_STATS, WEIGHT_TOPIC

# -------------------------------------------------------------------------
# Page Config 
# streamlit run app.py
# -------------------------------------------------------------------------
st.set_page_config(
    page_title="EchoMind Analysis",
    page_icon="🧠",
    layout="wide",
)

# -------------------------------------------------------------------------
# Sidebar & Config
# -------------------------------------------------------------------------
st.sidebar.title("🧠 EchoMind Config")

# API Key Handling
api_key = st.sidebar.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

model_name = st.sidebar.selectbox("Model", ["gpt-5-nano", "gpt-5-mini", "gpt-4o-mini"], index=0)

st.sidebar.markdown("---")
st.sidebar.info("카카오톡 대화 내용(.txt)을 업로드하여 성격과 대화 스타일을 분석하고, 가장 잘 맞는 친구를 추천받으세요.")

# -------------------------------------------------------------------------
# Helper Functions for UI
# -------------------------------------------------------------------------
def draw_radar_chart(data_dict, title, max_val=1.0):
    categories = list(data_dict.keys())
    values = list(data_dict.values())

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name=title
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max_val]
            )),
        showlegend=False,
        title=dict(text=title, y=0.98),
        margin=dict(t=100, b=80, l=100, r=100),  # 여백 대폭 확대
        font=dict(size=12) # 폰트 크기 조정
    )
    return fig

# -------------------------------------------------------------------------
# Main App Structure
# -------------------------------------------------------------------------
st.title("🧩 EchoMind : AI 페르소나 매칭 시스템")

tab1, tab2 = st.tabs(["📊 분석하기 (Analyze)", "💘 매칭하기 (Match)"])

# -------------------------------------------------------------------------
# Tab 1: Analysis
# -------------------------------------------------------------------------
with tab1:
    st.header("1. 대화 데이터 분석")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Input Mode Selection
        input_mode = st.radio("입력 방식 선택", ["대화 분석 (TXT)", "프로필 불러오기 (JSON)"], horizontal=True)
        
        if input_mode == "대화 분석 (TXT)":
            target_name = st.text_input("분석할 대화명 (본인 이름)", placeholder="카톡에 표시되는 이름 정확히 입력")
            uploaded_file = st.file_uploader("카카오톡 내보내기 파일 (.txt)", type=["txt"])
            analyze_btn = st.button("분석 시작", type="primary", use_container_width=True)
        else:
            uploaded_json = st.file_uploader("프로필 파일 (.json)", type=["json"])
            load_btn = st.button("프로필 로드", type="primary", use_container_width=True)

    with col2:
        # Logic for TXT Analysis
        if input_mode == "대화 분석 (TXT)" and analyze_btn:
            if not api_key:
                st.error("OpenAI API Key가 필요합니다. 왼쪽 사이드바에 입력해주세요.")
            elif not target_name:
                st.warning("분석할 대화명을 입력해주세요.")
            elif not uploaded_file:
                st.warning("대화 파일을 업로드해주세요.")
            else:
                with st.spinner("데이터 파싱 및 AI 분석 중... (약 10~30초 소요)"):
                    try:
                        # 1. Read & Parse
                        stringio = StringIO(uploaded_file.getvalue().decode("utf-8", errors="ignore"))
                        # We need an iterator for parse_kakao_lines
                        lines_iter = stringio
                        
                        rows = parse_kakao_lines(lines_iter)
                        
                        if not rows:
                            st.error("파싱된 대화가 없습니다. 파일 형식을 확인해주세요.")
                            st.stop()
                            
                        # 2. Analyze
                        profile = analyze_kakao_data(rows, target_name, model_name)
                        
                        # 3. Store in Session State
                        st.session_state['my_profile'] = profile
                        st.success("분석 완료!")
                        
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

        # Logic for JSON Load
        elif input_mode == "프로필 불러오기 (JSON)" and load_btn:
            if not uploaded_json:
                st.warning("JSON 파일을 업로드해주세요.")
            else:
                try:
                    data = json.load(uploaded_json)
                    # Simple validation
                    if "big5" not in data or "communication_style" not in data:
                        st.error("올바른 EchoMind 프로필 형식이 아닙니다.")
                    else:
                        st.session_state['my_profile'] = data
                        st.success("프로필 로드 완료!")
                except Exception as e:
                    st.error(f"파일 로드 중 오류: {e}")

        # Display Results if available
        if 'my_profile' in st.session_state:
            p = st.session_state['my_profile']
            meta = p.get('_meta', {})
            
            t_name = meta.get('target_name', '알 수 없음')
            gen_at = meta.get('generated_at', 'N/A')
            mod_name = meta.get('model', 'unknown')

            st.markdown(f"### 👤 **{t_name}** 님의 페르소나")
            st.markdown(f"Generated at: `{gen_at}` | Model: `{mod_name}`")
            
            # --- Metrics ---
            m_col1, m_col2, m_col3 = st.columns(3)
            stats = p.get('stats', {})
            dict_an = p.get('dictionary_analysis', {})
            
            m_col1.metric("대화 점유율", f"{stats.get('msg_share', 0)}%")
            m_col1.caption("전체 대화 중 내가 말한 비율")
            
            m_col2.metric("평균 답장 시간", f"{stats.get('avg_reply_latency', 0)}분")
            m_col2.caption("상대방 말에 반응하는 평균 시간")
            
            tox = dict_an.get('toxicity_score', 0) * 100
            m_col3.metric("독성(욕설) 지수", f"{tox:.1f}%")
            m_col3.caption("낮을수록 바른 언어 사용")

            # --- Download Button ---
            json_str = json.dumps(p, ensure_ascii=False, indent=2)
            # Safe name for file
            safe_name = meta.get('target_name', 'profile')
            file_name = f"profile_{safe_name}.json"
            st.download_button(
                label="📥 분석 결과 JSON 다운로드",
                data=json_str,
                file_name=file_name,
                mime="application/json",
            )

            st.divider()

            # --- Charts ---
            c_col1, c_col2 = st.columns(2)
            
            with c_col1:
                st.subheader("Big5 성격 특성")
                big5_data = p.get('big5', {})
                # Translate keys
                big5_map = {
                    "openness": "개방성(Openness)",
                    "conscientiousness": "성실성(Conscientiousness)",
                    "extraversion": "외향성(Extraversion)",
                    "agreeableness": "우호성(Agreeableness)",
                    "neuroticism": "신경성(Neuroticism)"
                }
                big5_ko = {big5_map.get(k, k): v for k, v in big5_data.items()}
                fig_big5 = draw_radar_chart(big5_ko, "Big 5 Traits")
                st.plotly_chart(fig_big5, use_container_width=True)
                
            with c_col2:
                st.subheader("커뮤니케이션 스타일")
                style_data = p.get('communication_style', {})
                # Translate keys
                style_map = {
                    "tone": "어조/말투(Tone)",
                    "directness": "직설성(Directness)",
                    "emotion_expression": "감정표현(Emotion)",
                    "empathy_signals": "공감반응(Empathy)",
                    "initiative": "대화주도(Initiative)",
                    "conflict_style": "갈등관리(Conflict)"
                }
                style_ko = {style_map.get(k, k): v for k, v in style_data.items()}
                fig_style = draw_radar_chart(style_ko, "Communication Style")
                st.plotly_chart(fig_style, use_container_width=True)

            # --- Topics ---
            st.subheader("🗣️ 주요 대화 주제")
            topics = p.get('topics', [])
            st.write(" ".join([f"`#{t}`" for t in topics]))

# -------------------------------------------------------------------------
# Tab 2: Matching
# -------------------------------------------------------------------------
with tab2:
    st.header("2. 베스트 파트너 매칭")
    
    if 'my_profile' not in st.session_state:
        st.warning("먼저 '분석하기' 탭에서 내 대화 데이터를 분석해주세요.")
    else:
        st.info("현재 분석된 프로필을 바탕으로 후보군과 매칭합니다.")
        
        candidates_dir = os.path.join(os.getcwd(), "candidates")
        match_btn = st.button("매칭 시작 (Start Matching)", type="primary")
        
        if match_btn:
            if not os.path.exists(candidates_dir):
                st.error(f"'candidates' 폴더를 찾을 수 없습니다: {candidates_dir}")
            else:
                with st.spinner("매칭 점수 계산 중..."):
                    my_profile = st.session_state['my_profile']
                    results = get_recommendations(my_profile, candidates_dir)
                
                if not results:
                    st.warning("매칭 가능한 후보가 없습니다.")
                else:
                    st.balloons()
                    st.markdown("### 🏆 매칭 결과 Top 5")
                    
                    for i, res in enumerate(results[:5]):
                        rank = i + 1
                        score = res['total_score']
                        name = res['name']
                        details = res['details']
                        common_topics = res['topics']
                        
                        # Card Styling
                        with st.expander(f"#{rank} {name} (총점: {score}점)", expanded=(i==0)):
                            col_a, col_b = st.columns([1, 1])
                            
                            with col_a:
                                # Progress bars for component scores
                                st.write("**세부 점수**")
                                st.progress(details['big5'] / WEIGHT_BIG5, text=f"성격 궁합 ({details['big5']} / {WEIGHT_BIG5})")
                                st.progress(details['style'] / WEIGHT_STYLE, text=f"대화 스타일 ({details['style']} / {WEIGHT_STYLE})")
                                st.progress(details['stats'] / WEIGHT_STATS, text=f"패턴 조화 ({details['stats']} / {WEIGHT_STATS})")
                                st.progress(details['topic'] / WEIGHT_TOPIC, text=f"관심사 ({details['topic']} / {WEIGHT_TOPIC})")
                                
                            with col_b:
                                st.write("**공통 관심사**")
                                if common_topics:
                                    st.write(", ".join([f"**{t}**" for t in common_topics]))
                                else:
                                    st.write("(공통된 키워드가 감지되지 않았습니다)")
                                    
                                st.caption("EchoMind 매칭 알고리즘 기반")
