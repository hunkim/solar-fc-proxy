#!/usr/bin/env python3
"""
Test script for structured output functionality in the Solar Proxy API
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Configuration
API_BASE_URL = "http://localhost:8000/v1"
API_KEY = os.getenv("UPSTAGE_API_KEY")  # Use the same key as the proxy

def test_structured_output():
    """Test structured output with validator schema"""
    
    print("Testing structured output with validator schema...")
    
    # Test case: Validator Output Schema (from Nanobrowser)
    payload = {
        "model": "solar-pro2-preview",
        "messages": [
            {
                "role": "system", 
                "content": "You are a validator that checks if tasks are completed correctly."
            },
            {
                "role": "user", 
                "content": "Validate this: User wanted to search for Python tutorials and I found a comprehensive tutorial on python.org. Is this valid?"
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "validator_output",
                "schema": {
                    "type": "object",
                    "properties": {
                        "is_valid": {
                            "anyOf": [
                                {"type": "boolean"},
                                {"type": "string"}
                            ]
                        },
                        "reason": {"type": "string"},
                        "answer": {"type": "string"}
                    },
                    "required": ["is_valid", "reason", "answer"],
                    "additionalProperties": False
                }
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers=headers,
        json=payload
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        result = response.json()
        print("Success! Response:")
        print(json.dumps(result, indent=2))
        
        # Validate the response structure
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        try:
            parsed_content = json.loads(content)
            print("\nValidation Results:")
            print(f"- JSON is valid: ✓")
            print(f"- Has 'is_valid' field: {'✓' if 'is_valid' in parsed_content else '✗'}")
            print(f"- Has 'reason' field: {'✓' if 'reason' in parsed_content else '✗'}")
            print(f"- Has 'answer' field: {'✓' if 'answer' in parsed_content else '✗'}")
            print(f"- Content: {parsed_content}")
        except json.JSONDecodeError as e:
            print(f"✗ Response content is not valid JSON: {e}")
            print(f"Raw content: {content}")
    else:
        print(f"Error: {response.text}")

def test_structured_output_streaming():
    """Test structured output with streaming"""
    
    print("\n" + "="*50)
    print("Testing structured output with streaming...")
    
    payload = {
        "model": "solar-pro2-preview",
        "stream": True,
        "messages": [
            {
                "role": "user", 
                "content": "Generate a person's info including name and age."
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "person_info",
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"}
                    },
                    "required": ["name", "age"],
                    "additionalProperties": False
                }
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        stream=True
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("Streaming response:")
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                print(line_str)
    else:
        print(f"Error: {response.text}")

def test_invalid_schema():
    """Test with invalid schema to check error handling"""
    
    print("\n" + "="*50)
    print("Testing invalid schema handling...")
    
    payload = {
        "model": "solar-pro2-preview",
        "messages": [
            {"role": "user", "content": "Test message"}
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "invalid_schema",
                "schema": None  # Invalid: null schema
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers=headers,
        json=payload
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 400:
        print("✓ Correctly returned 400 for invalid schema")
    else:
        print("✗ Expected 400 status code for invalid schema")

if __name__ == "__main__":
    if not API_KEY:
        print("Error: UPSTAGE_API_KEY not found in environment")
        exit(1)
    
    print("Solar Proxy API - Structured Output Test")
    print("="*50)
    
    try:
        test_structured_output()
        test_structured_output_streaming()
        test_invalid_schema()
        print("\n" + "="*50)
        print("All tests completed!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc() 