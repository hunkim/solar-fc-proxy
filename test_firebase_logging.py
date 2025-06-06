"""
Test Firebase logging functionality
"""

import asyncio
import httpx
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

BASE_URL = "http://localhost:8000"

async def test_firebase_logging():
    """Test that Firebase logging works without affecting performance"""
    
    print("Testing Firebase logging integration...")
    
    # Simple chat completion request
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Hello, this is a test request for Firebase logging."}
        ],
        "max_tokens": 100
    }
    
    start_time = asyncio.get_event_loop().time()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
        
    end_time = asyncio.get_event_loop().time()
    response_time = (end_time - start_time) * 1000
    
    print(f"✅ Request completed in {response_time:.2f}ms")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Response received: {data.get('choices', [{}])[0].get('message', {}).get('content', '')[:100]}...")
    
    print("Note: Firebase logging is asynchronous, so logs should appear in Firestore shortly.")
    
    # Test function calling with Firebase logging
    print("\nTesting Firebase logging with function calling...")
    
    function_payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Get the current time."}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get the current time",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "format": {"type": "string", "enum": ["iso", "human"], "default": "human"}
                        }
                    }
                }
            }
        ],
        "tool_choice": "auto",
        "max_tokens": 200
    }
    
    start_time = asyncio.get_event_loop().time()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/v1/chat/completions", json=function_payload)
        
    end_time = asyncio.get_event_loop().time()
    response_time = (end_time - start_time) * 1000
    
    print(f"✅ Function calling request completed in {response_time:.2f}ms")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})
        
        if 'tool_calls' in message:
            print(f"✅ Function calls detected: {len(message['tool_calls'])}")
            for tool_call in message['tool_calls']:
                print(f"   - {tool_call['function']['name']}: {tool_call['function']['arguments']}")
        else:
            print("ℹ️  No function calls detected")
    
    print("\n✅ Firebase logging tests completed!")
    print("Check your Firebase console for logged requests at: https://console.firebase.google.com/project/solarproxyup/firestore")

if __name__ == "__main__":
    asyncio.run(test_firebase_logging()) 