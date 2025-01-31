import os
import json
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import Json
from datetime import datetime
import requests
import google.generativeai as genai
import random


def construct_meme_prompt(
    user_input: str,
    meme_context: list,
    previous_attempts: list = None
) -> str:
    """
    Constructs a prompt for the meme generation model with randomized meme context.
    """
    if not user_input.strip():
        raise ValueError("user_input must be non-empty")
    if not meme_context:
        raise ValueError("meme_context must be non-empty")
    
    print(f"\n[PROMPT CONSTRUCTION] Starting with user input: {user_input}")

    # Shuffle the meme context
    shuffled_context = list(meme_context)  # Create a copy
    random.shuffle(shuffled_context)
    
    sections = []
    
    # Add failed attempts if they exist
    if previous_attempts:
        sections.append("PREVIOUS ATTEMPTS (TRY A DIFFERENT TEMPLATE):")
        sections.extend(str(attempt) for attempt in previous_attempts)
    
    sections.extend([
        f"USER INPUT: {user_input.strip()}",
        f"AVAILABLE CONTEXT: {str(shuffled_context)}"
    ])

    print("[PROMPT CONSTRUCTION] Prompt constructed successfully")
    
    return "\n\n".join(sections)

def clean_response(response: str) -> str:
    """
    Cleans AI response to ensure valid JSON formatting.
    Handles edge cases with 'json' prefix and smart quote issues.
    """
    # Remove 'json' prefix and newlines at start
    cleaned = response.lstrip('json\n')
    
    # Remove markdown code blocks and backticks
    cleaned = cleaned.strip('`').replace('```json', '').replace('```', '')
    
    # Replace various quote types with standard double quotes
    cleaned = cleaned.replace('"', '"').replace('"', '"').replace("'", '"')
    
    # Handle escaped quotes inside text strings
    cleaned = cleaned.replace('\\"', '"')

    
    # Remove any trailing commas before closing braces
    cleaned = cleaned.replace(',}', '}')
    cleaned = cleaned.replace(',]', ']')
    
    return cleaned.strip()

def generate_meme_completion(
    prompt: str,
    model: Any,
    max_attempts: int = 5,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generates a meme completion and validates JSON output, with multiple attempts.
    Includes JSON formatting instructions in prompt.
    """
    if config is None:
        config = {
            'max_output_tokens': 1000,
            'temperature': 0.1,
        }
    
    # # debug - I don't think this should be here, this belongs in prompt construction
    # # Add JSON formatting instructions to prompt
    # json_prompt = f"""
    # {prompt}

    # IMPORTANT: Respond with ONLY a valid JSON object containing template_id, text0, and text1.
    # Example format:
    # {{
    #     "template_id": "123456",
    #     "text0": "top text",
    #     "text1": "bottom text"
    # }}
    # """
    
    last_error = None
    for attempt in range(max_attempts):
        try:
            # Generate completion
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(**config)
            )
            
            if not response.text:
                last_error = RuntimeError("Model returned empty response")
                continue
            
            # Clean the response text
            cleaned_response = clean_response(response.text)
            
            # Parse JSON response
            meme_data = json.loads(cleaned_response)
            
            # # debug - this is the source of the drake error, methinks
            # # Validate required keys
            # required_keys = ['template_id', 'text0', 'text1']
            # if not all(key in meme_data for key in required_keys):
            #     missing_keys = [key for key in required_keys if key not in meme_data]
            #     raise ValueError(f"Missing required keys: {missing_keys}")
            
            return meme_data
            
        except (json.JSONDecodeError, ValueError) as e:
            last_error = RuntimeError(f"Invalid JSON in model response (attempt {attempt + 1}/{max_attempts}): {e}")
            continue  # Try again
            
    # If we get here, all attempts failed
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
                "host": os.getenv("DB_HOST"),
                "port": os.getenv("DB_PORT")
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