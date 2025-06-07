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
logging.basicConfig(level=logging.INFO)
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
        
        # Async log to Firebase (fire and forget)
        asyncio.create_task(firebase_logger.log_request_response(original_body, response_data, metadata))

async def stream_function_call_response_with_logging(
    response: httpx.Response, 
    tools: List[Dict],
    original_body: Dict, 
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
        
        # Async log to Firebase (fire and forget)
        asyncio.create_task(firebase_logger.log_request_response(original_body, response_data, metadata))

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

@app.get("/")
async def root():
    return {
        "message": "Solar Proxy API",
        "description": "Proxies OpenAI-compatible requests to Solar LLM with function calling support",
        "model_mapping": f"All model requests are mapped to: {DEFAULT_MODEL_NAME}",
        "features": [
            "Model mapping",
            "Streaming & non-streaming responses", 
            "Function calling via prompt engineering",
            "OpenAI API compatibility"
        ],
        "endpoints": {
            "chat_completions": "POST /v1/chat/completions - Chat completions with function calling",
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
        "features": ["function_calling", "streaming", "model_mapping", "api_key_authentication"],
        "auth_required": True,
        "auth_info": "Clients must provide a Bearer token in the Authorization header"
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy chat completions to Solar API with model mapping and function calling support"""
    
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
    response_data = None
    function_calls_detected = 0
    
    try:
        # Parse the incoming request body
        body = await request.json()
        original_body = body.copy()  # Keep original for logging
        
        # Log original model request
        original_model = body.get("model", "not specified")
        logger.info(f"Request for model '{original_model}' -> mapping to '{DEFAULT_MODEL_NAME}'")
        
        # Override the model with our default
        body["model"] = DEFAULT_MODEL_NAME
        
        # Check if this is a function calling request
        tools = body.pop("tools", None)
        tool_choice = body.pop("tool_choice", "auto")
        
        # Handle function calling
        if tools:
            logger.info(f"Function calling request with {len(tools)} tools")
            
            # Transform messages for function calling
            original_messages = body.get("messages", [])
            enhanced_messages = generate_function_calling_prompt(original_messages, tools, tool_choice)
            body["messages"] = enhanced_messages
        
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
                
                # Async log to Firebase (fire and forget)
                asyncio.create_task(firebase_logger.log_error(original_body, error_details, metadata))
                
                # Relay upstream error directly to client
                return Response(content=error_text, status_code=response.status_code, media_type="application/json")
            
            # Handle streaming response
            if is_streaming:
                if tools:
                    # Special handling for function call streaming
                    return StreamingResponse(
                        stream_function_call_response_with_logging(response, tools, original_body, start_time, original_model, request),
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
                        stream_response_with_logging(response, original_body, start_time, original_model, request),
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
                
                # Process function calling response if tools were provided
                if tools:
                    content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    function_calls, remaining_text = parse_function_calls(content)
                    
                    if function_calls:
                        function_calls_detected = len(function_calls)
                        logger.info(f"Detected {function_calls_detected} function calls")
                        formatted_response = format_function_call_response(function_calls, response_data)
                        response_data = formatted_response
                    else:
                        logger.info("No function calls detected, returning normal response")
                
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
                    'endpoint': '/v1/chat/completions'
                }
                
                # Async log to Firebase (fire and forget)
                asyncio.create_task(firebase_logger.log_request_response(original_body, response_data, metadata))
                
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