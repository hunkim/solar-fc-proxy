import httpx
import os
import logging
import sys
import json
import time
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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
REQUEST_TIMEOUT = float(os.getenv('REQUEST_TIMEOUT', 60.0))  # seconds

# Helper to normalize model name
def normalize_model_name(model: str | None) -> str:
    """If model is not provided or does not start with 'solar' (case-insensitive), replace it with 'Solar-Strawberry'."""
    if not isinstance(model, str) or not model.lower().startswith('solar'):
        return 'Solar-Strawberry'
    return model

app = FastAPI(title="Simplified Solar Proxy")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_api_key(authorization: str | None = None) -> str | None:
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

def prepare_headers(api_key: str) -> dict[str, str]:
    """Prepare request headers with authorization"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(None)
):
    """
    Simplified proxy endpoint. Normalizes model name and forwards the request.
    Supports both streaming and non-streaming responses.
    """
    try:
        body = await request.json()
        original_model = body.get('model')
        
        logger.info(f"Request received, original model: {original_model}")
        logger.debug(f"Request body: {json.dumps(body, indent=2, default=str)}")

        if not BASE_URL:
            logger.error("BASE_URL environment variable is not set")
            raise HTTPException(status_code=500, detail="Server configuration error: BASE_URL is not set")

        api_key = extract_api_key(authorization)
        if not api_key:
            raise HTTPException(status_code=401, detail="API key is missing or invalid")

        # Normalize model name directly in the body
        normalized_model = normalize_model_name(original_model) # Handles None correctly
        body['model'] = normalized_model
        if original_model != normalized_model:
            logger.info(f"Normalized model name from '{original_model}' to '{normalized_model}'")
        elif original_model is None and normalized_model: # Log if model was initially None and got set
            logger.info(f"Model set to default '{normalized_model}' as no model was provided.")


        headers = prepare_headers(api_key)
        target_url = BASE_URL # Assuming BASE_URL is the full path to the completions endpoint
        logger.info(f"Forwarding request to: {target_url} with model '{normalized_model}'")

        should_stream = body.get('stream', False)

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            if should_stream:
                body['stream'] = True # Ensure stream is True for the downstream request
                
                async def stream_generator():
                    try:
                        async with client.stream('POST', target_url, headers=headers, json=body) as response:
                            response.raise_for_status()
                            async for line in response.aiter_lines():
                                yield f"{line}\n\n" # Pass through SSE lines
                            # Ensure [DONE] is also passed if backend sends it, or handle termination.
                            # The backend should correctly terminate the stream.
                    except httpx.HTTPStatusError as e_stream:
                        error_text = await e_stream.response.aread()
                        logger.error(f"Streaming HTTP error from backend: {e_stream.response.status_code} - {error_text.decode()}")
                        error_detail = {"message": f"Error streaming from backend: {e_stream.response.status_code}", "upstream_error": error_text.decode()}
                        error_payload = json.dumps({"error": error_detail})
                        yield f"data: {error_payload}\n\n"
                        yield f"data: [DONE]\n\n"
                    except httpx.RequestError as e_req_stream:
                        logger.error(f"Streaming request error to backend: {str(e_req_stream)}")
                        error_detail = {"message": "Failed to connect to backend for streaming", "details": str(e_req_stream)}
                        error_payload = json.dumps({"error": error_detail})
                        yield f"data: {error_payload}\n\n"
                        yield f"data: [DONE]\n\n"
                    except Exception as e_stream_gen:
                        logger.error(f"General error during streaming: {str(e_stream_gen)}", exc_info=True)
                        error_detail = {"message": "An unexpected error occurred during streaming", "details": str(e_stream_gen)}
                        error_payload = json.dumps({"error": error_detail})
                        yield f"data: {error_payload}\n\n"
                        yield f"data: [DONE]\n\n"

                return StreamingResponse(
                    stream_generator(),
                    media_type="text/event-stream"
                )
            else:
                body['stream'] = False # Ensure stream is False for non-streaming
                try:
                    response = await client.post(target_url, headers=headers, json=body)
                    response.raise_for_status()
                    return JSONResponse(content=response.json(), status_code=response.status_code)
                except httpx.HTTPStatusError as e_post:
                    logger.error(f"Non-streaming HTTP error from backend: {e_post.response.status_code} - {e_post.response.text}")
                    try:
                        error_detail_json = e_post.response.json()
                        raise HTTPException(status_code=e_post.response.status_code, detail=error_detail_json)
                    except json.JSONDecodeError:
                        raise HTTPException(status_code=e_post.response.status_code, detail=e_post.response.text)
                except httpx.RequestError as e_req_post:
                    logger.error(f"Non-streaming request error to backend: {str(e_req_post)}")
                    raise HTTPException(status_code=502, detail=f"Error communicating with backend: {str(e_req_post)}")
                except Exception as e_post_gen:
                    logger.error(f"Non-streaming general error: {str(e_post_gen)}", exc_info=True)
                    raise HTTPException(status_code=500, detail=f"Internal server error: {str(e_post_gen)}")

    except json.JSONDecodeError as e_json:
        logger.error(f"Invalid JSON in request body: {str(e_json)}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON in request body: {str(e_json)}")
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e_main:
        logger.error(f"Unexpected error in chat_completions: {str(e_main)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e_main)}")

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
    # Default port, can be overridden by Uvicorn CLI args or environment variables
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
