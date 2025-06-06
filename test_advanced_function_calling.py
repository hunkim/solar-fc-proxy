"""
Advanced Function Calling Test Cases for Solar Proxy

This test suite covers advanced function calling scenarios including:
- Parallel function execution
- Function chaining and sequential operations  
- Complex parameter handling (nested objects, arrays, enums)
- Error handling and edge cases
- Performance testing with concurrent requests
- Integration with reasoning mode
"""

import asyncio
import httpx
import json
import pytest
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

BASE_URL = "http://localhost:8000"

class TestAdvancedFunctionCalling:
    """Advanced test cases for function calling scenarios"""

    async def test_parallel_function_calls_multiple_apis(self):
        """Test parallel execution of multiple different function calls"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Get the weather in New York, convert 100 USD to EUR, and calculate BMI for someone 75kg and 1.8m tall. Do all of these at once."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather for a city",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string", "description": "City name"},
                                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
                            },
                            "required": ["city"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "currency_convert",
                        "description": "Convert currency amounts",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "amount": {"type": "number"},
                                "from_currency": {"type": "string"},
                                "to_currency": {"type": "string"}
                            },
                            "required": ["amount", "from_currency", "to_currency"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "calculate_bmi",
                        "description": "Calculate Body Mass Index",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "weight": {"type": "number", "description": "Weight in kg"},
                                "height": {"type": "number", "description": "Height in meters"}
                            },
                            "required": ["weight", "height"]
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
            assert "choices" in data
            assert len(data["choices"]) > 0
            
            choice = data["choices"][0]
            message = choice["message"]
            
            # Should contain multiple tool calls
            if "tool_calls" in message:
                tool_calls = message["tool_calls"]
                print(f"Found {len(tool_calls)} tool calls:")
                for tool_call in tool_calls:
                    print(f"  - {tool_call['function']['name']}: {tool_call['function']['arguments']}")
                
                # Should have called multiple different functions
                function_names = [tc["function"]["name"] for tc in tool_calls]
                assert len(set(function_names)) > 1, "Should call multiple different functions"

    async def test_complex_nested_parameters(self):
        """Test function calls with complex nested object and array parameters"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Process a customer order with multiple items, shipping address, and payment method. Customer: John Doe, Items: 2x iPhone 15 Pro ($999 each), 1x AirPods Pro ($249), shipping to 123 Main St, New York, NY 10001, payment via credit card ending in 1234."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "process_order",
                        "description": "Process a complex customer order",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "customer": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"},
                                        "phone": {"type": "string"}
                                    },
                                    "required": ["name"]
                                },
                                "items": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "product_name": {"type": "string"},
                                            "quantity": {"type": "integer", "minimum": 1},
                                            "unit_price": {"type": "number", "minimum": 0},
                                            "category": {"type": "string", "enum": ["electronics", "clothing", "books", "other"]}
                                        },
                                        "required": ["product_name", "quantity", "unit_price"]
                                    }
                                },
                                "shipping_address": {
                                    "type": "object",
                                    "properties": {
                                        "street": {"type": "string"},
                                        "city": {"type": "string"},
                                        "state": {"type": "string"},
                                        "zip_code": {"type": "string"},
                                        "country": {"type": "string", "default": "USA"}
                                    },
                                    "required": ["street", "city", "state", "zip_code"]
                                },
                                "payment_method": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["credit_card", "debit_card", "paypal", "bank_transfer"]},
                                        "card_last_four": {"type": "string"},
                                        "expiry_month": {"type": "integer", "minimum": 1, "maximum": 12},
                                        "expiry_year": {"type": "integer"}
                                    },
                                    "required": ["type"]
                                }
                            },
                            "required": ["customer", "items", "shipping_address", "payment_method"]
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
            message = choice["message"]
            
            assert "tool_calls" in message
            tool_call = message["tool_calls"][0]
            assert tool_call["function"]["name"] == "process_order"
            
            # Parse and validate the complex arguments
            args = json.loads(tool_call["function"]["arguments"])
            assert "customer" in args
            assert "items" in args and isinstance(args["items"], list)
            assert "shipping_address" in args
            assert "payment_method" in args
            
            print(f"Complex order processed: {json.dumps(args, indent=2)}")

    async def test_function_with_enum_parameters(self):
        """Test function calls with enumerated parameter values"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Set the system to maintenance mode with high priority and send notifications to all administrators."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "set_system_mode",
                        "description": "Change system operational mode",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "mode": {
                                    "type": "string",
                                    "enum": ["active", "maintenance", "emergency", "offline"],
                                    "description": "System mode to set"
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high", "critical"],
                                    "description": "Priority level"
                                },
                                "notify_users": {
                                    "type": "boolean",
                                    "description": "Whether to notify users"
                                },
                                "notification_type": {
                                    "type": "string",
                                    "enum": ["email", "sms", "push", "all"],
                                    "description": "Type of notification to send"
                                }
                            },
                            "required": ["mode", "priority"]
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
            
            assert "tool_calls" in message
            tool_call = message["tool_calls"][0]
            args = json.loads(tool_call["function"]["arguments"])
            
            # Validate enum values
            assert args["mode"] in ["active", "maintenance", "emergency", "offline"]
            assert args["priority"] in ["low", "medium", "high", "critical"]
            
            print(f"System mode set: {args}")

    async def test_function_calling_with_reasoning_mode(self):
        """Test function calling combined with reasoning mode"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "I need to plan a data science project. Calculate the timeline, estimate costs, and determine team size. Think through this step by step."
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "calculate_project_timeline",
                        "description": "Calculate project timeline based on complexity",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "project_type": {
                                    "type": "string",
                                    "enum": ["data_analysis", "ml_model", "data_pipeline", "full_stack"]
                                },
                                "complexity": {
                                    "type": "string",
                                    "enum": ["simple", "medium", "complex", "enterprise"]
                                },
                                "team_experience": {
                                    "type": "string",
                                    "enum": ["junior", "mid", "senior", "expert"]
                                }
                            },
                            "required": ["project_type", "complexity"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "estimate_costs",
                        "description": "Estimate project costs",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "duration_weeks": {"type": "integer"},
                                "team_size": {"type": "integer"},
                                "infrastructure_type": {
                                    "type": "string",
                                    "enum": ["cloud", "on_premise", "hybrid"]
                                }
                            },
                            "required": ["duration_weeks", "team_size"]
                        }
                    }
                }
            ],
            "tool_choice": "auto",
            "reasoning_effort": "high",
            "max_tokens": 2000
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            
            # Should contain reasoning and potentially function calls
            print(f"Reasoning + Function calling response: {choice}")
            
            # Check for reasoning content
            if "content" in choice["message"] and choice["message"]["content"]:
                content = choice["message"]["content"]
                assert len(content) > 100  # Should have substantial reasoning content

    async def test_performance_multiple_concurrent_requests(self):
        """Test performance with multiple concurrent function calling requests"""
        payloads = []
        for i in range(5):
            payload = {
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Calculate the factorial of {10 + i} using the math function."
                    }
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "calculate_factorial",
                            "description": "Calculate factorial of a number",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "number": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "maximum": 20
                                    }
                                },
                                "required": ["number"]
                            }
                        }
                    }
                ],
                "tool_choice": "required",
                "max_tokens": 300
            }
            payloads.append(payload)

        start_time = time.time()
        
        async with httpx.AsyncClient() as client:
            tasks = []
            for payload in payloads:
                task = client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Concurrent requests completed in {total_time:.2f} seconds")
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "choices" in data

    async def test_tool_choice_specific_function_forcing(self):
        """Test forcing a specific function call with tool_choice"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "What's the weather like? Also, what time is it?"
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string"}
                            },
                            "required": ["location"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_time",
                        "description": "Get current time",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "timezone": {"type": "string", "default": "UTC"}
                            }
                        }
                    }
                }
            ],
            "tool_choice": {
                "type": "function",
                "function": {"name": "get_weather"}
            },
            "max_tokens": 500
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            # Should specifically call get_weather function
            if "tool_calls" in message:
                tool_calls = message["tool_calls"]
                assert len(tool_calls) >= 1
                assert tool_calls[0]["function"]["name"] == "get_weather"
            
            print(f"Forced function call: {message}")

    async def test_error_handling_invalid_parameters(self):
        """Test error handling when function calls have invalid parameters"""
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user",
                    "content": "Calculate the square root of negative number -25"
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "calculate_square_root",
                        "description": "Calculate square root of a number",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "number": {
                                    "type": "number",
                                    "minimum": 0,
                                    "description": "Must be a positive number"
                                }
                            },
                            "required": ["number"]
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
            
            # Should either handle the error gracefully or provide an explanation
            assert choice is not None
            print(f"Error handling response: {choice}")

if __name__ == "__main__":
    async def run_tests():
        test_instance = TestAdvancedFunctionCalling()
        
        print("=== Testing Parallel Function Calls ===")
        await test_instance.test_parallel_function_calls_multiple_apis()
        
        print("\n=== Testing Complex Parameters ===")
        await test_instance.test_complex_nested_parameters()
        
        print("\n=== Testing Enum Parameters ===")
        await test_instance.test_function_with_enum_parameters()
        
        print("\n=== Testing Reasoning + Function Calling ===")
        await test_instance.test_function_calling_with_reasoning_mode()
        
        print("\n=== Testing Performance ===")
        await test_instance.test_performance_multiple_concurrent_requests()
        
        print("\n=== Testing Tool Choice Forcing ===")
        await test_instance.test_tool_choice_specific_function_forcing()
        
        print("\n=== Testing Error Handling ===")
        await test_instance.test_error_handling_invalid_parameters()
        
        print("\n✅ All advanced function calling tests completed!")

    # Run the tests
    asyncio.run(run_tests()) 