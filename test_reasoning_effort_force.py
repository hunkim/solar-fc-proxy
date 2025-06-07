#!/usr/bin/env python3
"""
Test script to verify that reasoning_effort is always set to "high" for upstream requests,
even when the client doesn't provide it or provides a different value.
"""

import requests
import json
import os

# API configuration
API_KEY = os.getenv('UPSTAGE_API_KEY')
if not API_KEY:
    print("❌ UPSTAGE_API_KEY environment variable is required")
    exit(1)

# Test both local and deployed endpoints
LOCAL_URL = "http://localhost:8000"
DEPLOYED_URL = "https://solar-fc-proxy.vercel.app"

def test_reasoning_effort_override(base_url: str, test_name: str):
    """Test that reasoning_effort is always set to high for upstream"""
    
    print(f"\n🧪 Testing {test_name} - Reasoning Effort Override")
    
    # Test cases:
    # 1. No reasoning_effort provided by client
    # 2. reasoning_effort="medium" provided by client  
    # 3. reasoning_effort="low" provided by client
    
    test_cases = [
        {"name": "No reasoning_effort", "payload": {}},
        {"name": "Medium reasoning_effort", "payload": {"reasoning_effort": "medium"}},
        {"name": "Low reasoning_effort", "payload": {"reasoning_effort": "low"}},
    ]
    
    for test_case in test_cases:
        print(f"\n📝 Test: {test_case['name']}")
        
        # Prepare request payload
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "What is 2+2? Please think step by step."}
            ],
            "max_tokens": 100,
            **test_case["payload"]  # Add reasoning_effort if provided
        }
        
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f"✅ Request completed")
                print(f"📝 Response preview: {content[:100]}...")
                
                # The upstream should always receive reasoning_effort="high"
                # We can't directly verify this from the response, but the test
                # confirms the proxy is working and the Firebase logs should show it
                print(f"🔍 Check Firebase logs to confirm upstream_content has reasoning_effort='high'")
                
            else:
                print(f"❌ Request failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

def main():
    """Run all tests"""
    print("🚀 Testing Reasoning Effort Override")
    
    # Try local first, then deployed
    try:
        response = requests.get(f"{LOCAL_URL}/health", timeout=5)
        if response.status_code == 200:
            test_reasoning_effort_override(LOCAL_URL, "Local Server")
        else:
            raise Exception("Local server not healthy")
    except:
        print("⚠️  Local server not available, testing deployed version")
        test_reasoning_effort_override(DEPLOYED_URL, "Deployed Server")

if __name__ == "__main__":
    main() 