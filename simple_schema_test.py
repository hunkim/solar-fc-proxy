#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("UPSTAGE_API_KEY", "test-key")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Test null schema
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

# First test health endpoint
print("Testing health endpoint...")
try:
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"Health check - Status: {response.status_code}")
except Exception as e:
    print(f"Health check failed: {e}")

print("\nTesting null schema with 10 second timeout...")
try:
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=data, headers=headers, timeout=10)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
except requests.exceptions.Timeout:
    print("Request timed out!")
except Exception as e:
    print(f"Error: {e}")

# Test with a different API key to see if that's the issue
print("\nTesting with different API key...")
test_headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

try:
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=data, headers=test_headers, timeout=5)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
except requests.exceptions.Timeout:
    print("Request timed out!")
except Exception as e:
    print(f"Error: {e}") 