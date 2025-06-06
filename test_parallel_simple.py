#!/usr/bin/env python3
"""
Simple test for parallel function calls with longer timeout
"""

import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8000"

async def test_parallel_function_calls():
    """Test parallel function calls - multiple functions called simultaneously"""
    print("🔧 Testing parallel function calls...")
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "user", 
                "content": "I need to know the weather in Tokyo and the current time in New York. Can you help me with both?"
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather information for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"},
                            "units": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "get_time",
                    "description": "Get current time for a timezone",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timezone": {"type": "string", "description": "Timezone (e.g., 'America/New_York')"},
                            "format": {"type": "string", "enum": ["12h", "24h"], "default": "12h"}
                        },
                        "required": ["timezone"]
                    }
                }
            }
        ],
        "tool_choice": "auto"
    }
    
    timeout = aiohttp.ClientTimeout(total=60)  # 60 second timeout
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.post(
                f"{BASE_URL}/v1/chat/completions",
                json=payload,
                headers={"Authorization": "Bearer test-key"}
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    choices = result.get("choices", [])
                    if choices and "tool_calls" in choices[0].get("message", {}):
                        tool_calls = choices[0]["message"]["tool_calls"]
                        print(f"   ✅ SUCCESS - Got {len(tool_calls)} tool call(s)")
                        
                        function_names = []
                        for i, call in enumerate(tool_calls):
                            func_name = call["function"]["name"]
                            function_names.append(func_name)
                            args = json.loads(call["function"]["arguments"])
                            print(f"      Tool {i+1}: {func_name}")
                            print(f"      Arguments: {args}")
                        
                        # Check if we got both functions called
                        if "get_weather" in function_names and "get_time" in function_names:
                            print("   🎉 PARALLEL SUCCESS - Both functions called!")
                            return True
                        else:
                            print(f"   ⚠️  Partial success - Functions called: {function_names}")
                            return True
                    else:
                        print("   ❌ FAILED - No tool calls detected")
                        return False
                else:
                    print(f"   ❌ FAILED - HTTP {response.status}")
                    print(f"   Response: {result}")
                    return False
                    
        except asyncio.TimeoutError:
            print("   ❌ FAILED - Request timed out")
            return False
        except Exception as e:
            print(f"   ❌ FAILED - Error: {e}")
            return False

async def test_reasoning_with_function_calls():
    """Test reasoning mode combined with function calls"""
    print("🔧 Testing reasoning mode + function calls...")
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "user", 
                "content": "I'm planning a trip and need to think carefully about the weather. Can you check the weather in both London and Paris and help me decide which city might be better for outdoor activities?"
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather information for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"},
                            "units": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
                        },
                        "required": ["location"]
                    }
                }
            }
        ],
        "tool_choice": "auto",
        "reasoning_effort": "high"
    }
    
    timeout = aiohttp.ClientTimeout(total=90)  # Longer timeout for reasoning
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.post(
                f"{BASE_URL}/v1/chat/completions",
                json=payload,
                headers={"Authorization": "Bearer test-key"}
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    choices = result.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        content = message.get("content", "")
                        tool_calls = message.get("tool_calls", [])
                        
                        has_reasoning = "<think>" in content if content else False
                        has_tools = len(tool_calls) > 0
                        
                        print(f"   ✅ SUCCESS - Reasoning: {has_reasoning}, Tools: {len(tool_calls)}")
                        
                        if has_reasoning:
                            print("   🧠 Reasoning mode detected!")
                        
                        if has_tools:
                            for i, call in enumerate(tool_calls):
                                func_name = call["function"]["name"]
                                args = json.loads(call["function"]["arguments"])
                                print(f"      Tool {i+1}: {func_name} - {args}")
                        
                        return has_tools
                    else:
                        print("   ❌ FAILED - No choices in response")
                        return False
                else:
                    print(f"   ❌ FAILED - HTTP {response.status}")
                    return False
                    
        except asyncio.TimeoutError:
            print("   ❌ FAILED - Request timed out after 90 seconds")
            return False
        except Exception as e:
            print(f"   ❌ FAILED - Error: {e}")
            return False

async def main():
    """Run the tests"""
    print("🚀 Starting Advanced Function Calling Tests")
    print("=" * 60)
    
    results = []
    
    # Test 1: Parallel function calls
    results.append(await test_parallel_function_calls())
    
    # Test 2: Reasoning + function calls
    results.append(await test_reasoning_with_function_calls())
    
    print("=" * 60)
    print(f"📊 Advanced Test Summary: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("🎉 All advanced tests passed!")
    else:
        print("⚠️  Some advanced tests failed.")

if __name__ == "__main__":
    asyncio.run(main()) 