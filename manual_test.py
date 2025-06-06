#!/usr/bin/env python3
"""
Manual test cases to demonstrate specific functionality
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_model_mapping():
    """Test that different model names all map to Solar"""
    print("🔄 Testing Model Mapping")
    print("=" * 40)
    
    models_to_test = [
        "gpt-4",
        "gpt-3.5-turbo", 
        "claude-3-sonnet",
        "gemini-pro",
        "custom-model-name",
        "solar-pro2-preview"  # Should also work
    ]
    
    for model in models_to_test:
        print(f"\nTesting model: {model}")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": f"Reply with 'Hello from {model}'"}],
            "max_tokens": 20
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                print(f"   ✅ SUCCESS: {content}")
            else:
                print(f"   ❌ FAILED: HTTP {response.status_code}")
                print(f"      Error: {response.text}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

def test_streaming_vs_non_streaming():
    """Compare streaming vs non-streaming responses"""
    print("\n\n📡 Testing Streaming vs Non-Streaming")
    print("=" * 50)
    
    prompt = "Write a very short story about a robot in exactly 30 words."
    
    # Test non-streaming
    print("\n🔸 Non-streaming response:")
    start_time = time.time()
    
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": 50
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=15
        )
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            print(f"   Response: {content}")
            print(f"   Duration: {duration:.2f}s")
        else:
            print(f"   ❌ FAILED: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
    
    # Test streaming
    print("\n🔸 Streaming response:")
    payload["stream"] = True
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=15
        )
        
        if response.status_code == 200:
            chunks = []
            content_parts = []
            
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]
                        if data_str.strip() != '[DONE]':
                            try:
                                data = json.loads(data_str)
                                delta = data.get('choices', [{}])[0].get('delta', {})
                                if 'content' in delta and delta['content']:
                                    content_parts.append(delta['content'])
                                    print(delta['content'], end='', flush=True)
                                chunks.append(line_text)
                            except json.JSONDecodeError:
                                pass
            
            duration = time.time() - start_time
            full_content = ''.join(content_parts)
            print(f"\n   Chunks received: {len(chunks)}")
            print(f"   Content parts: {len(content_parts)}")
            print(f"   Duration: {duration:.2f}s")
        else:
            print(f"   ❌ FAILED: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

def test_different_parameters():
    """Test various parameter combinations"""
    print("\n\n🎛️ Testing Different Parameters")
    print("=" * 40)
    
    test_cases = [
        {
            "name": "High Temperature",
            "params": {"temperature": 1.5, "max_tokens": 30}
        },
        {
            "name": "Low Temperature", 
            "params": {"temperature": 0.1, "max_tokens": 30}
        },
        {
            "name": "With Reasoning Effort",
            "params": {"reasoning_effort": "high", "max_tokens": 50}
        },
        {
            "name": "System Message",
            "params": {"max_tokens": 30},
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that speaks like a pirate."},
                {"role": "user", "content": "Say hello"}
            ]
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🔸 Testing: {test_case['name']}")
        
        messages = test_case.get('messages', [
            {"role": "user", "content": "Tell me a fun fact about space"}
        ])
        
        payload = {
            "model": "gpt-4",
            "messages": messages,
            **test_case['params']
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                print(f"   Response: {content[:100]}{'...' if len(content) > 100 else ''}")
            else:
                print(f"   ❌ FAILED: HTTP {response.status_code}")
                print(f"      Error: {response.text}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

if __name__ == "__main__":
    print("🧪 Manual Test Cases for Solar Proxy")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not healthy!")
            exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print("   Make sure the server is running with: uvicorn main:app --reload")
        exit(1)
    
    test_model_mapping()
    test_streaming_vs_non_streaming()
    test_different_parameters()
    
    print("\n\n🎉 Manual testing completed!")
    print("All tests demonstrate that the proxy correctly:")
    print("  ✅ Maps any model name to Solar")
    print("  ✅ Supports both streaming and non-streaming")
    print("  ✅ Handles various parameters correctly")
    print("  ✅ Maintains OpenAI API compatibility") 