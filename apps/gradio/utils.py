import os
import json
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import Json
from datetime import datetime
import requests
import google.generativeai as genai

def construct_meme_prompt(
    user_input: str,
    meme_context: list,
    previous_attempts: list = None
) -> str:
    """Constructs a prompt for the meme generation model."""
    print(f"\n[PROMPT CONSTRUCTION] Starting with user input: {user_input}")
    
    # Input validation
    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("user_input must be a non-empty string")
    if not isinstance(meme_context, list) or not meme_context:
        raise ValueError("meme_context must be a non-empty list")
    
    # Construct the prompt
    prompt_parts = []
    
    # Add previous attempts if they exist
    if previous_attempts and len(previous_attempts) > 0:
        print(f"[PROMPT CONSTRUCTION] Including {len(previous_attempts)} previous attempts")
        declined_memes = "DECLINED MEMES (MAKE SOMETHING ELSE USING USER INPUT AND CONTEXT)\n===="
        for attempt in previous_attempts:
            declined_memes += f"\n{attempt}\n"
        prompt_parts.append(declined_memes)
    
    # Add user input and context
    prompt_parts.extend([
        f"USER INPUT:\n{user_input.strip()}",
        "====",
        f"AVAILABLE CONTEXT:\n{str(meme_context)}"
    ])
    
    final_prompt = "\n".join(prompt_parts)
    print("[PROMPT CONSTRUCTION] Prompt constructed successfully")
    return final_prompt

def generate_meme_completion(
    prompt: str,
    model: Any,
    max_attempts: int = 5,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generates a meme completion using the model."""
    print("\n[MEME GENERATION] Starting meme generation")
    
    if config is None:
        config = {
            'max_output_tokens': 1000,
            'temperature': 0.1,
        }
    
    last_error = None
    for attempt in range(max_attempts):
        print(f"[MEME GENERATION] Attempt {attempt + 1}/{max_attempts}")
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(**config)
            )
            
            if not response.text:
                raise RuntimeError("Model returned empty response")
                
            meme_data = json.loads(response.text)
            print("[MEME GENERATION] Successfully generated and parsed meme data")
            return meme_data
            
        except (json.JSONDecodeError, RuntimeError) as e:
            last_error = f"Attempt {attempt + 1} failed: {str(e)}"
            print(f"[MEME GENERATION] {last_error}")
            continue
            
    raise RuntimeError(f"Failed after {max_attempts} attempts. Last error: {last_error}")

def create_imgflip_meme(
    meme_data: Dict[str, Any],
    api_url: str = "https://api.imgflip.com/caption_image"
) -> Dict[str, Any]:
    """Creates a meme using the imgflip API."""
    print("\n[IMGFLIP API] Sending request to imgflip")
    
    try:
        response = requests.post(api_url, data=meme_data)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('success'):
            print("[IMGFLIP API] Successfully created meme")
            return {
                'success': True,
                'image_url': response_data['data']['url'],
                'raw_response': response_data
            }
        else:
            error_msg = response_data.get('error_message', 'Unknown error')
            print(f"[IMGFLIP API] Error: {error_msg}")
            return {
                'success': False,
                'error_message': error_msg,
                'raw_response': response_data
            }
            
    except Exception as e:
        print(f"[IMGFLIP API] Request failed: {str(e)}")
        raise RuntimeError(f"API request failed: {str(e)}")

def log_event(
    session_id: str,
    event_type: str,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    db_params: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """Logs an event to the PostgreSQL database."""
    print(f"\n[DATABASE] Logging event type: {event_type}")
    
    # Use default db_params if none provided
    if db_params is None:
        # Try to use socket connection first
        if os.path.exists('/var/run/postgresql/.s.PGSQL.5432'):
            db_params = {
                "dbname": "postgres",
                "user": os.getenv("DB_USER"),
                "password": os.getenv("DB_PASSWORD")
            }
        else:
            # Fall back to TCP connection
            db_params = {
                "dbname": "postgres",
                "user": os.getenv("DB_USER"),
                "password": os.getenv("DB_PASSWORD"),
                "host": os.getenv("DB_HOST", "localhost"),
                "port": os.getenv("DB_PORT", "5432")
            }
    
    # Add default metadata
    full_metadata = {
        "timestamp_utc": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }
    if metadata:
        full_metadata.update(metadata)
    
    try:
        # Establish connection
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        
        # Insert event
        insert_sql = """
        INSERT INTO events (session_id, type, data, metadata)
        VALUES (%s, %s, %s::jsonb, %s::jsonb)
        RETURNING event_id;
        """
        
        cur.execute(insert_sql, (
            session_id,
            event_type,
            Json(data),
            Json(full_metadata)
        ))
        
        event_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"[DATABASE] Successfully logged event with ID: {event_id}")
        return str(event_id)
        
    except psycopg2.Error as e:
        print(f"[DATABASE] Error: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()