"""
Run this script ONE TIME to create your Gemini File Search Store.
It will print the store name. Paste it into your .env file.
"""
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

store = client.file_search_stores.create(
    config={"display_name": "My RAG Knowledge Base"}
)

print("\n✅  File Search Store created!")
print(f"    Name: {store.name}")
print(f"\n📋  Add this to your .env:")
print(f"    GEMINI_FILE_STORE={store.name}")
print("\nNow run: python app.py")
