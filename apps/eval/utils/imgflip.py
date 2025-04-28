import os
import requests
from time import sleep

def create_imgflip_meme(meme_data, api_url="https://api.imgflip.com/caption_image"):
    """
    Creates a meme using the imgflip API.
    
    Args:
        meme_data: Dictionary containing template_id, text0, text1
        api_url: ImgFlip API URL
        
    Returns:
        Dictionary with success status, image URL or error message
    """
    print("\n[IMGFLIP API] Sending request to imgflip")
    
    try:
        # Add credentials to the data
        data = meme_data.copy()
        data.update({
            'username': os.getenv('IMGFLIP_USERNAME'),
            'password': os.getenv('IMGFLIP_PASSWORD')
        })
        
        # Add a small delay to respect API rate limits
        sleep(0.5)
        
        # Send request to ImgFlip
        response = requests.post(api_url, data=data)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('success'):
            print("[IMGFLIP API] Successfully created meme")
            return {
                'success': True,
                'image_url': response_data['data']['url']
            }
        else:
            error_msg = response_data.get('error_message', 'Unknown error')
            print(f"[IMGFLIP API] Error: {error_msg}")
            return {
                'success': False,
                'error_message': error_msg
            }
            
    except Exception as e:
        print(f"[IMGFLIP API] Request failed: {str(e)}")
        return {
            'success': False,
            'error_message': f"API request failed: {str(e)}"
        }