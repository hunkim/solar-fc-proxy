#!/usr/bin/env python3
"""
Test LangChain-style validator schema with union types (anyOf)
"""

import requests
import json

def test_langchain_validator():
    """Test with LangChain-style validator schema (with anyOf union types)"""
    payload = {
        'model': 'gpt-4',
        'messages': [
            {'role': 'system', 'content': 'You are a validator that checks if tasks were completed successfully.'},
            {'role': 'user', 'content': 'Please validate: The user asked to find the weather in Tokyo and I provided them with current weather data showing 22°C and sunny conditions.'}
        ],
        'response_format': {
            'type': 'json_schema',
            'json_schema': {
                'name': 'validator_output',
                'schema': {
                    'type': 'object',
                    'properties': {
                        'is_valid': {
                            'anyOf': [
                                {'type': 'boolean'},
                                {'type': 'string'}
                            ]
                        },
                        'reason': {'type': 'string'},
                        'answer': {'type': 'string'}
                    },
                    'required': ['is_valid', 'reason', 'answer'],
                    'additionalProperties': False
                }
            }
        }
    }

    print("🧪 Testing LangChain Validator Schema with Union Types...")
    response = requests.post(
        'http://localhost:8000/v1/chat/completions',
        headers={'Authorization': 'Bearer test', 'Content-Type': 'application/json'},
        json=payload
    )

    print(f'Status: {response.status_code}')
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        print(f'Generated JSON: {content}')
        
        # Validate the JSON
        try:
            parsed = json.loads(content)
            print(f'✓ Valid JSON with fields: {list(parsed.keys())}')
            print(f'✓ is_valid value: {parsed["is_valid"]} (type: {type(parsed["is_valid"]).__name__})')
            print(f'✓ reason: {parsed.get("reason", "N/A")}')
            print(f'✓ answer: {parsed.get("answer", "N/A")}')
            print(f'✓ All required fields present: {all(field in parsed for field in ["is_valid", "reason", "answer"])}')
            
            # Check union type validation (is_valid should be bool or string)
            is_valid_value = parsed["is_valid"]
            is_valid_type_ok = isinstance(is_valid_value, (bool, str))
            print(f'✓ Union type validation (bool|string): {is_valid_type_ok}')
            
        except Exception as e:
            print(f'✗ JSON parsing failed: {e}')
    else:
        print(f'✗ Error: {response.text}')

if __name__ == "__main__":
    test_langchain_validator() 