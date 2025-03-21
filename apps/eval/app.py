import os
import pickle
import gradio as gr
from dotenv import load_dotenv
from datetime import datetime

# Import utility modules
from utils.db import init_db, create_session, save_evaluation
from utils.gemini import initialize_model, generate_meme_completion
from utils.imgflip import create_imgflip_meme

# Load environment variables
load_dotenv()

# --- CONFIGURATION SECTION (edit these as needed) ---
# Load system prompt
with open('data/system_prompt.txt', 'r') as f:
    system_prompt = f.read()

# Load meme context
with open('data/memes20250128.pkl', 'rb') as f:
    meme_context = pickle.load(f)

# Load test prompts
with open('data/prompts.pkl', 'rb') as f:
    test_prompts = pickle.load(f)

# Configure model - EASY TO CHANGE
MODEL_NAME = 'gemini-1.5-flash'  # Change this line to switch models

# --- GRADIO APP ---
# Global state
current_prompt_idx = 0
current_session_id = None
current_results = None  # Will hold multiple results per prompt
selected_meme_index = None  # Track which meme variation is selected

# Initialize model
model = initialize_model(os.getenv('GEMINI_API_KEY'), MODEL_NAME, system_prompt)

# Initialize database schema (just create tables, no persistent connection)
init_db()

# Process a prompt through the entire pipeline
def process_prompt(prompt_text, num_variations=3):
    """
    Process a prompt through Gemini and ImgFlip, generating multiple variations.
    
    Args:
        prompt_text: The user prompt
        num_variations: Number of meme variations to generate
        
    Returns:
        List of result dictionaries
    """
    results = []
    previous_attempts = []
    
    for i in range(num_variations):
        try:
            # Generate meme completion with previous attempts for context
            meme_json = generate_meme_completion(prompt_text, meme_context, model, 
                                               previous_attempts=previous_attempts)
            
            if "error" in meme_json:
                results.append({
                    'success': False, 
                    'gemini_json': meme_json,
                    'error': meme_json["error"],
                    'attempt': i + 1
                })
                continue
                
            # Add to previous attempts to encourage diversity
            previous_attempts.append(meme_json)
                
            # Create meme with imgflip
            imgflip_result = create_imgflip_meme(meme_json)
            
            if imgflip_result["success"]:
                results.append({
                    'success': True,
                    'gemini_json': meme_json,
                    'image_url': imgflip_result["image_url"],
                    'attempt': i + 1
                })
            else:
                results.append({
                    'success': False,
                    'gemini_json': meme_json,
                    'error': imgflip_result["error_message"],
                    'attempt': i + 1
                })
        except Exception as e:
            results.append({
                'success': False,
                'error': str(e),
                'attempt': i + 1
            })
    
    return results

# Create Gradio interface
with gr.Blocks(title="Meme Evaluation") as app:
    gr.Markdown("# Meme Evaluation Tool")
    
    # Session information
    with gr.Row():
        experiment_input = gr.Textbox(
            label="Experiment Notes", 
            placeholder="What changed in this experiment?",
            lines=2
        )
        start_btn = gr.Button("Start Evaluation")
    
    # Prompt display
    prompt_display = gr.Textbox(label="Current Prompt", interactive=False)
    
    # Meme displays - creating a gallery for multiple memes
    gr.Markdown("### Generated Memes (3 variations)")
    
    # Container for multiple meme displays
    with gr.Row():
        # First meme
        with gr.Column():
            meme_image1 = gr.Image(label="Variation 1")
            error_display1 = gr.Textbox(label="Error", visible=False)
            select_btn1 = gr.Button("Select This Meme")
        
        # Second meme
        with gr.Column():
            meme_image2 = gr.Image(label="Variation 2")
            error_display2 = gr.Textbox(label="Error", visible=False)
            select_btn2 = gr.Button("Select This Meme")
        
        # Third meme
        with gr.Column():
            meme_image3 = gr.Image(label="Variation 3")
            error_display3 = gr.Textbox(label="Error", visible=False)
            select_btn3 = gr.Button("Select This Meme")
    
    # Currently selected meme indicator
    selected_variation = gr.Textbox(label="Selected Meme", value="None selected", interactive=False)
    
    # Evaluation controls
    with gr.Row():
        is_humor = gr.Checkbox(label="Is Humorous")
        is_creative = gr.Checkbox(label="Is Creative")
        is_shareable = gr.Checkbox(label="Is Shareable")
    
    comments = gr.Textbox(label="Comments", lines=3)
    
    # Navigation
    with gr.Row():
        submit_btn = gr.Button("Submit & Next", interactive=False)
        progress_text = gr.Textbox(label="Progress", interactive=False)
    
    # Event handlers
    def start_evaluation(note):
        global current_session_id, current_prompt_idx, current_results
        
        # Create a new session in the database
        current_session_id = create_session(note, MODEL_NAME)
        current_prompt_idx = 0
        
        if len(test_prompts) > 0:
            # Generate three meme variations
            results = process_prompt(test_prompts[0])
            current_results = results
            
            # Prepare outputs for each meme variation
            outputs = {
                prompt_display: test_prompts[0],
                progress_text: f"Prompt 1 of {len(test_prompts)}",
                selected_variation: "None selected",
                submit_btn: gr.update(interactive=False)
            }
            
            # Set up the display for each variation
            for i, result in enumerate(results):
                if i == 0:
                    if result.get('success'):
                        outputs.update({
                            meme_image1: result['image_url'],
                            error_display1: gr.update(visible=False)
                        })
                    else:
                        outputs.update({
                            meme_image1: None,
                            error_display1: gr.update(visible=True, value=result.get('error', 'Unknown error'))
                        })
                elif i == 1:
                    if result.get('success'):
                        outputs.update({
                            meme_image2: result['image_url'],
                            error_display2: gr.update(visible=False)
                        })
                    else:
                        outputs.update({
                            meme_image2: None,
                            error_display2: gr.update(visible=True, value=result.get('error', 'Unknown error'))
                        })
                elif i == 2:
                    if result.get('success'):
                        outputs.update({
                            meme_image3: result['image_url'],
                            error_display3: gr.update(visible=False)
                        })
                    else:
                        outputs.update({
                            meme_image3: None,
                            error_display3: gr.update(visible=True, value=result.get('error', 'Unknown error'))
                        })
            
            return outputs
        else:
            return {
                prompt_display: "No prompts available",
                progress_text: "No prompts to evaluate"
            }
    
    def select_meme(index):
        """Handle meme selection"""
        global selected_meme_index
        selected_meme_index = index
        
        if 0 <= index < len(current_results):
            variation_text = f"Selected: Variation {index + 1}"
            if not current_results[index].get('success'):
                variation_text += " (Error)"
        else:
            variation_text = "None selected"
        
        # Enable submit button if a meme is selected
        return {
            selected_variation: variation_text,
            submit_btn: gr.update(interactive=True)
        }

    def submit_and_next(humor_val, creative_val, shareable_val, comment_text):
        global current_prompt_idx, current_session_id, current_results, selected_meme_index
        
        # Save current evaluation
        if current_results and 0 <= selected_meme_index < len(current_results):
            # Get values from selected result
            result = current_results[selected_meme_index]
            gemini_json = result.get('gemini_json')
            image_url = result.get('image_url', None)
            error = None if result.get('success') else result.get('error')
            
            # Add attempt number to comments
            full_comment = f"Variation {selected_meme_index + 1} selected. " + comment_text
            
            # Save to database (each function call gets its own connection)
            save_evaluation(
                current_session_id,
                test_prompts[current_prompt_idx],
                gemini_json,
                image_url,
                humor_val,
                creative_val,
                shareable_val,
                full_comment,
                error
            )
        
        # Move to next prompt
        current_prompt_idx += 1
        selected_meme_index = None
        
        # Reset evaluation fields
        reset_fields = {
            is_humor: False,
            is_creative: False,
            is_shareable: False,
            comments: "",
            selected_variation: "None selected",
            submit_btn: gr.update(interactive=False),
        }
        
        # Check if we're done
        if current_prompt_idx >= len(test_prompts):
            return {
                **reset_fields,
                prompt_display: "Evaluation complete!",
                meme_image1: None,
                meme_image2: None,
                meme_image3: None,
                progress_text: f"Completed all {len(test_prompts)} prompts"
            }
        
        # Generate next meme variations
        next_prompt = test_prompts[current_prompt_idx]
        results = process_prompt(next_prompt)
        current_results = results
        
        # Prepare outputs for the next set of variations
        outputs = {
            **reset_fields,
            prompt_display: next_prompt,
            progress_text: f"Prompt {current_prompt_idx + 1} of {len(test_prompts)}"
        }
        
        # Set up the display for each variation
        for i, result in enumerate(results):
            if i == 0:
                if result.get('success'):
                    outputs.update({
                        meme_image1: result['image_url'],
                        error_display1: gr.update(visible=False)
                    })
                else:
                    outputs.update({
                        meme_image1: None,
                        error_display1: gr.update(visible=True, value=result.get('error', 'Unknown error'))
                    })
            elif i == 1:
                if result.get('success'):
                    outputs.update({
                        meme_image2: result['image_url'],
                        error_display2: gr.update(visible=False)
                    })
                else:
                    outputs.update({
                        meme_image2: None,
                        error_display2: gr.update(visible=True, value=result.get('error', 'Unknown error'))
                    })
            elif i == 2:
                if result.get('success'):
                    outputs.update({
                        meme_image3: result['image_url'],
                        error_display3: gr.update(visible=False)
                    })
                else:
                    outputs.update({
                        meme_image3: None,
                        error_display3: gr.update(visible=True, value=result.get('error', 'Unknown error'))
                    })
        
        return outputs
    
    # Connect event handlers
    start_btn.click(
        start_evaluation,
        inputs=experiment_input,
        outputs=[
            prompt_display, meme_image1, error_display1, 
            meme_image2, error_display2, meme_image3, error_display3,
            selected_variation, submit_btn, progress_text
        ]
    )
    
    # Connect selection buttons
    select_btn1.click(
        lambda: select_meme(0),
        inputs=[],
        outputs=[selected_variation, submit_btn]
    )
    
    select_btn2.click(
        lambda: select_meme(1),
        inputs=[],
        outputs=[selected_variation, submit_btn]
    )
    
    select_btn3.click(
        lambda: select_meme(2),
        inputs=[],
        outputs=[selected_variation, submit_btn]
    )
    
    submit_btn.click(
        submit_and_next,
        inputs=[is_humor, is_creative, is_shareable, comments],
        outputs=[
            is_humor, is_creative, is_shareable, comments,
            selected_variation, submit_btn, prompt_display,
            meme_image1, error_display1, meme_image2, error_display2,
            meme_image3, error_display3, progress_text
        ]
    )

# Launch the app
if __name__ == "__main__":
    app.launch()