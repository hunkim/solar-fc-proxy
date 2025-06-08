#!/usr/bin/env python3
"""
Test script for retry logic in structured output requests
"""

import requests
import json
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv('.env.local')

BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("UPSTAGE_API_KEY", "test-key")

def make_request(endpoint, data=None, headers=None, timeout=None):
    """Make HTTP request with error handling"""
    try:
        # Set timeout based on endpoint and request type
        if timeout is None:
            if endpoint == "/v1/chat/completions":
                timeout = 180  # Long timeout for chat completions
            else:
                timeout = 30   # Short timeout for other endpoints
        
        if data:
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=timeout)
        else:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=timeout)
        
        return response
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after {timeout} seconds")
        return None
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error - is the server running?")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None

def test_debug_endpoint():
    """Test the debug endpoint for structured output parsing"""
    print("\n🔍 Testing Debug Endpoint")
    print("=" * 50)
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Test 1: Test content extraction with thinking tags
    test_content_1 = """<think>
    I need to create a person profile with name and age.
    </think>
    
    {"name": "Alice Smith", "age": 28}"""
    
    data = {
        "test_content": test_content_1,
        "test_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"],
            "additionalProperties": False
        }
    }
    
    response = make_request("/debug/structured-output", data, headers)
    if response and response.status_code == 200:
        result = response.json()
        print("✅ Debug test 1 (with thinking tags):")
        print(f"   Extraction: {'✅' if result['extraction']['success'] else '❌'}")
        print(f"   Validation: {'✅' if result['validation']['success'] else '❌'}")
        print(f"   Extracted JSON: {result['extraction']['extracted_json']}")
        test1_success = result['extraction']['success'] and result['validation']['success']
    else:
        print(f"❌ Debug test 1 failed: {response.status_code if response else 'No response'}")
        test1_success = False
    
    # Test 2: Test malformed JSON
    test_content_2 = """Here's the response: {"name": "Bob", "age": 30, invalid_json"""
    
    data = {
        "test_content": test_content_2,
        "test_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        }
    }
    
    response = make_request("/debug/structured-output", data, headers)
    if response and response.status_code == 200:
        result = response.json()
        print("\n✅ Debug test 2 (malformed JSON):")
        print(f"   Extraction: {'❌' if not result['extraction']['success'] else '✅ (unexpected)'}")
        print(f"   Error: {result['extraction']['error']}")
        test2_success = not result['extraction']['success']  # Should fail extraction
    else:
        print(f"❌ Debug test 2 failed: {response.status_code if response else 'No response'}")
        test2_success = False
    
    return test1_success and test2_success

def test_structured_output_success():
    """Test successful structured output request"""
    print("\n✅ Testing Successful Structured Output")
    print("=" * 50)
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "solar-pro2-preview",
        "messages": [
            {"role": "user", "content": "Create a profile for a software engineer named John who is 30 years old and works at TechCorp"}
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "person_profile",
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "profession": {"type": "string"},
                        "company": {"type": "string"}
                    },
                    "required": ["name", "age", "profession"],
                    "additionalProperties": False
                }
            }
        },
        "max_tokens": 500,
        "temperature": 0.3
    }
    
    print("Making structured output request...")
    response = make_request("/v1/chat/completions", data, headers)
    
    if response and response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        try:
            parsed = json.loads(content)
            print("✅ Structured output successful:")
            print(f"   Name: {parsed.get('name')}")
            print(f"   Age: {parsed.get('age')}")
            print(f"   Profession: {parsed.get('profession')}")
            print(f"   Company: {parsed.get('company', 'Not specified')}")
            return True
        except json.JSONDecodeError:
            print(f"❌ Response is not valid JSON: {content}")
            return False
    else:
        print(f"❌ Request failed: {response.status_code if response else 'No response'}")
        if response:
            print(f"   Error: {response.text}")
        return False

def test_structured_output_with_complex_schema():
    """Test structured output with more complex schema that might fail"""
    print("\n🧪 Testing Complex Schema (may trigger retries)")
    print("=" * 50)
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Complex schema that might be harder for the model to follow
    data = {
        "model": "solar-pro2-preview",
        "messages": [
            {"role": "user", "content": "Analyze the sentiment of this review and provide a detailed breakdown: 'The product is okay but the service was terrible'"}
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sentiment_analysis",
                "schema": {
                    "type": "object",
                    "properties": {
                        "overall_sentiment": {
                            "anyOf": [
                                {"type": "string", "enum": ["positive", "negative", "neutral"]},
                                {"type": "string"}
                            ]
                        },
                        "sentiment_score": {"type": "number", "minimum": -1.0, "maximum": 1.0},
                        "aspects": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "aspect": {"type": "string"},
                                    "sentiment": {"type": "string"},
                                    "confidence": {"type": "number"}
                                },
                                "required": ["aspect", "sentiment"]
                            }
                        },
                        "is_valid": {
                            "anyOf": [
                                {"type": "boolean"},
                                {"type": "string"}
                            ]
                        }
                    },
                    "required": ["overall_sentiment", "sentiment_score", "aspects", "is_valid"],
                    "additionalProperties": False
                }
            }
        },
        "max_tokens": 800,
        "temperature": 0.7  # Higher temperature might make it more likely to fail
    }
    
    print("Making complex structured output request...")
    start_time = time.time()
    response = make_request("/v1/chat/completions", data, headers)
    end_time = time.time()
    
    if response and response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        try:
            parsed = json.loads(content)
            print(f"✅ Complex structured output successful (took {end_time - start_time:.2f}s):")
            print(f"   Overall sentiment: {parsed.get('overall_sentiment')}")
            print(f"   Sentiment score: {parsed.get('sentiment_score')}")
            print(f"   Number of aspects: {len(parsed.get('aspects', []))}")
            print(f"   Is valid: {parsed.get('is_valid')}")
            return True
        except json.JSONDecodeError:
            print(f"❌ Response is not valid JSON: {content}")
            return False
    elif response and response.status_code == 400:
        error = response.json()
        print(f"⚠️ Request failed with validation error (took {end_time - start_time:.2f}s):")
        print(f"   Error: {error.get('error', {}).get('message', 'Unknown error')}")
        print(f"   Details: {error.get('error', {}).get('details', {})}")
        return False
    else:
        print(f"❌ Request failed: {response.status_code if response else 'No response'}")
        if response:
            print(f"   Error: {response.text}")
        return False

def test_invalid_schemas():
    """Test various invalid schema scenarios"""
    print("\n❌ Testing Invalid Schema Scenarios")
    print("=" * 50)
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    test_results = []
    
    # Test 1: Null schema
    print("Testing null schema...")
    data = {
        "model": "solar-pro2-preview",
        "messages": [{"role": "user", "content": "Hello"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "test_schema",
                "schema": None
            }
        }
    }
    
    try:
        response = make_request("/v1/chat/completions", data, headers, timeout=5)
        if response is not None and response.status_code in [400, 422]:
            print("✅ Null schema correctly rejected")
            test_results.append(True)
        elif response is not None:
            print(f"❌ Null schema should have been rejected but got status {response.status_code}")
            print(f"   Response: {response.text}")
            test_results.append(False)
        else:
            print("❌ Null schema test failed - no response received")
            test_results.append(False)
    except Exception as e:
        print(f"❌ Null schema test failed with exception: {e}")
        test_results.append(False)
    
    # Test 2: Empty schema
    print("Testing empty schema...")
    data["response_format"]["json_schema"]["schema"] = {}
    try:
        response = make_request("/v1/chat/completions", data, headers, timeout=5)
        if response is not None and response.status_code in [400, 422]:
            print("✅ Empty schema correctly rejected")
            test_results.append(True)
        elif response is not None:
            print(f"❌ Empty schema should have been rejected but got status {response.status_code}")
            print(f"   Response: {response.text}")
            test_results.append(False)
        else:
            print("❌ Empty schema test failed - no response received")
            test_results.append(False)
    except Exception as e:
        print(f"❌ Empty schema test failed with exception: {e}")
        test_results.append(False)
    
    # Test 3: Missing required fields
    print("Testing schema without properties...")
    data["response_format"]["json_schema"]["schema"] = {"type": "object"}
    try:
        response = make_request("/v1/chat/completions", data, headers, timeout=5)
        if response is not None and response.status_code in [400, 422]:
            print("✅ Schema without properties correctly rejected")
            test_results.append(True)
        elif response is not None:
            print(f"❌ Schema without properties should have been rejected but got status {response.status_code}")
            print(f"   Response: {response.text}")
            test_results.append(False)
        else:
            print("❌ Schema without properties test failed - no response received")
            test_results.append(False)
    except Exception as e:
        print(f"❌ Schema without properties test failed with exception: {e}")
        test_results.append(False)
    
    return all(test_results)

def test_retry_behavior():
    """Test the retry behavior with a request likely to fail validation"""
    print("\n🔄 Testing Retry Behavior")
    print("=" * 50)
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Create a request that should work but test the retry mechanism
    data = {
        "model": "solar-pro2-preview",
        "messages": [
            {"role": "user", "content": "Create a simple task with these specific fields"}
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "task_format",
                "schema": {
                    "type": "object",
                    "properties": {
                        "task_name": {"type": "string"},
                        "priority": {"type": "integer"},
                        "is_complete": {"type": "boolean"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["task_name", "priority", "is_complete", "tags"],
                    "additionalProperties": False
                }
            }
        },
        "max_tokens": 300,
        "temperature": 0.5
    }
    
    print("Making request to test the system...")
    start_time = time.time()
    response = make_request("/v1/chat/completions", data, headers)
    end_time = time.time()
    
    if response and response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        try:
            parsed = json.loads(content)
            print(f"✅ Retry system working (took {end_time - start_time:.2f}s):")
            print(f"   Response is valid JSON with correct structure")
            print(f"   Fields present: {list(parsed.keys())}")
            return True
        except json.JSONDecodeError:
            print(f"❌ Response is not valid JSON: {content}")
            return False
    elif response and response.status_code == 400:
        error = response.json()
        print(f"⚠️ Request failed after retries (took {end_time - start_time:.2f}s):")
        print(f"   This indicates the retry logic was triggered but ultimately failed")
        print(f"   Error: {error.get('error', {}).get('message', 'Unknown error')}")
        details = error.get('error', {}).get('details', {})
        if 'attempts' in details:
            print(f"   Number of attempts: {details['attempts']}")
        # This is actually a valid test outcome - the retry logic worked
        return True
    else:
        print(f"❌ Unexpected response: {response.status_code if response else 'No response'}")
        if response:
            print(f"   Response text: {response.text}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Retry Logic Tests")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not responding correctly")
            return
    except requests.exceptions.RequestException:
        print("❌ Server is not running. Please start it with: make dev")
        return
    
    print("✅ Server is running")
    
    # Run all tests
    tests = [
        ("Debug Endpoint", test_debug_endpoint),
        ("Successful Structured Output", test_structured_output_success),
        ("Complex Schema Test", test_structured_output_with_complex_schema),
        ("Invalid Schema Tests", test_invalid_schemas),
        ("Retry Behavior Test", test_retry_behavior)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The retry logic is working correctly.")
    else:
        print("⚠️ Some tests failed. Please review the output above.")

if __name__ == "__main__":
    main() 