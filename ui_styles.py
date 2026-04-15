MAIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&family=Inter:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Poppins', sans-serif !important; }

.stApp {
    background: linear-gradient(rgba(5,8,18,0.82), rgba(5,8,18,0.82)),
                url("https://images.unsplash.com/photo-1584036561566-baf8f5f1b144?q=80&w=2000&auto=format&fit=crop") !important;
    background-size: cover !important;
    background-position: center !important;
    background-attachment: fixed !important;
    color: #e0e0e0;
}
[data-testid="stSidebar"] {
    background: rgba(5,8,18,0.97) !important;
    backdrop-filter: blur(20px) !important;
    border-right: 1px solid rgba(0,212,255,0.25) !important;
}
[data-testid="stSidebar"] * { color: #ffffff !important; }
[data-testid="stHeader"] { background-color: transparent !important; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #050812; }
::-webkit-scrollbar-thumb { background: linear-gradient(#00d4ff,#00ff88); border-radius: 10px; }

div[data-testid="metric-container"] {
    background: rgba(0,0,0,0.55);
    backdrop-filter: blur(12px);
    border-radius: 18px;
    padding: 22px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    border-left: 4px solid #00d4ff;
    transition: all 0.35s ease;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-6px) scale(1.02);
    box-shadow: 0 14px 40px rgba(0,212,255,0.3);
    border-left-color: #00ff88;
}
div[data-testid="metric-container"] label { color: #00d4ff !important; font-weight: 600; font-size: 14px; }
div[data-testid="metric-container"] div { color: #ffffff !important; font-weight: 700; }

div.stButton > button {
    background: rgba(0,212,255,0.08) !important;
    color: #00d4ff !important;
    border-radius: 30px !important;
    width: 100%;
    font-weight: 600 !important;
    border: 2px solid #00d4ff !important;
    padding: 12px !important;
    transition: all 0.3s ease !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 13px !important;
}
div.stButton > button:hover {
    background: linear-gradient(90deg,#00d4ff,#00ff88) !important;
    color: #000 !important;
    box-shadow: 0 0 25px rgba(0,212,255,0.5) !important;
    transform: translateY(-3px) !important;
    border-color: transparent !important;
}

.stTextInput input, .stTextArea textarea {
    background-color: rgba(0,0,0,0.45) !important;
    color: white !important;
    border-radius: 12px !important;
    border: 1px solid rgba(0,212,255,0.3) !important;
    padding: 10px 15px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border: 1px solid #00ff88 !important;
    box-shadow: 0 0 15px rgba(0,255,136,0.25) !important;
}

.gradient-header {
    background: linear-gradient(90deg,#00d4ff 0%,#00ff88 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    margin-bottom: 20px;
    font-size: 2rem;
}

.glass-card {
    background: rgba(255,255,255,0.03);
    backdrop-filter: blur(12px);
    border-radius: 18px;
    padding: 25px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    margin-bottom: 20px;
    transition: all 0.3s ease;
}
.glass-card:hover {
    border-color: rgba(0,212,255,0.3);
    box-shadow: 0 12px 40px rgba(0,212,255,0.15);
}

.ticker-wrap {
    overflow: hidden;
    white-space: nowrap;
    background: rgba(0,212,255,0.08);
    border: 1px solid rgba(0,212,255,0.25);
    padding: 11px 15px;
    border-radius: 12px;
    margin-bottom: 28px;
}
.ticker-text {
    display: inline-block;
    color: #00d4ff;
    font-weight: 600;
    font-size: 15px;
    animation: scrollLeft 30s linear infinite;
}
.ticker-text:hover { animation-play-state: paused; }
@keyframes scrollLeft {
    0%   { transform: translateX(100%); }
    100% { transform: translateX(-100%); }
}

.risk-high   { background:rgba(255,75,75,0.15);  border:1px solid #ff4b4b; border-radius:12px; padding:14px; }
.risk-medium { background:rgba(255,193,7,0.15);  border:1px solid #ffc107; border-radius:12px; padding:14px; }
.risk-low    { background:rgba(0,255,136,0.12);  border:1px solid #00ff88; border-radius:12px; padding:14px; }

.badge {
    display:inline-block; padding:4px 14px;
    border-radius:20px; font-size:12px; font-weight:700;
    margin:3px;
}
.badge-gold   { background:rgba(255,193,7,0.2);  color:#ffc107; border:1px solid #ffc107; }
.badge-blue   { background:rgba(0,212,255,0.2);  color:#00d4ff; border:1px solid #00d4ff; }
.badge-green  { background:rgba(0,255,136,0.2);  color:#00ff88; border:1px solid #00ff88; }

/* Breathe animation */
.breathe-container {
    display:flex; flex-direction:column;
    justify-content:center; align-items:center;
    height:260px;
    background:rgba(255,255,255,0.02);
    border-radius:20px;
    border:1px solid rgba(0,212,255,0.1);
    margin-top:20px;
}
.breathe-circle {
    width:100px; height:100px; border-radius:50%;
    background: radial-gradient(circle, #00ff88 0%, #00d4ff 100%);
    animation: breathe 8s ease-in-out infinite;
    box-shadow: 0 0 25px rgba(0,212,255,0.5);
}
@keyframes breathe {
    0%,100% { transform:scale(1); opacity:.6; box-shadow:0 0 12px rgba(0,212,255,.3); }
    50%      { transform:scale(1.8); opacity:1; box-shadow:0 0 45px rgba(0,255,136,.7); }
}

/* News card */
.news-card {
    background: rgba(255,255,255,0.03);
    padding:22px; border-radius:16px;
    border:1px solid rgba(0,212,255,0.18);
    margin-bottom:24px;
    transition: all 0.3s ease;
}
.news-card:hover { border-color:rgba(0,212,255,0.5); transform:translateY(-3px); }

/* Fade-in page animation */
.page-fade { animation: fadeIn 0.5s ease; }
@keyframes fadeIn { from{opacity:0; transform:translateY(12px)} to{opacity:1; transform:translateY(0)} }

[data-testid="stDataFrame"] {
    border-radius:14px; overflow:hidden;
    border:1px solid rgba(255,255,255,0.08);
}

.stChatInput { border-radius:15px !important; border:1px solid #00d4ff !important; }
.history-item {
    background:rgba(255,255,255,0.04); padding:10px 14px;
    border-radius:10px; margin-bottom:8px; font-size:13px;
    color:white; border-left:3px solid #00d4ff;
}

/* Leaderboard */
.lb-row {
    display:flex; align-items:center; justify-content:space-between;
    padding:12px 18px; border-radius:12px; margin-bottom:8px;
    background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06);
    transition:all 0.2s ease;
}
.lb-row:hover { background:rgba(0,212,255,0.08); }

.stTabs [data-baseweb="tab-list"] { gap:10px; }
.stTabs [data-baseweb="tab"] {
    background:rgba(0,0,0,0.3); border-radius:10px !important;
    border:1px solid rgba(255,255,255,0.08) !important;
    color:#a0aabf !important; font-weight:600;
    padding:8px 20px !important;
}
.stTabs [aria-selected="true"] {
    background:rgba(0,212,255,0.15) !important;
    border-color:#00d4ff !important;
    color:#00d4ff !important;
}
</style>
"""
