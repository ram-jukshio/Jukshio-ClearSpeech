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

# --- Custom CSS ---
st.markdown("""
    <style>
    /* Footer Styling */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f8f9fa;
        color: ivory;
        text-align: center;
        padding: 10px;
        font-size: 13px;
        border-top: 1px solid #e9ecef;
        z-index: 100;
    }
    .main-content {
        padding-bottom: 80px;
    }
    /* Tab Styling adjustment for better visibility */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #40e0d0;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E34234;
        color: black;
        border-bottom: 2px solid #E34234;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Shared Helper Functions ---

def get_audio_details(uploaded_file):
    """Returns formatted duration string and raw seconds."""
    duration_str = "Unknown"
    seconds = 0
    if MutagenFile and uploaded_file:
        try:
            uploaded_file.seek(0)
            meta = MutagenFile(uploaded_file)
            if meta is not None and meta.info.length:
                seconds = meta.info.length
                mins = int(seconds // 60)
                sec = int(seconds % 60)
                duration_str = f"{mins:02d}:{sec:02d}"
            uploaded_file.seek(0)
        except Exception:
            duration_str = "Error"
    return duration_str, seconds

def render_logs(log_container, log_list):
    """Updates the log container."""
    log_container.code("\n".join(log_list), language="bash")

def handle_api_error(resp, log_append_func):
    """Standardized error handling."""
    code = resp.status_code
    text = resp.text[:300]
    log_append_func(f"ERROR {code}: {text}")
    
    if code in [403, 404]:
        st.error(f"❌ **Connection Error ({code}):** Endpoint unreachable. Contact Developer.")
    elif code >= 500:
        st.error(f"⚠️ **Server Error ({code}):** Service unavailable. Try again later.")
    else:
        st.error(f"❌ Error: {text}")

# --- Header ---
st.title("🎙️ Jukshio's ClearSpeech")
st.markdown("Automated Audio Transcription & Translation Service")

# --- Tabs ---
tab_main, tab_transcript, tab_translate = st.tabs([
    "🚀 Main App (Full Flow)", 
    "📝 Transcript Only", 
    "🌎 Translation Only"
])

# ==========================================
# TAB 1: MAIN APP (Audio -> Transcript -> Translate)
# ==========================================
with tab_main:
    st.caption("End-to-end processing: Upload audio, get transcript and translation.")
    
    with st.container():
        c_in, c_det = st.columns([1, 1.5], gap="large")

        with c_in:
            st.subheader("Upload Audio")
            main_audio = st.file_uploader(
                "Supported: WAV, MP3, M4A", 
                type=['wav', 'mp3', 'm4a'], 
                key="main_audio_uploader"
            )

        with c_det:
            if main_audio:
                st.subheader("Settings")
                dur_str, dur_sec = get_audio_details(main_audio)
                
                m1, m2 = st.columns(2)
                m1.metric("File Size", f"{main_audio.size/1024:.2f} KB")
                m2.metric("Duration", dur_str)
                
                if dur_sec > 300:
                    st.warning("⚠️ Audio > 5 mins. May be slow.")

                st.markdown("---")
                rc1, rc2, rc3 = st.columns(3)
                main_lang = rc1.text_input("Source Lang", value="hi", key="main_lang")
                with rc2:
                    st.write("")
                    st.write("")
                    main_chunk = st.toggle("Chunking", value=True, key="main_chunk")
                with rc3:
                    main_model = st.selectbox(
                        "Model", 
                        ["200M SLM (Fast)", "1B Model (Standard)"],
                        key="main_model"
                    )
            else:
                st.info("👈 Upload a file to start.")

    if main_audio:
        st.markdown("")
        if st.button("🚀 Start Full Process", type="primary", use_container_width=True, key="main_btn"):
            is_fast = "200M" in main_model
            url_trans = "https://los-audio-service-dev.soham.ai/audio/text-translate-200m" if is_fast else "https://los-audio-service-dev.soham.ai/audio/text-translate"
            model_lbl = "200M SLM" if is_fast else "1B Standard"

            logs_exp = st.expander("📝 Logs", expanded=False)
            log_box = logs_exp.empty()
            sess_logs = []

            def log_main(msg):
                sess_logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                render_logs(log_box, sess_logs)

            try:
                log_main("Initializing...")
                with st.spinner("Step 1: Transcribing..."):
                    main_audio.seek(0)
                    files = {"audio": (main_audio.name, main_audio.getvalue(), main_audio.type)}
                    payload = {"source_lang": main_lang, "chunking": str(main_chunk).lower()}
                    
                    r1 = requests.post("https://los-audio-service-dev.soham.ai/audio/transcript", files=files, data=payload)
                    
                    if r1.status_code != 200:
                        handle_api_error(r1, log_main)
                        st.stop()
                    
                    d1 = r1.json()
                    transcript = d1.get("transcript", "")
                    log_main(f"Transcribed. Time: {d1.get('time_s')}s")

                with st.spinner(f"Step 2: Translating ({model_lbl})..."):
                    r2 = requests.post(url_trans, data={"text": transcript})
                    if r2.status_code != 200:
                        handle_api_error(r2, log_main)
                        st.stop()
                    
                    d2 = r2.json()
                    translated = d2.get("translated_text", "")
                    log_main("Translation Complete.")

                st.success("✅ Success")
                
                col_a, col_b = st.columns(2)
                col_a.text_area("Original", transcript, height=300, key="main_res_orig")
                col_b.text_area("Translated", translated, height=300, key="main_res_trans")

                final_md = f"# Report\n**File:** {main_audio.name}\n\n## Original\n{transcript}\n\n## Translation\n{translated}"
                st.download_button("⬇️ Download Report", final_md, "report.md", key="main_dl")

            except Exception as e:
                st.error(f"Error: {e}")

# ==========================================
# TAB 2: TRANSCRIPT ONLY
# ==========================================
with tab_transcript:
    st.caption("Convert Audio to Text (No Translation).")
    
    tc1, tc2 = st.columns([1, 1.5])
    with tc1:
        trans_audio = st.file_uploader("Upload Audio", type=['wav', 'mp3', 'm4a'], key="trans_audio")
    
    with tc2:
        if trans_audio:
            dur_str_t, dur_sec_t = get_audio_details(trans_audio)
            st.metric("Duration", dur_str_t)
            
            t_set1, t_set2 = st.columns(2)
            trans_lang = t_set1.text_input("Source Lang", value="hi", key="trans_lang")
            trans_chunk = t_set2.toggle("Chunking", value=True, key="trans_chunk")
            
            if st.button("📝 Get Transcript", type="primary", key="trans_btn"):
                log_exp_t = st.expander("Logs", expanded=False)
                log_box_t = log_exp_t.empty()
                logs_t = []

                def log_tr(msg):
                    logs_t.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                    render_logs(log_box_t, logs_t)

                try:
                    log_tr("Sending to /audio/transcript...")
                    with st.spinner("Transcribing..."):
                        trans_audio.seek(0)
                        files = {"audio": (trans_audio.name, trans_audio.getvalue(), trans_audio.type)}
                        payload = {"source_lang": trans_lang, "chunking": str(trans_chunk).lower()}
                        
                        r_t = requests.post("https://los-audio-service-dev.soham.ai/audio/transcript", files=files, data=payload)
                        
                        if r_t.status_code != 200:
                            handle_api_error(r_t, log_tr)
                        else:
                            d_t = r_t.json()
                            txt_res = d_t.get("transcript", "")
                            meta_model = d_t.get("model_used", "N/A")
                            meta_time = d_t.get("time_s", "N/A")
                            
                            log_tr(f"Success. Model: {meta_model}, Time: {meta_time}s")
                            st.success("✅ Transcript Generated")
                            
                            st.text_area("Transcript", txt_res, height=400, key="trans_out")
                            st.download_button("⬇️ Download .txt", txt_res, "transcript.txt", key="trans_dl")

                except Exception as e:
                    st.error(f"Error: {e}")

# ==========================================
# TAB 3: TRANSLATION ONLY
# ==========================================
with tab_translate:
    st.caption("Translate existing text into English.")
    
    col_txt, col_cfg = st.columns([2, 1])
    
    with col_txt:
        input_text = st.text_area("Paste Text Here", height=200, placeholder="Enter Hindi text here...", key="tl_input")
    
    with col_cfg:
        st.write("Settings")
        tl_model = st.selectbox(
            "Model", 
            ["200M SLM (Fast)", "1B Model (Standard)"],
            key="tl_model"
        )
        st.info("Target Language: English (Default)")
    
    if st.button("🌎 Translate Text", type="primary", key="tl_btn"):
        if not input_text.strip():
            st.warning("Please enter some text.")
        else:
            is_fast_tl = "200M" in tl_model
            url_tl = "https://los-audio-service-dev.soham.ai/audio/text-translate-200m" if is_fast_tl else "https://los-audio-service-dev.soham.ai/audio/text-translate"
            
            logs_exp_tl = st.expander("Logs", expanded=False)
            log_box_tl = logs_exp_tl.empty()
            logs_tl = []

            def log_transl(msg):
                logs_tl.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                render_logs(log_box_tl, logs_tl)

            try:
                log_transl(f"Sending to {url_tl}...")
                with st.spinner("Translating..."):
                    r_tl = requests.post(url_tl, data={"text": input_text})
                    
                    if r_tl.status_code != 200:
                        handle_api_error(r_tl, log_transl)
                    else:
                        d_tl = r_tl.json()
                        res_tl = d_tl.get("translated_text", "")
                        
                        log_transl("Success.")
                        st.success("✅ Translation Generated")
                        
                        st.text_area("English Output", res_tl, height=200, key="tl_out")
                        st.download_button("⬇️ Download Text", res_tl, "translation.txt", key="tl_dl")
            except Exception as e:
                st.error(f"Error: {e}")

# --- Footer ---
st.markdown("""
    <div class="footer">
        Developed by <a href="mailto:ramarao.bikkina@jukshio.com">Ram Bikkina</a> | Powered by <b>Jukshio</b>
    </div>
    """, unsafe_allow_html=True)