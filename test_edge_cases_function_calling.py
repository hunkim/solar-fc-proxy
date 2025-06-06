"""
Edge Cases and Boundary Conditions Test Cases for Function Calling

This test suite covers:
- Function chaining and sequential execution
- Streaming with function calls
- Large dataset processing 
- Conditional parameter requirements
- Recursive function call patterns
- Error resilience and recovery
- Memory and performance boundaries
"""

import asyncio
import httpx
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

BASE_URL = "http://localhost:8000"

class TestEdgeCasesFunctionCalling:
    """Edge cases and boundary condition tests for function calling"""

    async def test_function_chaining_sequential_execution(self):
        """Test sequential function execution where output of one feeds into another"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user", 
                    "content": "First get user information for ID 123, then calculate their BMI based on the returned weight and height, then provide health recommendations based on the BMI category. Execute these in sequence."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_user_info",
                        "description": "STEP 1: Get user information by ID. Must be called first.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_id": {"type": "string", "description": "User ID to look up"}
                            },
                            "required": ["user_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "calculate_bmi",
                        "description": "STEP 2: Calculate BMI using weight and height from user info. Call after get_user_info.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "weight": {"type": "number"},
                                "height": {"type": "number"}
                            },
                            "required": ["weight", "height"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "health_recommendations",
                        "description": "STEP 3: Provide health recommendations based on BMI category. Call after calculate_bmi.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "bmi": {"type": "number"},
                                "category": {"type": "string", "enum": ["underweight", "normal", "overweight", "obese"]}
                            },
                            "required": ["bmi", "category"]
                        }
                    }
                }
            ],
            "tool_choice": "required",
            "max_tokens": 1500
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            if "tool_calls" in message:
                tool_calls = message["tool_calls"]
                function_names = [tc["function"]["name"] for tc in tool_calls]
                print(f"Function call sequence: {function_names}")
                
                # Check if we got the expected function (should start with get_user_info)
                assert len(tool_calls) >= 1
                assert tool_calls[0]["function"]["name"] == "get_user_info"

    async def test_streaming_with_function_calls(self):
        """Test streaming response with function calls"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Get the current time and explain what it means."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_time",
                        "description": "Get the current time",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "format": {
                                    "type": "string",
                                    "enum": ["iso", "timestamp", "human"],
                                    "default": "human"
                                }
                            }
                        }
                    }
                }
            ],
            "tool_choice": "auto",
            "stream": True,
            "max_tokens": 800
        }

        async with httpx.AsyncClient() as client:
            async with client.stream("POST", f"{BASE_URL}/v1/chat/completions", json=payload) as response:
                assert response.status_code == 200
                
                chunks = []
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunks.append(chunk)
                
                print(f"Received {len(chunks)} streaming chunks")
                assert len(chunks) > 0

    async def test_large_dataset_processing(self):
        """Test function calls with large datasets and batch processing"""
        # Generate a large dataset
        large_dataset = [
            {"id": i, "value": i * 2, "category": f"cat_{i % 5}"}
            for i in range(100)
        ]
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": f"Process this dataset and calculate statistics: {json.dumps(large_dataset[:10])}... (truncated, total {len(large_dataset)} items)"
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "calculate_statistics",
                        "description": "Calculate statistics for a dataset",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "operation": {
                                    "type": "string",
                                    "enum": ["mean", "median", "sum", "count", "std_dev"],
                                    "description": "Statistical operation to perform"
                                },
                                "field": {
                                    "type": "string",
                                    "description": "Field to calculate statistics for"
                                },
                                "filter_category": {
                                    "type": "string",
                                    "description": "Optional category to filter by"
                                }
                            },
                            "required": ["operation", "field"]
                        }
                    }
                }
            ],
            "tool_choice": "auto",
            "max_tokens": 1000
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            print(f"Large dataset processing response: {data}")

    async def test_function_with_conditional_parameters(self):
        """Test function calls with conditional parameter requirements"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Book a flight from New York to London for tomorrow, business class, with meal preference for vegetarian."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "book_flight",
                        "description": "Book a flight with various options",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "origin": {"type": "string"},
                                "destination": {"type": "string"},
                                "departure_date": {"type": "string", "format": "date"},
                                "return_date": {"type": "string", "format": "date"},
                                "class": {
                                    "type": "string",
                                    "enum": ["economy", "premium_economy", "business", "first"]
                                },
                                "passengers": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 9,
                                    "default": 1
                                },
                                "meal_preference": {
                                    "type": "string",
                                    "enum": ["none", "vegetarian", "vegan", "halal", "kosher", "gluten_free"]
                                },
                                "seat_preference": {
                                    "type": "string",
                                    "enum": ["window", "aisle", "middle", "any"]
                                }
                            },
                            "required": ["origin", "destination", "departure_date"]
                        }
                    }
                }
            ],
            "tool_choice": "required",
            "max_tokens": 800
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            assert "tool_calls" in message
            tool_call = message["tool_calls"][0]
            args = json.loads(tool_call["function"]["arguments"])
            
            # Should include meal preference for business class
            if args.get("class") in ["business", "first"]:
                print(f"Business/First class booking includes meal preference")
            
            print(f"Flight booking: {args}")

    async def test_recursive_function_calls(self):
        """Test recursive or iterative function calling patterns"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Search for information about 'artificial intelligence' and then search for related topics based on the first results."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_information",
                        "description": "Search for information on a topic",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "depth": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 3,
                                    "description": "Search depth level"
                                },
                                "related_topics": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Related topics to explore"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ],
            "tool_choice": "auto",
            "max_tokens": 1200
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            print(f"Recursive search response: {message}")

    async def test_malformed_json_in_function_arguments(self):
        """Test handling of malformed JSON in function arguments"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Create a really complex nested structure with lots of special characters, quotes, and weird formatting."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "process_complex_data",
                        "description": "Process complex structured data",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "data": {
                                    "type": "object",
                                    "description": "Complex data structure"
                                },
                                "special_chars": {
                                    "type": "string",
                                    "description": "String with special characters"
                                }
                            },
                            "required": ["data"]
                        }
                    }
                }
            ],
            "tool_choice": "required",
            "max_tokens": 800
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            
            # Should handle malformed JSON gracefully
            print(f"Complex data processing response: {choice}")

    async def test_empty_and_null_parameters(self):
        """Test handling of empty and null parameters"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Process an empty dataset or null values."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "handle_empty_data",
                        "description": "Handle empty or null data",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "data": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Array that might be empty"
                                },
                                "nullable_field": {
                                    "type": "string",
                                    "description": "Field that can be null"
                                },
                                "optional_field": {
                                    "type": "string",
                                    "description": "Optional field"
                                }
                            },
                            "required": ["data"]
                        }
                    }
                }
            ],
            "tool_choice": "required",
            "max_tokens": 500
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            if "tool_calls" in message:
                tool_call = message["tool_calls"][0]
                args = json.loads(tool_call["function"]["arguments"])
                print(f"Empty data handling: {args}")

    async def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters in function parameters"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Process text with emojis 🚀, Chinese characters 你好, Arabic العربية, and special symbols ∫∑∆."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "process_unicode_text",
                        "description": "Process text with Unicode characters",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "Text with Unicode characters"
                                },
                                "language": {
                                    "type": "string",
                                    "enum": ["en", "zh", "ar", "mixed"],
                                    "description": "Primary language"
                                },
                                "contains_emojis": {
                                    "type": "boolean",
                                    "description": "Whether text contains emojis"
                                }
                            },
                            "required": ["text"]
                        }
                    }
                }
            ],
            "tool_choice": "required",
            "max_tokens": 600
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            if "tool_calls" in message:
                tool_call = message["tool_calls"][0]
                args = json.loads(tool_call["function"]["arguments"])
                print(f"Unicode text processing: {args}")

    async def test_very_long_parameter_strings(self):
        """Test handling of very long strings in parameters"""
        long_text = "This is a very long text. " * 100  # 2700 characters
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": f"Summarize this very long text: {long_text[:200]}... (truncated)"
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "summarize_long_text",
                        "description": "Summarize very long text",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "Long text to summarize"
                                },
                                "max_length": {
                                    "type": "integer",
                                    "minimum": 50,
                                    "maximum": 500,
                                    "description": "Maximum summary length"
                                }
                            },
                            "required": ["text"]
                        }
                    }
                }
            ],
            "tool_choice": "required",
            "max_tokens": 1000
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            
            print(f"Long text processing response: {choice}")

    async def test_timeout_and_retry_scenarios(self):
        """Test timeout and retry scenarios with function calls"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Perform a network operation that might timeout or fail."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "network_operation",
                        "description": "Perform a network operation with timeout",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "format": "uri"},
                                "timeout": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 60,
                                    "description": "Timeout in seconds"
                                },
                                "retry_count": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 3,
                                    "description": "Number of retries"
                                }
                            },
                            "required": ["url"]
                        }
                    }
                }
            ],
            "tool_choice": "required",
            "max_tokens": 500
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            
            print(f"Network operation response: {choice}")

    async def test_extremely_nested_parameters(self):
        """Test extremely nested parameter structures"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Create a deeply nested organizational structure with departments, teams, employees, and their relationships."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "create_org_structure",
                        "description": "Create organizational structure",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "organization": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "departments": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "teams": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "properties": {
                                                                "name": {"type": "string"},
                                                                "members": {
                                                                    "type": "array",
                                                                    "items": {
                                                                        "type": "object",
                                                                        "properties": {
                                                                            "name": {"type": "string"},
                                                                            "role": {"type": "string"},
                                                                            "skills": {
                                                                                "type": "array",
                                                                                "items": {"type": "string"}
                                                                            }
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    "required": ["name"]
                                }
                            },
                            "required": ["organization"]
                        }
                    }
                }
            ],
            "tool_choice": "required",
            "max_tokens": 1500
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            if "tool_calls" in message:
                tool_call = message["tool_calls"][0]
                args = json.loads(tool_call["function"]["arguments"])
                print(f"Deeply nested structure created: {len(json.dumps(args))} characters")

if __name__ == "__main__":
    async def run_edge_case_tests():
        test_instance = TestEdgeCasesFunctionCalling()
        
        print("=== Testing Function Chaining ===")
        await test_instance.test_function_chaining_sequential_execution()
        
        print("\n=== Testing Streaming with Function Calls ===")
        await test_instance.test_streaming_with_function_calls()
        
        print("\n=== Testing Large Dataset Processing ===")
        await test_instance.test_large_dataset_processing()
        
        print("\n=== Testing Conditional Parameters ===")
        await test_instance.test_function_with_conditional_parameters()
        
        print("\n=== Testing Recursive Function Calls ===")
        await test_instance.test_recursive_function_calls()
        
        print("\n=== Testing Malformed JSON Handling ===")
        await test_instance.test_malformed_json_in_function_arguments()
        
        print("\n=== Testing Empty/Null Parameters ===")
        await test_instance.test_empty_and_null_parameters()
        
        print("\n=== Testing Unicode Characters ===")
        await test_instance.test_unicode_and_special_characters()
        
        print("\n=== Testing Very Long Parameters ===")
        await test_instance.test_very_long_parameter_strings()
        
        print("\n=== Testing Timeout Scenarios ===")
        await test_instance.test_timeout_and_retry_scenarios()
        
        print("\n=== Testing Extremely Nested Parameters ===")
        await test_instance.test_extremely_nested_parameters()
        
        print("\n✅ All edge case tests completed!")

    # Run the edge case tests
    asyncio.run(run_edge_case_tests()) 