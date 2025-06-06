#!/bin/bash

# Text Summarization API Test Script
# Make sure your API is running on http://localhost:8000

API_BASE="http://localhost:8000"

echo "🚀 Testing Text Summarization API"
echo "=================================="
echo

# Health Check
echo "1️⃣ Health Check"
echo "----------------"
curl -s -X GET "$API_BASE/health" | jq '.'
echo
echo

# Basic Summarization
echo "2️⃣ Basic Summarization"
echo "----------------------"
curl -s -X POST "$API_BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Artificial intelligence (AI) is intelligence demonstrated by machines, in contrast to the natural intelligence displayed by humans and animals. Leading AI textbooks define the field as the study of intelligent agents: any device that perceives its environment and takes actions that maximize its chance of successfully achieving its goals. Colloquially, the term artificial intelligence is often used to describe machines that mimic cognitive functions that humans associate with the human mind, such as learning and problem solving."
  }' | jq '.'
echo
echo

# Summarization with Length Limit
echo "3️⃣ Summarization with 30-word limit"
echo "-----------------------------------"
curl -s -X POST "$API_BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Climate change refers to long-term shifts in global temperatures and weather patterns. While climate change is a natural phenomenon, scientific evidence shows that human activities have been the main driver of climate change since the 1800s. Burning fossil fuels like coal, oil, and gas produces greenhouse gas emissions that act like a blanket wrapped around the Earth, trapping the sun's heat and raising temperatures.",
    "max_length": 30,
    "reasoning_effort": "high"
  }' | jq '.'
echo
echo

# Summarization with Different Reasoning Efforts
echo "4️⃣ Testing Different Reasoning Efforts"
echo "--------------------------------------"

text="Machine learning is a method of data analysis that automates analytical model building. It is a branch of artificial intelligence based on the idea that systems can learn from data, identify patterns and make decisions with minimal human intervention. Machine learning algorithms build a model based on sample data, known as training data, in order to make predictions or decisions without being explicitly programmed to do so."

for effort in "low" "medium" "high"; do
  echo "🔄 Reasoning effort: $effort"
  curl -s -X POST "$API_BASE/summarize" \
    -H "Content-Type: application/json" \
    -d "{
      \"text\": \"$text\",
      \"max_length\": 25,
      \"reasoning_effort\": \"$effort\"
    }" | jq '.summary, .word_count_summary'
  echo
done

# Error Handling Test
echo "5️⃣ Error Handling Test (short text)"
echo "-----------------------------------"
curl -s -X POST "$API_BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Short"
  }' | jq '.'
echo
echo

# Long Text Example
echo "6️⃣ Long Text Example"
echo "--------------------"
curl -s -X POST "$API_BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The Internet of Things (IoT) describes the network of physical objects that are embedded with sensors, software, and other technologies for the purpose of connecting and exchanging data with other devices and systems over the internet. These devices range from ordinary household objects to sophisticated industrial tools. With more than 7 billion connected IoT devices today, experts are expecting this number to grow to 10 billion by 2020 and 22 billion by 2025. Oracle has a network of device partners. The explosion of connected devices has generated massive amounts of data. To deal with this, many IoT deployments use edge computing, which keeps data close to where it is generated rather than sending it across long routes to data centers or clouds before processing. Computing is done on the device itself, or on a local computer or server, rather than in a far-off data center or cloud. This keeps costs down and improves response times. Edge analytics allows for real-time data processing and decision making at the edge of the network.",
    "max_length": 50,
    "reasoning_effort": "medium"
  }' | jq '.summary, .word_count_original, .word_count_summary'

echo
echo "✅ API testing completed!" 