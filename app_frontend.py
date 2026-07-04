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

        try:
            response = requests.post("http://127.0.0.1:8000/chat", 
            json = {"history": st.session_state.messages}
            )
            if response.status_code == 200:
                results = response.json()

                agent_reply = results.get("agent_message", "Analysis processed.")
                st.session_state.messages.append({"role": "assistant", "content": agent_reply})
                with st.chat_message("assistant"):
                    st.write(agent_reply)

                st.session_state.telemetry = results
                st.rerun()
            else:
                st.error("Engine Communication Error: Backend API returned a faulty status code.")
        except requests.exceptions.ConnectionError:
            st.error("Infrastructure Offline: Please make sure your FastAPI Uvicorn server is running on port 8000.")
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