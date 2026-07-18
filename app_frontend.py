import streamlit as st
import requests

st.set_page_config(
    page_title = "Visalify",
    page_icon = "🛡️",
    layout = "wide",
    initial_sidebar_state = "collapsed"
)

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
 
        :root {
            --ink: #14171B;
            --muted: #6B6F76;
            --paper: #FAFAF8;
            --panel: #F1F0EA;
            --hairline: #E4E2DA;
            --seal: #1F5F4E;
            --seal-soft: rgba(31, 95, 78, 0.08);
            --risk: #A34418;
            --risk-soft: rgba(163, 68, 24, 0.08);
        }
 
        header[data-testid="stHeader"] { display: none !important; }
 
        .main .block-container {
            padding-top: 3.5rem !important;
            padding-bottom: 4rem !important;
            max-width: 880px !important;
        }
 
        .stApp {
            background-color: var(--paper) !important;
            color: var(--ink) !important;
            font-family: 'IBM Plex Sans', -apple-system, sans-serif;
        }
 
        /* ---- Brand mark ---- */
        .brand-mark {
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: var(--seal);
            margin-bottom: 1.4rem;
        }
        .brand-mark::before {
            content: "";
            display: inline-block;
            width: 6px; height: 6px;
            background: var(--seal);
            border-radius: 50%;
            margin-right: 8px;
        }
 
        /* ---- Headline ---- */
        .main-title {
            font-family: 'Fraunces', serif;
            font-optical-sizing: auto;
            font-weight: 600;
            font-size: 3.1rem;
            line-height: 1.08;
            letter-spacing: -0.5px;
            color: var(--ink);
            margin-bottom: 1.3rem;
        }
        .main-subtitle {
            color: var(--muted);
            font-size: 1.05rem;
            font-weight: 400;
            line-height: 1.65;
            max-width: 640px;
            margin-bottom: 0;
        }
        .main-subtitle strong { color: var(--ink); font-weight: 600; }
 
        .hairline {
            border: none;
            border-top: 1px solid var(--hairline);
            margin: 2.6rem 0 2.2rem 0;
        }
 
        /* ---- Section eyebrows (real sequence: 01 profile, 02 role, 03 review) ---- */
        .step-eyebrow {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            font-weight: 500;
            letter-spacing: 0.04em;
            color: var(--seal);
            margin-bottom: 0.55rem;
        }
 
        div[data-testid="stHorizontalBlock"] {
            background-color: transparent !important;
            padding: 0 !important;
            box-shadow: none !important;
            gap: 2.5rem !important;
        }
 
        .stTextArea label { display: none !important; }
 
        /* ---- Form fields: institutional, not pill-shaped ---- */
        textarea {
            background-color: #FFFFFF !important;
            border: 1px solid var(--hairline) !important;
            border-radius: 6px !important;
            color: var(--ink) !important;
            padding: 14px 16px !important;
            font-size: 0.95rem !important;
            font-family: 'IBM Plex Sans', sans-serif !important;
            line-height: 1.5 !important;
            transition: all 0.18s ease-in-out !important;
            height: 56px !important;
        }
        textarea::placeholder { color: #A3A29B !important; font-size: 0.92rem !important; }
        textarea:focus {
            border-color: var(--seal) !important;
            box-shadow: 0 0 0 3px var(--seal-soft) !important;
            height: 220px !important;
        }
 
        /* ---- Action button ---- */
        div.stButton > button {
            background: var(--ink) !important;
            color: #FFFFFF !important;
            border-radius: 6px !important;
            border: none !important;
            padding: 0.8rem 1.8rem !important;
            font-weight: 500 !important;
            font-size: 0.88rem !important;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            width: auto !important;
            margin: 0.4rem 0 0 0 !important;
            display: block !important;
            transition: all 0.15s ease;
        }
        div.stButton > button:hover {
            background: var(--seal) !important;
            color: #FFFFFF !important;
        }
        div.stButton > button:active { transform: scale(0.98); }
 
        /* ---- Verdict stamp (signature element) ---- */
        .stamp-wrap { display: flex; align-items: center; gap: 2rem; margin-bottom: 0.5rem; }
        .stamp {
            width: 128px; height: 128px;
            border-radius: 50%;
            border: 2.5px solid currentColor;
            display: flex; align-items: center; justify-content: center;
            text-align: center;
            transform: rotate(-7deg);
            flex-shrink: 0;
            position: relative;
        }
        .stamp::before {
            content: "";
            position: absolute; inset: 6px;
            border: 1px solid currentColor;
            border-radius: 50%;
            opacity: 0.55;
        }
        .stamp span {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            line-height: 1.3;
            padding: 0 10px;
        }
        .stamp.safe { color: var(--seal); }
        .stamp.risk { color: var(--risk); }
 
        .score-block .score-label {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            color: var(--muted);
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
        }
        .score-block .score-value {
            font-family: 'Fraunces', serif;
            font-weight: 600;
            font-size: 3.4rem;
            line-height: 1;
            color: var(--ink);
            letter-spacing: -1px;
        }
        .score-block .score-value span { font-size: 1.6rem; color: var(--muted); font-weight: 400; }
 
        /* ---- Margin notes for flagged issues ---- */
        .note-card {
            border-left: 3px solid var(--risk);
            background: var(--risk-soft);
            border-radius: 0 6px 6px 0;
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.7rem;
        }
        .note-card .note-cat {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--risk);
            margin-bottom: 0.35rem;
        }
        .note-card p { margin: 0.15rem 0 !important; font-size: 0.92rem; color: var(--ink); }
        .note-card b { color: var(--ink); }
 
        /* ---- Section headers ---- */
        .section-head {
            font-family: 'IBM Plex Sans', sans-serif;
            font-weight: 600;
            font-size: 1rem;
            color: var(--ink);
            margin-bottom: 0.2rem;
        }
        .section-caption {
            color: var(--muted);
            font-size: 0.88rem;
            margin-bottom: 0.9rem;
        }
 
        code {
            background-color: var(--panel) !important;
            color: var(--ink) !important;
            border: 1px solid var(--hairline) !important;
            border-radius: 6px !important;
            padding: 20px !important;
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.88rem !important;
            line-height: 1.6 !important;
        }
    </style>
""", unsafe_allow_html = True)

st.markdown('<div class="brand-mark">Visalify: Immigration-Safe Resume Review</div>', unsafe_allow_html=True)
st.markdown('<div class="main-title">Sound like an expert.<br>Not a manager.</div>', unsafe_allow_html=True)
st.markdown("""
    <p class="main-subtitle">
        Typical resume advice pushes leadership words like "managed" or "led." But for
        specialized technical visas, that same language can read as evidence you're a
        corporate manager rather than the hands-on expert the role requires, a common
        trigger for rejection. <strong>Paste your resume and the target job below</strong> and
        we'll show you exactly where that risk shows up, then rewrite it.
    </p>
""", unsafe_allow_html = True)

st.markdown('<hr class="hairline">', unsafe_allow_html=True)

col1, col2 = st.columns(2, gap = "large")

with col1:
    profile_input = st.text_area(
        "Your Current Resume or Profile Text:", 
        placeholder = "Type or paste your resume or experience history here...",
        label_visibility = "collapsed"
    )

with col2:
    jd_input = st.text_area(
        "Job Requirement:", 
        placeholder = "Paste the target job description or requirements here...",
        label_visibility = "collapsed"
    )

st.markdown("<br>", unsafe_allow_html = True)
run = st.button("Run Compliance Check")

if run:
    if not profile_input or not jd_input:
        st.error("Please provide both your resume and the target job description to run the analysis.")
    else:
        with st.spinner("Reviewing your text..."):
            try:
                payload = {"candidate_profile": profile_input, "job_description": jd_input}
                response = requests.post("http://127.0.0.1:8000/match", json=payload, timeout=60)
 
                if response.status_code == 200:
                    data = response.json()
                    verdict = str(data.get('compliance_verdict', ''))
                    verdict_lower = verdict.lower()
                    is_safe = any(w in verdict_lower for w in ["low", "clear", "pass", "safe"])
                    stamp_class = "safe" if is_safe else "risk"
 
                    st.markdown('<hr class="hairline">', unsafe_allow_html=True)
                    st.markdown('<div class="step-eyebrow">03: COMPLIANCE REVIEW</div>', unsafe_allow_html=True)
 
                    st.markdown(f"""
                        <div class="stamp-wrap">
                            <div class="stamp {stamp_class}"><span>{verdict}</span></div>
                            <div class="score-block">
                                <div class="score-label">Job Match Score</div>
                                <div class="score-value">{data['overall_match_score']}<span>/100</span></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
 
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown('<div class="section-head">Flagged Language</div>', unsafe_allow_html=True)
                    st.markdown('<div class="section-caption">Terms that read as management rather than hands-on expertise, and how to fix them.</div>', unsafe_allow_html=True)
 
                    for gap in data['detected_gaps']:
                        st.markdown(f"""
                            <div class="note-card">
                                <div class="note-cat">{gap['category']}</div>
                                <p><b>Risk:</b> {gap['detected_risk']}</p>
                                <p><b>Fix:</b> {gap['optimization_strategy']}</p>
                            </div>
                        """, unsafe_allow_html=True)
 
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown('<div class="section-head">Rewritten, Visa-Safe Version</div>', unsafe_allow_html=True)
                    st.markdown('<div class="section-caption">Technical terms matched to the job, high-risk management language removed.</div>', unsafe_allow_html=True)
                    st.code(data['optimized_profile'], language="text")
                else:
                    st.error("Something went wrong on the server. Please try running it again.")
            except Exception:
                st.error("Could not reach the analysis engine. Make sure your backend server is running.")