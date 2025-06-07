#!/usr/bin/env python3
"""Test streaming response logging"""

import requests
import os
from dotenv import load_dotenv

load_dotenv('.env.local')
UPSTAGE_API_KEY = os.getenv('UPSTAGE_API_KEY', 'test-key')

def test_streaming_logging():
    url = "http://localhost:8000"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {UPSTAGE_API_KEY}"
    }
    
    # Test streaming without function calls
    print("🧪 Testing streaming response logging...")
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Count from 1 to 5 slowly"}],
        "stream": True
    }
    
    try:
        response = requests.post(f"{url}/v1/chat/completions", headers=headers, json=payload, stream=True)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("Streaming response:")
            for line in response.iter_lines():
                if line:
                    print(line.decode('utf-8'))
                    if b'[DONE]' in line:
                        break
            print("✅ Streaming test completed - should be logged to Firebase")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_streaming_logging() 