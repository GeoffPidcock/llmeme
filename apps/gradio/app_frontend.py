import gradio as gr
import google.generativeai as genai
import json
import os
from uuid import uuid4
from utils import construct_meme_prompt, generate_meme_completion, create_imgflip_meme, log_event
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from both .env and shell
load_dotenv()  # This adds .env variables to os.environ
os.environ.update(os.environ)  # Ensure shell variables are included

# # Environment check at startup
# print("\n=== Environment Check ===")
# required_env_vars = [
#     'GEMINI_API_KEY',
#     'IMGFLIP_USERNAME',
#     'IMGFLIP_PASSWORD',
#     'DB_HOST',
#     'DB_PORT',
#     'DB_USER',
#     'DB_PASSWORD'
# ]

# for var in required_env_vars:
#     value = os.getenv(var)
#     if value:
#         # Show first few chars of sensitive data
#         masked_value = value[:4] + '****' if 'KEY' in var or 'PASSWORD' in var else value
#         print(f"✓ {var} is set: {masked_value}")
#     else:
#         print(f"✗ {var} is not set!")

# print("=====================\n")

# # Test database connection
# try:
#     test_session_id = str(uuid4())  # Generate proper UUID
#     test_event_id = log_event(
#         session_id=test_session_id,
#         event_type="startup",
#         data={"status": "initializing"},
#     )
#     print(f"Database connection successful (test event ID: {test_event_id})")
# except Exception as e:
#     print(f"Warning: Database connection failed: {e}")
#     print("The app will continue without database logging")

# Load configuration and context
with open('system_prompt.txt', 'r') as f:
    system_prompt = f.read()

with open('memes20250128.json', 'r') as f:
    meme_context = json.load(f)

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction=system_prompt,
)

def generate_meme(prompt: str, state: dict = None) -> tuple:
    """Generate a meme based on the user prompt."""
    if state is None:
        state = {"session_id": str(uuid4()), "previous_attempts": []}
    
    try:
        # Generate meme specification
        full_prompt = construct_meme_prompt(
            prompt, 
            meme_context, 
            state["previous_attempts"]
        )
        
        meme_data = generate_meme_completion(
            prompt=full_prompt,
            model=model,
            max_attempts=10
        )
        
        # Add imgflip credentials
        meme_data.update({
            'username': os.getenv('IMGFLIP_USERNAME'),
            'password': os.getenv('IMGFLIP_PASSWORD')
        })
        
        # Create meme
        imgflip_response = create_imgflip_meme(meme_data)
        
        if imgflip_response['success']:
            # Store attempt for potential retry
            state["previous_attempts"].append(meme_data)
            state["current_meme_url"] = imgflip_response['image_url']
            
            # Log success
            log_event(
                session_id=state["session_id"],
                event_type="meme_created",
                data={
                    "prompt": prompt,
                    "image_url": imgflip_response['image_url'],
                    "template_id": meme_data['template_id']
                },
                metadata={
                    "client_timestamp": datetime.now().isoformat()
                }
            )
            
            return (
                imgflip_response['image_url'],  # Display image
                gr.update(visible=True),        # Show buttons
                state                           # Update state
            )
            
        else:
            raise RuntimeError(f"Meme creation failed: {imgflip_response['error_message']}")
            
    except Exception as e:
        # Log error
        log_event(
            session_id=state["session_id"],
            event_type="error",
            data={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "prompt": prompt
            }
        )
        return (
            None,                      # No image
            gr.update(visible=False),  # Hide buttons
            state                      # Keep state
        )

def like_meme(state: dict) -> None:
    """Log when a user likes a meme."""
    if state and "current_meme_url" in state:
        log_event(
            session_id=state["session_id"],
            event_type="meme_liked",
            data={
                "image_url": state["current_meme_url"]
            },
            metadata={
                "client_timestamp": datetime.now().isoformat()
            }
        )
        return "Thanks for the feedback! Try another one or generate a new meme."

# Define the Gradio interface
with gr.Blocks() as app:
    gr.Markdown("# 🎭 LLMeme")
    gr.Markdown("Enter a prompt and I'll create a meme for you!")
    
    # State management
    state = gr.State(value=None)
    
    with gr.Row():
        prompt = gr.Textbox(
            label="Your meme idea",
            placeholder="Example: I am trying to create a funny meme using AI, and I think AI is holding me back",
            lines=2
        )
    
    with gr.Row():
        submit_btn = gr.Button("Generate Meme!", variant="primary")
    
    with gr.Row():
        image_output = gr.Image(
            label="Your Meme",
            show_label=False,
        )
    
    with gr.Row(visible=False) as button_row:
        retry_btn = gr.Button("Try Another", variant="secondary")
        like_btn = gr.Button("I like this one!", variant="primary")
    
    feedback_text = gr.Textbox(
        label="Feedback",
        interactive=False,
        visible=False
    )
    
    # Event handlers
    submit_btn.click(
        fn=generate_meme,
        inputs=[prompt, state],
        outputs=[image_output, button_row, state]
    )
    
    retry_btn.click(
        fn=generate_meme,
        inputs=[prompt, state],
        outputs=[image_output, button_row, state]
    )
    
    like_btn.click(
        fn=like_meme,
        inputs=[state],
        outputs=[feedback_text]
    ).then(
        lambda: gr.update(visible=True),
        None,
        [feedback_text]
    )
    
if __name__ == "__main__":
    app.launch()