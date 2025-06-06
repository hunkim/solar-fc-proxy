# Solar Proxy API

A reliable FastAPI proxy that forwards OpenAI-compatible API requests to Solar LLM, automatically mapping any model name to your configured Solar model.

## Features

- 🔄 **Model Mapping**: Automatically maps any requested model to Solar (configurable)
- 🚀 **OpenAI Compatibility**: Works with any OpenAI-compatible client
- 📡 **Streaming Support**: Supports both streaming and non-streaming responses
- 🔒 **Secure**: API key management with environment variables
- 📊 **Monitoring**: Built-in health checks and logging
- 🌐 **Vercel Ready**: Configured for easy deployment on Vercel

## Quick Start

### 1. Install Dependencies

```bash
# Using virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `env.example` to `.env.local` and set your values:

```bash
cp env.example .env.local
```

Edit `.env.local`:
```bash
# Required: Your Upstage API key for Solar
UPSTAGE_API_KEY=your_upstage_api_key_here

# Optional: Default model name (defaults to solar-pro2-preview)
DEFAULT_MODEL_NAME=solar-pro2-preview
```

> Get your API key from [Upstage Console](https://console.upstage.ai/)

### 3. Run the Server

```bash
# Development mode
uvicorn main:app --reload --port 8000

# Or directly
python main.py
```

The proxy will be available at `http://localhost:8000`

## Usage

### With OpenAI Python Client

```python
from openai import OpenAI

# Point to your proxy instead of OpenAI
client = OpenAI(
    api_key="dummy-key",  # Not used, but required by client
    base_url="http://localhost:8000/v1"
)

# Any model name will be mapped to your configured Solar model
response = client.chat.completions.create(
    model="gpt-4",  # This will be mapped to solar-pro2-preview
    messages=[
        {"role": "user", "content": "Hello, how are you?"}
    ]
)

print(response.choices[0].message.content)
```

### With curl

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-3.5-turbo",
       "messages": [
         {"role": "user", "content": "Explain quantum computing"}
       ],
       "max_tokens": 150
     }'
```

### Streaming Example

```python
from openai import OpenAI

client = OpenAI(
    api_key="dummy-key",
    base_url="http://localhost:8000/v1"
)

stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Write a short story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## API Endpoints

### Core Endpoints

- `POST /v1/chat/completions` - Chat completions (main proxy endpoint)
- `GET /v1/models` - List available models
- `GET /health` - Health check
- `GET /` - API information

### Model Mapping

The proxy automatically maps **any** model name in requests to your configured Solar model:

- `gpt-4` → `solar-pro2-preview`
- `gpt-3.5-turbo` → `solar-pro2-preview`  
- `claude-3` → `solar-pro2-preview`
- `custom-model` → `solar-pro2-preview`

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UPSTAGE_API_KEY` | Yes | - | Your Upstage API key |
| `DEFAULT_MODEL_NAME` | No | `solar-pro2-preview` | Solar model to use |

### Available Solar Models

You can set `DEFAULT_MODEL_NAME` to any of these Solar models:

- `solar-pro2-preview` (latest, recommended)
- `solar-pro`
- `solar-1-mini-chat`

## Deployment

### Vercel Deployment

This proxy is configured for Vercel deployment:

1. Fork/clone this repository
2. Connect to Vercel
3. Set environment variables in Vercel dashboard:
   - `UPSTAGE_API_KEY`: Your Upstage API key
   - `DEFAULT_MODEL_NAME`: Your preferred Solar model (optional)
4. Deploy

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Monitoring & Health

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "api_key_configured": true,
  "service": "Solar Proxy API", 
  "default_model": "solar-pro2-preview"
}
```

### Logs

The proxy logs all model mapping and errors:

```
INFO: Request for model 'gpt-4' -> mapping to 'solar-pro2-preview'
```

## Error Handling

The proxy handles various error scenarios gracefully:

- **Missing API key**: Returns 500 with clear error message
- **Upstream API errors**: Forwards Solar API error responses
- **Timeouts**: 504 with timeout message (120s timeout)
- **Invalid JSON**: 400 with validation error
- **Unsupported endpoints**: 404 with helpful message

## Compatibility

This proxy is compatible with:

- ✅ OpenAI Python SDK
- ✅ OpenAI Node.js SDK  
- ✅ LangChain
- ✅ Any OpenAI-compatible client
- ✅ curl/HTTP clients

## Development

### Project Structure

```
.
├── main.py              # Main proxy application
├── requirements.txt     # Python dependencies
├── vercel.json         # Vercel deployment config
├── env.example         # Environment variables example
└── README.md           # This file
```

### Testing

Test the proxy with various model names:

```bash
# Test with different model names - all should work
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'

curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3", "messages": [{"role": "user", "content": "Hello"}]}'
```

## License

This project is open source and available under the MIT License.
