from fastapi import FastAPI
from gradio.routes import mount_gradio_app
import modal

from app_frontend import app as blocks

# Create a Modal image with required dependencies
image = modal.Image.debian_slim().pip_install(
    "gradio<6",  # Gradio version below 6
    "google-generativeai",  # Gemini API
    "psycopg2-binary",  # PostgreSQL
    "python-dotenv",  # Environment variables
    "requests"  # For imgflip API
).add_local_file("system_prompt.txt", "/root/system_prompt.txt").add_local_file("memes20250128.pkl", "/root/memes20250128.pkl")  # Include required files

# Define the Modal app
app = modal.App("LLMeme", image=image)

@app.function(
    concurrency_limit=1,  # Only one instance (Gradio uses local file storage, preventing multiple replicas)
    allow_concurrent_inputs=1000,  # Async handling for up to 1000 concurrent requests within a single instance
    secrets=[
        modal.Secret.from_name("gemini-secret"),  # GEMINI_API_KEY
        modal.Secret.from_name("imgflip-secret"),  # IMGFLIP_USERNAME, IMGFLIP_PASSWORD
        modal.Secret.from_name("postgres-secret")  # DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
    ]
)
@modal.asgi_app() # Register this as an ASGI app (compatible with FastAPI)
def serve() -> FastAPI:
    """
    Main server function that:
    - Wraps Gradio inside FastAPI
    - Deploys the API through Modal with a single instance for session consistency
    """
    api = FastAPI(docs=True) # Enable Swagger documentation at /docs
    
    # Mount Gradio app at root path
    return mount_gradio_app(
        app=api,
        blocks=blocks,
        path="/"
    )

@app.local_entrypoint()
def main():
    """
    Local development entry point: 
    - Allows running the app locally for testing
    - Prints the type of Gradio app to confirm readiness
    """
    print(f"{type(blocks)} is ready to go!")