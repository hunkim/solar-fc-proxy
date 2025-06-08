# Structured Output Support

The Solar Proxy API now supports OpenAI-compatible structured output via the `response_format` parameter. This allows you to receive JSON responses that conform to a specific schema.

## Features

- ✅ **Schema Validation**: Validates incoming JSON schemas and ensures responses conform to them
- ✅ **Union Types**: Supports complex types like `anyOf` for fields that can be multiple types
- ✅ **Streaming Support**: Works with both streaming and non-streaming requests
- ✅ **Error Handling**: Provides detailed error messages for schema validation failures
- ✅ **Firebase Logging**: Logs structured output requests and validation results

## Usage

### Basic Example

```python
import requests

payload = {
    "model": "solar-pro2-preview",
    "messages": [
        {"role": "user", "content": "Generate a person's profile"}
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
                    "occupation": {"type": "string"}
                },
                "required": ["name", "age"],
                "additionalProperties": False
            }
        }
    }
}

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    headers={"Authorization": "Bearer your-api-key"},
    json=payload
)
```

### LangChain Validator Schema (Nanobrowser Compatible)

```python
payload = {
    "model": "solar-pro2-preview",
    "messages": [
        {
            "role": "system", 
            "content": "You are a validator that checks if tasks are completed correctly."
        },
        {
            "role": "user", 
            "content": "Validate this task completion..."
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
```

### Streaming Example

```python
payload = {
    "model": "solar-pro2-preview",
    "stream": True,  # Enable streaming
    "messages": [...],
    "response_format": {
        "type": "json_schema",
        "json_schema": {...}
    }
}

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    headers={"Authorization": "Bearer your-api-key"},
    json=payload,
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

## Schema Requirements

### Supported Types
- `string`
- `integer`
- `number` (float)
- `boolean`
- `array`
- `object`
- `anyOf` (union types)

### Required Fields
Your schema must include:
- `type`: "object" (only object schemas are supported)
- `properties`: Dictionary of field definitions

### Optional Fields
- `required`: Array of required field names
- `additionalProperties`: Boolean (defaults to true)

## Error Handling

The API returns detailed error messages for various scenarios:

### Invalid Schema
```json
{
    "detail": "Invalid schema for response_format 'my_schema': Schema must have 'type' field"
}
```

### Validation Failure
```json
{
    "detail": "Structured output validation failed: Required field 'name' missing from response"
}
```

### JSON Parse Error
```json
{
    "detail": "Structured output validation failed: No valid JSON found in response"
}
```

## Integration with LangChain

This implementation is fully compatible with LangChain's `withStructuredOutput()` method:

```typescript
// In your LangChain code, this will now work with solar-pro2-preview
const structuredLlm = llm.withStructuredOutput(schema);
const result = await structuredLlm.invoke(messages);
```

## Testing

Run the included test script to verify functionality:

```bash
python test_structured_output.py
```

## Limitations

1. **Object Types Only**: Only object-type schemas are supported (not arrays or primitives at the root level)
2. **Solar Model Dependency**: The quality of structured output depends on the Solar model's ability to follow instructions
3. **Validation Overhead**: Schema validation adds minimal latency to responses
4. **Streaming Behavior**: In streaming mode, the full response is validated before being sent to avoid partial invalid JSON

## Implementation Details

The structured output feature works by:

1. **Schema Validation**: Validating the incoming JSON schema for correctness
2. **Prompt Engineering**: Adding detailed instructions to the system prompt about the required JSON format
3. **Response Parsing**: Extracting JSON from the model's response (handles reasoning mode and code blocks)
4. **Output Validation**: Ensuring the generated JSON conforms to the provided schema
5. **Error Recovery**: Providing meaningful error messages when validation fails

This approach ensures compatibility with models that don't natively support structured output while maintaining the OpenAI API contract. 