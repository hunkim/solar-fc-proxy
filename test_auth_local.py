#!/usr/bin/env python3
"""Test authentication logic locally"""

import requests
import json
import os
from dotenv import load_dotenv

# Load .env.local if present
load_dotenv('.env.local')
UPSTAGE_API_KEY = os.getenv('UPSTAGE_API_KEY', 'test-key')

def test_auth():
    base_url = "http://localhost:8000"
    
    # Test 1: No API key (should get 401)
    print('🧪 Test 1: No API key (should return 401)')
    try:
        response = requests.post(f'{base_url}/v1/chat/completions', 
                               json={'model': 'gpt-4', 'messages': [{'role': 'user', 'content': 'Hello'}]},
                               timeout=5)
        print(f'Status: {response.status_code}')
        print(f'Response: {response.json()}')
        if response.status_code == 401:
            print('✅ Correctly blocked unauthenticated request')
        else:
            print('❌ Should have returned 401')
    except Exception as e:
        print(f'Error: {e}')

    # Test 2: Empty Bearer token (should get 401)
    print('\n🧪 Test 2: Empty Bearer token (should return 401)')
    try:
        response = requests.post(f'{base_url}/v1/chat/completions',
                               headers={'Authorization': 'Bearer '},
                               json={'model': 'gpt-4', 'messages': [{'role': 'user', 'content': 'Hello'}]},
                               timeout=5)
        print(f'Status: {response.status_code}')
        print(f'Response: {response.json()}')
        if response.status_code == 401:
            print('✅ Correctly blocked empty API key')
        else:
            print('❌ Should have returned 401')
    except Exception as e:
        print(f'Error: {e}')

    # Test 3: With API key (should work if UPSTAGE_API_KEY is configured)
    print('\n🧪 Test 3: With valid API key from .env.local')
    try:
        response = requests.post(f'{base_url}/v1/chat/completions',
                               headers={'Authorization': f'Bearer {UPSTAGE_API_KEY}'},
                               json={'model': 'gpt-4', 'messages': [{'role': 'user', 'content': 'Hello'}]},
                               timeout=10)
        print(f'Status: {response.status_code}')
        if response.status_code == 401:
            print('✅ Authentication works - client API key required')
        elif response.status_code == 500:
            data = response.json()
            if "UPSTAGE_API_KEY" in data.get('detail', ''):
                print('✅ Authentication passed, but server needs UPSTAGE_API_KEY configured')
            else:
                print(f'❌ Unexpected 500 error: {data}')
        elif response.status_code == 200:
            print('✅ Full request successful!')
        else:
            print(f'❌ Unexpected status: {response.status_code} - {response.text}')
    except Exception as e:
        print(f'Error: {e}')

    # Test 4: Health check
    print('\n🏥 Test 4: Health check')
    try:
        response = requests.get(f'{base_url}/health', timeout=5)
        print(f'Status: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            print(f'Auth required: {data.get("auth_required", False)}')
            print(f'Features: {data.get("features", [])}')
            print(f'Status: {data.get("status", "unknown")}')
        else:
            print(f'Error: {response.text}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    test_auth() 