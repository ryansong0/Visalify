import streamlit as st
import requests
import pypdf

st.set_page_config(
    page_title = "VisaGuard // Compliance Engine",
    page_icon = "🛡️",
    layout = "wide",
    initial_sidebar_state = "expanded"
)

st.markdown("""
    <style>
    /* main background and fonts */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0d1117;
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #c9d1d9;
    }
            
    /* technical code accents */
    code, pre, [data-testid="stMarkdownContainer"] pre code {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px;
    }
    
    /* left sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #161b22 !important;
        border-right: 1px solid #30363d;
    }

    /* metric & highlight cards */
    div[data-testid="metric-container"] {
        background: rgba(22, 27, 34, 0.6);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }

    /* metrics label changes */
    div[data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        letter-spacing: -1px;
    }
            
    /* custom status cards */
    .violation-card {
        background-color: rgba(248, 81, 73, 0.08);
        border: 1px solid rgba(248, 81, 73, 0.4);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .violation-title {
        color: #f85149;
        font-weight: 700;
        font-size: 14px;
        font-family: 'JetBrains Mono', monospace;
        margin-bottom: 6px;
    }
    
    .safe-banner {
        background-color: rgba(56, 139, 253, 0.1);
        border: 1px solid rgba(56, 139, 253, 0.4);
        border-radius: 8px;
        padding: 16px;
        color: #58a6ff;
    }
    </style>
""", unsafe_allow_html = True)

def highlight_text(full_text: str, flags: list):
    highlighted = full_text
    for flag in flags:
        target = flag.get("matched_text")
        if target and target in highlighted:
            highlighted = highlighted.replace(
                target, f"<span style='background-color: #ffcccb; color: black; padding: 2px 4px; border-radius: 4px; font-weight: bold;'>{target}</span>"
            )
    return highlighted

def extract_text_from_pdf(uploaded_file):
    """Parses text from an uploaded Streamlit file-like object."""
    try:
        reader = pypdf.PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"Failed to parse PDF: {e}")
        return None

with st.sidebar:
    st.markdown("<h2 style='color:#58a6ff; font-family:\"JetBrains Mono\"; font-size:18px;'>⚡ SYSTEM METRICS</h2>", unsafe_allow_html = True)
    st.markdown("---")
    st.markdown("**LLM Gateway Core:** `llama3.2:latest` (Ollama Engine)")
    st.markdown("**Parser Standard:** `8 CFR 214.6 (TN-1/2)`")
    st.markdown("**NLP Vector Embeddings:** Cosine Similarity Matrix")
    st.markdown("---")
    st.markdown("<h3 style='font-size:14px; font-family:\"JetBrains Mono\";'>SYSTEM UTILITIES</h3>", unsafe_allow_html = True)
    
    if st.button("🔄 Flush Telemetry Cache", use_container_width = True):
        st.session_state.messages = [{"role": "assistant", "content": "Hello! Paste a job profile description or list your core responsibilities."}]
        st.session_state.telemetry = {
            "risk_score": 0, "overall_risk_level": "Pending", 
            "flags": [], "requires_more_info": True, "has_evaluated": False
        }
        st.rerun()

if "messages" not in st.session_state or not st.session_state.messages:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Paste a job profile description, upload a PDF resume, or summarize your role..."}
    ]
if "telemetry" not in st.session_state:
    st.session_state.telemetry = {
        "risk_score": 0, "overall_risk_level": "Pending", "flags": [], "requires_more_info": True, "has_evaluated": False
    }

st.markdown("<h1 style='color:#ffffff; font-size: 28px; letter-spacing: -0.5px;'>VisaGuard <span style='color:#58a6ff; font-family:\"JetBrains Mono\"; font-size:16px;'>v2.0 // Compliance Analyzer</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#8b949e; margin-top:-10px; font-size:14px;'>Automated statutory risk auditing framework for professional visa engineering applications.</p>", unsafe_allow_html = True)
st.markdown("---")

col_left, col_right = st.columns([3, 2], gap = "large")

with col_left:
    st.markdown("<h3 style='font-size:16px; font-family:\"JetBrains Mono\"; color:#8b949e;'>[01] INPUT CHANNELS</h3>", unsafe_allow_html = True)
    
    uploaded_file = st.file_uploader("Drop PDF or Text Job Specifications here", type = ["pdf", "txt"], label_visibility = "collapsed")
    if uploaded_file is not None:
        if st.button("🚀 Run Document Compliance Audit", use_container_width = True):
            with st.spinner("Processing local vector parsing..."):
                extracted_text = extract_text_from_pdf(uploaded_file)
            
            if extracted_text:
                st.session_state.messages.append({"role": "user", "content": f"[PDF Document Uploaded]:\n\n{extracted_text}"})
                st.session_state.telemetry = {"risk_score": 0, "overall_risk_level": "Pending", "flags": [], "requires_more_info": True, "has_evaluated": False}

                try:
                    res = requests.post("http://127.0.0.1:8000/chat", json = {"history": st.session_state.messages})
                    if res.status_code == 200:
                        results = res.json()
                        st.session_state.messages.append({"role": "assistant", "content": results.get("agent_message")})
                        st.session_state.telemetry = results
                        st.session_state.telemetry["has_evaluated"] = True
                        st.rerun()
                    else:
                        st.error("Backend Error parsing document.")
                except requests.exceptions.ConnectionError:
                    st.error("FastAPI Infrastructure Offline.")

    st.markdown("---")
    st.markdown("<h3 style='font-size:16px; font-family:\"JetBrains Mono\"; color:#8b949e;'>[02] ANALYST DIALOGUE</h3>", unsafe_allow_html=True)
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Input role description or ask follow-up questions..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        st.session_state.telemetry = {"risk_score": 0, "overall_risk_level": "Pending", "flags": [], "requires_more_info": True, "has_evaluated": True}
        
        try:
            res = requests.post("http://127.0.0.1:8000/chat", json = {"history": st.session_state.messages})
            if res.status_code == 200:
                data = res.json()
                st.session_state.messages.append({"role": "assistant", "content": data["agent_message"]})
                st.session_state.telemetry = data
                st.session_state.telemetry["has_evaluated"] = True
                st.rerun()
            else:
                st.error("Engine Communication Error: Backend API returned a faulty status code.")
        except requests.exceptions.ConnectionError:
            st.error("Infrastructure Offline: Please make sure your FastAPI Uvicorn server is running on port 8000.")

with col_right:
    st.markdown("<h3 style='font-size:16px; font-family:\"JetBrains Mono\"; color:#8b949e;'>[03] REAL-TIME TELEMETRY</h3>", unsafe_allow_html=True)
    
    tel = st.session_state.telemetry
    score = tel.get("risk_score", 0)
    level = tel.get("overall_risk_level", "Pending")
    has_evaluated = tel.get("has_evaluated", False)
    
    # colors based on risk level
    if level in ["Critical", "High"]:
        color_hex = "#f85149"  
    elif level == "Medium":
        color_hex = "#d29922"  
    elif level == "Safe":
        color_hex = "#58a6ff"  
    else:
        color_hex = "#8b949e"  

    # dashboard score metric blocks
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric(label="AUDIT RISK SCORE", value = f"{score} / 100")
    with m_col2:
        st.markdown(f"""
            <div style='background: rgba(22, 27, 34, 0.6); border: 1px solid #30363d; border-radius:8px; padding:10px 20px; height:80px;'>
                <p style='margin:0; font-size:12px; color:#8b949e; font-weight:600;'>RISK ASSIGNMENT</p>
                <p style='margin:0; font-size:22px; font-weight:700; color:{color_hex}; font-family:\"JetBrains Mono\";'>{level.upper()}</p>
            </div>
        """, unsafe_allow_html = True)
        
    st.markdown("---")
    st.markdown("<h4 style='font-size:14px; font-family:\"JetBrains Mono\"; color:#8b949e;'>STATUTORY VIOLATION MAP</h4>", unsafe_allow_html = True)


st.set_page_config(page_title = "VisaGuard Compliance AI", page_icon = "🛡️", layout = "wide")

st.title("🛡️ VisaGuard: Compliance Analysis Dashboard")
st.markdown("Evaluate job descriptions against TN Visa occupational restrictions using NLP context-awareness.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Paste a job profile description or summarize your role, and I will cross-reference it against 8 CFR regulations."}
    ]
if "telemetry" not in st.session_state:
    st.session_state.telemetry = {
        "risk_score": 0, "overall_risk_level": "Pending", "flags": [], "requires_more_info": True, "has_evaluated": False
    }

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("💬 Compliance Consultation")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    if user_input := st.chat_input("Provide role responsibilities or reply to follow-ups..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
        
        st.session_state.telemetry = {"risk_score": 0, "overall_risk_level": "Pending", "flags": [], "requires_more_info": True, "has_evaluated": False}

        try:
            response = requests.post("http://127.0.0.1:8000/chat", 
            json = {"history": st.session_state.messages}
            )

            print(f"DEBUG STATUS CODE: {response.status_code}")
            print(f"DEBUG RESPONSE TEXT: {response.text}")


            if response.status_code == 200:
                results = response.json()


                agent_reply = results.get("agent_message", "Analysis processed.")
                st.session_state.messages.append({"role": "assistant", "content": agent_reply})
                st.session_state.telemetry = results
                st.session_state.telemetry["has_evaluated"] = True
                st.rerun()
            else:
                st.error("Engine Communication Error: Backend API returned a faulty status code.")
        except requests.exceptions.ConnectionError:
            st.error("Infrastructure Offline: Please make sure your FastAPI Uvicorn server is running on port 8000.")
with col2:
    st.subheader("📋 Document Ingestion")

    uploaded_file = st.file_uploader("Upload a Job Description or Resume (PDF)", type = ["pdf"])
    
    if uploaded_file is not None:
        if st.button("🚀 Run Document Compliance Audit"):
            with st.spinner("Processing local vector parsing..."):
                extracted_text = extract_text_from_pdf(uploaded_file)
            
            if extracted_text:
                st.session_state.messages.append({"role": "user", "content": f"[PDF Document Uploaded]:\n\n{extracted_text}"})
                
                st.session_state.telemetry = {"risk_score": 0, "overall_risk_level": "Pending", "flags": [], "requires_more_info": True, "has_evaluated": False}

                try:
                    response = requests.post("http://127.0.0.1:8000/chat", 
                        json = {"history": st.session_state.messages}
                    )
                    if response.status_code == 200:
                        results = response.json()
                        st.session_state.messages.append({"role": "assistant", "content": results.get("agent_message")})
                        st.session_state.telemetry = results
                        st.session_state.telemetry["has_evaluated"] = True
                        st.success("Document analyzed successfully!")
                        st.rerun()
                    else:
                        st.error("Backend Error parsing document.")
                except requests.exceptions.ConnectionError:
                    st.error("FastAPI Infrastructure Offline.")

    st.markdown("---")
    st.subheader("📊 Telemetry Metrics")
    tel = st.session_state.telemetry
    
    score = tel.get("risk_score", 0)
    level = tel.get("overall_risk_level", "Pending")
    more_info = tel.get("requires_more_info", False)
    has_evaluated = tel.get("has_evaluated", False)
    
    if not has_evaluated or level == "Pending":
        st.info("📊 System Ready: Awaiting a document upload or conversational input to begin telemetry tracking.")
    elif level in ["Critical", "High"]:
        st.error(f"🚨 Status: {level} Risk ({score}/100)")
    elif level == "Medium":
        st.warning(f"⚠️ Status: {level} Risk ({score}/100)")
    elif level == "Safe":
        st.success(f"✅ Status: {level} / Compliant ({score}/100)")
    else:
        st.info("📊 System Ready: Awaiting context data input.")

    if has_evaluated and level != "Pending" and more_info and score == 0:
        st.info("🔄 Status: Awaiting Details (Gathering clearer context from dialogue)")
    
        
    flags = tel.get("flags", [])
    if flags:
        st.markdown(f"### Highlighted Risk Metrics ({len(flags)})")
        user_inputs = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
        if user_inputs:
            annotated_html = highlight_text(user_inputs[-1], flags)
            st.markdown(f"<div style='border: 1px solid #ddd; padding: 10px; border-radius: 5px; max-height: 250px; overflow-y: auto;'>{annotated_html}</div>", unsafe_allow_html=True)

        for idx, flag in enumerate(flags):
            with st.expander(f"Violation #{idx+1}: '{flag.get('matched_text')}'"):
                st.markdown(f"**Reason:** {flag.get('reason')}")
                st.info(f"💡 **Suggested Correction:** {flag.get('suggested_alternative')}")
        
    st.markdown("---")
    if st.button("🔄 Clear Analysis & Reset Session"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! Paste a job profile description, upload a PDF resume, or summarize your role..."}
        ]
        st.session_state.telemetry = {
            "risk_score": 0, "overall_risk_level": "Pending", "flags": [], "requires_more_info": True, "has_evaluated": False
        }
        st.rerun()