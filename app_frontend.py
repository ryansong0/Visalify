import streamlit as st
import requests

st.set_page_config(page_title = "VisaGuard Compliance AI", page_icon = "🛡️", layout = "wide")

st.title("🛡️ VisaGuard: Compliance Analysis Dashboard")
st.markdown("Evaluate job descriptions against TN Visa occupational restrictions using NLP context-awareness.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Paste a job profile description or summarize your role, and I will cross-reference it against 8 CFR regulations."}
    ]
if "telemetry" not in st.session_state:
    st.session_state.telemetry = {
        "risk_score": 0, "overall_risk_level": "Safe", "flags": [], "requires_more_info": True
    }

def render_highlighted_text(text, flags):
    if not flags:
        st.write(text)
        return

    sorted_flags = sorted(flags, key = lambda x: x["start"])

    annotated_fragments = []
    current_idx = 0

    for flag in sorted_flags:
        start = flag["start"]
        end = flag["end"]
        term = flag["matched_text"]
        severity = flag["severity"].upper()

        color_map = {"CRITICAL": "#ff4b4b", "HIGH": "#ffa500", "MEDIUM": "#ffeb3b", "LOW": "#f0f2f6"}
        bg_color = color_map.get(severity, "#f0f2f6")
        text_color = "#000000" if severity in ["MEDIUM", "LOW"] else "#ffffff"

        if start > current_idx:
            annotated_fragments.append(text[current_idx: start])

        annotated_fragments.append((term, f"{severity}", bg_color, text_color))
        current_idx = end

    if current_idx < len(text):
        annotated_fragments.append(text[current_idx:])

    annotated_text(*annotated_fragments)


col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("📋 Input Job Description")
    job_text = st.text_area(
        "Paste the raw role responsibilities below:", 
        height = 300, 
        placeholder = "e.g., You will manage a team of engineers and oversee our code deployment pipelines..."
    )
    analyze_button = st.button("Run Compliance Audit", type = "primary", use_container_width = True)

    if analyze_button and job_text:
        st.subheader("🔍 Contextual Analysis & Highlights")
        try:
            response = requests.post("http://127.0.0.1:8000/analyze", json={"job_description": job_text})
            if response.status_code == 200:
                results = response.json()
                render_highlighted_text(job_text, results.get("flags", []))
        except requests.exceptions.ConnectionError:
            pass

with col2:
    st.subheader("📊 Telemetry Metrics")
    
    if analyze_button and job_text:
        try:
            response = requests.post("http://127.0.0.1:8000/analyze", json = {"job_description": job_text})
            
            if response.status_code == 200:
                results = response.json()
                
                score = results.get("risk_score", 0)
                level = results.get("overall_risk_level", "Safe")
                
                if level in ["Critical", "High"]:
                    st.error(f"Overall Status: {level} Risk ({score}/100)")
                elif level == "Medium":
                    st.warning(f"Overall Status: {level} Risk ({score}/100)")
                else:
                    st.success(f"Overall Status: {level} / Compliant ({score}/100)")
                
                flags = results.get("flags", [])
                if flags:
                    st.markdown(f"### Found {len(flags)} Risk Factors:")
                    for idx, flag in enumerate(flags):
                        with st.expander(f"⚠️ Flag #{idx+1}: '{flag['matched_text']}' ({flag['severity'].upper()})"):
                            st.markdown(f"**Reason:** {flag['reason']}")
                            st.info(f"💡 **Suggested Rephrasing:** {flag['suggested_alternative']}")
                else:
                    st.balloons()
                    st.success("✨ Zero compliance regularities or structural risks detected!")
            else:
                st.error("Engine Communication Error: Backend API returned a faulty status code.")
        except requests.exceptions.ConnectionError:
            st.error("Infrastructure Offline: Please make sure your FastAPI Uvicorn server is running on port 8000.")
    else:
        st.info("Awaiting input text. Input a description and click analyze to populate compliance telemetry.")