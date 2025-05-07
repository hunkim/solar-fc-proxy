import httpx
import os
import logging
import sys
import json
import time
import asyncio
from typing import Dict, Any, Optional, List, Generator
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

# Configure logging properly
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration constants
BASE_URL = os.getenv('BASE_URL')
REQUEST_TIMEOUT = 60.0  # seconds
MAX_RETRIES = 2
RETRY_DELAY = 1.0  # seconds

# Tool/function related parameters that should be removed before forwarding
TOOL_RELATED_PARAMS = [
    'functions', 'function_call', 
    'tools', 'tool_choice', 
    'response_format'
]

# Helper to normalize model name
def normalize_model_name(model: str) -> str:
    """If model does not start with 'solar' (case-insensitive), replace it with 'Solar-Strawberry'"""
    if not isinstance(model, str) or not model.lower().startswith('solar'):
        return 'Solar-Strawberry'
    return model

app = FastAPI(title="Solar Function Call Proxy")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up the rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

# Helper class for robust HTTP requests
class RobustClient:
    @staticmethod
    async def post(url: str, headers: Dict[str, str], json_data: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> httpx.Response:
        """Make a POST request with retry logic for improved reliability"""
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, headers=headers, json=json_data)
                    response.raise_for_status()
                    return response
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt == MAX_RETRIES:
                    logger.error(f"Failed after {MAX_RETRIES} attempts: {str(e)}")
                    if isinstance(e, httpx.HTTPStatusError):
                        try:
                            # Try to get detailed error message from the response
                            error_content = e.response.text
                            try:
                                # Try to parse as JSON for better formatting
                                error_json = json.loads(error_content)
                                error_detail = f"HTTP {e.response.status_code} error: {json.dumps(error_json, indent=2)}"
                            except json.JSONDecodeError:
                                # If not JSON, use the raw text
                                error_detail = f"HTTP {e.response.status_code} error: {error_content}"
                        except Exception:
                            # Fallback if we can't get the response content
                            error_detail = f"HTTP {e.response.status_code} error from server"
                        
                        # Log the full error details
                        logger.error(f"Server returned error: {error_detail}")
                        status_code = e.response.status_code
                    else:
                        status_code = 500
                        error_detail = f"Request failed: {str(e)}"
                    raise HTTPException(status_code=status_code, detail=error_detail)
                else:
                    # Log the full error details even on retry
                    if isinstance(e, httpx.HTTPStatusError):
                        try:
                            error_content = e.response.text
                            try:
                                error_json = json.loads(error_content)
                                error_detail = f"Server returned: {json.dumps(error_json, indent=2)}"
                            except json.JSONDecodeError:
                                error_detail = f"Server returned: {error_content}"
                            logger.warning(f"Attempt {attempt+1} failed with response: {error_detail}")
                        except Exception:
                            logger.warning(f"Attempt {attempt+1} failed, retrying in {RETRY_DELAY}s: {str(e)}")
                    else:
                        logger.warning(f"Attempt {attempt+1} failed, retrying in {RETRY_DELAY}s: {str(e)}")
                    await asyncio.sleep(RETRY_DELAY)

    @staticmethod
    async def stream(url: str, headers: Dict[str, str], json_data: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Generator:
        """Stream a POST request with retry logic for improved reliability"""
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream('POST', url, headers=headers, json=json_data) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line:
                                if line.startswith('data: '):
                                    yield f"{line}\n\n"
                                else:
                                    yield f"data: {line}\n\n"
                            if line == '[DONE]':
                                break
                        return  # Successful completion
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt == MAX_RETRIES:
                    logger.error(f"Streaming failed after {MAX_RETRIES} attempts: {str(e)}")
                    
                    # Include more detailed error info in the stream response
                    error_details = str(e)
                    if isinstance(e, httpx.HTTPStatusError):
                        try:
                            error_content = e.response.text
                            error_details = f"HTTP {e.response.status_code}: {error_content}"
                            # Log the full error
                            logger.error(f"Server returned error: {error_content}")
                        except Exception:
                            pass
                    
                    error_message = f"data: {{\"error\": \"{error_details}\"}}\n\n"
                    yield error_message
                    yield "data: [DONE]\n\n"
                    return
                else:
                    # Log more detailed errors on retry
                    if isinstance(e, httpx.HTTPStatusError):
                        try:
                            error_content = e.response.text
                            logger.warning(f"Streaming attempt {attempt+1} failed with response: {error_content}")
                        except Exception:
                            logger.warning(f"Streaming attempt {attempt+1} failed, retrying in {RETRY_DELAY}s: {str(e)}")
                    else:
                        logger.warning(f"Streaming attempt {attempt+1} failed, retrying in {RETRY_DELAY}s: {str(e)}")
                    await asyncio.sleep(RETRY_DELAY)


def extract_api_key(authorization: Optional[str] = None) -> Optional[str]:
    """Extract API key from authorization header"""
    if not authorization:
        return None
    
    authorization = authorization.strip()
    try:
        if " " in authorization:
            # Handle "Bearer <token>" format
            api_key = authorization.split(" ")[1]
        else:
            # Handle raw token format
            api_key = authorization
        
        return api_key
    except Exception as e:
        logger.warning(f"Error extracting API key: {e}")
        return None

def prepare_headers(api_key: str) -> Dict[str, str]:
    """Prepare request headers with authorization"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize and validate the payload without modifying model selection"""
    # Create a copy to avoid modifying the original
    sanitized = payload.copy()

    # Normalize model name
    original_model = sanitized.get('model')
    sanitized['model'] = normalize_model_name(original_model)
    if original_model != sanitized['model']:
        logger.info(f"Normalized model name from {original_model} to {sanitized['model']}")

    # Ensure messages is a list
    if "messages" not in sanitized or not isinstance(sanitized["messages"], list):
        sanitized["messages"] = []
    
    # Log the payload for debugging
    logger.debug(f"Sanitized payload: {json.dumps(sanitized, default=str)}")
    return sanitized

def clean_for_backend(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove function/tool related parameters before sending to backend"""
    # Create a copy to avoid modifying the original
    clean_payload = payload.copy()
    
    # Remove all tool-related parameters
    for param in TOOL_RELATED_PARAMS:
        if param in clean_payload:
            clean_payload.pop(param)
    
    return clean_payload

def prepare_function_call_prompt(functions: List[Dict[str, Any]], function_call: Optional[Any] = None) -> str:
    """Prepare the system prompt for function calling"""
    system_prompt = """/no_think You are a helpful assistant that responds in JSON format for function calling.
You must analyze the user's request and determine which function to call from the available functions.
You must respond ONLY with a JSON object in the following format:
{
  "function_call": {
    "name": "function_name",
    "arguments": {
      "param1": "value1",
      "param2": "value2",
      ...
    }
  }
}

Available functions:
"""
    
    # Add function definitions to the system prompt
    for function in functions:
        system_prompt += f"\nFunction: {function['name']}\n"
        system_prompt += f"Description: {function.get('description', 'No description')}\n"
        
        if 'parameters' in function:
            system_prompt += "Parameters:\n"
            required_params = function.get('parameters', {}).get('required', [])
            properties = function.get('parameters', {}).get('properties', {})
            
            for param_name, param_details in properties.items():
                required_marker = "(required)" if param_name in required_params else "(optional)"
                param_type = param_details.get('type', 'any')
                param_desc = param_details.get('description', 'No description')
                system_prompt += f"  - {param_name} {required_marker}: {param_type} - {param_desc}\n"
    
    # Handle the function_call parameter
    if function_call and function_call != "auto":
        if function_call == "none":
            system_prompt += "\nIMPORTANT: Do not call any function. Just respond normally."
        elif isinstance(function_call, dict) and 'name' in function_call:
            specific_function = function_call.get('name', '')
            system_prompt += f"\nIMPORTANT: You must call the function '{specific_function}' only."
    
    return system_prompt

def merge_user_messages(messages: List[Dict[str, str]]) -> str:
    """Merge user and assistant messages into a single content string"""
    user_messages = [msg for msg in messages if msg.get('role') != 'system']
    user_content = ""
    
    for msg in user_messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        user_content += f"{role}: {content}\n"
    
    return user_content

def parse_function_response(content: str) -> Dict[str, Any]:
    """Parse function calling response from LLM and handle edge cases"""
    # Find JSON block if it's embedded in text
    json_start = content.find('{')
    json_end = content.rfind('}') + 1
    
    if json_start >= 0 and json_end > json_start:
        json_str = content[json_start:json_end]
        try:
            function_data = json.loads(json_str)
            
            # Validate function_call format if present
            if "function_call" in function_data:
                fc = function_data["function_call"]
                if not isinstance(fc, dict) or "name" not in fc:
                    # Fix malformed function call
                    return {"content": content}
                
                # Ensure arguments is a dict
                if "arguments" not in fc or not isinstance(fc["arguments"], dict):
                    # Handle string arguments (sometimes LLMs return them as JSON strings)
                    if "arguments" in fc and isinstance(fc["arguments"], str):
                        try:
                            fc["arguments"] = json.loads(fc["arguments"])
                        except json.JSONDecodeError:
                            fc["arguments"] = {}
                    else:
                        fc["arguments"] = {}
            
            return function_data
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from response: {json_str}")
    
    # Default if no valid JSON found
    return {"content": content}

def format_openai_response(llm_response: Dict[str, Any], function_data: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Format the response to match OpenAI's API format"""
    # Create OpenAI-compatible response
    openai_response = {
        "id": llm_response.get('id', f'chatcmpl-{os.urandom(4).hex()}'),
        "object": "chat.completion",
        "created": llm_response.get('created', int(time.time())),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                },
                "finish_reason": "function_call" if "function_call" in function_data else "stop"
            }
        ],
        "usage": llm_response.get('usage', {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        })
    }
    
    # Add either content or function_call to the message
    if "function_call" in function_data:
        openai_response["choices"][0]["message"]["function_call"] = function_data["function_call"]
    else:
        openai_response["choices"][0]["message"]["content"] = function_data.get("content", "")
    
    return openai_response

@app.post("/v1/chat/completions")
@limiter.limit("10/minute")
async def chat_completions(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(None)
):
    """
    Main endpoint that handles both regular chat completions and function calling.
    Compatible with OpenAI's chat completions API.
    """
    try:
        # Parse request body
        body = await request.json()

        model = body.get('model')
        # Log request details
        msg_count = len(body.get('messages', []))
        logger.info(f"Request received with {msg_count} messages, model: {model}")
        logger.info(f"Request body: {json.dumps(body, indent=2)}")
        
        # Ensure BASE_URL is set
        if not BASE_URL:
            logger.error("BASE_URL environment variable is not set")
            raise HTTPException(status_code=500, detail="Server configuration error: BASE_URL is not set")
        
        # Get API key
        api_key = extract_api_key(authorization)
        if not api_key:
            raise HTTPException(status_code=401, detail="API key is missing or invalid")
        
        # Check for function calling (either via functions or tools parameter)
        functions = body.get('functions', None)
        function_call = body.get('function_call', None)
        
        # Support for OpenAI's tools format
        tools = body.get('tools', None)
        tool_choice = body.get('tool_choice', None)
        
        # Check if the last message is a tool response
        messages = body.get('messages', [])
        is_tool_response = False
        if messages and messages[-1].get('role') == 'tool':
            # If last message is a tool response, handle it as a regular message
            is_tool_response = True
            logger.info("Last message is a tool response, handling as regular chat completion")
        
        # Convert tools format to functions format if needed
        if not functions and tools and not is_tool_response:
            functions = []
            for tool in tools:
                if tool.get('type') == 'function':
                    functions.append(tool.get('function', {}))
            
            # Convert tool_choice to function_call if present
            if tool_choice and tool_choice != "auto" and tool_choice != "none":
                if isinstance(tool_choice, dict) and tool_choice.get('type') == 'function':
                    function_call = {'name': tool_choice.get('function', {}).get('name')}
                
        should_stream = body.get('stream', False)
        
        # Prepare headers
        headers = prepare_headers(api_key)
        
        # Log the target URL (without the API key)
        logger.info(f"Forwarding request to: {BASE_URL}")
        
        # Handle regular chat completion (no function/tool calling) or tool response
        if not functions or is_tool_response:
            # Sanitize payload without modifying model
            payload = sanitize_payload(body)
            
            # Remove any tool-related parameters
            clean_payload = clean_for_backend(payload)
            
            # Handle streaming response
            if should_stream:
                # Ensure stream is enabled for the downstream request
                clean_payload['stream'] = True
                return StreamingResponse(
                    RobustClient.stream(BASE_URL, headers, clean_payload),
                    media_type="text/event-stream"
                )
            else:
                # Handle non-streaming case
                clean_payload['stream'] = False
                response = await RobustClient.post(BASE_URL, headers, clean_payload)
                return JSONResponse(response.json())
        
        # Handle function calling via prompting
        payload = sanitize_payload(body)
        
        # Prepare function call prompt
        system_prompt = prepare_function_call_prompt(functions, function_call)
        user_content = merge_user_messages(payload.get('messages', []))
        
        # Create new messages array
        new_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        logger.info(f"New messages for function calling: {json.dumps(new_messages, indent=2)}")

        # Create a clean payload for the backend (without tool parameters)
        clean_payload = clean_for_backend(payload)
        clean_payload['messages'] = new_messages
        clean_payload['stream'] = False  # Function calls can't be streamed
        
        # Make the request to the LLM
        try:
            response = await RobustClient.post(BASE_URL, headers, clean_payload)
            llm_response = response.json()
        except Exception as e:
            logger.error(f"Error calling LLM API: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Error communicating with language model API: {str(e)}")
        
        # Extract and process the content
        content = llm_response.get('choices', [{}])[0].get('message', {}).get('content', '')
        function_data = parse_function_response(content)
        
        # Format and return OpenAI-compatible response
        openai_response = format_openai_response(
            llm_response, 
            function_data,
            normalize_model_name(body.get('model', 'solar-pro'))  # Use the normalized model name
        )
        
        # Convert function_call to tool_call if original request used tools format
        if tools and "function_call" in function_data:
            # Add tool_calls array to response
            function_call_data = function_data["function_call"]
            # Convert arguments to JSON string as required by OpenAI API
            arguments_dict = function_call_data.get("arguments", {})
            arguments_str = json.dumps(arguments_dict)
            
            openai_response["choices"][0]["message"]["tool_calls"] = [
                {
                    "id": f"call_{os.urandom(4).hex()}",
                    "type": "function", 
                    "function": {
                        "name": function_call_data.get("name", ""),
                        "arguments": arguments_str
                    }
                }
            ]
            # Change finish reason to "tool_calls"
            openai_response["choices"][0]["message"].pop("function_call", None)
            openai_response["choices"][0]["finish_reason"] = "tool_calls"
        
        logger.info(f"OpenAI response: {openai_response}")
        
        return JSONResponse(openai_response)
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request body: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON in request body: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy", 
        "timestamp": time.time(),
        "base_url_configured": bool(BASE_URL)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
