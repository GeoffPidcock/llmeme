import json
import random
import google.generativeai as genai

def initialize_model(api_key, model_name, system_prompt):
    """Initialize Gemini model with system prompt"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
    )
    return model

def construct_meme_prompt(user_input, meme_context, previous_attempts=None):
    """
    Construct prompt for meme generation with previous attempts context.
    
    Args:
        user_input: The user's request
        meme_context: List of available meme templates
        previous_attempts: List of previous meme generation attempts to avoid repetition
        
    Returns:
        Formatted prompt string
    """
    if not user_input.strip():
        return {"error": "Empty user input"}
    
    # Shuffle the meme context
    shuffled_context = list(meme_context)  # Create a copy
    random.shuffle(shuffled_context)
    
    sections = []
    
    # Add previous attempts context to encourage diversity
    if previous_attempts and len(previous_attempts) > 0:
        sections.append("PREVIOUS ATTEMPTS (TRY A DIFFERENT TEMPLATE):")
        for i, attempt in enumerate(previous_attempts):
            if isinstance(attempt, dict):
                sections.append(f"Attempt {i+1}: {json.dumps(attempt)}")
            else:
                sections.append(f"Attempt {i+1}: {str(attempt)}")
    
    sections.append("""
    IMPORTANT: Respond with ONLY a valid JSON object containing template_id, text0, and text1.
    Example format:
    {
        "template_id": "123456",
        "text0": "top text",
        "text1": "bottom text"
    }
    """)
    
    sections.extend([
        f"USER INPUT: {user_input.strip()}",
        f"AVAILABLE CONTEXT: {str(shuffled_context[:10])}"  # Limit to 10 for brevity
    ])

    return "\n\n".join(sections)

def clean_response(response_text):
    """
    Cleans AI response to ensure valid JSON formatting.
    Handles edge cases with 'json' prefix and smart quote issues.
    """
    # Remove 'json' prefix and newlines at start
    cleaned = response_text.lstrip('json\n')
    
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

def generate_meme_completion(prompt_text, meme_context, model, max_attempts=3, previous_attempts=None):
    """
    Generate meme completion from Gemini with diversity encouragement.
    
    Args:
        prompt_text: The user's request
        meme_context: List of available meme templates
        model: Initialized Gemini model
        max_attempts: Number of retry attempts for generation
        previous_attempts: List of previous meme generations to avoid repetition
        
    Returns:
        Meme data dictionary or error
    """
    config = {
        'max_output_tokens': 1000,
        'temperature': 0.1,
    }
    
    # Construct prompt with previous attempts if available
    meme_prompt = construct_meme_prompt(prompt_text, meme_context, previous_attempts)
    
    last_error = None
    for attempt in range(max_attempts):
        try:
            # Generate completion
            response = model.generate_content(
                meme_prompt,
                generation_config=genai.GenerationConfig(**config)
            )
            
            if not response.text:
                last_error = RuntimeError("Model returned empty response")
                continue
            
            # Clean the response text
            cleaned_response = clean_response(response.text)
            
            # Parse JSON response
            meme_data = json.loads(cleaned_response)
            
            # Validate required keys
            required_keys = ['template_id']
            missing_keys = [key for key in required_keys if key not in meme_data]
            
            if missing_keys:
                last_error = ValueError(f"Missing required keys: {missing_keys}")
                continue
            
            return meme_data
            
        except (json.JSONDecodeError, ValueError) as e:
            last_error = RuntimeError(f"Invalid JSON in model response (attempt {attempt + 1}/{max_attempts}): {e}")
            continue
            
    # If we get here, all attempts failed
    return {"error": f"Failed after {max_attempts} attempts. Last error: {str(last_error)}"}