import streamlit as st
import os
import sqlite3
import hashlib
import google.generativeai as genai
from PIL import Image
from datetime import datetime
import time
import requests
from streamlit_lottie import st_lottie

# -----------------------------------------------------------------------------
# 0. CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Medivio | Medical Clarity", 
    page_icon="⚕️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Fix Upload
config_dir = ".streamlit"
if not os.path.exists(config_dir): os.makedirs(config_dir)
with open(os.path.join(config_dir, "config.toml"), "w") as f:
    f.write("[server]\nenableXsrfProtection=false\nenableCORS=false\nmaxUploadSize=200\n")

# API Setup
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("⚠️ API Key Missing. Add GOOGLE_API_KEY to Secrets.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
# FIXED: Use the correct model name
model = genai.GenerativeModel('gemini-1.5-pro')

# -----------------------------------------------------------------------------
# 1. DATABASE SYSTEM
# -----------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect('medivio_final_v10.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, joined_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, type TEXT, summary TEXT, risk_level TEXT, date TEXT)''')
    conn.commit()
    conn.close()

def hash_pass(password): return hashlib.sha256(str.encode(password)).hexdigest()

def register_user(email, password):
    conn = sqlite3.connect('medivio_final_v10.db')
    try:
        conn.execute("INSERT INTO users VALUES (?, ?, ?)", (email, hash_pass(password), datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def login_user(email, password):
    conn = sqlite3.connect('medivio_final_v10.db')
    data = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, hash_pass(password))).fetchall()
    conn.close()
    return data

def add_history(email, type, summary, risk):
    conn = sqlite3.connect('medivio_final_v10.db')
    conn.execute("INSERT INTO history (email, type, summary, risk_level, date) VALUES (?, ?, ?, ?, ?)", 
                 (email, type, summary[:100], risk, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def get_user_stats(email):
    conn = sqlite3.connect('medivio_final_v10.db')
    history = conn.execute("SELECT type, date FROM history WHERE email=? ORDER BY id DESC LIMIT 10", (email,)).fetchall()
    last_scan = history[0][1] if history else "New User"
    conn.close()
    return history, last_scan

init_db()

# -----------------------------------------------------------------------------
# 2. SESSION STATE & CSS
# -----------------------------------------------------------------------------
if 'page' not in st.session_state: st.session_state.page = 'landing'
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_email' not in st.session_state: st.session_state.user_email = ""
if 'analysis_result' not in st.session_state: st.session_state.analysis_result = None
if 'analysis_images' not in st.session_state: st.session_state.analysis_images = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap');
    
    .stApp {
        background: radial-gradient(circle at 50% 0%, #1e293b 0%, #020617 100%);
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #f8fafc;
    }

    /* Clean Card Style */
    .stContainer {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 20px;
    }
    
    /* Result Cards */
    .result-card {
        background: #0f172a;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        border-left: 4px solid #334155;
    }

    div.stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white; border: none; border-radius: 8px; font-weight: 600;
        padding: 12px 20px; width: 100%; transition: transform 0.2s;
    }
    div.stButton > button:hover { transform: scale(1.02); }

    .chat-user { background: #334155; padding: 12px; border-radius: 12px 12px 0 12px; margin-bottom: 10px; text-align: right; margin-left: 20%; }
    .chat-ai { background: #1e293b; border: 1px solid #3b82f6; padding: 12px; border-radius: 12px 12px 12px 0; margin-bottom: 10px; text-align: left; margin-right: 20%; }

    .history-item {
        font-size: 0.9rem;
        padding: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #e2e8f0;
    }
    .history-date { color: #64748b; font-size: 0.7rem; margin-left: 10px;}

    #MainMenu, footer, header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. LOGIC
# -----------------------------------------------------------------------------
def get_gemini_analysis(images, text_context, mode):
    role = "a helpful medical assistant"
    if mode == "Radiologist Expert": role = "a senior radiologist. Use precise technical terminology."
    elif mode == "Simple Explanation": role = "a compassionate doctor explaining to a patient. Use simple analogies."
    
    base_instruction = f"Analyze these medical images and the following patient context: '{text_context}'." if images else f"Analyze the following patient symptoms/notes: '{text_context}'."

    prompt = [
        f"You are Medivio, {role}.",
        base_instruction,
        "Strictly format your output into 5 parts separated by '|||'.",
        "Part 1: A Short, Descriptive Title (Max 4 words, e.g. 'Chest X-Ray Normal', 'Flu Symptoms')",
        "Part 2: Clinical Findings (What is seen or described?)",
        "Part 3: Risk Assessment (Low/Medium/High)",
        "Part 4: Severity Score (Just the word: Low, Medium, or High)",
        "Part 5: Recommended Actions",
        "Do not use Markdown headers. Just raw text for each section."
    ]
    
    content = prompt + images if images else prompt
    try:
        response = model.generate_content(content)
        return response.text
    except Exception as e:
        return f"Error|||System Error|||Low|||Low|||{str(e)}"

def chat_with_scan(user_query):
    prev_findings = st.session_state.analysis_result
    images = st.session_state.analysis_images
    context_prompt = [
        "You are Medivio. You have ALREADY analyzed this patient's scan.",
        f"Here is your previous analysis summary: {prev_findings}",
        "The user is asking a follow-up question. Do NOT re-analyze the whole image from scratch unless asked.",
        "Answer the specific question based on the findings above.",
        f"User Question: {user_query}"
    ]
    full_content = context_prompt + images if images else context_prompt
    try:
        response = model.generate_content(full_content)
        return response.text
    except: return "I couldn't process that. Please try again."

def go_to(page):
    st.session_state.page = page
    st.rerun()

def do_sign_out():
    st.session_state.logged_in=False
    st.session_state.analysis_result=None
    st.session_state.analysis_images=[]
    st.session_state.chat_history=[]
    st.session_state.auth_mode = 'login'
    go_to('landing')

# -----------------------------------------------------------------------------
# 4. PAGES
# -----------------------------------------------------------------------------

# --- LANDING ---
def show_landing():
    c1, c2 = st.columns([1, 6])
    with c1: st.markdown("<h3 style='color:#3b82f6; margin:0;'>MEDIVIO</h3>", unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1.3, 1])
    with col1:
        st.markdown("<h1 style='font-size: 4rem; line-height: 1.1; margin-bottom:20px;'>Upload your medical report.<br><span style='background: -webkit-linear-gradient(0deg, #3b82f6, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>Get answers in seconds.</span></h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#94a3b8; font-size:1.2rem; line-height:1.6;'>AI that translates scans, labs, and clinical notes into language you understand.</p>", unsafe_allow_html=True)
        
        b1, b2 = st.columns([1,1.5])
        with b1: 
            if st.button("Start Now"): go_to('login')
        with b2: 
            if st.button("How it Works"): go_to('about')

    with col2:
        st.markdown("""
        <div style='text-align:center; animation: float 6s ease-in-out infinite;'>
            <div style='font-size: 7rem;'>🧬</div>
        </div>
        """, unsafe_allow_html=True)

    # PURE MARKDOWN FOOTER (No HTML Tags)
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    st.divider()
    st.caption("Disclaimer: Medivio is an AI-powered analysis tool. It does not provide medical diagnosis. Always consult a qualified healthcare professional for medical advice.")

# --- ABOUT (CLEAN TEXT ONLY) ---
def show_about():
    if st.button("← Back"): go_to('landing')
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.title("About Medivio")
    
    st.markdown("""
    Medivio is an intelligent interface for your health. It acts as a secure bridge between 
    complex medical data—like X-Rays, MRI scans, and doctor's notes—and clear human understanding.
    """)
    
    st.divider()
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Our Mission")
        st.markdown("""
        To democratize access to medical information. We believe everyone should be able to 
        understand their own health records instantly, without waiting days for an appointment.
        """)
        
    with col_b:
        st.subheader("Technology")
        st.markdown("""
        Medivio leverages **Google Gemini 1.5 Pro**, a multimodal AI model capable of processing 
        vision (images) and text simultaneously. This allows for context-aware analysis that 
        mimics the reasoning of a medical professional.
        """)
        
    st.divider()
    
    st.subheader("How It Works")
    f1, f2, f3 = st.columns(3)
    
    with f1:
        st.info("**1. Upload**\n\nDrag & Drop medical scans or paste clinical notes securely.")
        
    with f2:
        st.info("**2. Analyze**\n\nOur AI engine detects patterns, risks, and anomalies instantly.")
        
    with f3:
        st.success("**3. Understand**\n\nReceive a clear, jargon-free explanation of your health data.")

# --- AUTH ---
def show_auth():
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        with st.container():
            if st.session_state.auth_mode == 'login':
                st.markdown("<h2 style='text-align:center; margin-bottom:10px;'>Member Login</h2>", unsafe_allow_html=True)
                email = st.text_input("Email", key="l_e")
                pw = st.text_input("Password", type="password", key="l_p")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Sign In"):
                    if login_user(email, pw):
                        st.session_state.logged_in=True
                        st.session_state.user_email=email
                        go_to('dashboard')
                    else: st.error("Invalid Credentials")
                
                st.markdown("---")
                if st.button("Create Account", type="secondary"):
                    st.session_state.auth_mode = 'register'
                    st.rerun()
                    
            else: 
                st.markdown("<h2 style='text-align:center; margin-bottom:10px;'>Create Account</h2>", unsafe_allow_html=True)
                re = st.text_input("Email", key="r_e")
                rp = st.text_input("Password", type="password", key="r_p")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Sign Up"):
                    if register_user(re, rp): 
                        st.success("Account created! Please sign in.")
                        time.sleep(1.5)
                        st.session_state.auth_mode = 'login'
                        st.rerun()
                    else: st.error("Email already used.")
                
                st.markdown("---")
                if st.button("Back to Login", type="secondary"):
                    st.session_state.auth_mode = 'login'
                    st.rerun()

# --- DASHBOARD ---
def show_dashboard():
    history_data, last_active = get_user_stats(st.session_state.user_email)
    
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user_email}")
        st.markdown("<div style='color:#10b981; margin-bottom:20px'>● Online</div>", unsafe_allow_html=True)
        
        if st.button("Start New Analysis"):
            st.session_state.analysis_result = None
            st.session_state.analysis_images = []
            st.session_state.chat_history = []
            st.rerun()
            
        st.markdown("---")
        st.markdown(f"<div style='font-size:0.75rem; color:#64748b; margin-bottom:10px;'>Last active: {last_active}</div>", unsafe_allow_html=True)
        st.markdown("##### History")
        
        if history_data:
            for h_title, h_date in history_data:
                st.markdown(f"""
                <div class='history-item'>
                    <b>{h_title}</b>
                    <span class='history-date'>{h_date}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No scans yet.")
            
        st.markdown("---")
        if st.button("Sign Out"): do_sign_out()

    st.title("Diagnostic Interface")
    
    if st.session_state.analysis_result is None:
        with st.container():
            st.write("Upload your medical data below.")
            img_files = st.file_uploader("Upload Medical Scans (X-Ray, MRI, CT)", type=['png','jpg','jpeg'], accept_multiple_files=True)
            c1, c2 = st.columns([2, 1])
            with c1: txt_context = st.text_area("Patient Symptoms / Clinical Context", height=100, placeholder="E.g. Patient has chest pain for 3 weeks...")
            with c2: mode = st.selectbox("Analysis Mode", ["Radiologist Expert", "Simple Explanation"])
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Run Analysis"):
                if not img_files and not txt_context: st.error("Please upload an image or provide text.")
                else:
                    with st.spinner("Processing Multi-Modal Data..."):
                        pil_images = [Image.open(x) for x in img_files] if img_files else []
                        res = get_gemini_analysis(pil_images, txt_context, mode)
                        st.session_state.analysis_result = res
                        st.session_state.analysis_images = pil_images
                        
                        parts = res.split("|||")
                        if len(parts) >= 5:
                            title = parts[0].strip().replace("Part 1:", "").replace("**", "").strip()
                            risk_lvl = parts[3].strip()
                            add_history(st.session_state.user_email, title, res, risk_lvl)
                        else:
                            add_history(st.session_state.user_email, "Analysis", res, "Unknown")
                        st.rerun()
    
    else:
        res = st.session_state.analysis_result
        images = st.session_state.analysis_images
        
        col_act1, col_act2 = st.columns([1, 4])
        with col_act1:
            if st.button("💬 Chat with Scan"): go_to('chat')
        
        st.markdown("---")
        
        parts = res.split("|||")
        if len(parts) >= 5:
            title, obs, risks, severity, actions = parts[0], parts[1], parts[2], parts[3], parts[4]
            
            sev_clean = severity.strip().lower()
            bar_class = "risk-fill-low"
            color = "#22c55e"
            if "medium" in sev_clean: bar_class = "risk-fill-med"; color = "#eab308"
            if "high" in sev_clean: bar_class = "risk-fill-high"; color = "#ef4444"
            
            # Severity Bar (HTML is required here for custom CSS visuals, but kept simple)
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.05); padding:20px; border-radius:10px; border-left:5px solid {color};'>
                <h4 style='margin:0; color:{color}'>SEVERITY: {severity.upper()}</h4>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"### {title}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<div class='result-card' style='border-color:#3b82f6'><h4 style='color:#3b82f6'>🔍 Findings</h4>{obs}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='result-card' style='border-color:#f59e0b'><h4 style='color:#f59e0b'>⚠️ Risks</h4>{risks}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='result-card' style='border-color:#10b981'><h4 style='color:#10b981'>✅ Protocol</h4>{actions}</div>", unsafe_allow_html=True)
                if images: st.image(images[0], caption="Primary Scan Reference", use_container_width=True)

# --- CHAT PAGE ---
def show_chat():
    if st.button("← Back to Results"): go_to('dashboard')
    st.title("💬 Chat with Scan")
    if st.session_state.analysis_images:
        with st.expander("View Scans Reference"):
            cols = st.columns(len(st.session_state.analysis_images))
            for idx, img in enumerate(st.session_state.analysis_images):
                with cols[idx]: st.image(img, width=150)
    
    chat_container = st.container()
    user_input = st.chat_input("Ask a follow-up question about the findings...")
    
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("Consulting Analysis..."):
            ai_reply = chat_with_scan(user_input)
            st.session_state.chat_history.append({"role": "ai", "content": ai_reply})
            
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg['role'] == 'user': st.markdown(f"<div class='chat-user'>{msg['content']}</div>", unsafe_allow_html=True)
            else: st.markdown(f"<div class='chat-ai'>{msg['content']}</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 5. ROUTING
# -----------------------------------------------------------------------------
if st.session_state.page == 'landing': show_landing()
elif st.session_state.page == 'login': show_auth()
elif st.session_state.page == 'dashboard': 
    if st.session_state.logged_in: show_dashboard()
    else: go_to('login')
elif st.session_state.page == 'chat':
    if st.session_state.logged_in: show_chat()
    else: go_to('login')
elif st.session_state.page == 'about': show_about()
