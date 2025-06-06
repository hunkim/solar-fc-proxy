#!/usr/bin/env python3
"""
Comprehensive test suite for Solar Proxy API
Tests various scenarios including streaming, model mapping, and error handling
"""

import asyncio
import aiohttp
import json
import time
import os
from typing import Dict, Any, Optional

# Test configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 30

class ProxyTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = None
        self.test_results = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_health_check(self):
        """Test health check endpoint"""
        print("🏥 Testing health check...")
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                data = await response.json()
                status = "✅ PASS" if response.status == 200 else "❌ FAIL"
                print(f"   {status} - Health Check: {data}")
                return response.status == 200
        except Exception as e:
            print(f"   ❌ FAIL - Health Check Error: {e}")
            return False
    
    async def test_root_endpoint(self):
        """Test root endpoint"""
        print("🏠 Testing root endpoint...")
        try:
            async with self.session.get(f"{self.base_url}/") as response:
                data = await response.json()
                status = "✅ PASS" if response.status == 200 else "❌ FAIL"
                print(f"   {status} - Root endpoint: {data.get('message', 'No message')}")
                return response.status == 200
        except Exception as e:
            print(f"   ❌ FAIL - Root endpoint error: {e}")
            return False
    
    async def test_models_endpoint(self):
        """Test models listing endpoint"""
        print("📋 Testing models endpoint...")
        try:
            async with self.session.get(f"{self.base_url}/v1/models") as response:
                data = await response.json()
                status = "✅ PASS" if response.status == 200 else "❌ FAIL"
                model_count = len(data.get('data', []))
                print(f"   {status} - Models endpoint: {model_count} models listed")
                return response.status == 200
        except Exception as e:
            print(f"   ❌ FAIL - Models endpoint error: {e}")
            return False
    
    async def test_chat_completion(self, model: str, stream: bool = False, 
                                 test_name: str = None, **kwargs):
        """Test chat completion with various configurations"""
        test_name = test_name or f"Chat completion ({model}, stream={stream})"
        print(f"💬 Testing {test_name}...")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Say hello in exactly 5 words."}
            ],
            "stream": stream,
            "max_tokens": 50,
            **kwargs
        }
        
        try:
            start_time = time.time()
            
            if stream:
                return await self._test_streaming_response(payload, test_name)
            else:
                return await self._test_regular_response(payload, test_name, start_time)
                
        except Exception as e:
            print(f"   ❌ FAIL - {test_name} error: {e}")
            return False
    
    async def _test_regular_response(self, payload: Dict[str, Any], 
                                   test_name: str, start_time: float):
        """Test regular (non-streaming) response"""
        async with self.session.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            
            duration = time.time() - start_time
            
            if response.status == 200:
                data = await response.json()
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f"   ✅ PASS - {test_name}")
                print(f"      Response: {content[:100]}{'...' if len(content) > 100 else ''}")
                print(f"      Duration: {duration:.2f}s")
                return True
            else:
                error_text = await response.text()
                print(f"   ❌ FAIL - {test_name}: HTTP {response.status}")
                print(f"      Error: {error_text}")
                return False
    
    async def _test_streaming_response(self, payload: Dict[str, Any], test_name: str):
        """Test streaming response"""
        async with self.session.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            
            if response.status == 200:
                chunks = []
                content_parts = []
                
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        chunks.append(line_text)
                        # Try to parse streaming data
                        try:
                            data_str = line_text[6:]  # Remove 'data: '
                            if data_str != '[DONE]':
                                data = json.loads(data_str)
                                delta_content = data.get('choices', [{}])[0].get('delta', {}).get('content')
                                if delta_content:
                                    content_parts.append(delta_content)
                        except json.JSONDecodeError:
                            pass  # Skip malformed JSON
                
                full_content = ''.join(content_parts)
                print(f"   ✅ PASS - {test_name}")
                print(f"      Chunks received: {len(chunks)}")
                print(f"      Content parts: {len(content_parts)}")
                print(f"      Full response: {full_content[:100]}{'...' if len(full_content) > 100 else ''}")
                return True
            else:
                error_text = await response.text()
                print(f"   ❌ FAIL - {test_name}: HTTP {response.status}")
                print(f"      Error: {error_text}")
                return False
    
    async def test_error_cases(self):
        """Test various error scenarios"""
        print("🚨 Testing error cases...")
        
        # Test invalid JSON
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                data="invalid json",
                headers={"Content-Type": "application/json"}
            ) as response:
                status = "✅ PASS" if response.status == 400 else "❌ FAIL"
                print(f"   {status} - Invalid JSON handling: HTTP {response.status}")
        except Exception as e:
            print(f"   ❌ FAIL - Invalid JSON test error: {e}")
        
        # Test missing required fields
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json={"model": "gpt-4"},  # Missing messages
                headers={"Content-Type": "application/json"}
            ) as response:
                status = "✅ PASS" if response.status >= 400 else "❌ FAIL"
                print(f"   {status} - Missing messages field: HTTP {response.status}")
        except Exception as e:
            print(f"   ❌ FAIL - Missing fields test error: {e}")
        
        # Test unsupported endpoint
        try:
            async with self.session.post(f"{self.base_url}/v1/unsupported") as response:
                status = "✅ PASS" if response.status == 404 else "❌ FAIL"
                print(f"   {status} - Unsupported endpoint: HTTP {response.status}")
        except Exception as e:
            print(f"   ❌ FAIL - Unsupported endpoint test error: {e}")
    
    async def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting Solar Proxy Test Suite")
        print("=" * 50)
        
        tests = [
            self.test_health_check(),
            self.test_root_endpoint(),
            self.test_models_endpoint(),
            
            # Test different models (should all map to Solar)
            self.test_chat_completion("gpt-4", stream=False, test_name="GPT-4 (non-streaming)"),
            self.test_chat_completion("gpt-3.5-turbo", stream=False, test_name="GPT-3.5-turbo (non-streaming)"),
            self.test_chat_completion("claude-3", stream=False, test_name="Claude-3 (non-streaming)"),
            self.test_chat_completion("custom-model", stream=False, test_name="Custom model (non-streaming)"),
            
            # Test streaming
            self.test_chat_completion("gpt-4", stream=True, test_name="GPT-4 (streaming)"),
            self.test_chat_completion("gpt-3.5-turbo", stream=True, test_name="GPT-3.5-turbo (streaming)"),
            
            # Test with different parameters
            self.test_chat_completion("gpt-4", stream=False, test_name="With temperature", temperature=0.8),
            self.test_chat_completion("gpt-4", stream=False, test_name="With max_tokens", max_tokens=20),
            self.test_chat_completion("gpt-4", stream=False, test_name="With reasoning_effort", reasoning_effort="high"),
            
            # Test longer conversation
            self.test_chat_completion(
                "gpt-4", 
                stream=False, 
                test_name="Multi-turn conversation",
                messages=[
                    {"role": "user", "content": "What is 2+2?"},
                    {"role": "assistant", "content": "2+2 equals 4."},
                    {"role": "user", "content": "What about 3+3?"}
                ]
            ),
            
            self.test_error_cases(),
        ]
        
        results = await asyncio.gather(*tests, return_exceptions=True)
        
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)
        
        passed = sum(1 for r in results if r is True)
        total = len([r for r in results if isinstance(r, bool)])
        
        print(f"Tests passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print("⚠️  Some tests failed. Check the output above for details.")
        
        return passed == total

async def main():
    """Main test runner"""
    async with ProxyTester() as tester:
        success = await tester.run_all_tests()
        return success

if __name__ == "__main__":
    # Check if server is running
    print("🔍 Checking if Solar Proxy server is running...")
    
    try:
        import requests
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running!")
        else:
            print("❌ Server responded but with error status")
            print("   Make sure your UPSTAGE_API_KEY is set in .env.local")
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running!")
        print("   Please start the server with: uvicorn main:app --reload")
        exit(1)
    except Exception as e:
        print(f"❌ Error checking server: {e}")
        exit(1)
    
    # Run tests
    print("\n" + "🧪 Starting tests...")
    success = asyncio.run(main())
    exit(0 if success else 1) 