import sqlite3
from datetime import datetime
import json

# Database path - defined as a constant
DB_PATH = 'meme_evaluations.db'

def get_db_connection():
    """Get a fresh database connection that's safe for the current thread"""
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    """Initialize SQLite database for storing evaluations"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        model TEXT NOT NULL
    )''')
    
    # Create evaluations table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        prompt TEXT NOT NULL,
        meme_template_id TEXT,
        gemini_json TEXT,
        imgflip_url TEXT,
        is_humor INTEGER,
        is_creative INTEGER,
        is_shareable INTEGER,
        comments TEXT,
        error TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions (id)
    )''')
    
    conn.commit()
    conn.close()

def create_session(name, model_name):
    """Create a new evaluation session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO sessions (name, timestamp, model) VALUES (?, ?, ?)",
            (name, datetime.now().isoformat(), model_name)
        )
        
        conn.commit()
        session_id = cursor.lastrowid
        return session_id
    finally:
        conn.close()

def save_evaluation(session_id, prompt, gemini_json, imgflip_url, 
                   is_humor, is_creative, is_shareable, comments, error=None):
    """Save an evaluation to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Extract meme template ID from gemini_json if available
        meme_template_id = None
        if isinstance(gemini_json, dict) and 'template_id' in gemini_json:
            meme_template_id = gemini_json['template_id']
        
        cursor.execute(
            "INSERT INTO evaluations VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, prompt, meme_template_id,
             json.dumps(gemini_json) if isinstance(gemini_json, dict) else gemini_json, 
             imgflip_url, 
             1 if is_humor else 0, 1 if is_creative else 0, 1 if is_shareable else 0,
             comments, error, datetime.now().isoformat())
        )
        
        conn.commit()
    finally:
        conn.close()

def get_evaluation_summary(session_id=None):
    """Get summary of evaluations, optionally filtered by session_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if session_id:
            cursor.execute("""
                SELECT 
                    s.name,
                    COUNT(*) as total,
                    SUM(e.is_humor) as humor_count,
                    SUM(e.is_creative) as creative_count,
                    SUM(e.is_shareable) as shareable_count,
                    COUNT(DISTINCT e.meme_template_id) as unique_templates
                FROM evaluations e
                JOIN sessions s ON e.session_id = s.id
                WHERE e.session_id = ?
                GROUP BY e.session_id
            """, (session_id,))
        else:
            cursor.execute("""
                SELECT 
                    s.name,
                    COUNT(*) as total,
                    SUM(e.is_humor) as humor_count,
                    SUM(e.is_creative) as creative_count,
                    SUM(e.is_shareable) as shareable_count,
                    COUNT(DISTINCT e.meme_template_id) as unique_templates
                FROM evaluations e
                JOIN sessions s ON e.session_id = s.id
                GROUP BY e.session_id
            """)
        
        results = cursor.fetchall()
        return results
    finally:
        conn.close()

def get_template_diversity(session_id):
    """Get diversity of meme templates used in a session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                meme_template_id,
                COUNT(*) as count
            FROM evaluations
            WHERE session_id = ?
            GROUP BY meme_template_id
            ORDER BY count DESC
        """, (session_id,))
        
        results = cursor.fetchall()
        return results
    finally:
        conn.close()