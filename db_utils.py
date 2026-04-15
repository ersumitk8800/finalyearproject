import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = "database.db"


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reviews
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, country TEXT, review TEXT, rating INTEGER,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # Migration: add timestamp column to old tables that don't have it
    try:
        c.execute("ALTER TABLE reviews ADD COLUMN timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        conn.commit()
    except Exception:
        pass  # Column already exists, ignore
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, name TEXT, email TEXT, bio TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS news
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT,
                  image_url TEXT, image_size INTEGER,
                  date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT,
                  action_type TEXT, action_details TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS myth_questions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT,
                  is_fact INTEGER, explanation TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leaderboard
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT,
                  score INTEGER, total INTEGER,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # Default myth questions
    c.execute("SELECT COUNT(*) FROM myth_questions")
    if c.fetchone()[0] == 0:
        defaults = [
            ("Garmi (High Temperature) aane se COVID-19 virus apne aap mar jata hai.", 0,
             "Bilkul galat! WHO ke mutabiq, COVID-19 kisi bhi mausam mein fail sakta hai."),
            ("Vaccine lagwane ke baad bhi aap doosron ko virus fela sakte hain.", 1,
             "Sach! Vaccine aapko serious bimari se bachati hai, lekin aap virus carrier ban sakte hain."),
            ("Antibiotics lene se COVID-19 theek ho jata hai.", 0,
             "Myth! COVID-19 ek Virus hai, aur Antibiotics sirf Bacteria par kaam karti hain."),
            ("Aarogya Setu ya contact tracing apps madadgar saabit hue hain.", 1,
             "Fact! In apps ne suruwat mein hotspots identify karne me badi bhumika nibhayi thi."),
            ("Garam paani peene aur bhaap (steam) lene se virus body se nikal jata hai.", 0,
             "Myth! Bhaap lene se gale me aaram milta hai, par ye virus ko maar nahi sakta."),
            ("Masks pehenna COVID-19 se suraksha mein madad karta hai.", 1,
             "Bilkul sach! N95 ya surgical masks droplets ka transmission rokne mein kaafi effective hain."),
            ("5G towers COVID-19 virus spread karte hain.", 0,
             "Ek bada jhooth! Viruses radio waves ya mobile networks par travel nahi kar sakte."),
            ("COVID-19 se recover hone ke baad bhi dobara infection ho sakta hai.", 1,
             "Sach! Reinfection possible hai, isliye vaccinated rehna zaroori hai.")
        ]
        c.executemany(
            "INSERT INTO myth_questions (question, is_fact, explanation) VALUES (?,?,?)",
            defaults
        )
    conn.commit()
    conn.close()

def log_activity(action_type, action_details):
    try:
        conn = get_conn()
        c = conn.cursor()
        user = "Guest"
        if st.session_state.get('logged_in') and st.session_state.get('user_data'):
            user = st.session_state.user_data[0]
        c.execute(
            "INSERT INTO activity_logs (username, action_type, action_details) VALUES (?,?,?)",
            (user, action_type, str(action_details))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_leaderboard_score(username, score, total):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO leaderboard (username, score, total) VALUES (?,?,?)",
        (username, score, total)
    )
    conn.commit()
    conn.close()

def get_leaderboard(limit=10):
    conn = get_conn()
    df = pd.read_sql_query(
        f"SELECT username, MAX(score) as best_score, total FROM leaderboard GROUP BY username ORDER BY best_score DESC LIMIT {limit}",
        conn
    )
    conn.close()
    return df

def get_all_reviews():
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM reviews ORDER BY timestamp DESC", conn)
    except Exception:
        # Fallback if timestamp column missing (very old DB)
        df = pd.read_sql_query("SELECT * FROM reviews", conn)
    conn.close()
    return df

def get_user_reviews(name):
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT country, review, rating, timestamp FROM reviews WHERE name=? ORDER BY timestamp DESC",
            conn, params=(name,)
        )
    except Exception:
        df = pd.read_sql_query(
            "SELECT country, review, rating FROM reviews WHERE name=?",
            conn, params=(name,)
        )
    conn.close()
    return df

def get_activity_logs():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT 200",
        conn
    )
    conn.close()
    return df

def get_myth_questions():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM myth_questions", conn)
    conn.close()
    return df

def delete_myth_question(question_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM myth_questions WHERE id=?", (question_id,))
    conn.commit()
    conn.close()

def bulk_insert_myth_questions(questions: list):
    """questions = list of (question, is_fact, explanation) tuples"""
    conn = get_conn()
    c = conn.cursor()
    c.executemany(
        "INSERT INTO myth_questions (question, is_fact, explanation) VALUES (?,?,?)",
        questions
    )
    conn.commit()
    conn.close()
