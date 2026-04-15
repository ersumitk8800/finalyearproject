import streamlit as st
st.set_page_config(page_title="COVID-19 Analysis Hub", layout="wide", initial_sidebar_state="expanded")

import requests, pandas as pd, plotly.express as px, sqlite3, base64, datetime
from streamlit_option_menu import option_menu
from fpdf import FPDF
from bs4 import BeautifulSoup
from ui_styles import MAIN_CSS
from db_utils import (init_db, log_activity, save_leaderboard_score,
                      get_leaderboard, get_all_reviews, get_user_reviews,
                      get_activity_logs, get_myth_questions, get_conn,
                      delete_myth_question, bulk_insert_myth_questions)
from api_utils import (get_country_data, get_all_global, get_top_countries,
                       get_all_countries_map, get_india_states,
                       get_vaccination_countries, get_vaccination_timeline,
                       get_global_vaccination, get_historical_global, fetch_news_items)

GROQ_API_KEY = "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"
ADMIN_PASSWORD = "admin123"

st.markdown(MAIN_CSS, unsafe_allow_html=True)
init_db()

# ── Session state ──────────
for k, v in [("logged_in", False), ("user_data", None), ("messages", []),
              ("query_history", []), ("mb_score", 0), ("mb_q_index", 0),
              ("mb_show_exp", False), ("mb_answered_correct", False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Groq helper ──────
def call_groq(prompt, system="", model="llama-3.1-8b-instant"):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    try:
        r = requests.post(url, json={"model": model, "messages": msgs, "temperature": 0.3},
                          headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'].strip()
        else:
            return None
    except Exception:
        return None

def call_groq_vision(base64_image, user_text="Describe this image in detail related to COVID-19 or health.", system=""):
    """Send an image + text to Groq vision model for analysis."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({
        "role": "user",
        "content": [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
    })
    try:
        r = requests.post(url, json={"model": "meta-llama/llama-4-scout-17b-16e-instruct",
                                     "messages": msgs, "temperature": 0.3, "max_tokens": 1024},
                          headers=headers, timeout=40)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'].strip()
        else:
            return None
    except Exception:
        return None

def fetch_covid_data_smart(location_text):
    """Smart COVID data fetcher with multiple fallbacks."""
    loc_text = location_text.strip().lower()
    # Global keywords
    global_keywords = ["all", "global", "world", "duniya", "worldwide", "total"]
    if any(kw in loc_text for kw in global_keywords):
        try:
            cd = requests.get("https://disease.sh/v3/covid-19/all", timeout=8).json()
            return cd, "Global"
        except Exception:
            return None, None
    # Try direct country fetch
    try:
        cd = requests.get(f"https://disease.sh/v3/covid-19/countries/{location_text}", timeout=8).json()
        if isinstance(cd, dict) and 'cases' in cd:
            return cd, cd.get('country', location_text)
    except Exception:
        pass
    # Try searching country list
    try:
        all_countries = requests.get("https://disease.sh/v3/covid-19/countries", timeout=8).json()
        loc_lower = location_text.lower()
        for c in all_countries:
            cname = c.get('country', '').lower()
            if loc_lower in cname or cname in loc_lower:
                return c, c.get('country', location_text)
    except Exception:
        pass
    return None, None

# ── PDF helper ─────────────────────────────────────────────
def create_pdf(country, data, fig):
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(200, 15, "COVID-19 Analysis Report", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Country : {country}", ln=True)
    pdf.cell(200, 10, f"Total Cases  : {data.get('cases',0):,}", ln=True)
    pdf.cell(200, 10, f"Total Deaths : {data.get('deaths',0):,}", ln=True)
    pdf.cell(200, 10, f"Recovered    : {data.get('recovered',0):,}", ln=True)
    pdf.cell(200, 10, f"Active       : {data.get('active',0):,}", ln=True)
    try:
        fig.write_image("temp_chart.png")
        pdf.image("temp_chart.png", x=10, y=100, w=185)
    except Exception:
        pass
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(200, 10, "Generated by COVID-19 Analysis Hub", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1')

def dl_link(data, fname):
    b64 = base64.b64encode(data).decode()
    return (f'<a href="data:application/pdf;base64,{b64}" download="{fname}" '
            f'style="text-decoration:none">'
            f'<button style="width:100%;background:linear-gradient(90deg,#00d4ff,#00ff88);'
            f'color:#000;padding:14px;border-radius:30px;border:none;font-weight:700;'
            f'cursor:pointer;font-size:15px">📄 Download PDF Report</button></a>')

# ── Plotly layout ──────────────────────────────────────────
PL = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
          font_color="white", margin=dict(l=20,r=20,t=50,b=20))
COLORS = ['#00d4ff','#00ff88','#ff4b4b','#feca57','#a29bfe','#fd79a8']

def ticker(text):
    st.markdown(f'<div class="ticker-wrap"><div class="ticker-text">{text}</div></div>',
                unsafe_allow_html=True)

def section(title):
    st.markdown(f"<h3 style='color:#00d4ff;margin:18px 0 10px'>{title}</h3>",
                unsafe_allow_html=True)

def hr():
    st.markdown("<hr style='border:1px solid rgba(255,255,255,0.08);margin:20px 0'>",
                unsafe_allow_html=True)


#  SIDEBAR

if st.session_state.logged_in:
    ud = st.session_state.user_data
    st.sidebar.markdown(f"""
    <div style="background:rgba(255,255,255,0.04);backdrop-filter:blur(10px);
                padding:22px;border-radius:18px;text-align:center;
                border:1px solid rgba(255,255,255,0.08);margin-bottom:20px;">
      <img src="https://ui-avatars.com/api/?name={ud[2]}&background=00d4ff&color=fff&rounded=true&bold=true"
           style="width:80px;border:3px solid rgba(0,212,255,0.5);border-radius:50%;margin-bottom:12px">
      <h3 style="color:white;margin:0">{ud[2]}</h3>
      <span class="badge badge-green" style="margin-top:8px;display:inline-block">🟢 Active Analyst</span>
    </div>""", unsafe_allow_html=True)
else:
    st.sidebar.markdown("""
    <div style="background:rgba(255,255,255,0.04);padding:22px;border-radius:18px;
                text-align:center;border:1px solid rgba(255,255,255,0.08);margin-bottom:20px;">
      <div style="width:72px;height:72px;background:rgba(255,255,255,0.08);border-radius:50%;
                  margin:0 auto 12px;display:flex;align-items:center;justify-content:center">
        <span style="font-size:30px">👤</span></div>
      <h3 style="color:white;margin:0">Guest Mode</h3>
      <p style="color:#ff4b4b;font-size:13px;margin-top:5px">Login for full access</p>
    </div>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h3 style='color:#00d4ff;text-align:center'>📌 Navigation</h3>", unsafe_allow_html=True)
    page = option_menu(
        menu_title=None,
        options=["Global Dashboard","India Analysis","Top 10 Trends","Global Heatmap",
                 "Country Comparison","Vaccination Tracker","News Feed",
                 "User Login & Profile","User Reviews","Admin Panel",
                 "Health Shield","Covid AI Chat","Myth Buster Game"],
        icons=["globe","graph-up","bar-chart","map","arrow-left-right","patch-check",
               "newspaper","person","chat-left-text","lock","shield-plus","robot","controller"],
        menu_icon="cast", default_index=0,
        styles={
            "container":{"padding":"0!important","background-color":"transparent"},
            "icon":{"color":"#00d4ff","font-size":"17px"},
            "nav-link":{"font-size":"14px","text-align":"left","margin":"6px 0",
                        "padding":"11px","border-radius":"10px","color":"#c0c8d8"},
            "nav-link-selected":{"background":"linear-gradient(90deg,rgba(0,212,255,.18),rgba(0,212,255,0))",
                                 "color":"#00d4ff","border-left":"3px solid #00d4ff","font-weight":"700"},
        }
    )

# PAGE 1 — GLOBAL DASHBOARD

if page == "Global Dashboard":
    ticker("🚀 LIVE: Global COVID-19 recovery rate improving &nbsp;|&nbsp; 🌍 12 Billion+ doses administered &nbsp;|&nbsp; 💉 Stay vaccinated – Stay safe!")
    st.markdown("<h1 class='gradient-header'>📊 Global COVID-19 Dashboard</h1>", unsafe_allow_html=True)

    section("🔍 Search Any Country")
    search_country = st.text_input("", "USA", placeholder="e.g. India, USA, Japan...")

    with st.spinner("Fetching live data..."):
        data = get_country_data(search_country)

    if data and 'country' in data:
        log_activity("Country_Search", search_country)
        c1, c2 = st.columns([1, 10])
        with c1:
            st.markdown(f'<img src="{data["countryInfo"]["flag"]}" style="width:85px;border-radius:8px;box-shadow:0 4px 15px rgba(0,0,0,.5)">',
                        unsafe_allow_html=True)
        with c2:
            st.markdown(f"<h2 style='color:white;margin-top:12px'>🌐 {data['country'].upper()}</h2>",
                        unsafe_allow_html=True)
        hr()
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Total Cases 🤒", f"{data['cases']:,}", f"+{data['todayCases']:,}")
        m2.metric("Total Deaths ⚰️", f"{data['deaths']:,}", f"+{data['todayDeaths']:,}")
        m3.metric("Recovered ✨", f"{data['recovered']:,}")
        m4.metric("Active ⚡", f"{data['active']:,}")
        hr()

        section(f"🎨 Visual Charts — {data['country']}")
        chart_type = st.selectbox("Chart Type", ["Bar Chart","Pie Chart","Line Chart","Area Chart"])
        gd = pd.DataFrame({'Status':['Cases','Deaths','Recovered','Active'],
                           'Count':[data['cases'],data['deaths'],data['recovered'],data['active']]})
        if chart_type == "Bar Chart":
            fig = px.bar(gd, x='Status', y='Count', color='Status', text_auto='.2s',
                         color_discrete_sequence=COLORS)
        elif chart_type == "Pie Chart":
            fig = px.pie(gd, names='Status', values='Count', hole=0.4,
                         color_discrete_sequence=COLORS)
        elif chart_type == "Line Chart":
            fig = px.line(gd, x='Status', y='Count', markers=True)
            fig.update_traces(line_color='#00d4ff', marker=dict(size=10, color='#00ff88'))
        else:
            fig = px.area(gd, x='Status', y='Count')
            fig.update_traces(line_color='#00d4ff', fillcolor='rgba(0,212,255,0.15)')
        fig.update_layout(**PL)
        st.plotly_chart(fig, use_container_width=True)

        if data['cases'] > 0:
            rr = (data['recovered'] / data['cases']) * 100
            st.markdown("<p style='color:#a0aabf;margin-bottom:5px'>Recovery Progress</p>", unsafe_allow_html=True)
            st.progress(min(rr/100, 1.0))
            if rr > 95:
                st.success(f"🟢 SAFE ZONE — Recovery rate: {rr:.1f}%")
            elif rr > 80:
                st.warning(f"🟡 CAUTION — Recovery rate: {rr:.1f}%")
            else:
                st.error(f"🔴 HIGH RISK — Recovery rate: {rr:.1f}%")

        hr()
        section("📈 Historical Global Trend")
        with st.spinner("Loading trend data..."):
            hist = get_historical_global(180)
        if hist:
            cases_hist = pd.DataFrame(list(hist.get('cases',{}).items()), columns=['Date','Cases'])
            deaths_hist = pd.DataFrame(list(hist.get('deaths',{}).items()), columns=['Date','Deaths'])
            fig_h = px.area(cases_hist, x='Date', y='Cases', title="Global Cases – Last 180 Days")
            fig_h.update_traces(line_color='#00d4ff', fillcolor='rgba(0,212,255,0.12)')
            fig_h.update_layout(**PL)
            st.plotly_chart(fig_h, use_container_width=True)

        hr()
        # Download + Upload side by side
        btn_col, upload_col = st.columns([1, 1])
        with btn_col:
            try:
                pdf_file = create_pdf(data['country'], data, fig)
                st.markdown(dl_link(pdf_file, f"{data['country']}_report.pdf"), unsafe_allow_html=True)
            except Exception:
                pass
        with upload_col:
            st.markdown("""
            <div style="background:linear-gradient(90deg,rgba(0,255,136,.12),rgba(0,212,255,.12));
                        padding:14px 20px;border-radius:15px;border:1px dashed rgba(0,255,136,.5);
                        text-align:center">
              <p style="color:#00ff88;font-weight:700;margin:0;font-size:15px">
                📂 Upload Your Own Data for Analysis</p>
              <p style="color:#a0aabf;font-size:12px;margin:4px 0 0">CSV or Excel — any rows & columns</p>
            </div>""", unsafe_allow_html=True)
            uploaded = st.file_uploader("", type=["csv","xlsx","xls"],
                                        label_visibility="collapsed",
                                        key="dashboard_uploader")
            # NO st.rerun() here — that caused infinite loop
            # Just store reference; analyzer section below reads it directly

    else:
        st.error("❌ Country not found. Please check spelling.")

    # CUSTOM DATA ANALYZER 
    # Read directly from the widget — no session state loop
    _uf = st.session_state.get("dashboard_uploader")
    if _uf is not None:
        hr()
        st.markdown("""
        <div style="background:linear-gradient(135deg,rgba(0,255,136,.15),rgba(0,212,255,.15));
                    padding:24px;border-radius:18px;text-align:center;margin-bottom:24px;
                    border:1px solid rgba(0,255,136,.3)">
          <h2 style="margin:0;color:white">📊 Custom Data Analyzer</h2>
          <p style="color:#a0aabf;margin:6px 0 0">Aapki uploaded file ka complete analysis</p>
        </div>""", unsafe_allow_html=True)

        uf = _uf
        try:
            if uf.name.endswith(".csv"):
                df_up = pd.read_csv(uf)
            else:
                df_up = pd.read_excel(uf)
        except Exception as e:
            st.error(f"File read error: {e}")
            st.stop()

        # ── Stats Row ─
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("📋 Total Rows",    f"{len(df_up):,}")
        s2.metric("📌 Total Columns", f"{len(df_up.columns):,}")
        num_cols = df_up.select_dtypes(include='number').columns.tolist()
        cat_cols = df_up.select_dtypes(exclude='number').columns.tolist()
        s3.metric("🔢 Numeric Cols",  len(num_cols))
        s4.metric("🔤 Text Cols",     len(cat_cols))

        hr()
        section("📋 Data Preview")
        preview_rows = st.slider("Kitne rows dikhane hain?", 5, min(100, len(df_up)), 10, key="preview_n")
        st.dataframe(df_up.head(preview_rows), use_container_width=True)

        # ── Download uploaded data as CSV ──
        csv_bytes = df_up.to_csv(index=False).encode()
        st.download_button("⬇️ Download as CSV", csv_bytes, "analyzed_data.csv", "text/csv")

        hr()
        section("📈 Smart Chart Builder")

        if num_cols:
            cc1, cc2, cc3 = st.columns(3)
            chart_kind = cc1.selectbox("Chart Type",
                ["Bar Chart","Line Chart","Area Chart","Scatter Plot",
                 "Pie Chart","Box Plot","Histogram"], key="uc_kind")
            x_col = cc2.selectbox("X-Axis / Category", df_up.columns.tolist(), key="uc_x")
            y_col = cc3.selectbox("Y-Axis (Numeric)", num_cols, key="uc_y")

            color_col = None
            if len(cat_cols) > 0:
                color_col = st.selectbox("Color by (optional)", ["None"] + cat_cols, key="uc_color")
                if color_col == "None": color_col = None

            if st.button("🚀 Generate Chart", key="gen_chart_btn"):
                try:
                    if chart_kind == "Bar Chart":
                        uf_fig = px.bar(df_up, x=x_col, y=y_col, color=color_col,
                                        text_auto=True, color_discrete_sequence=COLORS)
                    elif chart_kind == "Line Chart":
                        uf_fig = px.line(df_up, x=x_col, y=y_col, color=color_col,
                                         markers=True, color_discrete_sequence=COLORS)
                    elif chart_kind == "Area Chart":
                        uf_fig = px.area(df_up, x=x_col, y=y_col, color=color_col,
                                         color_discrete_sequence=COLORS)
                    elif chart_kind == "Scatter Plot":
                        uf_fig = px.scatter(df_up, x=x_col, y=y_col, color=color_col,
                                            color_discrete_sequence=COLORS, size_max=12)
                    elif chart_kind == "Pie Chart":
                        uf_fig = px.pie(df_up, names=x_col, values=y_col,
                                        color_discrete_sequence=COLORS, hole=0.35)
                    elif chart_kind == "Box Plot":
                        uf_fig = px.box(df_up, x=x_col if color_col else None,
                                        y=y_col, color=color_col,
                                        color_discrete_sequence=COLORS)
                    else:  # Histogram
                        uf_fig = px.histogram(df_up, x=y_col, color=color_col,
                                              color_discrete_sequence=COLORS, nbins=30)

                    uf_fig.update_layout(**PL, title=f"{chart_kind}: {y_col} vs {x_col}")
                    st.plotly_chart(uf_fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Chart error: {e}. Please try different columns.")

            hr()
            # ── Auto Smart Charts ──
            section("🤖 Auto Smart Charts (AI Recommended)")
            auto_cols = num_cols[:4]  # top 4 numeric columns
            if len(auto_cols) >= 1:
                acols = st.columns(min(len(auto_cols), 2))
                for i, col in enumerate(auto_cols[:4]):
                    with acols[i % 2]:
                        try:
                            # Distribution histogram for each numeric col
                            af = px.histogram(df_up, x=col, nbins=25,
                                              title=f"Distribution: {col}",
                                              color_discrete_sequence=[COLORS[i % len(COLORS)]])
                            af.update_layout(**PL, height=280)
                            st.plotly_chart(af, use_container_width=True)
                        except Exception:
                            pass

            # Correlation heatmap if 2+ numeric cols
            if len(num_cols) >= 2:
                hr()
                section("🔥 Correlation Heatmap")
                try:
                    corr = df_up[num_cols].corr()
                    import plotly.figure_factory as ff
                    hm = px.imshow(corr, text_auto=".2f",
                                   color_continuous_scale="RdBu_r",
                                   title="Numeric Columns Correlation")
                    hm.update_layout(**PL, height=400)
                    st.plotly_chart(hm, use_container_width=True)
                except Exception:
                    pass

        else:
            st.warning("⚠️ File mein koi numeric column nahi mila. Charts ke liye numeric data hona zaroori hai.")

        hr()
        # ── Statistical Summary ───
        section("📊 Statistical Summary")
        if num_cols:
            st.dataframe(df_up[num_cols].describe().round(2), use_container_width=True)

        # ── AI Insights via Groq ──
        hr()
        section("🤖 AI Insights — Data ka Analysis")
        if st.button("✨ Generate AI Insights", key="ai_insights_btn"):
            with st.spinner("AI data analyze kar raha hai..."):
                # Build a compact summary for AI
                col_info = ", ".join([f"{c}({df_up[c].dtype})" for c in df_up.columns[:12]])
                sample = df_up.head(5).to_string(index=False)
                if num_cols:
                    desc_str = df_up[num_cols[:6]].describe().round(2).to_string()
                else:
                    desc_str = "No numeric columns"

                ai_data_prompt = f"""Analyze this dataset and give 5 key insights:

Columns: {col_info}
Rows: {len(df_up)}
Statistics:
{desc_str}

Sample rows:
{sample}

Give insights in simple Hindi/English mixed language. Focus on:
1. What this data seems to be about
2. Key patterns or trends
3. Any outliers or anomalies
4. Min/Max highlights
5. One actionable recommendation

Keep each insight short (1-2 lines). Use bullet points."""

                insights = call_groq(ai_data_prompt, system="You are a data analyst. Give concise, useful insights.")

            if insights:
                st.markdown(f"""
                <div class="glass-card" style="border-left:4px solid #00ff88">
                  <h4 style="color:#00ff88;margin:0 0 12px">🤖 AI Analysis Results</h4>
                  <div style="color:#e0e0e0;line-height:1.8;white-space:pre-wrap">{insights}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.error("AI se connect nahi ho saka.")

        hr()
        if st.button("❌ Close Analyzer", key="close_analyzer"):
            # Clear the uploader widget via its key
            if 'dashboard_uploader' in st.session_state:
                del st.session_state['dashboard_uploader']
            st.rerun()



# PAGE 2 — INDIA ANALYSIS

elif page == "India Analysis":
    st.markdown("<h1 class='gradient-header'>🇮🇳 India State-wise Deep Dive</h1>", unsafe_allow_html=True)
    with st.spinner("Loading India data..."):
        df_india = get_india_states()
    if df_india.empty:
        st.error("Data unavailable."); st.stop()

    section("📊 Compare States")
    defaults = [s for s in ["Maharashtra","Delhi","Uttar Pradesh"] if s in df_india['state'].values]
    selected = st.multiselect("Select States", df_india['state'].unique(), default=defaults)
    if selected:
        cdf = df_india[df_india['state'].isin(selected)]
        fig_i = px.bar(cdf, x='state', y=['cases','deaths','recovered'],
                       barmode='group', title="State-wise Comparison",
                       color_discrete_sequence=COLORS)
        fig_i.update_layout(**PL)
        st.plotly_chart(fig_i, use_container_width=True)

    hr()
    section("🔍 Individual State Analysis")
    state = st.selectbox("Select State", df_india['state'].unique())
    sd = df_india[df_india['state']==state].iloc[0]
    rr = (sd['recovered']/sd['cases'])*100 if sd['cases']>0 else 0
    c1,c2 = st.columns([1,2])
    with c1:
        if rr > 90: st.success(f"🟢 SAFE\nRecovery: {rr:.1f}%")
        else: st.warning(f"🟡 CAUTION\nRecovery: {rr:.1f}%")
    with c2:
        a,b = st.columns(2)
        a.metric("Active Cases", f"{sd['active']:,}")
        b.metric("Total Deaths", f"{sd['deaths']:,}")

    hr()
    section("📊 Top 10 States by Active Cases")
    style = st.radio("Chart Style", ["Bar","Pie"], horizontal=True)
    if style == "Bar":
        fig_s = px.bar(df_india.head(10), x='state', y='active', color='state',
                       color_discrete_sequence=COLORS)
    else:
        fig_s = px.pie(df_india.head(10), names='state', values='active', hole=0.35,
                       color_discrete_sequence=COLORS)
    fig_s.update_layout(**PL)
    st.plotly_chart(fig_s, use_container_width=True)

    hr()
    section("📋 All States Data")
    st.dataframe(df_india, use_container_width=True)


# PAGE 3 — TOP 10 TRENDS

elif page == "Top 10 Trends":
    st.markdown("<h1 class='gradient-header'>🏆 Top 10 Countries — Trend Analysis</h1>", unsafe_allow_html=True)
    with st.spinner("Loading data..."):
        df_top = get_top_countries(10)
    if df_top.empty:
        st.error("Data unavailable."); st.stop()

    section("🎨 Visualization Settings")
    c1,c2 = st.columns(2)
    chart = c1.selectbox("Chart Type", ["Bar Chart","Pie Chart","Line Chart"])
    cat = c2.radio("Data Category", ["cases","deaths","recovered","tests"], horizontal=True)

    if chart == "Bar Chart":
        fig_t = px.bar(df_top, x='country', y=cat, color='country', text_auto='.2s',
                       color_discrete_sequence=COLORS)
    elif chart == "Pie Chart":
        fig_t = px.pie(df_top, names='country', values=cat, hole=0.4,
                       color_discrete_sequence=COLORS)
    else:
        fig_t = px.line(df_top, x='country', y=cat, markers=True)
        fig_t.update_traces(line_color='#00d4ff', marker=dict(size=12,color='#00ff88'))
    fig_t.update_layout(**PL)
    st.plotly_chart(fig_t, use_container_width=True)

    hr()
    section("📋 Full Data Table")
    cols = [c for c in ['country','cases','todayCases','deaths','recovered','tests'] if c in df_top.columns]
    st.dataframe(df_top[cols], use_container_width=True)


# PAGE 4 — GLOBAL HEATMAP

elif page == "Global Heatmap":
    st.markdown("<h1 class='gradient-header'>🗺️ COVID-19 Global Heatmap</h1>", unsafe_allow_html=True)
    with st.spinner("Loading map data..."):
        df_map = get_all_countries_map()
    if df_map.empty:
        st.error("Data unavailable."); st.stop()

    opt = st.selectbox("Display on Map", ["cases","deaths","recovered","active"])
    fig_m = px.choropleth(df_map, locations="country", locationmode="country names",
                          color=opt, hover_name="country",
                          color_continuous_scale=px.colors.diverging.RdYlGn[::-1],
                          title="Global COVID-19 Risk Map")
    fig_m.update_layout(height=650, margin={"r":0,"t":50,"l":0,"b":0},
                        paper_bgcolor="rgba(0,0,0,0)", font_color="white",
                        geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='rgba(0,0,0,0)'))
    st.plotly_chart(fig_m, use_container_width=True)
    st.info("💡 Scroll to zoom, hover for details.")


# PAGE 5 — COUNTRY COMPARISON

elif page == "Country Comparison":
    st.markdown("<h1 class='gradient-header'>⚖️ Country Comparison Tool</h1>", unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    country1 = c1.text_input("Country 1", "India")
    country2 = c2.text_input("Country 2", "USA")

    with st.spinner("Fetching comparison data..."):
        r1 = get_country_data(country1)
        r2 = get_country_data(country2)

    if r1 and r2 and 'country' in r1 and 'country' in r2:
        metrics = ["Total Cases","Deaths","Recovered","Active"]
        vals1 = [r1['cases'],r1['deaths'],r1['recovered'],r1['active']]
        vals2 = [r2['cases'],r2['deaths'],r2['recovered'],r2['active']]
        df_c = pd.DataFrame({"Metric":metrics, r1['country']:vals1, r2['country']:vals2})

        m1,m2,m3,m4 = st.columns(4)
        for col,m,v1,v2 in zip([m1,m2,m3,m4], metrics, vals1, vals2):
            col.metric(m, f"{v1:,}", f"{v1-v2:+,}")

        hr()
        fig_c = px.bar(df_c, x="Metric", y=[r1['country'],r2['country']],
                       barmode='group', title=f"{r1['country']} vs {r2['country']}",
                       color_discrete_sequence=['#00d4ff','#00ff88'])
        fig_c.update_layout(**PL)
        st.plotly_chart(fig_c, use_container_width=True)

        rr1 = (r1['recovered']/r1['cases']*100) if r1['cases']>0 else 0
        rr2 = (r2['recovered']/r2['cases']*100) if r2['cases']>0 else 0
        hr()
        section("📊 Recovery Rate Comparison")
        rc1,rc2 = st.columns(2)
        with rc1:
            st.markdown(f"<p style='color:#a0aabf'>{r1['country']} Recovery Rate</p>", unsafe_allow_html=True)
            st.progress(min(rr1/100,1.0))
            st.markdown(f"<b style='color:#00ff88'>{rr1:.1f}%</b>", unsafe_allow_html=True)
        with rc2:
            st.markdown(f"<p style='color:#a0aabf'>{r2['country']} Recovery Rate</p>", unsafe_allow_html=True)
            st.progress(min(rr2/100,1.0))
            st.markdown(f"<b style='color:#00ff88'>{rr2:.1f}%</b>", unsafe_allow_html=True)
    else:
        st.error("❌ Could not fetch data. Check country names.")


# PAGE 6 — VACCINATION TRACKER

elif page == "Vaccination Tracker":
    st.markdown("<h1 class='gradient-header'>💉 Global Vaccination Tracker</h1>", unsafe_allow_html=True)
    with st.spinner("Loading country list..."):
        clist = get_vaccination_countries()

    idx = clist.index("India") if "India" in clist else 0
    sel = st.selectbox("Select Country", clist, index=idx)

    with st.spinner(f"Loading {sel} data..."):
        df_vac = get_vaccination_timeline(sel, 30)
        global_total = get_global_vaccination()

    if df_vac is not None:
        latest = df_vac['Total Doses'].iloc[-1]
        c1,c2 = st.columns([1,2])
        with c1:
            st.metric(f"Total Doses — {sel}", f"{latest:,}")
            st.markdown("<br>", unsafe_allow_html=True)
            if global_total:
                st.info(f"🌍 World Total: **{global_total:,}**")
        with c2:
            fig_v = px.bar(df_vac, x='Date', y='Total Doses',
                           title=f"30-Day Vaccination Drive — {sel}",
                           color='Total Doses', color_continuous_scale='Mint')
            fig_v.update_layout(**PL)
            st.plotly_chart(fig_v, use_container_width=True)
    else:
        st.error(f"Vaccination data not available for {sel}.")


# PAGE 7 — NEWS FEED

elif page == "News Feed":
    st.markdown("<h1 class='gradient-header'>📰 Live Health & COVID News</h1>", unsafe_allow_html=True)
    IMGS = [
        "https://images.unsplash.com/photo-1532938911079-1b06ac7ceec7?w=800&q=80",
        "https://images.unsplash.com/photo-1584483766114-2cea6facdf57?w=800&q=80",
        "https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=800&q=80",
        "https://images.unsplash.com/photo-1583324113626-70df0f4deaab?w=800&q=80",
    ]
    topic = st.text_input("🔍 Search news topic", "covid health india")
    with st.spinner("Fetching live news..."):
        articles = fetch_news_items(topic.replace(" ","+"), 9)

    if articles:
        cols = st.columns(3)
        for i, art in enumerate(articles):
            img = IMGS[i % len(IMGS)]
            with cols[i % 3]:
                st.markdown(f"""
                <div class="news-card">
                  <img src="{img}" style="width:100%;height:180px;object-fit:cover;border-radius:10px;margin-bottom:12px">
                  <h4 style="color:#00d4ff;margin:0 0 8px 0;font-size:15px;line-height:1.4">{art['title']}</h4>
                  <p style="color:#a0aabf;font-size:11px;margin-bottom:10px">🕒 {art['date']}</p>
                  <p style="color:#e0e0e0;font-size:13px;line-height:1.6">{art['desc']}</p>
                  <a href="{art['link']}" target="_blank"
                     style="display:inline-block;margin-top:10px;padding:8px 18px;
                            background:rgba(0,212,255,0.1);color:#00d4ff;text-decoration:none;
                            border-radius:20px;border:1px solid #00d4ff;font-size:12px;font-weight:600">
                    Read More 🔗</a>
                </div>""", unsafe_allow_html=True)
    else:
        st.warning("Could not fetch news. Check your internet connection.")


# PAGE 8 — USER LOGIN & PROFILE

elif page == "User Login & Profile":
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(0,212,255,.18),rgba(0,255,136,.18));
                padding:28px;border-radius:20px;text-align:center;margin-bottom:28px;
                border:1px solid rgba(0,212,255,.3)">
      <h1 style="margin:0;color:white">🔐 Secured User Panel</h1>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.logged_in:
        _, col, _ = st.columns([0.5,2,0.5])
        with col:
            tab_l, tab_r = st.tabs(["🔒 Login","📝 Register"])
            with tab_r:
                section("Create New Account")
                nu = st.text_input("Username", key="ru")
                nn = st.text_input("Full Name", key="rn")
                ne = st.text_input("Email", key="re")
                nb = st.text_area("Short Bio", key="rb")
                np_ = st.text_input("Password", type="password", key="rp")
                if st.button("🚀 Register Now"):
                    if nu and nn and np_:
                        try:
                            conn = get_conn(); c = conn.cursor()
                            c.execute("INSERT INTO users VALUES (?,?,?,?,?)",(nu,np_,nn,ne,nb))
                            conn.commit(); conn.close()
                            st.success("Account created! Go to Login tab.")
                        except Exception:
                            st.error("Username already exists!")
                    else:
                        st.error("Username, Name and Password are required.")
            with tab_l:
                section("Login to Your Account")
                lu = st.text_input("Username", key="lu")
                lp = st.text_input("Password", type="password", key="lp")
                if st.button("🔑 Login Securely"):
                    conn = get_conn(); c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username=? AND password=?",(lu,lp))
                    res = c.fetchone(); conn.close()
                    if res:
                        st.session_state.logged_in = True
                        st.session_state.user_data = res
                        st.success("Login successful! Redirecting...")
                        st.rerun()
                    else:
                        st.error("Wrong username or password.")
    else:
        ud = st.session_state.user_data
        st.markdown(f"""
        <div class="glass-card" style="border-left:5px solid #00ff88">
          <h2 style="color:white;margin-top:0">Welcome back, <span style="color:#00ff88">{ud[2]}</span>! 👋</h2>
          <hr style="border-color:rgba(255,255,255,0.08)">
          <p style="color:#e0e0e0"><b>Username:</b> <span style="color:#00d4ff">{ud[0]}</span></p>
          <p style="color:#e0e0e0"><b>Email:</b> <span style="color:#00d4ff">{ud[3]}</span></p>
          <p style="color:#e0e0e0"><b>Bio:</b> {ud[4]}</p>
        </div>""", unsafe_allow_html=True)

        hr()
        section("🏅 Your Achievement Badges")
        reviews_df = get_user_reviews(ud[2])
        lb_df = get_leaderboard(100)
        badges = []
        badges.append('<span class="badge badge-blue">📊 Data Explorer</span>')
        if not reviews_df.empty:
            badges.append('<span class="badge badge-green">✍️ Reviewer</span>')
        if not lb_df.empty and ud[0] in lb_df['username'].values:
            score_row = lb_df[lb_df['username']==ud[0]]
            if not score_row.empty and score_row.iloc[0]['best_score'] >= 50:
                badges.append('<span class="badge badge-gold">🏆 Myth Buster Pro</span>')
        st.markdown(" ".join(badges), unsafe_allow_html=True)

        hr()
        section("📝 Your Reviews")
        if not reviews_df.empty:
            st.dataframe(reviews_df, use_container_width=True)
        else:
            st.info("You haven't submitted any reviews yet.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout Securely"):
            st.session_state.logged_in = False
            st.session_state.user_data = None
            st.rerun()


# PAGE 9 — USER REVIEWS

elif page == "User Reviews":
    st.markdown("<h1 class='gradient-header'>💬 Community Reviews</h1>", unsafe_allow_html=True)
    section("📤 Submit Your Feedback")
    with st.form("review_form"):
        name = st.text_input("Full Name")
        country = st.text_input("Country / State")
        rating = st.slider("Rate Platform Accuracy", 1, 5, 4)
        msg = st.text_area("Your Review")
        if st.form_submit_button("Submit Review"):
            if name and msg:
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO reviews (name,country,review,rating) VALUES (?,?,?,?)",
                          (name,country,msg,rating))
                conn.commit(); conn.close()
                st.success("✅ Review submitted! Thank you.")
                log_activity("Review_Submitted", f"{name} - {rating}★")
            else:
                st.error("Name and review message are required.")

    hr()
    section("🌟 Community Reviews")
    df_r = get_all_reviews()
    if not df_r.empty:
        for _, row in df_r.iterrows():
            stars = "⭐" * int(row['rating'])
            st.markdown(f"""
            <div class="glass-card">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <h4 style="margin:0;color:#00d4ff">{row['name']} — {row['country']}</h4>
                <span style="font-size:18px">{stars}</span>
              </div>
              <p style="color:#e0e0e0;margin-top:10px;line-height:1.6">{row['review']}</p>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No reviews yet. Be the first!")


# PAGE 10 — ADMIN PANEL

elif page == "Admin Panel":
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(255,75,75,.18),rgba(255,150,75,.18));
                padding:28px;border-radius:20px;text-align:center;margin-bottom:28px;
                border:1px solid rgba(255,75,75,.3)">
      <h1 style="margin:0;color:white">🔐 Admin Control Center</h1>
    </div>""", unsafe_allow_html=True)

    pw = st.text_input("Admin Secret Key", type="password")
    if pw == ADMIN_PASSWORD:
        st.success("✅ Access Granted!")
        t1,t2,t3,t4 = st.tabs(["📢 Post News","📊 Manage Reviews","🕵️ Activity Logs","🎮 Game Quiz"])

        with t1:
            section("Post to News Feed")
            with st.form("news_form", clear_on_submit=True):
                nt = st.text_input("Headline")
                nc = st.text_area("Content")
                ni = st.text_input("Image URL (optional)")
                ns = st.slider("Image Size %", 10, 100, 80)
                if st.form_submit_button("🚀 Publish"):
                    if nt and nc:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO news (title,content,image_url,image_size) VALUES (?,?,?,?)",
                                  (nt,nc,ni,ns))
                        conn.commit(); conn.close()
                        st.success("Published!")
                    else:
                        st.error("Title and content required.")

        with t2:
            section("All User Reviews")
            df_rv = get_all_reviews()
            st.dataframe(df_rv, use_container_width=True)
            if st.button("⚠️ Delete All Reviews"):
                conn = get_conn(); conn.cursor().execute("DELETE FROM reviews")
                conn.commit(); conn.close()
                st.warning("All reviews deleted."); st.rerun()

        with t3:
            section("Live Activity Logs")
            df_lg = get_activity_logs()
            if not df_lg.empty:
                st.dataframe(df_lg, use_container_width=True, height=350)
                ac = df_lg['action_type'].value_counts().reset_index()
                ac.columns = ['Action','Count']
                fig_ac = px.pie(ac, names='Action', values='Count', hole=0.4,
                                color_discrete_sequence=COLORS)
                fig_ac.update_layout(**PL, height=300)
                st.plotly_chart(fig_ac, use_container_width=True)
                if st.button("🗑️ Clear Logs"):
                    conn = get_conn(); conn.cursor().execute("DELETE FROM activity_logs")
                    conn.commit(); conn.close()
                    st.warning("Logs cleared."); st.rerun()
            else:
                st.info("No logs yet.")

        with t4:
            ai_tab, manual_tab, manage_tab = st.tabs(
                ["🤖 AI Generate Questions", "✍️ Add Manually", "🗂️ Manage Questions"]
            )

            # ── Sub-tab 1: AI Generation ──
            with ai_tab:
                section("🤖 AI se COVID Quiz Questions Generate Karein")
                st.markdown(
                    "<p style='color:#a0aabf'>Topic likhein aur AI automatically "
                    "COVID myth/fact questions generate karega.</p>",
                    unsafe_allow_html=True
                )
                ai_topic = st.text_input(
                    "Topic / Context",
                    "COVID-19 vaccines, symptoms, and prevention",
                    key="ai_topic"
                )
                ai_count = st.slider("Kitne questions generate karein?", 2, 8, 4, key="ai_count")

                if st.button("✨ Generate Questions via AI", key="ai_gen_btn"):
                    with st.spinner("AI questions generate kar raha hai..."):
                        ai_prompt = f"""Generate exactly {ai_count} COVID-19 quiz questions about: {ai_topic}.
Return ONLY a JSON array. Each item must have:
- "question": a clear statement (not a question form)
- "is_fact": 1 if true/fact, 0 if myth/false
- "explanation": 1-2 sentence medical explanation

Example format:
[{{"question": "...", "is_fact": 1, "explanation": "..."}}]

Return only valid JSON, nothing else."""
                        raw = call_groq(ai_prompt, system="You are a COVID-19 medical expert. Return only valid JSON arrays.")

                    if raw:
                        try:
                            import json, re
                            # Extract JSON array from response
                            match = re.search(r'\[.*\]', raw, re.DOTALL)
                            if match:
                                parsed = json.loads(match.group())
                                st.session_state['ai_generated_qs'] = parsed
                                st.success(f"✅ {len(parsed)} questions generate ho gaye! Niche review karein aur save karein.")
                            else:
                                st.error("AI ne sahi format mein jawab nahi diya. Dobara try karein.")
                        except Exception as e:
                            st.error(f"Parsing error: {e}")
                            st.code(raw)
                    else:
                        st.error("AI se connect nahi ho saka. API key check karein.")

                # Preview & Save generated questions
                if 'ai_generated_qs' in st.session_state and st.session_state['ai_generated_qs']:
                    hr()
                    section("📋 Generated Questions — Preview & Save")
                    gen_qs = st.session_state['ai_generated_qs']
                    valid = []
                    for i, q in enumerate(gen_qs):
                        q_text = q.get('question', '')
                        is_f   = int(q.get('is_fact', 0))
                        expl   = q.get('explanation', '')
                        badge  = '<span class="badge badge-green">✅ FACT</span>' if is_f else '<span class="badge badge-gold" style="color:#ff4b4b;border-color:#ff4b4b;background:rgba(255,75,75,.15)">❌ MYTH</span>'
                        st.markdown(f"""
                        <div class="glass-card" style="border-left:4px solid {'#00ff88' if is_f else '#ff4b4b'}">
                          <div style="display:flex;justify-content:space-between;align-items:flex-start">
                            <p style="color:white;font-weight:600;margin:0;flex:1">Q{i+1}. {q_text}</p>
                            {badge}
                          </div>
                          <p style="color:#a0aabf;font-size:13px;margin-top:8px">💡 {expl}</p>
                        </div>""", unsafe_allow_html=True)
                        if q_text and expl:
                            valid.append((q_text, is_f, expl))

                    col_s, col_c = st.columns(2)
                    with col_s:
                        if st.button("💾 Save All to Database", key="save_ai_qs"):
                            if valid:
                                bulk_insert_myth_questions(valid)
                                del st.session_state['ai_generated_qs']
                                st.success(f"✅ {len(valid)} questions saved!")
                                st.rerun()
                    with col_c:
                        if st.button("🗑️ Discard", key="discard_ai_qs"):
                            del st.session_state['ai_generated_qs']
                            st.rerun()

            # ── Sub-tab 2: Manual Add ─────
            with manual_tab:
                section("✍️ Manually Add Question")
                with st.form("quiz_form", clear_on_submit=True):
                    nq  = st.text_area("Question / Statement")
                    qt  = st.radio("Type", ["Myth 🔴", "Fact 🟢"])
                    ne_ = st.text_area("Medical Explanation")
                    if st.form_submit_button("➕ Add Question"):
                        if nq and ne_:
                            is_f = 1 if "Fact" in qt else 0
                            conn = get_conn(); c = conn.cursor()
                            c.execute(
                                "INSERT INTO myth_questions (question,is_fact,explanation) VALUES (?,?,?)",
                                (nq, is_f, ne_)
                            )
                            conn.commit(); conn.close()
                            st.success("✅ Question added!")
                        else:
                            st.error("Question aur Explanation dono zaroori hain.")

            # ── Sub-tab 3: Manage / Delete ──
            with manage_tab:
                section("🗂️ All Questions — Delete Individual")
                df_qs = get_myth_questions()
                if df_qs.empty:
                    st.info("Koi question nahi hai. Pehle add karein.")
                else:
                    for _, row in df_qs.iterrows():
                        is_f  = bool(row['is_fact'])
                        badge = '<span class="badge badge-green">FACT</span>' if is_f else '<span style="background:rgba(255,75,75,.15);color:#ff4b4b;border:1px solid #ff4b4b;border-radius:20px;padding:3px 12px;font-size:11px;font-weight:700">MYTH</span>'
                        col_q, col_del = st.columns([9, 1])
                        with col_q:
                            st.markdown(f"""
                            <div style="background:rgba(255,255,255,.03);padding:14px 18px;
                                        border-radius:12px;border:1px solid rgba(255,255,255,.07);
                                        margin-bottom:6px">
                              <div style="display:flex;gap:10px;align-items:center">
                                <span style="color:#a0aabf;font-size:12px">#{int(row['id'])}</span>
                                {badge}
                                <span style="color:white;font-size:14px">{row['question']}</span>
                              </div>
                              <p style="color:#a0aabf;font-size:12px;margin:6px 0 0 0">💡 {row['explanation']}</p>
                            </div>""", unsafe_allow_html=True)
                        with col_del:
                            st.markdown("<div style='margin-top:4px'>", unsafe_allow_html=True)
                            if st.button("🗑️", key=f"del_q_{row['id']}", help=f"Delete Q#{int(row['id'])}"):
                                delete_myth_question(int(row['id']))
                                st.success(f"Question #{int(row['id'])} deleted!")
                                st.rerun()
                            st.markdown("</div>", unsafe_allow_html=True)

                    hr()
                    if st.button("⚠️ Delete ALL Questions", key="del_all_qs"):
                        conn = get_conn()
                        conn.cursor().execute("DELETE FROM myth_questions")
                        conn.commit(); conn.close()
                        st.warning("Saare questions delete ho gaye!"); st.rerun()

    elif pw == "":
        st.info("Enter admin password to access controls.")
    else:
        st.error("❌ Incorrect password. Access denied.")


# PAGE 11 — HEALTH SHIELD

elif page == "Health Shield":
    ticker("🚨 NEW 2026 helplines launched &nbsp;|&nbsp; 💉 Vaccinations slots open for age 5-12 &nbsp;|&nbsp; 📞 Call 1075 for National COVID Helpline")
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(255,75,75,.18),rgba(162,0,255,.18));
                padding:28px;border-radius:20px;text-align:center;margin-bottom:22px;
                border:1px solid rgba(255,75,75,.3)">
      <h1 style="margin:0;color:white">🛡️ Health Shield</h1>
    </div>""", unsafe_allow_html=True)

    tab_symp, tab_hosp = st.tabs(["🧪 AI Symptom Checker","🏥 Hospital Directory"])

    with tab_symp:
        section("Self-Assessment Health Quiz")
        st.info("Note: This is for guidance only. For emergencies contact a doctor immediately.")
        score = 0
        q1 = st.radio("1. Do you have high fever (100°F+)?",["No","Yes"])
        q2 = st.radio("2. Difficulty breathing continuously?",["No","Yes"])
        q3 = st.radio("3. Persistent dry cough?",["No","Yes"])
        q4 = st.radio("4. Loss of taste or smell?",["No","Yes"])
        q5 = st.radio("5. Extreme fatigue or body ache?",["No","Yes"])
        if q1=="Yes": score+=2
        if q2=="Yes": score+=5
        if q3=="Yes": score+=3
        if q4=="Yes": score+=4
        if q5=="Yes": score+=2
        if st.button("📊 Get Risk Assessment"):
            log_activity("Symptom_Check", f"Score={score}")
            st.markdown("<br>", unsafe_allow_html=True)
            if score == 0:
                st.markdown('<div class="risk-low"><h3 style="color:#00ff88;margin:0">✅ LOW RISK</h3><p style="color:#e0e0e0">You appear safe. Maintain hygiene and stay masked in crowds.</p></div>', unsafe_allow_html=True)
            elif score <= 5:
                st.markdown('<div class="risk-medium"><h3 style="color:#ffc107;margin:0">⚠️ MEDIUM RISK</h3><p style="color:#e0e0e0">Mild symptoms. Isolate at home, rest, drink warm water and monitor.</p></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="risk-high"><h3 style="color:#ff4b4b;margin:0">🚨 HIGH RISK</h3><p style="color:#e0e0e0">Consult a doctor immediately and get your RT-PCR test done.</p></div>', unsafe_allow_html=True)
            st.progress(min(score/16, 1.0))
            st.caption(f"Risk Score: {score}/16")

    with tab_hosp:
        section("Live Hospital Resource Directory")
        city = st.selectbox("Select City", ["Delhi","Mumbai","Gorakhpur","Bangalore","Lucknow"])
        hospitals = {
            "Delhi":[["AIIMS","ICU (Ventilator)","Available",5,"011-26588500"],
                     ["Safdarjung","General Ward","Full",0,"011-26165060"],
                     ["Max Healthcare","Emergency","Available",5,"011-26515050"],
                     ["Apollo Delhi","Oxygen Bed","Available",8,"011-71791090"]],
            "Mumbai":[["Seven Hills","ICU","Available",10,"022-67676767"],
                      ["Nanavati Hospital","Oxygen Bed","Full",0,"022-26267500"],
                      ["Lilavati Hospital","General","Available",4,"022-26751000"],
                      ["Fortis Mumbai","Pediatric","Available",15,"022-43524352"]],
            "Gorakhpur":[["BRD Medical College","ICU","Available",20,"0551-2273307"],
                         ["St. Andrews","Emergency","Available",8,"0551-2333534"],
                         ["City Multispeciality","ICU","Full",0,"0551-2200100"],
                         ["Aarogyam Hospital","General Ward","Available",10,"0551-2500400"]],
            "Bangalore":[["Manipal Hospital","ICU","Available",15,"080-25024444"],
                         ["Narayana Health","General Ward","Available",22,"080-71222222"],
                         ["Fortis Bangalore","Oxygen Bed","Full",0,"080-66214444"],
                         ["St. Johns Medical","Isolation","Available",12,"080-22065000"]],
            "Lucknow":[["KGMU","ICU","Available",20,"0522-2257450"],
                       ["Medanta Lucknow","Emergency","Available",18,"0522-4505050"],
                       ["SGPGI","General Ward","Full",0,"0522-2668004"],
                       ["Sahara Hospital","Ventilator","Available",7,"0522-6780001"]],
        }
        df_h = pd.DataFrame(hospitals[city], columns=["Hospital","Department","Status","Beds","Contact"])
        def hl(v): return f"color:{'#ff4b4b' if v=='Full' else '#00ff88'};font-weight:700"
        st.dataframe(df_h.style.map(hl, subset=['Status']), use_container_width=True)

    hr()
    section("🛠️ Personal Health Tools")
    tt1,tt2,tt3,tt4 = st.tabs(["🫁 Oxygen Calc","💉 Vaccine Scheduler","🚨 SOS Generator","🧘 Mental Wellness"])

    with tt1:
        spo2 = st.slider("SpO2 Level (%)", 70, 100, 97)
        wt = st.number_input("Weight (kg)", 30, 150, 70)
        if st.button("🧮 Calculate"):
            if spo2 >= 95: st.success("✅ Normal oxygen level. Keep monitoring.")
            elif spo2 >= 90: st.warning(f"⚠️ Mild drop. ~{round(wt*0.1,1)} L/min flow may be needed. See a doctor.")
            else: st.error("🚨 Critical! Immediate oxygen support needed.")

    with tt2:
        last = st.date_input("Last Vaccine Dose Date")
        if st.button("📅 Calculate Next Dose"):
            nxt = last + datetime.timedelta(days=180)
            st.info(f"📅 Next booster: **{nxt.strftime('%d %B, %Y')}** (approx.)")

    with tt3:
        section("WhatsApp Emergency SOS Generator")
        sn = st.text_input("Patient Name")
        sr = st.selectbox("Requirement",["Oxygen Cylinder","ICU Bed","Normal Bed","Plasma/Blood","Ambulance"])
        sc = st.text_input("City / Location")
        sp = st.text_input("Contact Number")
        if st.button("🚨 Generate SOS Link"):
            if sn and sp:
                msg = f"🚨 *URGENT HELP NEEDED* 🚨%0A%0A👤 *Patient:* {sn}%0A🏥 *Need:* {sr}%0A📍 *Location:* {sc}%0A📞 *Contact:* {sp}"
                wa = f"https://api.whatsapp.com/send?text={msg}"
                st.markdown(f'<div class="glass-card" style="text-align:center"><p style="color:white">Message ready! Click to share:</p><a href="{wa}" target="_blank" style="display:inline-block;padding:12px 28px;background:#25D366;color:white;text-decoration:none;border-radius:25px;font-weight:700;box-shadow:0 4px 15px rgba(37,211,102,.4)">💬 Share on WhatsApp</a></div>', unsafe_allow_html=True)
            else:
                st.error("Patient name and contact required.")

    with tt4:
        st.markdown("""
        <div class="breathe-container">
          <div class="breathe-circle"></div>
          <p style="margin-top:38px;color:#a0aabf;font-weight:700;letter-spacing:3px;font-size:14px">INHALE ... EXHALE</p>
        </div>
        <p style="color:#a0aabf;text-align:center;margin-top:15px;font-size:13px">
          Follow the breathing circle to reduce anxiety and stress.<br>
          Inhale when it expands · Hold · Exhale when it contracts
        </p>""", unsafe_allow_html=True)


# PAGE 12 — COVID AI CHAT

elif page == "Covid AI Chat":
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(0,212,255,.18),rgba(0,255,136,.18));
                padding:28px;border-radius:20px;text-align:center;margin-bottom:24px;
                border:1px solid rgba(0,212,255,.3)">
      <h1 style="margin:0;color:white">✨ COVID-19 AI Assistant</h1>
      <p style="color:#a0aabf;margin:8px 0 0">Ask in Hindi or English • Upload images for AI analysis 🖼️</p>
    </div>""", unsafe_allow_html=True)

    with st.sidebar:
        hr()
        section("🕒 Recent Questions")
        if st.session_state.query_history:
            for q in reversed(st.session_state.query_history[-8:]):
                st.markdown(f'<div class="history-item">💬 {q}</div>', unsafe_allow_html=True)
        else:
            st.caption("No questions asked yet.")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.session_state.query_history = []
            st.rerun()

    # ── Quick Suggestions ─────────────────────────────────────────
    suggestions = ["COVID cases in India today?", "Japan ka recovery rate?",
                   "Global death toll?", "USA mein active cases?"]
    st.markdown("**💡 Quick Questions:**")
    sc1, sc2, sc3, sc4 = st.columns(4)
    prefill = None
    for col, sug in zip([sc1, sc2, sc3, sc4], suggestions):
        if col.button(sug, key=f"sug_{sug}"):
            prefill = sug

    # ── Image Upload Section ───────────────────────────────────────
    hr()
    st.markdown("<h4 style='color:#00d4ff;margin-bottom:8px'>🖼️ Image Analysis (Optional)</h4>",
                unsafe_allow_html=True)
    up_col, info_col = st.columns([1, 2])
    with up_col:
        chat_image = st.file_uploader(
            "Upload image for AI to analyze",
            type=["jpg", "jpeg", "png", "webp"],
            key="chat_image_uploader",
            help="Upload a medical report, chart, news screenshot, or any health-related image"
        )
    with info_col:
        st.markdown("""
        <div style="background:rgba(0,212,255,0.07);border:1px dashed rgba(0,212,255,0.4);
                    border-radius:12px;padding:14px;margin-top:4px">
          <p style="color:#a0aabf;font-size:13px;margin:0">
            📌 <b style='color:#00d4ff'>Kya upload kar sakte hain:</b><br>
            • COVID test reports / medical documents<br>
            • News screenshots ya charts<br>
            • X-Ray ya health scans<br>
            • Vaccination certificates<br>
            AI image ko analyze karke jawab dega 🤖
          </p>
        </div>""", unsafe_allow_html=True)
    hr()

    # ── Chat History Display ───────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Chat Input ────────────────────────────────────────────────
    user_q = st.chat_input("Ask your question in Hindi/English...") or prefill

    if user_q:
        log_activity("AI_Query", user_q)
        st.session_state.messages.append({"role": "user", "content": user_q})
        st.session_state.query_history.append(user_q)
        with st.chat_message("user"):
            st.markdown(user_q)

        ai = None

        if chat_image is not None:
            # Image uploaded: use vision AI
            with st.spinner("AI image analyze kar raha hai..."):
                img_bytes = chat_image.read()
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                vision_sys = (
                    "You are a professional COVID-19 and health AI assistant. "
                    "Analyze the uploaded image and answer the user question. "
                    "Reply in the same language as the user (Hindi/Hinglish/English)."
                )
                ai = call_groq_vision(
                    img_b64,
                    user_text="User sawaal: " + user_q + "\n\nIs image ka analysis karo.",
                    system=vision_sys
                )
                if not ai:
                    ai = "Image analyze nahi ho saka. Clear image upload karein."
        else:
            # Text only: detect location then fetch COVID data
            with st.spinner("AI soch raha hai..."):
                loc_p = (
                    "User question: '" + user_q + "'\n"
                    "If about global/world/duniya reply only: all\n"
                    "If about a specific country reply ONLY that country English name.\n"
                    "If no location mentioned reply only: general\n"
                    "Reply with one word only, nothing else."
                )
                loc = call_groq(loc_p)
                loc = loc.strip().strip('"').strip("'").strip() if loc else "general"
                # remove any extra words if model replied with a sentence
                loc = loc.split()[0] if loc else "general"

                if loc.lower() == "general":
                    sys_p = (
                        "You are a professional COVID-19 AI assistant with deep medical knowledge. "
                        "Answer concisely. Reply in same language as user (Hindi/Hinglish/English)."
                    )
                    ai = call_groq("Question: " + user_q, sys_p)
                    if not ai:
                        ai = "AI se jawab nahi mila. Thodi der baad retry karein."
                else:
                    cd, loc_name = fetch_covid_data_smart(loc)
                    if cd and isinstance(cd, dict) and "cases" in cd:
                        def _f(v):
                            try:
                                return f"{int(v):,}"
                            except Exception:
                                return str(v)
                        ctx = (
                            "COVID-19 live data for " + str(loc_name) + ":\n"
                            "Cases: " + _f(cd.get("cases", 0)) + "\n"
                            "Today Cases: " + _f(cd.get("todayCases", 0)) + "\n"
                            "Deaths: " + _f(cd.get("deaths", 0)) + "\n"
                            "Recovered: " + _f(cd.get("recovered", 0)) + "\n"
                            "Active: " + _f(cd.get("active", 0)) + "\n"
                            "Tests: " + _f(cd.get("tests", 0))
                        )
                        sys_p = (
                            "You are a COVID-19 AI assistant. "
                            "Use the live data to answer conversationally. "
                            "Reply in same language as user. Be concise."
                        )
                        ai = call_groq("Data:\n" + ctx + "\n\nQuestion: " + user_q, sys_p)
                        if not ai:
                            ai = "Data for " + str(loc_name) + ":\n" + ctx
                    else:
                        sys_p = "You are a COVID-19 AI. Live data unavailable. Answer from knowledge. Same language as user."
                        ai = call_groq("Question: " + user_q, sys_p)
                        if not ai:
                            ai = "Live data nahi mila. Country name check karein ya retry karein."

        # Show response — NO st.rerun() to prevent duplicate/loop issue
        if ai:
            with st.chat_message("assistant"):
                st.markdown(ai)
            st.session_state.messages.append({"role": "assistant", "content": ai})


# PAGE 13 — MYTH BUSTER GAME

elif page == "Myth Buster Game":
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(255,75,75,.18),rgba(0,212,255,.18));
                padding:28px;border-radius:20px;text-align:center;margin-bottom:24px;
                border:1px solid rgba(0,212,255,.3)">
      <h1 style="margin:0;color:white">🎮 COVID Myth Buster</h1>
      <p style="color:#a0aabf;margin:8px 0 0">Can you tell Myths from Facts? Score +10 for each correct answer!</p>
    </div>""", unsafe_allow_html=True)

    questions = get_myth_questions().to_dict('records')
    if not questions:
        st.warning("No questions available. Ask admin to add some."); st.stop()

    cur = st.session_state.mb_q_index
    if cur < len(questions):
        prog = cur / len(questions)
        c1,c2 = st.columns([3,1])
        with c1:
            st.progress(prog)
            st.markdown(f"<p style='color:#a0aabf;font-size:13px'>Question {cur+1} of {len(questions)}</p>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='background:rgba(0,255,136,.1);border:1px solid #00ff88;padding:10px;border-radius:10px;text-align:center'><h3 style='margin:0;color:#00ff88'>🏆 {st.session_state.mb_score}</h3></div>", unsafe_allow_html=True)

        q = questions[cur]
        st.markdown(f"""
        <div class="glass-card" style="border-left:5px solid #00d4ff">
          <h2 style="color:white;line-height:1.5">🤔 "{q['question']}"</h2>
        </div>""", unsafe_allow_html=True)

        if not st.session_state.mb_show_exp:
            b1,b2 = st.columns(2)
            with b1:
                if st.button("🔴 MYTH (False)", use_container_width=True):
                    st.session_state.mb_answered_correct = (not bool(q['is_fact']))
                    if st.session_state.mb_answered_correct: st.session_state.mb_score += 10
                    st.session_state.mb_show_exp = True; st.rerun()
            with b2:
                if st.button("🟢 FACT (True)", use_container_width=True):
                    st.session_state.mb_answered_correct = bool(q['is_fact'])
                    if st.session_state.mb_answered_correct: st.session_state.mb_score += 10
                    st.session_state.mb_show_exp = True; st.rerun()
        else:
            if st.session_state.mb_answered_correct:
                st.success("🎉 Correct! +10 Points")
            else:
                st.error("❌ Wrong answer!")
            st.info(f"**Explanation:** {q['explanation']}")
            if st.button("Next ➡️", use_container_width=True):
                st.session_state.mb_q_index += 1
                st.session_state.mb_show_exp = False; st.rerun()
    else:
        st.balloons()
        fs = st.session_state.mb_score
        mx = len(questions) * 10
        pct = fs/mx if mx>0 else 0
        msg = "🏆 Perfect! You're a COVID expert!" if pct==1 else ("👍 Great job!" if pct>=0.6 else "📚 Keep learning!")
        col = "#00ff88" if pct==1 else ("#00d4ff" if pct>=0.6 else "#ff4b4b")
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.04);padding:40px;border-radius:20px;
                    text-align:center;border:2px solid {col};box-shadow:0 0 25px {col}40">
          <h1 style="font-size:52px;margin:0">🎯 {fs} / {mx}</h1>
          <h3 style="color:{col}">{msg}</h3>
          <div style="margin-top:15px">
            <span style="color:#a0aabf">Accuracy: </span>
            <span style="color:{col};font-weight:700;font-size:20px">{pct*100:.0f}%</span>
          </div>
        </div>""", unsafe_allow_html=True)

        hr()
        section("💾 Save Your Score to Leaderboard")
        lb_name = st.text_input("Your display name", value=st.session_state.user_data[0] if st.session_state.logged_in else "")
        if st.button("Save Score"):
            if lb_name:
                save_leaderboard_score(lb_name, fs, mx)
                st.success("Score saved!")

        hr()
        section("🏆 Leaderboard — Top Players")
        lb = get_leaderboard(10)
        if not lb.empty:
            medals = ["🥇","🥈","🥉"] + ["🏅"]*(len(lb)-3)
            for i,(_, row) in enumerate(lb.iterrows()):
                pct_s = row['best_score']/row['total'] if row['total']>0 else 0
                st.markdown(f"""
                <div class="lb-row">
                  <span style="font-size:22px">{medals[i]}</span>
                  <span style="color:white;font-weight:600;flex:1;margin-left:15px">{row['username']}</span>
                  <span style="color:#00ff88;font-weight:700">{int(row['best_score'])} pts</span>
                  <span style="color:#a0aabf;font-size:12px;margin-left:12px">({pct_s*100:.0f}%)</span>
                </div>""", unsafe_allow_html=True)

        if st.button("🔄 Play Again", use_container_width=True):
            st.session_state.mb_score = 0
            st.session_state.mb_q_index = 0
            st.session_state.mb_show_exp = False; st.rerun()