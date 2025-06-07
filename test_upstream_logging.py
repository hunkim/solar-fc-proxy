#!/usr/bin/env python3
"""Test upstream content logging for function calling"""

import requests
import os
from dotenv import load_dotenv

load_dotenv('.env.local')
UPSTAGE_API_KEY = os.getenv('UPSTAGE_API_KEY', 'test-key')

def test_upstream_logging():
    url = "http://localhost:8000"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {UPSTAGE_API_KEY}"
    }
    
    # Test function calling request (this should create upstream_content logging)
    print("🧪 Testing function calling with upstream content logging...")
    payload = {
        "model": "gpt-4",  # Original model request
        "messages": [
            {"role": "user", "content": "What's the current weather in Tokyo?"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather in a given location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA"
                            },
                            "unit": {
                                "type": "string", 
                                "enum": ["celsius", "fahrenheit"]
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ],
        "tool_choice": "auto"
    }
    
    try:
        response = requests.post(f"{url}/v1/chat/completions", headers=headers, json=payload)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Function calling request completed")
            print(f"Response has choices: {len(result.get('choices', []))}")
            if result.get('choices'):
                message = result['choices'][0].get('message', {})
                if message.get('tool_calls'):
                    print(f"✅ Function calls detected: {len(message['tool_calls'])}")
                else:
                    print("ℹ️ No function calls in response")
            print("📝 This request should be logged with both original payload and upstream_content")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_upstream_logging() 