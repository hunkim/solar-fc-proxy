#!/usr/bin/env python3
"""
Test Firebase initialization in the same context as the server
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables exactly like main.py
load_dotenv('.env.local')

print("🔧 Testing Firebase in Server Context...")
print(f"Working directory: {os.getcwd()}")
print()

# Test environment variables
firebase_vars = {
    'FIREBASE_PROJECT_ID': os.getenv('FIREBASE_PROJECT_ID'),
    'FIREBASE_CLIENT_EMAIL': os.getenv('FIREBASE_CLIENT_EMAIL'), 
    'FIREBASE_PRIVATE_KEY_ID': os.getenv('FIREBASE_PRIVATE_KEY_ID'),
    'FIREBASE_CLIENT_ID': os.getenv('FIREBASE_CLIENT_ID'),
    'FIREBASE_PRIVATE_KEY': bool(os.getenv('FIREBASE_PRIVATE_KEY'))  # Just check if exists
}

print("📋 Environment Variables:")
for key, value in firebase_vars.items():
    status = "✅" if value else "❌"
    print(f"  {status} {key}: {value}")
print()

# Test importing firebase_logger
try:
    print("📦 Testing firebase_logger import...")
    from firebase_logger import firebase_logger
    print("  ✅ Firebase logger imported successfully")
    
    # Test if firebase_logger is initialized
    print("🔥 Testing Firebase logger status...")
    if hasattr(firebase_logger, 'db') and firebase_logger.db is not None:
        print("  ✅ Firebase logger is properly initialized")
        
        # Test writing a log
        print("📝 Testing Firebase write...")
        test_data = {
            "test": True,
            "message": "Server context test",
            "timestamp": "2025-06-07T21:30:00"
        }
        
        asyncio_import = False
        try:
            import asyncio
            asyncio_import = True
        except ImportError:
            pass
            
        if asyncio_import:
            import asyncio
            asyncio.run(firebase_logger.log_request(test_data))
            print("  ✅ Firebase write test completed")
        else:
            print("  ⚠️  asyncio not available for write test")
            
    else:
        print("  ❌ Firebase logger is NOT initialized")
        print(f"  💡 firebase_logger.db: {getattr(firebase_logger, 'db', 'NOT_SET')}")
        
        # Try to initialize manually
        print("🔧 Attempting manual initialization...")
        try:
            firebase_logger._init_firebase()
            print("  ✅ Manual initialization successful")
        except Exception as e:
            print(f"  ❌ Manual initialization failed: {e}")
            
except Exception as e:
    print(f"  ❌ Failed to import firebase_logger: {e}")
    import traceback
    traceback.print_exc()

print("\n🎯 Summary:")
print("  This test simulates the exact same environment as the server")
print("  If Firebase works here but not in the server, there's a context issue")
print("  If it fails here too, there's a configuration problem") 