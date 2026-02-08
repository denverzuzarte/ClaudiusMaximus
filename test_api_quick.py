import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load .env
load_dotenv('.env')

api_key = os.getenv('GOOGLE_API_KEY')
print(f"API Key loaded: {api_key[:20]}..." if api_key else "NOT FOUND")

# Test the API by generating content
try:
    client = genai.Client()
    response = client.models.generate_content(
        model='models/gemini-2.5-flash',
        contents='Say hello in 3 words',
        config=types.GenerateContentConfig(temperature=0.3)
    )
    result = response.text
    print(f"✓ API Key is VALID and WORKING!")
    print(f"✓ Test response: {result}")
except Exception as e:
    print(f"✗ API Key FAILED: {e}")
