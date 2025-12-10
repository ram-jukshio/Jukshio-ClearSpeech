import streamlit as st
import requests
import time
import textwrap
from io import BytesIO

# Try to import mutagen for audio duration checks
try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

# --- Page Config ---
st.set_page_config(page_title="ClearSpeech | Jukshio", layout="wide", page_icon="🎙️")

# --- Custom CSS for Polish ---
st.markdown("""
    <style>
    /* Subtle footer */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f8f9fa;
        color: #6c757d;
        text-align: center;
        padding: 10px;
        font-size: 13px;
        border-top: 1px solid #e9ecef;
        z-index: 100;
    }
    .main-content {
        padding-bottom: 80px;
    }
    /* Metric label styling */
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #666;
    }
    /* Remove extra top padding */
    .block-container {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Header ---
st.title("🎙️ Jukshio's ClearSpeech")
st.markdown("Automated Audio Transcription & Translation Service")
st.divider()

# --- Main Layout ---
# We use a container to keep inputs organized together
with st.container():
    col_input, col_details = st.columns([1, 1.5], gap="large")

    with col_input:
        st.subheader("Upload Audio")
        audio_file = st.file_uploader(
            "Supported formats: WAV, MP3, M4A", 
            type=['wav', 'mp3', 'm4a'], 
            label_visibility="visible"
        )

    # --- File Details & Settings (Only visible if file uploaded) ---
    with col_details:
        if audio_file:
            st.subheader("File Details & Settings")
            
            # 1. Calculate Duration
            duration_str = "Unknown"
            audio_duration_secs = 0
            
            if MutagenFile:
                try:
                    audio_file.seek(0)
                    meta = MutagenFile(audio_file)
                    if meta is not None and meta.info.length:
                        audio_duration_secs = meta.info.length
                        mins = int(audio_duration_secs // 60)
                        secs = int(audio_duration_secs % 60)
                        duration_str = f"{mins:02d}:{secs:02d}"
                    audio_file.seek(0)
                except Exception:
                    duration_str = "Error reading metadata"

            # 2. Display Metrics cleanly
            m1, m2 = st.columns(2)
            m1.metric("File Size", f"{audio_file.size / 1024:.2f} KB")
            m2.metric("Duration", duration_str)

            # 3. Warning Logic
            if audio_duration_secs > 300:
                st.warning("⚠️ **Note:** Audio exceeds 5 minutes. Processing might be slower.")

            # 4. Settings Controls
            st.markdown("---") # Thin separator
            c1, c2, c3 = st.columns(3)
            with c1:
                source_lang = st.text_input("Source Language", value="hi", help="hi for hindi, en for english, te for telugu, etc.")
            with c2:
                # Vertical alignment spacer
                st.write("") 
                st.write("")
                chunking = st.toggle("Smart Chunking", value=True, help="If you want to transcribe the audio in chunks, you can enable this.")
            with c3:
                model_choice = st.selectbox(
                    "Translation Model",
                    options=["200M SLM (Fast)", "1B Model (Standard)"],
                    help="200M SLM is the fast model and 1B Model is the standard model."
                )
        else:
            # Placeholder content to keep layout balanced when empty
            st.info("👈 Please upload a file to configure settings.")

# --- Processing Logic ---
if audio_file:
    st.markdown("") # Spacer
    if st.button("Start Processing🖱️", type="secondary", use_container_width=True, help="Click this button to start the transcription and translation process."):
        
        # Determine Model Label early for logs
        is_fast_model = "200M" in model_choice
        model_label = "200M SLM" if is_fast_model else "1B Standard"
        translate_endpoint = "https://los-audio-service-dev.soham.ai/audio/text-translate-200m" if is_fast_model else "https://los-audio-service-dev.soham.ai/audio/text-translate"

        # --- Logs Area ---
        logs_expander = st.expander("📝 View System Logs", expanded=False)
        log_placeholder = logs_expander.empty()
        session_logs = []

        def log(msg):
            timestamp = time.strftime("%H:%M:%S")
            session_logs.append(f"[{timestamp}] {msg}")
            log_placeholder.code("\n".join(session_logs), language="bash")

        def handle_error(resp):
            code = resp.status_code
            text = resp.text[:300]
            log(f"ERROR {code}: {text}")
            
            if code in [403, 404]:
                st.error(f"❌ **Connection Error ({code}):** Endpoint unreachable. Please contact the developer.")
            elif code >= 500:
                st.error(f"⚠️ **Server Error ({code}):** Service unavailable. Please try again in 5 minutes.")
            else:
                st.error(f"❌ Error: {text}")
            return False

        # --- Execution ---
        try:
            log("Initializing...")
            
            # Step 1: Transcribe
            with st.spinner("Step 1/2: Transcribing Audio..."):
                url_stt = "https://los-audio-service-dev.soham.ai/audio/transcript"
                log(f"Sending to STT: {url_stt}")
                
                audio_file.seek(0)
                files = {"audio": (audio_file.name, audio_file.getvalue(), audio_file.type)}
                payload_stt = {"source_lang": source_lang, "chunking": str(chunking).lower()}
                
                resp_stt = requests.post(url_stt, files=files, data=payload_stt)
                
                if resp_stt.status_code != 200:
                    handle_error(resp_stt)
                    st.stop() # Stop execution on failure
                
                data_stt = resp_stt.json()
                transcript = data_stt.get("transcript", "")
                process_time = data_stt.get("time_s", 0)
                log(f"Transcription Complete. Time: {process_time}s")

            # Step 2: Translate
            with st.spinner(f"Step 2/2: Translating ({model_label})..."):
                log(f"Sending to Translator: {translate_endpoint}")
                
                payload_trans = {"text": transcript}
                resp_trans = requests.post(translate_endpoint, data=payload_trans)
                
                if resp_trans.status_code != 200:
                    handle_error(resp_trans)
                    st.stop()

                data_trans = resp_trans.json()
                translated_text = data_trans.get("translated_text", "")
                log("Translation Complete.")

            # --- Success UI ---
            st.divider()
            st.success("✅ Processing Complete")

            # Dual Pane View
            col_orig, col_trans = st.columns(2)
            
            with col_orig:
                st.caption("ORIGINAL TRANSCRIPT")
                st.text_area("Original", transcript, height=300, label_visibility="collapsed")
            
            with col_trans:
                st.caption("ENGLISH TRANSLATION")
                st.text_area("Translated", translated_text, height=300, label_visibility="collapsed")

            # Download Section
            report_content = textwrap.dedent(f"""
                # ClearSpeech Report
                **File:** {audio_file.name} | **Duration:** {duration_str} | **Model:** {model_label}
                
                ## Original Transcript ({source_lang})
                {transcript}
                
                ## English Translation
                {translated_text}
            """).strip()

            st.download_button(
                label="⬇️ Download Report (.md)",
                data=report_content,
                file_name=f"Report_{audio_file.name}.md",
                mime="text/markdown",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Critical Error: {str(e)}")
            log(f"EXCEPTION: {str(e)}")

# --- Footer ---
st.markdown("""
    <div class="footer">
        Developed by <a href="mailto:ramarao.bikkina@jukshio.com">Ram Bikkina</a> | Powered by <b>Jukshio</b>
    </div>
    """, unsafe_allow_html=True)