import requests
import os
from dotenv import load_dotenv

load_dotenv('.env.local')
API_KEY = os.getenv('UPSTAGE_API_KEY', 'sk-xxx')

DEPLOYED_URL = "https://solar-fc-proxy.vercel.app/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

payload = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Stream test: say hello and stop."}],
    "stream": True
}

def main():
    print(f"Streaming from {DEPLOYED_URL} ...")
    with requests.post(DEPLOYED_URL, headers=headers, json=payload, stream=True, timeout=60) as resp:
        print(f"Status: {resp.status_code}")
        for chunk in resp.iter_lines(decode_unicode=True):
            if chunk:
                print(chunk)
        print("Stream finished.")

if __name__ == "__main__":
    main() 