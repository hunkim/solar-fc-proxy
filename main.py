from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
import httpx
import os
import json
import logging
import uuid
import re
import time
import asyncio
from typing import Dict, Any, AsyncGenerator, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env.local file FIRST
load_dotenv('.env.local')

# Import Firebase logger AFTER environment variables are loaded
from firebase_logger import firebase_logger

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Solar Proxy API",
    description="A proxy that relays OpenAI-compatible requests to Solar LLM with function calling support",
    version="1.0.0"
)

# Configuration
UPSTAGE_API_URL = "https://api.upstage.ai/v1/chat/completions"
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
DEFAULT_MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "solar-pro2-preview")

# Timeout configuration
REQUEST_TIMEOUT = 120.0

# Structured Output Support Functions
def validate_json_schema(schema: Optional[Dict]) -> bool:
    """Validate incoming JSON schema structure"""
    if schema is None:
        raise ValueError("Schema cannot be null")
    if not schema:
        raise ValueError("Schema cannot be empty")
    
    # Check required schema fields
    required_fields = ["type", "properties"]
    for field in required_fields:
        if field not in schema:
            raise ValueError(f"Schema must have '{field}' field")
    
    # Validate schema structure
    if schema["type"] != "object":
        raise ValueError("Only object type schemas are supported")
    
    if not isinstance(schema["properties"], dict):
        raise ValueError("Properties must be a dictionary")
    
    return True

def validate_field_type(value: Any, field_schema: Dict) -> bool:
    """Validate individual field against its schema"""
    if "anyOf" in field_schema:
        # Handle union types (like is_valid: boolean | string)
        for option in field_schema["anyOf"]:
            if validate_simple_type(value, option):
                return True
        return False
    else:
        return validate_simple_type(value, field_schema)

def validate_simple_type(value: Any, type_schema: Dict) -> bool:
    """Validate value against simple type schema"""
    expected_type = type_schema.get("type")
    
    if expected_type == "boolean":
        return isinstance(value, bool)
    elif expected_type == "string":
        return isinstance(value, str)
    elif expected_type == "number":
        return isinstance(value, (int, float))
    elif expected_type == "integer":
        return isinstance(value, int)
    elif expected_type == "array":
        return isinstance(value, list)
    elif expected_type == "object":
        return isinstance(value, dict)
    
    return False

def validate_response_against_schema(response_json: Dict, schema: Dict) -> bool:
    """Validate generated JSON against the schema"""
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    # Check required fields
    for field in required:
        if field not in response_json:
            raise ValueError(f"Required field '{field}' missing from response")
    
    # Validate field types
    for field, value in response_json.items():
        if field in properties:
            field_schema = properties[field]
            if not validate_field_type(value, field_schema):
                raise ValueError(f"Field '{field}' has invalid type. Expected: {field_schema}, Got: {type(value).__name__}")
    
    # Check additionalProperties
    if schema.get("additionalProperties") is False:
        for field in response_json:
            if field not in properties:
                raise ValueError(f"Additional property '{field}' not allowed")
    
    return True

def extract_json_from_text(text: str) -> Dict:
    """Extract JSON from text response if model wraps it"""
    # Handle reasoning mode: extract content after </think> tag if present
    working_content = text
    if '<think>' in text and '</think>' in text:
        post_think_content = text.split('</think>', 1)[-1].strip()
        if post_think_content:
            working_content = post_think_content
    
    # Try to parse the entire working content as JSON first
    try:
        return json.loads(working_content.strip())
    except json.JSONDecodeError:
        pass
    
    # Look for JSON blocks wrapped in code markers
    json_patterns = [
        r'```json\s*(.*?)\s*```',  # ```json ... ```
        r'```\s*(.*?)\s*```',      # ``` ... ```
        r'\{[\s\S]*\}',            # Bare JSON objects
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, working_content, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    raise ValueError("No valid JSON found in response")

def generate_structured_output_prompt(messages: List[Dict], schema: Dict, schema_name: str) -> List[Dict]:
    """Convert structured output request to prompt-engineered messages"""
    
    # Create schema instructions for the system prompt
    schema_instruction = f"""STRUCTURED OUTPUT REQUIRED:

You must respond with valid JSON that exactly matches this schema:

Schema name: {schema_name}
Schema: {json.dumps(schema, indent=2)}

CRITICAL REQUIREMENTS:
1. Your response must be ONLY valid JSON - no additional text
2. All required fields must be present: {schema.get('required', [])}
3. Field types must match the schema exactly
4. No additional properties unless allowed by the schema
5. If you use reasoning mode (<think> tags), place the JSON response AFTER the </think> closing tag
6. Do not wrap the JSON in code blocks or explanatory text

Example format:
{{"field1": "value1", "field2": true, "field3": "value3"}}
"""

    # Prepare messages with structured output context
    enhanced_messages = []
    
    # Add or enhance system message
    system_message_added = False
    for msg in messages:
        if msg.get("role") == "system":
            enhanced_content = msg["content"] + "\n\n" + schema_instruction
            enhanced_messages.append({"role": "system", "content": enhanced_content})
            system_message_added = True
        else:
            enhanced_messages.append(msg)
    
    # Add system message if none existed
    if not system_message_added:
        enhanced_messages.insert(0, {"role": "system", "content": schema_instruction})
    
    return enhanced_messages

def format_structured_output_response(json_content: str, original_response: Dict) -> Dict:
    """Format structured output as OpenAI-compatible response"""
    
    return {
        "id": original_response.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
        "object": "chat.completion",
        "created": original_response.get("created", int(time.time())),
        "model": original_response.get("model", DEFAULT_MODEL_NAME),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json_content
            },
            "logprobs": None,
            "finish_reason": "stop"
        }],
        "usage": original_response.get("usage", {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }),
        "system_fingerprint": original_response.get("system_fingerprint")
    }

def generate_function_calling_prompt(messages: List[Dict], tools: List[Dict], tool_choice: Any = "auto") -> List[Dict]:
    """Convert function calling request to prompt-engineered messages"""
    
    # Create function descriptions for the system prompt
    function_descriptions = []
    for tool in tools:
        if tool.get("type") == "function":
            func = tool
            if "function" in tool:  # Handle nested function format
                func = tool["function"]
            
            desc = f"Function: {func['name']}\n"
            desc += f"Description: {func['description']}\n"
            desc += f"Parameters: {json.dumps(func['parameters'], indent=2)}\n"
            function_descriptions.append(desc)
    
    # Create system message for function calling
    function_system_prompt = f"""You are an AI assistant with access to the following functions:

{chr(10).join(function_descriptions)}

IMPORTANT INSTRUCTIONS:
1. When the user's request requires calling one or more functions, you should:
   - Think through the problem in <think> tags if needed
   - After your thinking, provide the function calls as a JSON array
   
2. Each function call should have this exact format:
   {{
     "type": "function_call",
     "id": "fc_<random_id>",
     "call_id": "call_<random_id>",
     "name": "<function_name>",
     "arguments": "<json_string_of_arguments>"
   }}

3. If multiple functions need to be called, return multiple objects in the array.
4. If no functions need to be called, respond normally with text.
5. The "arguments" field must be a JSON string (not an object).
6. Make sure the JSON is valid and properly formatted.
7. IMPORTANT: If you use reasoning mode (<think> tags), place the function call JSON AFTER the </think> closing tag.

Tool choice setting: {tool_choice}
"""

    if tool_choice == "required":
        function_system_prompt += "\n7. CRITICAL: You MUST call at least one function for this request. This is MANDATORY. Even if the user's message doesn't seem to need a function, you must choose the most appropriate one and call it with reasonable parameters. Do not respond with regular text - you MUST return a JSON array with at least one function call."
    elif isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
        forced_function = tool_choice.get("function", {}).get("name")
        function_system_prompt += f"\n7. You MUST call the function '{forced_function}' for this request. This is required regardless of what the user asks."

    # Prepare messages with function calling context
    enhanced_messages = []
    
    # Add or enhance system message
    system_message_added = False
    for msg in messages:
        if msg.get("role") == "system":
            enhanced_content = msg["content"] + "\n\n" + function_system_prompt
            enhanced_messages.append({"role": "system", "content": enhanced_content})
            system_message_added = True
        else:
            enhanced_messages.append(msg)
    
    # Add system message if none existed
    if not system_message_added:
        enhanced_messages.insert(0, {"role": "system", "content": function_system_prompt})
    
    return enhanced_messages

def parse_function_calls(content: str) -> tuple[List[Dict], Optional[str]]:
    """Parse Solar's response to extract function calls"""
    
    # Handle reasoning mode: extract content after </think> tag if present
    working_content = content
    if '<think>' in content and '</think>' in content:
        # Extract content after the thinking section
        post_think_content = content.split('</think>', 1)[-1].strip()
        if post_think_content:
            working_content = post_think_content
    
    # Try to find JSON array in the response
    json_pattern = r'\[[\s\S]*?\]'
    json_matches = re.findall(json_pattern, working_content)
    
    function_calls = []
    remaining_text = content
    
    for json_match in json_matches:
        try:
            parsed = json.loads(json_match)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and item.get("type") == "function_call":
                        # Ensure required fields and generate IDs if missing
                        if "id" not in item:
                            item["id"] = f"fc_{uuid.uuid4().hex[:8]}"
                        if "call_id" not in item:
                            item["call_id"] = f"call_{uuid.uuid4().hex[:8]}"
                        function_calls.append(item)
                
                # Remove the JSON from the text
                remaining_text = remaining_text.replace(json_match, "").strip()
        except json.JSONDecodeError:
            continue
    
    # If no function calls found, try single object format
    if not function_calls:
        single_json_pattern = r'\{[\s\S]*?\}'
        single_matches = re.findall(single_json_pattern, working_content)
        
        for json_match in single_matches:
            try:
                parsed = json.loads(json_match)
                if isinstance(parsed, dict) and parsed.get("type") == "function_call":
                    if "id" not in parsed:
                        parsed["id"] = f"fc_{uuid.uuid4().hex[:8]}"
                    if "call_id" not in parsed:
                        parsed["call_id"] = f"call_{uuid.uuid4().hex[:8]}"
                    function_calls.append(parsed)
                    remaining_text = remaining_text.replace(json_match, "").strip()
                    break
            except json.JSONDecodeError:
                continue
    
    return function_calls, remaining_text if remaining_text else None

def format_function_call_response(function_calls: List[Dict], original_response: Dict) -> Dict:
    """Format function calls as OpenAI-compatible response"""
    
    # Create choices with function calls
    choices = []
    for i, func_call in enumerate(function_calls):
        choice = {
            "index": i,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": func_call.get("call_id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {
                        "name": func_call["name"],
                        "arguments": func_call["arguments"]
                    }
                }]
            },
            "logprobs": None,
            "finish_reason": "tool_calls"
        }
        choices.append(choice)
    
    # If no function calls, return first choice only
    if not choices:
        choices = [original_response.get("choices", [{}])[0]]
    
    return {
        "id": original_response.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
        "object": "chat.completion",
        "created": original_response.get("created"),
        "model": original_response.get("model"),
        "choices": choices,
        "usage": original_response.get("usage"),
        "system_fingerprint": original_response.get("system_fingerprint")
    }

async def stream_response_with_logging(
    response: httpx.Response, 
    original_body: Dict, 
    upstream_content: Dict,
    start_time: float,
    original_model: str,
    request: Request
) -> AsyncGenerator[str, None]:
    """Stream the response from the upstream API with logging"""
    accumulated_response = ""
    accumulated_content = ""
    response_id = None
    
    try:
        async for chunk in response.aiter_text():
            if chunk:
                accumulated_response += chunk
                
                # Try to extract content from streaming chunks
                lines = chunk.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() != '[DONE]':
                            try:
                                data = json.loads(data_str)
                                if not response_id:
                                    response_id = data.get('id', f"chatcmpl-{uuid.uuid4().hex[:8]}")
                                
                                delta_content = data.get('choices', [{}])[0].get('delta', {}).get('content')
                                if delta_content:
                                    accumulated_content += delta_content
                            except json.JSONDecodeError:
                                pass
                
                yield chunk
    except Exception as e:
        logger.error(f"Error streaming response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        # Log the complete streaming response in proper OpenAI format
        response_time = (time.time() - start_time) * 1000
        metadata = {
            'response_time_ms': response_time,
            'status_code': 200,
            'original_model': original_model,
            'mapped_model': DEFAULT_MODEL_NAME,
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown'),
            'is_streaming': True,
            'function_calls_detected': 0,
            'endpoint': '/v1/chat/completions'
        }
        
        # Create a proper OpenAI chat completion response format for logging
        response_data = {
            "id": response_id or f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": DEFAULT_MODEL_NAME,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": accumulated_content
                },
                "logprobs": None,
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": -1,  # Not available in streaming
                "completion_tokens": -1,  # Not available in streaming 
                "total_tokens": -1
            },
            "_streaming_metadata": {
                "content_length": len(accumulated_response),
                "chunks_received": len([line for line in accumulated_response.split('\n') if line.startswith('data:')])
            }
        }
        
        # Create enhanced original_body with upstream_content if modified
        enhanced_original_body = original_body.copy()
        if upstream_content:
            enhanced_original_body['_upstream_content'] = upstream_content
        
        # Async log to Firebase (fire and forget)
        asyncio.create_task(firebase_logger.log_request_response(enhanced_original_body, response_data, metadata))

async def stream_function_call_response_with_logging(
    response: httpx.Response, 
    tools: List[Dict],
    original_body: Dict, 
    upstream_content: Dict,
    start_time: float,
    original_model: str,
    request: Request
) -> AsyncGenerator[str, None]:
    """Stream function call responses in OpenAI format with logging"""
    
    accumulated_content = ""
    accumulated_response = ""
    response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    function_calls_detected = 0
    extracted_function_calls = []
    
    try:
        async for chunk in response.aiter_text():
            if chunk:
                accumulated_response += chunk
                # Try to parse streaming data
                lines = chunk.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            # Process accumulated content for function calls
                            function_calls, remaining_text = parse_function_calls(accumulated_content)
                            
                            if function_calls:
                                function_calls_detected = len(function_calls)
                                extracted_function_calls = function_calls
                                # Send function call events
                                for i, func_call in enumerate(function_calls):
                                    # Send function call start event
                                    func_event = {
                                        "id": response_id,
                                        "object": "chat.completion.chunk",
                                        "created": 1234567890,
                                        "model": DEFAULT_MODEL_NAME,
                                        "choices": [{
                                            "index": i,
                                            "delta": {
                                                "tool_calls": [{
                                                    "index": i,
                                                    "id": func_call.get("call_id", f"call_{uuid.uuid4().hex[:8]}"),
                                                    "type": "function",
                                                    "function": {
                                                        "name": func_call["name"],
                                                        "arguments": func_call["arguments"]
                                                    }
                                                }]
                                            },
                                            "logprobs": None,
                                            "finish_reason": "tool_calls"
                                        }]
                                    }
                                    yield f"data: {json.dumps(func_event)}\n\n"
                            
                            yield "data: [DONE]\n\n"
                            return
                        
                        try:
                            data = json.loads(data_str)
                            delta_content = data.get('choices', [{}])[0].get('delta', {}).get('content')
                            if delta_content:
                                accumulated_content += delta_content
                                
                                # Check if we're building function calls
                                if '[{' in accumulated_content or '{"type"' in accumulated_content:
                                    # Don't stream content while building function calls
                                    continue
                                else:
                                    # Stream normal content
                                    yield chunk
                        except json.JSONDecodeError:
                            yield chunk
                    else:
                        yield chunk
    except Exception as e:
        logger.error(f"Error streaming function call response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        # Log the complete streaming response in proper OpenAI format
        response_time = (time.time() - start_time) * 1000
        metadata = {
            'response_time_ms': response_time,
            'status_code': 200,
            'original_model': original_model,
            'mapped_model': DEFAULT_MODEL_NAME,
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown'),
            'is_streaming': True,
            'function_calls_detected': function_calls_detected,
            'endpoint': '/v1/chat/completions'
        }
        
        # Create a proper OpenAI chat completion response format for logging
        if function_calls_detected > 0:
            # Format as function calling response
            tool_calls = []
            for i, func_call in enumerate(extracted_function_calls):
                tool_calls.append({
                    "id": func_call.get("call_id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {
                        "name": func_call["name"],
                        "arguments": func_call["arguments"]
                    }
                })
            
            response_data = {
                "id": response_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": DEFAULT_MODEL_NAME,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls
                    },
                    "logprobs": None,
                    "finish_reason": "tool_calls"
                }],
                "usage": {
                    "prompt_tokens": -1,  # Not available in streaming
                    "completion_tokens": -1,  # Not available in streaming 
                    "total_tokens": -1
                },
                "_streaming_metadata": {
                    "content_length": len(accumulated_response),
                    "chunks_received": len([line for line in accumulated_response.split('\n') if line.startswith('data:')])
                }
            }
        else:
            # Format as regular response
            response_data = {
                "id": response_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": DEFAULT_MODEL_NAME,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": accumulated_content
                    },
                    "logprobs": None,
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": -1,  # Not available in streaming
                    "completion_tokens": -1,  # Not available in streaming 
                    "total_tokens": -1
                },
                "_streaming_metadata": {
                    "content_length": len(accumulated_response),
                    "chunks_received": len([line for line in accumulated_response.split('\n') if line.startswith('data:')])
                }
            }
        
        # Create enhanced original_body with upstream_content if modified
        enhanced_original_body = original_body.copy()
        if upstream_content:
            enhanced_original_body['_upstream_content'] = upstream_content
        
        # Async log to Firebase (fire and forget)
        asyncio.create_task(firebase_logger.log_request_response(enhanced_original_body, response_data, metadata))

async def stream_response(response: httpx.Response) -> AsyncGenerator[str, None]:
    """Stream the response from the upstream API"""
    try:
        async for chunk in response.aiter_text():
            if chunk:
                yield chunk
    except Exception as e:
        logger.error(f"Error streaming response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

async def stream_function_call_response(response: httpx.Response, tools: List[Dict]) -> AsyncGenerator[str, None]:
    """Stream function call responses in OpenAI format"""
    
    accumulated_content = ""
    response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    
    try:
        async for chunk in response.aiter_text():
            if chunk:
                # Try to parse streaming data
                lines = chunk.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            # Process accumulated content for function calls
                            function_calls, remaining_text = parse_function_calls(accumulated_content)
                            
                            if function_calls:
                                # Send function call events
                                for i, func_call in enumerate(function_calls):
                                    # Send function call start event
                                    func_event = {
                                        "id": response_id,
                                        "object": "chat.completion.chunk",
                                        "created": 1234567890,
                                        "model": DEFAULT_MODEL_NAME,
                                        "choices": [{
                                            "index": i,
                                            "delta": {
                                                "tool_calls": [{
                                                    "index": i,
                                                    "id": func_call.get("call_id", f"call_{uuid.uuid4().hex[:8]}"),
                                                    "type": "function",
                                                    "function": {
                                                        "name": func_call["name"],
                                                        "arguments": func_call["arguments"]
                                                    }
                                                }]
                                            },
                                            "logprobs": None,
                                            "finish_reason": "tool_calls"
                                        }]
                                    }
                                    yield f"data: {json.dumps(func_event)}\n\n"
                            
                            yield "data: [DONE]\n\n"
                            return
                        
                        try:
                            data = json.loads(data_str)
                            delta_content = data.get('choices', [{}])[0].get('delta', {}).get('content')
                            if delta_content:
                                accumulated_content += delta_content
                                
                                # Check if we're building function calls
                                if '[{' in accumulated_content or '{"type"' in accumulated_content:
                                    # Don't stream content while building function calls
                                    continue
                                else:
                                    # Stream normal content
                                    yield chunk
                        except json.JSONDecodeError:
                            yield chunk
                    else:
                        yield chunk
    except Exception as e:
        logger.error(f"Error streaming function call response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

async def stream_structured_output_response_with_logging(
    response: httpx.Response, 
    schema: Dict,
    schema_name: str,
    original_body: Dict, 
    upstream_content: Dict,
    start_time: float,
    original_model: str,
    request: Request
) -> AsyncGenerator[str, None]:
    """Stream structured output responses with validation and logging"""
    
    accumulated_content = ""
    accumulated_response = ""
    response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    validation_successful = False
    validated_json = ""
    
    try:
        async for chunk in response.aiter_text():
            if chunk:
                accumulated_response += chunk
                # Try to parse streaming data
                lines = chunk.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            # Process accumulated content for structured output
                            try:
                                response_json = extract_json_from_text(accumulated_content)
                                validate_response_against_schema(response_json, schema)
                                validated_json = json.dumps(response_json)
                                validation_successful = True
                                
                                # Send the final validated JSON content
                                final_event = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": DEFAULT_MODEL_NAME,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": validated_json
                                        },
                                        "logprobs": None,
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"data: {json.dumps(final_event)}\n\n"
                                
                            except (ValueError, json.JSONDecodeError) as e:
                                logger.error(f"Structured output validation failed: {e}")
                                # Send error event
                                error_event = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": DEFAULT_MODEL_NAME,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": f"Error: Structured output validation failed: {str(e)}"
                                        },
                                        "logprobs": None,
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"data: {json.dumps(error_event)}\n\n"
                            
                            yield "data: [DONE]\n\n"
                            return
                        
                        try:
                            data = json.loads(data_str)
                            delta_content = data.get('choices', [{}])[0].get('delta', {}).get('content')
                            if delta_content:
                                accumulated_content += delta_content
                                # Don't stream content until we validate it
                                continue
                        except json.JSONDecodeError:
                            # Non-JSON streaming data, pass through
                            yield chunk
                    else:
                        yield chunk
    except Exception as e:
        logger.error(f"Error streaming structured output response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        # Log the complete streaming response
        response_time = (time.time() - start_time) * 1000
        metadata = {
            'response_time_ms': response_time,
            'status_code': 200,
            'original_model': original_model,
            'mapped_model': DEFAULT_MODEL_NAME,
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown'),
            'is_streaming': True,
            'structured_output_requested': True,
            'structured_output_valid': validation_successful,
            'schema_name': schema_name,
            'endpoint': '/v1/chat/completions'
        }
        
        # Create a proper OpenAI chat completion response format for logging
        response_data = {
            "id": response_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": DEFAULT_MODEL_NAME,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": validated_json if validation_successful else accumulated_content
                },
                "logprobs": None,
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": -1,  # Not available in streaming
                "completion_tokens": -1,  # Not available in streaming 
                "total_tokens": -1
            },
            "_streaming_metadata": {
                "content_length": len(accumulated_response),
                "chunks_received": len([line for line in accumulated_response.split('\n') if line.startswith('data:')]),
                "structured_output_validation": {
                    "requested_schema": schema_name,
                    "validation_successful": validation_successful
                }
            }
        }
        
        # Create enhanced original_body with upstream_content if modified
        enhanced_original_body = original_body.copy()
        if upstream_content:
            enhanced_original_body['_upstream_content'] = upstream_content
        
        # Async log to Firebase (fire and forget)
        asyncio.create_task(firebase_logger.log_request_response(enhanced_original_body, response_data, metadata))

async def stream_structured_output_response(response: httpx.Response, schema: Dict, schema_name: str) -> AsyncGenerator[str, None]:
    """Stream structured output responses with validation (no logging)"""
    
    accumulated_content = ""
    response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    
    try:
        async for chunk in response.aiter_text():
            if chunk:
                # Try to parse streaming data
                lines = chunk.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            # Process accumulated content for structured output
                            try:
                                response_json = extract_json_from_text(accumulated_content)
                                validate_response_against_schema(response_json, schema)
                                validated_json = json.dumps(response_json)
                                
                                # Send the final validated JSON content
                                final_event = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": DEFAULT_MODEL_NAME,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": validated_json
                                        },
                                        "logprobs": None,
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"data: {json.dumps(final_event)}\n\n"
                                
                            except (ValueError, json.JSONDecodeError) as e:
                                logger.error(f"Structured output validation failed: {e}")
                                # Send error event
                                error_event = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": DEFAULT_MODEL_NAME,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": f"Error: Structured output validation failed: {str(e)}"
                                        },
                                        "logprobs": None,
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"data: {json.dumps(error_event)}\n\n"
                            
                            yield "data: [DONE]\n\n"
                            return
                        
                        try:
                            data = json.loads(data_str)
                            delta_content = data.get('choices', [{}])[0].get('delta', {}).get('content')
                            if delta_content:
                                accumulated_content += delta_content
                                # Don't stream content until we validate it
                                continue
                        except json.JSONDecodeError:
                            # Non-JSON streaming data, pass through
                            yield chunk
                    else:
                        yield chunk
    except Exception as e:
        logger.error(f"Error streaming structured output response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

def generate_schema_example(schema: Dict) -> str:
    """Generate an example JSON output based on the schema"""
    try:
        properties = schema.get("properties", {})
        example = {}
        
        for field_name, field_schema in properties.items():
            if "anyOf" in field_schema:
                # Handle union types - use the first option
                first_option = field_schema["anyOf"][0]
                example[field_name] = generate_field_example(field_name, first_option)
            else:
                example[field_name] = generate_field_example(field_name, field_schema)
        
        return json.dumps(example, indent=2)
    except Exception:
        # Fallback to a simple example
        return '{"field": "value"}'

def generate_field_example(field_name: str, field_schema: Dict) -> Any:
    """Generate an example value for a specific field"""
    field_type = field_schema.get("type", "string")
    
    if field_type == "string":
        if "name" in field_name.lower():
            return "John Doe"
        elif "reason" in field_name.lower():
            return "This is a valid reason"
        elif "answer" in field_name.lower():
            return "This is the answer"
        else:
            return "example_value"
    elif field_type == "boolean":
        return True
    elif field_type == "integer":
        if "age" in field_name.lower():
            return 30
        else:
            return 42
    elif field_type == "number":
        return 3.14
    elif field_type == "array":
        return ["example_item"]
    elif field_type == "object":
        return {"example_key": "example_value"}
    else:
        return "example"

@app.get("/")
async def root():
    return {
        "message": "Solar Proxy API",
        "description": "Proxies OpenAI-compatible requests to Solar LLM with function calling, structured output, and intelligent retry logic",
        "model_mapping": f"All model requests are mapped to: {DEFAULT_MODEL_NAME}",
        "features": [
            "Model mapping",
            "Streaming & non-streaming responses", 
            "Function calling via prompt engineering",
            "Structured output via prompt engineering",
            "OpenAI API compatibility"
        ],
        "endpoints": {
            "chat_completions": "POST /v1/chat/completions - Chat completions with function calling and structured output",
            "health": "GET /health - Health check"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    api_key_configured = bool(UPSTAGE_API_KEY)
    return {
        "status": "healthy" if api_key_configured else "degraded",
        "api_key_configured": api_key_configured,
        "service": "Solar Proxy API",
        "default_model": DEFAULT_MODEL_NAME,
        "features": ["function_calling", "structured_output", "streaming", "model_mapping", "api_key_authentication"],
        "auth_required": True,
        "auth_info": "Clients must provide a Bearer token in the Authorization header"
    }

@app.post("/debug/structured-output")
async def debug_structured_output(request: Request):
    """Debug endpoint to test structured output parsing without validation"""
    try:
        body = await request.json()
        
        # Check auth
        auth_header = request.headers.get("authorization", "")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization required")
        
        client_api_key = auth_header[7:]
        
        # Extract test parameters
        test_content = body.get("test_content", "")
        test_schema = body.get("test_schema")
        
        if test_content:
            # Test JSON extraction
            try:
                extracted_json = extract_json_from_text(test_content)
                extraction_success = True
                extraction_error = None
            except Exception as e:
                extracted_json = None
                extraction_success = False
                extraction_error = str(e)
            
            # Test schema validation if provided
            validation_success = None
            validation_error = None
            if test_schema and extracted_json:
                try:
                    validate_response_against_schema(extracted_json, test_schema)
                    validation_success = True
                except Exception as e:
                    validation_success = False
                    validation_error = str(e)
            
            return {
                "test_content": test_content,
                "test_schema": test_schema,
                "extraction": {
                    "success": extraction_success,
                    "extracted_json": extracted_json,
                    "error": extraction_error
                },
                "validation": {
                    "success": validation_success,
                    "error": validation_error
                } if test_schema else None
            }
        
        # Make a real test request to Solar
        test_messages = body.get("messages", [
            {"role": "user", "content": "Generate a simple person profile with name and age"}
        ])
        
        headers = {
            "Authorization": f"Bearer {client_api_key}",
            "Content-Type": "application/json"
        }
        
        test_payload = {
            "model": DEFAULT_MODEL_NAME,
            "messages": test_messages,
            "reasoning_effort": "high",
            "max_tokens": 500,
            "temperature": 0.3
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(UPSTAGE_API_URL, headers=headers, json=test_payload)
            
            if response.status_code != 200:
                return {
                    "error": "Upstream API error",
                    "status_code": response.status_code,
                    "response_text": response.text
                }
            
            response_data = response.json()
            content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Test JSON extraction
            try:
                extracted_json = extract_json_from_text(content)
                extraction_success = True
                extraction_error = None
            except Exception as e:
                extracted_json = None
                extraction_success = False
                extraction_error = str(e)
            
            return {
                "upstream_response": {
                    "status_code": response.status_code,
                    "content": content,
                    "full_response": response_data
                },
                "extraction": {
                    "success": extraction_success,
                    "extracted_json": extracted_json,
                    "error": extraction_error
                },
                "diagnostics": {
                    "content_length": len(content),
                    "contains_think_tags": "<think>" in content and "</think>" in content,
                    "contains_json_blocks": "```json" in content or "```" in content,
                    "contains_braces": "{" in content and "}" in content
                }
            }
    
    except Exception as e:
        return {
            "error": "Debug endpoint error",
            "message": str(e),
            "type": type(e).__name__
        }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy chat completions to Solar API with model mapping, function calling, and structured output support"""
    
    # Check client API key first
    auth_header = request.headers.get("authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: API key required. Please provide a valid API key in the Authorization header."
        )
    
    # Extract client API key
    client_api_key = auth_header[7:]  # Remove "Bearer " prefix
    if not client_api_key.strip():
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid API key format."
        )
    
    # Track timing and metadata for Firebase logging
    start_time = time.time()
    original_body = None
    upstream_content = None  # Store modified content sent to upstream
    response_data = None
    function_calls_detected = 0
    
    try:
        # Parse the incoming request body
        body = await request.json()
        original_body = body.copy()  # Keep original for logging
        
        # Log original model request
        original_model = body.get("model", "not specified")
        logger.debug(f"Request for model '{original_model}' -> mapping to '{DEFAULT_MODEL_NAME}'")
        
        # Override the model with our default
        body["model"] = DEFAULT_MODEL_NAME
        
        # Always set reasoning_effort to "high" for upstream requests
        body["reasoning_effort"] = "high"
        
        # Check if this is a structured output request
        response_format = body.pop("response_format", None)
        structured_output_schema = None
        structured_output_schema_name = None
        
        # Handle structured output
        if response_format and response_format.get("type") == "json_schema":
            json_schema_config = response_format.get("json_schema", {})
            structured_output_schema = json_schema_config.get("schema")
            structured_output_schema_name = json_schema_config.get("name", "structured_output")
            
            # Always validate the schema, even if it's None/null
            try:
                # Validate the schema first - this will catch null/empty schemas
                validate_json_schema(structured_output_schema)
                logger.debug(f"Structured output request with schema: {structured_output_schema_name}")
                
                # Transform messages for structured output
                original_messages = body.get("messages", [])
                enhanced_messages = generate_structured_output_prompt(
                    original_messages, 
                    structured_output_schema, 
                    structured_output_schema_name
                )
                body["messages"] = enhanced_messages
                
                # Store the modified upstream content for logging
                upstream_content = body.copy()
                
            except ValueError as e:
                logger.error(f"Invalid structured output schema: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid schema for response_format '{structured_output_schema_name}': {str(e)}"
                )
        
        # Check if this is a function calling request
        tools = body.pop("tools", None)
        tool_choice = body.pop("tool_choice", "auto")
        
        # Handle function calling (only if not already handling structured output)
        if tools and not structured_output_schema:
            logger.debug(f"Function calling request with {len(tools)} tools")
            
            # Transform messages for function calling
            original_messages = body.get("messages", [])
            enhanced_messages = generate_function_calling_prompt(original_messages, tools, tool_choice)
            body["messages"] = enhanced_messages
            
            # Store the modified upstream content for logging
            upstream_content = body.copy()
        
        # Prepare headers for upstream request (use client API key)
        headers = {
            "Authorization": f"Bearer {client_api_key}",
            "Content-Type": "application/json"
        }
    
        # Forward user-agent if present
        if "user-agent" in request.headers:
            headers["User-Agent"] = request.headers["user-agent"]
        
        # Check if streaming is requested
        is_streaming = body.get("stream", False)
        
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                UPSTAGE_API_URL, 
                headers=headers, 
                json=body,
                timeout=REQUEST_TIMEOUT
            )
            
            # If upstream returns an error, pass it through
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Upstream API error: {response.status_code} - {error_text}")
                
                # Log error to Firebase
                response_time = (time.time() - start_time) * 1000
                metadata = {
                    'response_time_ms': response_time,
                    'status_code': response.status_code,
                    'original_model': original_model,
                    'mapped_model': DEFAULT_MODEL_NAME,
                    'client_ip': request.client.host if request.client else 'unknown',
                    'user_agent': request.headers.get('user-agent', 'unknown'),
                    'is_streaming': is_streaming,
                    'endpoint': '/v1/chat/completions'
                }
                
                error_details = {
                    'status_code': response.status_code,
                    'message': error_text,
                    'type': 'upstream_api_error'
                }
                
                # Create enhanced original_body with upstream_content if modified
                enhanced_original_body = original_body.copy()
                if upstream_content:
                    enhanced_original_body['_upstream_content'] = upstream_content
                
                # Async log to Firebase (fire and forget)
                asyncio.create_task(firebase_logger.log_error(enhanced_original_body, error_details, metadata))
                
                # Relay upstream error directly to client
                return Response(content=error_text, status_code=response.status_code, media_type="application/json")
            
            # Handle streaming response
            if is_streaming:
                if structured_output_schema:
                    # Special handling for structured output streaming
                    return StreamingResponse(
                        stream_structured_output_response_with_logging(
                            response, 
                            structured_output_schema, 
                            structured_output_schema_name, 
                            original_body, 
                            upstream_content, 
                            start_time, 
                            original_model, 
                            request
                        ),
                        media_type="text/plain",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Content-Type": "text/plain; charset=utf-8"
                        }
                    )
                elif tools:
                    # Special handling for function call streaming
                    return StreamingResponse(
                        stream_function_call_response_with_logging(response, tools, original_body, upstream_content, start_time, original_model, request),
                        media_type="text/plain",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Content-Type": "text/plain; charset=utf-8"
                        }
                    )
                else:
                    # Regular streaming
                    return StreamingResponse(
                        stream_response_with_logging(response, original_body, upstream_content, start_time, original_model, request),
                        media_type="text/plain",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Content-Type": "text/plain; charset=utf-8"
                        }
                    )
            
            # Handle non-streaming response
            else:
                response_data = response.json()
                
                # Process structured output response if schema was provided
                if structured_output_schema:
                    content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    # Retry logic for structured output validation
                    max_retries = 3
                    retry_count = 0
                    validation_successful = False
                    last_error = None
                    
                    while retry_count < max_retries and not validation_successful:
                        try:
                            # Extract and validate JSON from the response
                            response_json = extract_json_from_text(content)
                            validate_response_against_schema(response_json, structured_output_schema)
                            
                            # Format as structured output response
                            validated_json = json.dumps(response_json)
                            formatted_response = format_structured_output_response(validated_json, response_data)
                            response_data = formatted_response
                            validation_successful = True
                            logger.debug(f"Structured output validated successfully for schema: {structured_output_schema_name}" + 
                                      (f" (after {retry_count} retries)" if retry_count > 0 else ""))
                            
                        except (ValueError, json.JSONDecodeError) as e:
                            retry_count += 1
                            last_error = e
                            logger.warning(f"Structured output validation failed (attempt {retry_count}/{max_retries}): {e}")
                            
                            if retry_count < max_retries:
                                # Retry with adjusted parameters
                                logger.debug(f"Retrying structured output request (attempt {retry_count + 1}/{max_retries})")
                                
                                # Adjust temperature slightly for retry (make it more focused)
                                retry_temperature = max(0.1, body.get("temperature", 0.7) - (retry_count * 0.2))
                                
                                # Create retry request body
                                retry_body = body.copy()
                                retry_body["temperature"] = retry_temperature
                                retry_body["max_tokens"] = body.get("max_tokens", 1000)
                                
                                # Enhanced prompt for retry
                                if retry_count == 1:
                                    # First retry: emphasize JSON format
                                    enhanced_messages = []
                                    for msg in retry_body["messages"]:
                                        if msg.get("role") == "system":
                                            enhanced_content = msg["content"] + "\n\nIMPORTANT: You MUST respond with ONLY valid JSON. Do not include any explanatory text, code blocks, or reasoning. Just the raw JSON object."
                                            enhanced_messages.append({"role": "system", "content": enhanced_content})
                                        else:
                                            enhanced_messages.append(msg)
                                    retry_body["messages"] = enhanced_messages
                                elif retry_count == 2:
                                    # Second retry: add example and simplify
                                    enhanced_messages = []
                                    for msg in retry_body["messages"]:
                                        if msg.get("role") == "system":
                                            schema_example = generate_schema_example(structured_output_schema)
                                            enhanced_content = msg["content"] + f"\n\nEXAMPLE OUTPUT:\n{schema_example}\n\nRespond with EXACTLY this format - pure JSON only."
                                            enhanced_messages.append({"role": "system", "content": enhanced_content})
                                        else:
                                            enhanced_messages.append(msg)
                                    retry_body["messages"] = enhanced_messages
                                
                                # Make retry request
                                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as retry_client:
                                    retry_response = await retry_client.post(
                                        UPSTAGE_API_URL, 
                                        headers=headers, 
                                        json=retry_body,
                                        timeout=REQUEST_TIMEOUT
                                    )
                                    
                                    if retry_response.status_code == 200:
                                        response_data = retry_response.json()
                                        content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                                        logger.debug(f"Retry {retry_count} response content: {content[:200]}...")
                                    else:
                                        logger.error(f"Retry {retry_count} failed with status {retry_response.status_code}")
                                        break
                            else:
                                # All retries exhausted
                                logger.error(f"All {max_retries} structured output validation attempts failed. Last error: {last_error}")
                                # Log the actual content that failed validation for debugging
                                logger.error(f"Final content that failed validation: {content[:500]}...")
                                
                                # Return detailed error response
                                error_response = {
                                    "error": {
                                        "message": f"Structured output validation failed after {max_retries} attempts: {str(last_error)}",
                                        "type": "structured_output_validation_error",
                                        "param": structured_output_schema_name,
                                        "code": "invalid_structured_output",
                                        "details": {
                                            "attempts": max_retries,
                                            "last_error": str(last_error),
                                            "content_preview": content[:200] if content else "No content"
                                        }
                                    }
                                }
                                
                                return Response(
                                    content=json.dumps(error_response),
                                    status_code=400,
                                    media_type="application/json"
                                )
                
                # Process function calling response if tools were provided
                elif tools:
                    content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    function_calls, remaining_text = parse_function_calls(content)
                    
                    if function_calls:
                        function_calls_detected = len(function_calls)
                        logger.debug(f"Detected {function_calls_detected} function calls")
                        formatted_response = format_function_call_response(function_calls, response_data)
                        response_data = formatted_response
                    else:
                        logger.debug("No function calls detected, returning normal response")
                
                # Calculate response time and prepare metadata
                response_time = (time.time() - start_time) * 1000
                metadata = {
                    'response_time_ms': response_time,
                    'status_code': 200,
                    'original_model': original_model,
                    'mapped_model': DEFAULT_MODEL_NAME,
                    'client_ip': request.client.host if request.client else 'unknown',
                    'user_agent': request.headers.get('user-agent', 'unknown'),
                    'is_streaming': is_streaming,
                    'function_calls_detected': function_calls_detected,
                    'structured_output_requested': bool(structured_output_schema),
                    'structured_output_schema_name': structured_output_schema_name if structured_output_schema else None,
                    'endpoint': '/v1/chat/completions'
                }
                
                # Create enhanced original_body with upstream_content if modified
                enhanced_original_body = original_body.copy()
                if upstream_content:
                    enhanced_original_body['_upstream_content'] = upstream_content
                
                # Async log to Firebase (fire and forget)
                asyncio.create_task(firebase_logger.log_request_response(enhanced_original_body, response_data, metadata))
                
                return response_data
    
    except json.JSONDecodeError as e:
        # Log JSON decode error
        response_time = (time.time() - start_time) * 1000
        metadata = {
            'response_time_ms': response_time,
            'status_code': 400,
            'original_model': original_body.get('model') if original_body else 'unknown',
            'mapped_model': DEFAULT_MODEL_NAME,
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown'),
            'endpoint': '/v1/chat/completions'
        }
        
        error_details = {
            'status_code': 400,
            'message': f"Invalid JSON in request body: {str(e)}",
            'type': 'json_decode_error'
        }
        
        asyncio.create_task(firebase_logger.log_error(original_body or {}, error_details, metadata))
        
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON in request body: {str(e)}"
        )
    except httpx.TimeoutException:
        logger.error("Request to upstream API timed out")
        
        # Log timeout error
        response_time = (time.time() - start_time) * 1000
        metadata = {
            'response_time_ms': response_time,
            'status_code': 504,
            'original_model': original_body.get('model') if original_body else 'unknown',
            'mapped_model': DEFAULT_MODEL_NAME,
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown'),
            'endpoint': '/v1/chat/completions'
        }
        
        error_details = {
            'status_code': 504,
            'message': 'Request to upstream service timed out',
            'type': 'timeout_error'
        }
        
        asyncio.create_task(firebase_logger.log_error(original_body or {}, error_details, metadata))
        
        raise HTTPException(
            status_code=504,
            detail="Request to upstream service timed out"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from upstream: {e.response.status_code} - {e.response.text}")
        
        # Log HTTP status error
        response_time = (time.time() - start_time) * 1000
        metadata = {
            'response_time_ms': response_time,
            'status_code': e.response.status_code,
            'original_model': original_body.get('model') if original_body else 'unknown',
            'mapped_model': DEFAULT_MODEL_NAME,
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown'),
            'endpoint': '/v1/chat/completions'
        }
        
        error_details = {
            'status_code': e.response.status_code,
            'message': f'Upstream API error: {e.response.text}',
            'type': 'http_status_error'
        }
        
        asyncio.create_task(firebase_logger.log_error(original_body or {}, error_details, metadata))
        
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Upstream API error: {e.response.text}"
        )
    except HTTPException:
        # Re-raise HTTPExceptions (like our 400 errors) so they aren't caught by the generic handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        
        # Log unexpected error
        response_time = (time.time() - start_time) * 1000
        metadata = {
            'response_time_ms': response_time,
            'status_code': 500,
            'original_model': original_body.get('model') if original_body else 'unknown',
            'mapped_model': DEFAULT_MODEL_NAME,
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown'),
            'endpoint': '/v1/chat/completions'
        }
        
        error_details = {
            'status_code': 500,
            'message': f'Internal server error: {str(e)}',
            'type': 'unexpected_error'
        }
        
        asyncio.create_task(firebase_logger.log_error(original_body or {}, error_details, metadata))
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Optional: Add models endpoint for compatibility
@app.get("/v1/models")
async def list_models():
    """List available models (returns only solar-pro2-preview)"""
    models = [
        {
            "id": "solar-pro2-preview",
            "object": "model",
            "created": 1677610602,
            "owned_by": "solar-proxy",
            "permission": [],
            "root": "solar-pro2-preview",
            "parent": None
        }
    ]
    return {
        "object": "list",
        "data": models
    }

# Catch-all for other v1 endpoints to provide helpful error messages
@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all_v1(path: str, request: Request):
    """Catch-all for unsupported v1 endpoints"""
    logger.warning(f"Unsupported endpoint requested: {request.method} /v1/{path}")
    raise HTTPException(
        status_code=404,
        detail=f"Endpoint /v1/{path} is not supported by this proxy. Supported endpoints: /v1/chat/completions, /v1/models"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 