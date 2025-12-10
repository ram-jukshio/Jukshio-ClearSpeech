import streamlit as st
import requests
import time
import textwrap

# --- Page Config ---
st.set_page_config(page_title="Jukshio's ClearSpeech", layout="wide")

# --- Custom CSS for Footer and Layout ---
st.markdown("""
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f0f2f6;
        color: #333;
        text-align: center;
        padding: 10px;
        font-size: 14px;
        z-index: 100;
        border-top: 1px solid #ddd;
    }
    .main-container {
        padding-bottom: 60px; /* Space for footer */
    }
    </style>
    """, unsafe_allow_html=True)

# --- Header ---
st.title("🎙️ Jukshio's ClearSpeech")

# --- Configuration Section (Main Page) ---
# Grouping inputs into columns for a minimal look
col_file, col_conf = st.columns([1, 1.5])

with col_file:
    # st.subheader("1. Upload")
    audio_file = st.file_uploader("Select Audio File", type=['wav', 'mp3', 'm4a'], label_visibility="collapsed")
    if audio_file:
        st.caption(f"📁 **{audio_file.name}** ({audio_file.size / 1024:.2f} KB)")

with col_conf:
    # st.subheader("2. Settings")
    c1, c2, c3 = st.columns(3)
    with c1:
        source_lang = st.text_input("Language Code", value="hi")
    with c2:
        # Toggle needs a label, keeping it short
        st.write("") # Spacer to align with text input
        chunking = st.toggle("Chunking", value=True)
    with c3:
        model_choice = st.selectbox(
            "Translation Model",
            options=[ "200M SLM Model (Fast)", "1B Model (Standard)"]
        )

st.divider()

# --- Helper Function for Error Handling ---
def handle_api_error(response, log_func):
    """Parses status codes and provides user-friendly actionable feedback."""
    code = response.status_code
    error_text = response.text[:200] + "..." if len(response.text) > 200 else response.text
    
    # Clean up HTML from error text for logs if it's a standard nginx error
    if "<html>" in error_text:
        log_func(f"Error {code}: Server returned HTML response (likely Nginx/Proxy error).")
    else:
        log_func(f"Error {code}: {error_text}")

    if code in [404, 403]:
        st.error(f"❌ **Access Error ({code}):** The endpoint is unreachable or permission is denied.")
        st.info("💡 **Tip:** Please contact the developer to check API endpoint URLs and permissions.")
    elif code in [502, 503, 504]:
        st.error(f"⚠️ **Server Error ({code}):** The service is temporarily unavailable.")
        st.warning("💡 **Suggestion:** The server might be down or restarting. Please wait a couple of minutes and try again.")
    else:
        st.error(f"❌ **Unexpected Error ({code}):** {error_text}")

# --- Main Processing ---
if st.button("🚀 Start Processing", type="primary", use_container_width=True):
    if not audio_file:
        st.warning("Please upload an audio file first.")
    else:
        # Logs Expander
        logs_container = st.expander("📝 System Logs", expanded=True)
        log_display = logs_container.empty()
        session_logs = []

        def log(msg):
            timestamp = time.strftime("%H:%M:%S")
            entry = f"[{timestamp}] {msg}"
            session_logs.append(entry)
            log_display.code("\n".join(session_logs), language="bash")
            print(entry)

        try:
            log("Initializing process...")
            
            # --- Request 1: Transcription ---
            url_1 = "https://los-audio-service-dev.soham.ai/audio/transcript"
            log(f"Step 1: Transcription Request -> {url_1}")
            
            audio_file.seek(0)
            files = {"audio": (audio_file.name, audio_file.getvalue(), audio_file.type)}
            payload_1 = {"source_lang": source_lang, "chunking": str(chunking).lower()}
            
            resp_1 = requests.post(url_1, files=files, data=payload_1)
            
            if resp_1.status_code != 200:
                handle_api_error(resp_1, log)
            else:
                data_1 = resp_1.json()
                transcript = data_1.get("transcript", "")
                audio_duration = data_1.get("time_s", 0)
                stt_model_name = data_1.get("model_used", "Unknown")
                
                log(f"Transcript success. Duration: {audio_duration}s")
                
                # --- Request 2: Translation ---
                if "200M" in model_choice:
                    url_2 = "https://los-audio-service-dev.soham.ai/audio/text-translate-200m"
                    model_label = "200M SLM"
                else:
                    url_2 = "https://los-audio-service-dev.soham.ai/audio/text-translate"
                    model_label = "1B Model"

                log(f"Step 2: Translation Request ({model_label}) -> {url_2}")
                
                payload_2 = {"text": transcript}
                resp_2 = requests.post(url_2, data=payload_2)
                
                if resp_2.status_code != 200:
                    handle_api_error(resp_2, log)
                else:
                    data_2 = resp_2.json()
                    translated = data_2.get("translated_text", "")
                    log("Translation success. Process Complete.")
                    
                    st.divider()
                    
                    # --- Metrics ---
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Audio Duration", f"{audio_duration}s")
                    m2.metric("Transcript Len", f"{len(transcript)} chars")
                    m3.metric("Translation Len", f"{len(translated)} chars")
                    m4.metric("Model", model_label)
                    
                    st.divider()

                    # --- Output Text Areas ---
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader("Original Transcript")
                        st.text_area("Source", transcript, height=300)
                    with c2:
                        st.subheader("English Translation")
                        st.text_area("Target", translated, height=300)

                    # --- Final Markdown Report ---
                    st.subheader("Final Report")
                    
                    # Using textwrap.dedent to fix indentation issues in the output string
                    final_report = textwrap.dedent(f"""
                        **Filename:** {audio_file.name}

                        **Original Transcript:**
                        {transcript}

                        **Translation:**
                        {translated}
                    """).strip()
                    
                    st.code(final_report, language="markdown")
                    
                    st.download_button(
                        label="⬇️ Download Report",
                        data=final_report,
                        file_name=f"{audio_file.name}_report.md",
                        mime="text/markdown",
                        type="secondary"
                    )

        except Exception as e:
            st.error(f"Critical Application Error: {str(e)}")
            log(f"EXCEPTION: {str(e)}")

# --- Footer ---
st.markdown("""
    <div class="footer">
        Developed by <a href="mailto:ramarao.bikkina@jukshio.com">Ram Bikkina</a>. 
        Powered by and all Rights Reserved Under <b>Jukshio</b>.
    </div>
    """, unsafe_allow_html=True)