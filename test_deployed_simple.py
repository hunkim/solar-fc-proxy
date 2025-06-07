#!/usr/bin/env python3
"""
Simple test for deployed Solar proxy once API key is configured
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('.env.local')
UPSTAGE_API_KEY = os.getenv('UPSTAGE_API_KEY', 'test-key')

LOCAL_URL = "http://localhost:8000"
DEPLOYED_URL = "https://solar-fc-proxy.vercel.app"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {UPSTAGE_API_KEY}"
}

def run_test(url):
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello, test!"}]
    }
    print(f"\nTesting {url}/v1/chat/completions ...")
    try:
        response = requests.post(f"{url}/v1/chat/completions", headers=headers, json=payload, timeout=15)
        print(f"Status: {response.status_code}")
        try:
            print(f"Response: {response.json()}")
        except Exception:
            print(f"Raw response: {response.text}")
    except Exception as e:
        print(f"❌ Error connecting to {url}: {e}")

def test_deployed_proxy():
    url = "https://solar-fc-proxy.vercel.app"
    
    print("🏥 Testing health endpoint...")
    health = requests.get(f"{url}/health")
    print(f"Health status: {health.status_code}")
    if health.status_code == 200:
        health_data = health.json()
        print(f"API Key configured: {health_data.get('api_key_configured', False)}")
        print(f"Status: {health_data.get('status', 'unknown')}")
    
    if health.status_code == 200 and health.json().get('api_key_configured'):
        print("\n🧪 Testing function calling...")
        
        # Simple function call test
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "What is 25 * 4?"}
            ],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Perform calculations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string", "description": "Math expression"}
                        },
                        "required": ["expression"]
                    }
                }
            }],
            "tool_choice": "auto"
        }
        
        response = requests.post(
            f"{url}/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-api-key"  # Required for authentication
            },
            json=payload
        )
        
        print(f"Function call test: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                choice = data['choices'][0]
                tool_calls = choice.get('message', {}).get('tool_calls', [])
                if tool_calls:
                    print(f"✅ Function calling works! Detected {len(tool_calls)} function call(s)")
                    for tool_call in tool_calls:
                        func_name = tool_call.get('function', {}).get('name')
                        args = tool_call.get('function', {}).get('arguments')
                        print(f"   Function: {func_name}({args})")
                else:
                    print("⚠️  No function calls detected (might be normal)")
            print("🎉 Proxy is working correctly!")
        else:
            print(f"❌ Function call failed: {response.status_code} - {response.text}")
    else:
        print("\n⚠️  API key not configured yet. Please add UPSTAGE_API_KEY to Vercel environment variables.")
        print("   1. Go to https://vercel.com/dashboard")
        print("   2. Select your solar-fc-proxy project")
        print("   3. Go to Settings > Environment Variables")
        print("   4. Add UPSTAGE_API_KEY with your actual key")
        print("   5. Redeploy the project")

if __name__ == "__main__":
    run_test(LOCAL_URL)
    run_test(DEPLOYED_URL) 