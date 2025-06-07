#!/usr/bin/env python3
"""
Check Firebase logs to see if proxy data is being logged
"""

import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

def check_proxy_logs():
    """Check if proxy logs exist in Firebase"""
    print("🔍 Checking Firebase Proxy Logs...")
    
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # Check if already initialized, if not initialize
        if not firebase_admin._apps:
            # Create credentials from environment variables
            cred_dict = {
                "type": "service_account",
                "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
                "private_key": os.getenv('FIREBASE_PRIVATE_KEY'),
                "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                "auth_uri": os.getenv('FIREBASE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
                "token_uri": os.getenv('FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
                "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_X509_CERT_URL', 'https://www.googleapis.com/oauth2/v1/certs'),
                "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL'),
                "universe_domain": os.getenv('FIREBASE_UNIVERSE_DOMAIN', 'googleapis.com')
            }
            
            # Initialize Firebase
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("  ✅ Firebase initialized")
        
        # Get Firestore client
        db = firestore.client()
        
        # Check current day's collection
        current_day = datetime.now().strftime('%Y_%m_%d')
        collection_name = f"proxy_logs_{current_day}"
        
        print(f"  📂 Checking collection: {collection_name}")
        
        # Get recent logs (limit to 10 most recent)
        logs_ref = db.collection(collection_name).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10)
        logs = logs_ref.get()
        
        if not logs:
            print("  ❌ No proxy logs found in Firebase!")
            print("  💡 This means Firebase logging is not working in the proxy server.")
            return False
        
        print(f"  ✅ Found {len(logs)} recent log entries!")
        print("\n📋 Recent Proxy Logs:")
        print("=" * 80)
        
        for i, log in enumerate(logs, 1):
            data = log.to_dict()
            timestamp = data.get('timestamp', 'Unknown')
            request_id = data.get('request_id', 'Unknown')
            model_req = data.get('model_requested', 'Unknown')
            model_used = data.get('model_used', 'Unknown')
            status = data.get('status', 'Unknown')
            response_time = data.get('response_time_ms', 'Unknown')
            tokens = data.get('total_tokens', 'Unknown')
            
            print(f"{i}. 📄 Document ID: {log.id}")
            print(f"   🕐 Timestamp: {timestamp}")
            print(f"   🆔 Request ID: {request_id}")
            print(f"   🤖 Model: {model_req} → {model_used}")
            print(f"   ✅ Status: {status}")
            print(f"   ⏱️  Response Time: {response_time}ms")
            print(f"   🎯 Tokens: {tokens}")
            print()
        
        print("=" * 80)
        print("🎉 Firebase logging is working correctly!")
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking Firebase logs: {e}")
        return False

def main():
    print("🔥 Firebase Proxy Logs Checker")
    print("=" * 50)
    
    success = check_proxy_logs()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ SUCCESS: Firebase logging is working!")
        print("💡 All proxy requests are being logged to Cloud Firestore.")
    else:
        print("❌ ISSUE: No logs found in Firebase.")
        print("💡 Check if the server restarted properly with new environment variables.")
        print("💡 Make sure Firestore security rules allow writes.")
    print("=" * 50)

if __name__ == "__main__":
    main() 