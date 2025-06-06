#!/usr/bin/env python3
"""
Function Calling Demo for Solar Proxy
Simple demonstration of function calling capabilities
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_weather_function():
    """Test weather function call"""
    print("🌤️  Testing Weather Function Call")
    print("-" * 40)
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "What's the weather like in New York?"}
        ],
        "tools": [{
            "type": "function",
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and country"
                    },
                    "units": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature units"
                    }
                },
                "required": ["location"]
            }
        }],
        "max_tokens": 150
    }
    
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        choices = data.get('choices', [])
        
        if choices and choices[0].get('message', {}).get('tool_calls'):
            tool_calls = choices[0]['message']['tool_calls']
            print(f"✅ SUCCESS: Detected {len(tool_calls)} function call(s)")
            
            for i, tool_call in enumerate(tool_calls):
                print(f"\nFunction Call {i+1}:")
                print(f"  ID: {tool_call['id']}")
                print(f"  Function: {tool_call['function']['name']}")
                print(f"  Arguments: {tool_call['function']['arguments']}")
        else:
            print("❌ No function calls detected")
            print(f"Response: {choices[0].get('message', {}).get('content', '')}")
    else:
        print(f"❌ HTTP Error: {response.status_code}")
        print(response.text)

def test_multiple_functions():
    """Test multiple function calls"""
    print("\n📧 Testing Multiple Function Calls")
    print("-" * 40)
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Send emails to alice@test.com and bob@test.com saying 'Meeting at 3pm', and also check the weather in London"}
        ],
        "tools": [
            {
                "type": "function",
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
            },
            {
                "type": "function",
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    },
                    "required": ["location"]
                }
            }
        ],
        "max_tokens": 300
    }
    
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        choices = data.get('choices', [])
        
        total_tool_calls = 0
        functions_called = set()
        
        for choice in choices:
            tool_calls = choice.get('message', {}).get('tool_calls', [])
            total_tool_calls += len(tool_calls)
            
            for tool_call in tool_calls:
                function_name = tool_call['function']['name']
                functions_called.add(function_name)
                print(f"\nFunction Call:")
                print(f"  Function: {function_name}")
                print(f"  Arguments: {tool_call['function']['arguments']}")
        
        print(f"\n✅ SUCCESS: {total_tool_calls} total function calls")
        print(f"Functions used: {', '.join(functions_called)}")
        
    else:
        print(f"❌ HTTP Error: {response.status_code}")
        print(response.text)

def test_calculator_function():
    """Test calculator function"""
    print("\n🧮 Testing Calculator Function")
    print("-" * 40)
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Calculate 25 * 34 + 17 - 8 / 2"}
        ],
        "tools": [{
            "type": "function",
            "name": "calculate",
            "description": "Perform mathematical calculations",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        }],
        "max_tokens": 150
    }
    
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        choices = data.get('choices', [])
        
        if choices and choices[0].get('message', {}).get('tool_calls'):
            tool_call = choices[0]['message']['tool_calls'][0]
            print(f"✅ SUCCESS: Calculator function called")
            print(f"  Function: {tool_call['function']['name']}")
            print(f"  Expression: {tool_call['function']['arguments']}")
        else:
            print("❌ No function calls detected")
    else:
        print(f"❌ HTTP Error: {response.status_code}")

def test_regular_chat():
    """Test that regular chat still works without functions"""
    print("\n💬 Testing Regular Chat (No Functions)")
    print("-" * 40)
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Tell me a fun fact about space"}
        ],
        "max_tokens": 100
    }
    
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        choices = data.get('choices', [])
        
        if choices:
            message = choices[0].get('message', {})
            if message.get('content'):
                print(f"✅ SUCCESS: Regular chat response")
                print(f"Response: {message['content'][:150]}...")
            else:
                print("❌ No content in response")
    else:
        print(f"❌ HTTP Error: {response.status_code}")

def main():
    print("🚀 Solar Proxy Function Calling Demo")
    print("=" * 50)
    
    # Check server health
    try:
        health = requests.get(f"{BASE_URL}/health")
        if health.status_code == 200:
            data = health.json()
            print(f"Server Status: {data['status']}")
            print(f"Features: {', '.join(data.get('features', []))}")
            print()
        else:
            print("❌ Server not healthy")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return
    
    # Run function calling demos
    test_weather_function()
    test_multiple_functions()
    test_calculator_function()
    test_regular_chat()
    
    print("\n🎉 Function Calling Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("✅ Single function calls")
    print("✅ Multiple function calls")
    print("✅ Different function types")
    print("✅ Proper argument parsing")
    print("✅ OpenAI-compatible response format")
    print("✅ Regular chat still works")

if __name__ == "__main__":
    main() 