#!/usr/bin/env python3
"""
Examples for using the Text Summarization API
"""

import requests
import httpx
import asyncio
import json

# API base URL
BASE_URL = "http://localhost:8000"

def test_basic_summarization():
    """Basic example with minimal parameters"""
    url = f"{BASE_URL}/summarize"
    
    data = {
        "text": """
        Artificial intelligence (AI) is intelligence demonstrated by machines, in contrast to 
        the natural intelligence displayed by humans and animals. Leading AI textbooks define 
        the field as the study of intelligent agents: any device that perceives its environment 
        and takes actions that maximize its chance of successfully achieving its goals. 
        Colloquially, the term artificial intelligence is often used to describe machines 
        that mimic cognitive functions that humans associate with the human mind, such as 
        learning and problem solving. The traditional problems (or goals) of AI research 
        include reasoning, knowledge representation, planning, learning, natural language 
        processing, perception, and the ability to move and manipulate objects.
        """
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        
        print("=== Basic Summarization ===")
        print(f"Original length: {result['word_count_original']} words")
        print(f"Summary length: {result['word_count_summary']} words")
        print(f"Summary: {result['summary']}")
        print()
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

def test_with_length_limit():
    """Example with length limitation"""
    url = f"{BASE_URL}/summarize"
    
    data = {
        "text": """
        Climate change refers to long-term shifts in global temperatures and weather patterns. 
        While climate change is a natural phenomenon, scientific evidence shows that human 
        activities have been the main driver of climate change since the 1800s. Burning fossil 
        fuels like coal, oil, and gas produces greenhouse gas emissions that act like a blanket 
        wrapped around the Earth, trapping the sun's heat and raising temperatures. The main 
        greenhouse gases that are causing climate change are carbon dioxide and methane. These 
        come from using gasoline for driving a car or coal for heating a building, for example. 
        Clearing land and cutting down forests can also release carbon dioxide. Agriculture, 
        oil and gas operations are major sources of methane emissions. Energy, industry, 
        transport, buildings, agriculture and land use are among the main sectors causing 
        greenhouse gas emissions.
        """,
        "max_length": 30,
        "reasoning_effort": "high"
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        
        print("=== Summarization with Length Limit (30 words) ===")
        print(f"Original length: {result['word_count_original']} words")
        print(f"Summary length: {result['word_count_summary']} words")
        print(f"Summary: {result['summary']}")
        print()
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

async def test_async_summarization():
    """Async example using httpx"""
    url = f"{BASE_URL}/summarize"
    
    data = {
        "text": """
        Machine learning is a method of data analysis that automates analytical model building. 
        It is a branch of artificial intelligence based on the idea that systems can learn from 
        data, identify patterns and make decisions with minimal human intervention. Machine 
        learning algorithms build a model based on sample data, known as training data, in order 
        to make predictions or decisions without being explicitly programmed to do so. Machine 
        learning algorithms are used in a wide variety of applications, such as in medicine, 
        email filtering, speech recognition, and computer vision, where it is difficult or 
        unfeasible to develop conventional algorithms to perform the needed tasks.
        """,
        "max_length": 40,
        "reasoning_effort": "medium"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data)
            response.raise_for_status()
            result = response.json()
            
            print("=== Async Summarization ===")
            print(f"Original length: {result['word_count_original']} words")
            print(f"Summary length: {result['word_count_summary']} words")
            print(f"Summary: {result['summary']}")
            print()
            
        except httpx.RequestError as e:
            print(f"Error: {e}")

def test_health_check():
    """Test the health endpoint"""
    url = f"{BASE_URL}/health"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        result = response.json()
        
        print("=== Health Check ===")
        print(f"Status: {result['status']}")
        print(f"API Key Configured: {result['api_key_configured']}")
        print(f"Service: {result['service']}")
        print()
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

def test_error_handling():
    """Test error handling with invalid input"""
    url = f"{BASE_URL}/summarize"
    
    # Test with too short text
    data = {
        "text": "Short"  # Less than 10 characters
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 422:
            print("=== Error Handling Test ===")
            print("✓ Correctly rejected text that's too short")
            print(f"Response: {response.json()}")
            print()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

def test_multiple_reasoning_efforts():
    """Test different reasoning effort levels"""
    url = f"{BASE_URL}/summarize"
    
    sample_text = """
    The Internet of Things (IoT) describes the network of physical objects that are embedded 
    with sensors, software, and other technologies for the purpose of connecting and exchanging 
    data with other devices and systems over the internet. These devices range from ordinary 
    household objects to sophisticated industrial tools. With more than 7 billion connected 
    IoT devices today, experts are expecting this number to grow to 10 billion by 2020 and 
    22 billion by 2025. Oracle has a network of device partners.
    """
    
    for effort in ["low", "medium", "high"]:
        data = {
            "text": sample_text,
            "max_length": 25,
            "reasoning_effort": effort
        }
        
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            result = response.json()
            
            print(f"=== Reasoning Effort: {effort.upper()} ===")
            print(f"Summary: {result['summary']}")
            print(f"Word count: {result['word_count_summary']} words")
            print()
            
        except requests.exceptions.RequestException as e:
            print(f"Error with {effort} effort: {e}")

if __name__ == "__main__":
    print("🚀 Testing Text Summarization API\n")
    
    # Test health first
    test_health_check()
    
    # Basic tests
    test_basic_summarization()
    test_with_length_limit()
    
    # Async test
    print("Running async test...")
    asyncio.run(test_async_summarization())
    
    # Error handling
    test_error_handling()
    
    # Different reasoning efforts
    test_multiple_reasoning_efforts()
    
    print("✅ All tests completed!") 