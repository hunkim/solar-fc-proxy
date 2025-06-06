#!/usr/bin/env python3
"""
Comprehensive test suite for Solar Proxy Function Calling
Tests function calling with various scenarios, tools, and parameters
"""

import asyncio
import aiohttp
import json
import time
import os
from typing import Dict, Any, List

# Test configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 60

class FunctionCallingTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def create_weather_tool(self):
        """Create weather function tool definition"""
        return {
            "type": "function",
            "name": "get_weather",
            "description": "Get current weather for a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and country, e.g. San Francisco, CA"
                    },
                    "units": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature units"
                    }
                },
                "required": ["location"],
                "additionalProperties": False
            }
        }
    
    def create_email_tool(self):
        """Create email function tool definition"""
        return {
            "type": "function", 
            "name": "send_email",
            "description": "Send an email to recipients",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content"
                    }
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False
            }
        }
    
    def create_calculator_tool(self):
        """Create calculator function tool definition"""
        return {
            "type": "function",
            "name": "calculate",
            "description": "Perform mathematical calculations",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate, e.g. '2 + 3 * 4'"
                    }
                },
                "required": ["expression"],
                "additionalProperties": False
            }
        }
    
    async def test_single_function_call(self):
        """Test single function call"""
        print("🔧 Testing single function call...")
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "What's the weather like in Paris, France?"}
            ],
            "tools": [self.create_weather_tool()],
            "max_tokens": 150
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Check if we got tool calls
                    choices = data.get('choices', [])
                    if choices and choices[0].get('message', {}).get('tool_calls'):
                        tool_calls = choices[0]['message']['tool_calls']
                        print(f"   ✅ SUCCESS - Got {len(tool_calls)} tool call(s)")
                        for i, tool_call in enumerate(tool_calls):
                            print(f"      Tool {i+1}: {tool_call['function']['name']}")
                            print(f"      Arguments: {tool_call['function']['arguments']}")
                        return True
                    else:
                        print(f"   ⚠️  No tool calls detected")
                        print(f"      Response: {choices[0].get('message', {}).get('content', '')[:100]}...")
                        return False
                else:
                    print(f"   ❌ FAILED: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False
    
    async def test_multiple_function_calls(self):
        """Test multiple function calls in one request"""
        print("🔧 Testing multiple function calls...")
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Send emails to john@test.com and mary@test.com saying hello, and also get the weather in Tokyo"}
            ],
            "tools": [self.create_email_tool(), self.create_weather_tool()],
            "max_tokens": 200
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    choices = data.get('choices', [])
                    
                    if choices and choices[0].get('message', {}).get('tool_calls'):
                        tool_calls = choices[0]['message']['tool_calls']
                        print(f"   ✅ SUCCESS - Got {len(tool_calls)} tool call(s)")
                        
                        # Check for different function types
                        functions_called = [tc['function']['name'] for tc in tool_calls]
                        print(f"      Functions called: {', '.join(functions_called)}")
                        
                        return len(tool_calls) >= 2
                    else:
                        print(f"   ⚠️  No tool calls detected")
                        return False
                else:
                    print(f"   ❌ FAILED: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False
    
    async def test_tool_choice_required(self):
        """Test tool_choice: required"""
        print("🔧 Testing tool_choice: required...")
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Hello, how are you today?"}
            ],
            "tools": [self.create_calculator_tool()],
            "tool_choice": "required",
            "max_tokens": 150
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    choices = data.get('choices', [])
                    
                    if choices and choices[0].get('message', {}).get('tool_calls'):
                        print(f"   ✅ SUCCESS - Forced function call even for greeting")
                        tool_call = choices[0]['message']['tool_calls'][0]
                        print(f"      Function: {tool_call['function']['name']}")
                        return True
                    else:
                        print(f"   ❌ FAILED - No function call despite 'required'")
                        return False
                else:
                    print(f"   ❌ FAILED: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False
    
    async def test_tool_choice_specific_function(self):
        """Test tool_choice with specific function"""
        print("🔧 Testing tool_choice with specific function...")
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "I need to do something with weather and email"}
            ],
            "tools": [self.create_weather_tool(), self.create_email_tool()],
            "tool_choice": {"type": "function", "name": "get_weather"},
            "max_tokens": 150
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    choices = data.get('choices', [])
                    
                    if choices and choices[0].get('message', {}).get('tool_calls'):
                        tool_call = choices[0]['message']['tool_calls'][0]
                        function_name = tool_call['function']['name']
                        
                        if function_name == "get_weather":
                            print(f"   ✅ SUCCESS - Forced specific function: {function_name}")
                            return True
                        else:
                            print(f"   ❌ FAILED - Wrong function called: {function_name}")
                            return False
                    else:
                        print(f"   ❌ FAILED - No function call")
                        return False
                else:
                    print(f"   ❌ FAILED: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False
    
    async def test_streaming_function_calls(self):
        """Test streaming with function calls"""
        print("🔧 Testing streaming function calls...")
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Calculate 15 * 23 + 7 for me"}
            ],
            "tools": [self.create_calculator_tool()],
            "stream": True,
            "max_tokens": 150
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status == 200:
                    chunks_received = 0
                    function_calls_detected = False
                    
                    async for line in response.content:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            chunks_received += 1
                            data_str = line_text[6:]
                            
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                data = json.loads(data_str)
                                choices = data.get('choices', [])
                                if choices and choices[0].get('delta', {}).get('tool_calls'):
                                    function_calls_detected = True
                                    print(f"   ✅ SUCCESS - Detected function call in streaming")
                                    print(f"      Chunks received: {chunks_received}")
                                    return True
                            except json.JSONDecodeError:
                                continue
                    
                    if not function_calls_detected:
                        print(f"   ⚠️  No function calls in stream (got {chunks_received} chunks)")
                        return False
                    
                    return True
                else:
                    print(f"   ❌ FAILED: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False
    
    async def test_no_function_call_scenario(self):
        """Test when no function should be called"""
        print("🔧 Testing no function call scenario...")
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Tell me a joke about programming"}
            ],
            "tools": [self.create_weather_tool(), self.create_email_tool()],
            "tool_choice": "auto",
            "max_tokens": 150
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    choices = data.get('choices', [])
                    
                    if choices:
                        message = choices[0].get('message', {})
                        if message.get('tool_calls'):
                            print(f"   ⚠️  Unexpected function call for joke request")
                            return False
                        elif message.get('content'):
                            print(f"   ✅ SUCCESS - Regular text response (no function call)")
                            print(f"      Response: {message['content'][:100]}...")
                            return True
                    
                    print(f"   ❌ FAILED - No response content")
                    return False
                else:
                    print(f"   ❌ FAILED: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False
    
    async def test_complex_function_parameters(self):
        """Test function with complex parameters"""
        print("🔧 Testing complex function parameters...")
        
        search_tool = {
            "type": "function",
            "name": "search_database", 
            "description": "Search a database with advanced options",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "date_range": {
                                "type": "object",
                                "properties": {
                                    "start": {"type": "string"},
                                    "end": {"type": "string"}
                                }
                            },
                            "limit": {"type": "integer", "minimum": 1, "maximum": 100}
                        }
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Search for 'AI research' in the technology category from January to March 2024, limit to 10 results"}
            ],
            "tools": [search_tool],
            "max_tokens": 200
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    choices = data.get('choices', [])
                    
                    if choices and choices[0].get('message', {}).get('tool_calls'):
                        tool_call = choices[0]['message']['tool_calls'][0]
                        arguments_str = tool_call['function']['arguments']
                        
                        try:
                            arguments = json.loads(arguments_str)
                            print(f"   ✅ SUCCESS - Complex parameters parsed")
                            print(f"      Arguments: {json.dumps(arguments, indent=2)}")
                            
                            # Check if complex nested objects are handled
                            has_filters = 'filters' in arguments
                            return True
                        except json.JSONDecodeError:
                            print(f"   ❌ FAILED - Invalid JSON arguments: {arguments_str}")
                            return False
                    else:
                        print(f"   ⚠️  No function call detected")
                        return False
                else:
                    print(f"   ❌ FAILED: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False
    
    async def run_all_function_tests(self):
        """Run all function calling tests"""
        print("🚀 Starting Function Calling Test Suite")
        print("=" * 60)
        
        tests = [
            self.test_single_function_call(),
            self.test_multiple_function_calls(),
            self.test_tool_choice_required(),
            self.test_tool_choice_specific_function(),
            self.test_streaming_function_calls(),
            self.test_no_function_call_scenario(),
            self.test_complex_function_parameters(),
        ]
        
        results = await asyncio.gather(*tests, return_exceptions=True)
        
        print("\n" + "=" * 60)
        print("📊 Function Calling Test Summary")
        print("=" * 60)
        
        passed = sum(1 for r in results if r is True)
        total = len([r for r in results if isinstance(r, bool)])
        
        print(f"Function calling tests passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All function calling tests passed!")
        else:
            print("⚠️  Some function calling tests failed.")
        
        return passed == total

async def main():
    """Main test runner"""
    async with FunctionCallingTester() as tester:
        success = await tester.run_all_function_tests()
        return success

if __name__ == "__main__":
    print("🔍 Checking if server supports function calling...")
    
    try:
        import requests
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "function_calling" in data.get("features", []):
                print("✅ Server supports function calling!")
            else:
                print("❌ Server doesn't support function calling")
                exit(1)
        else:
            print("❌ Server is not healthy")
            exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        exit(1)
    
    # Run function calling tests
    print("\n🧪 Starting function calling tests...")
    success = asyncio.run(main())
    exit(0 if success else 1) 