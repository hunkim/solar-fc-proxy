#!/usr/bin/env python3
"""
Test function calling capabilities of the deployed Solar proxy
URL: https://solar-fc-proxy.vercel.app
"""

import json
import requests
import time
from typing import Dict, Any, List

# Deployed endpoint
BASE_URL = "https://solar-fc-proxy.vercel.app"

def test_function_calling(tools: List[Dict], messages: List[Dict], test_name: str) -> None:
    """Test function calling with the deployed proxy"""
    print(f"\n🧪 Testing: {test_name}")
    print("=" * 50)
    
    payload = {
        "model": "gpt-4",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7
    }
    
    print(f"📤 Request to {BASE_URL}/v1/chat/completions")
    print(f"💭 User message: {messages[-1]['content']}")
    print(f"🔧 Tools available: {len(tools)}")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-api-key"  # Required for authentication
            },
            json=payload,
            timeout=30
        )
        
        duration = time.time() - start_time
        
        print(f"⏱️  Response time: {duration:.2f}s")
        print(f"📊 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'choices' in data and len(data['choices']) > 0:
                choice = data['choices'][0]
                message = choice.get('message', {})
                
                print(f"✅ Success! Got {len(data['choices'])} choice(s)")
                
                # Check for function calls
                tool_calls = message.get('tool_calls', [])
                if tool_calls:
                    print(f"🔧 Function calls detected: {len(tool_calls)}")
                    for i, tool_call in enumerate(tool_calls, 1):
                        func_name = tool_call.get('function', {}).get('name', 'unknown')
                        args = tool_call.get('function', {}).get('arguments', '{}')
                        print(f"   {i}. {func_name}({args})")
                else:
                    content = message.get('content', '')
                    print(f"💬 Text response: {content[:100]}...")
                
                # Check usage stats
                if 'usage' in data:
                    usage = data['usage']
                    print(f"📈 Token usage: {usage.get('total_tokens', 'N/A')} total")
                
                print("✨ Test passed!")
                
            else:
                print("❌ No choices in response")
                print(f"Response: {data}")
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏰ Request timed out")
    except requests.exceptions.RequestException as e:
        print(f"🔥 Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"📝 JSON decode error: {e}")
        print(f"Raw response: {response.text[:500]}")

def main():
    print("🚀 Testing Solar Function Calling Proxy")
    print(f"🌐 Endpoint: {BASE_URL}")
    print("🔍 Testing various function calling scenarios...\n")
    
    # Test 1: Simple calculator function
    calc_tools = [{
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Perform basic arithmetic calculations",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')"
                    }
                },
                "required": ["expression"]
            }
        }
    }]
    
    test_function_calling(
        tools=calc_tools,
        messages=[
            {"role": "user", "content": "What is 15 * 8 + 42?"}
        ],
        test_name="Simple Calculator"
    )
    
    # Test 2: Weather function
    weather_tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather information for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit"
                    }
                },
                "required": ["location"]
            }
        }
    }]
    
    test_function_calling(
        tools=weather_tools,
        messages=[
            {"role": "user", "content": "What's the weather like in Tokyo today?"}
        ],
        test_name="Weather Query"
    )
    
    # Test 3: Multiple tools available
    multi_tools = [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "description": "Maximum number of results"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "Send an email",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email"},
                        "subject": {"type": "string", "description": "Email subject"},
                        "body": {"type": "string", "description": "Email body"}
                    },
                    "required": ["to", "subject", "body"]
                }
            }
        }
    ]
    
    test_function_calling(
        tools=multi_tools,
        messages=[
            {"role": "user", "content": "Search for 'latest AI developments' and send me the results via email"}
        ],
        test_name="Multiple Tools - Search & Email"
    )
    
    # Test 4: Complex data processing
    data_tools = [{
        "type": "function",
        "function": {
            "name": "analyze_data",
            "description": "Analyze a dataset and provide insights",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Array of numerical data points"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["mean", "median", "trend", "correlation"],
                        "description": "Type of analysis to perform"
                    }
                },
                "required": ["data", "analysis_type"]
            }
        }
    }]
    
    test_function_calling(
        tools=data_tools,
        messages=[
            {"role": "user", "content": "Analyze this sales data for trends: [100, 120, 95, 180, 220, 250, 180, 300]"}
        ],
        test_name="Data Analysis"
    )
    
    # Test 5: No function call expected (regular chat)
    test_function_calling(
        tools=calc_tools,  # Tools available but shouldn't be used
        messages=[
            {"role": "user", "content": "Tell me a joke about programming"}
        ],
        test_name="Regular Chat (No Function Call Expected)"
    )
    
    # Test 6: Health check endpoint
    print(f"\n🏥 Testing health endpoint...")
    try:
        health_response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"📊 Health check status: {health_response.status_code}")
        if health_response.status_code == 200:
            print(f"✅ Health response: {health_response.json()}")
        else:
            print(f"❌ Health check failed: {health_response.text}")
    except Exception as e:
        print(f"🔥 Health check error: {e}")
    
    print(f"\n🎯 All tests completed!")
    print(f"🌟 Your Solar proxy is deployed and ready at: {BASE_URL}")

if __name__ == "__main__":
    main() 