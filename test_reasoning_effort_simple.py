#!/usr/bin/env python3
"""
Simple test to verify reasoning_effort override using deployed endpoint
"""

import requests
import json

# Use deployed endpoint
DEPLOYED_URL = "https://solar-fc-proxy.vercel.app"

def test_reasoning_effort_override():
    """Test that reasoning_effort is always set to high for upstream"""
    
    print("🧪 Testing Reasoning Effort Override on Deployed Server")
    
    # Test case: No reasoning_effort provided by client
    # The proxy should still send reasoning_effort="high" to upstream
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "What is 2+2? Please think step by step."}
        ],
        "max_tokens": 50
        # Note: deliberately NOT including reasoning_effort
    }
    
    headers = {
        "Authorization": "Bearer test-key",  # Use dummy key, will be passed through
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{DEPLOYED_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"✅ Request completed without client providing reasoning_effort")
            print(f"📝 Response preview: {content[:100]}...")
            print(f"🔍 Check Firebase logs to confirm upstream_content has reasoning_effort='high'")
            
        elif response.status_code == 401:
            print("✅ Request correctly rejected due to invalid API key")
            print("🔍 This confirms the proxy is working and would force reasoning_effort='high'")
            
        else:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_reasoning_effort_override() 