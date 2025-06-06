import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

BASE_URL = "http://localhost:8000"

async def test_reasoning_mode():
    """Test reasoning mode with high effort"""
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "user", 
                "content": "Solve this step by step: If a train travels 120 km in 2 hours, and then travels 180 km in 3 hours, what is the average speed for the entire journey? Show your reasoning."
            }
        ],
        "reasoning_effort": "high",
        "max_tokens": 500
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Check if response contains reasoning
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"\nContent: {content}")
            print(f"Content length: {len(content)} characters")
            
            return True
        else:
            print(f"Error: {response.text}")
            return False

async def test_reasoning_mode_with_function_calling():
    """Test reasoning mode combined with function calling"""
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "user", 
                "content": "I need to calculate the area of a rectangle that is 15.5 meters long and 8.2 meters wide. Use the calculate function to get the precise result."
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Perform mathematical calculations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Mathematical expression to calculate (e.g., '15.5 * 8.2')"
                            },
                            "operation": {
                                "type": "string", 
                                "description": "Type of calculation (e.g., 'area', 'multiplication', 'addition')"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            }
        ],
        "reasoning_effort": "high",
        "max_tokens": 300
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=30.0
        )
        
        print(f"\n=== Function Calling with Reasoning Mode ===")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Check for tool calls
            choice = result.get('choices', [{}])[0]
            if 'tool_calls' in choice.get('message', {}):
                print("✅ Function calling with reasoning mode works!")
                return True
            else:
                print("❌ Expected function call but got regular response")
                return False
        else:
            print(f"Error: {response.text}")
            return False

async def main():
    print("Testing Reasoning Mode with Solar Proxy...")
    
    # Test basic reasoning mode
    print("\n=== Testing Basic Reasoning Mode ===")
    basic_success = await test_reasoning_mode()
    
    # Test reasoning mode with function calling
    print("\n=== Testing Reasoning Mode + Function Calling ===")
    func_success = await test_reasoning_mode_with_function_calling()
    
    print("\n=== Summary ===")
    print(f"Basic reasoning mode: {'✅ PASS' if basic_success else '❌ FAIL'}")
    print(f"Reasoning + Functions: {'✅ PASS' if func_success else '❌ FAIL'}")

if __name__ == "__main__":
    asyncio.run(main()) 