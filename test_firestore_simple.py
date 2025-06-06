#!/usr/bin/env python3
"""
Simple Firestore test to verify Firebase configuration
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

def test_environment_variables():
    """Test if all required Firebase environment variables are set"""
    print("🔧 Testing Firebase Environment Variables...")
    
    required_vars = [
        'FIREBASE_PROJECT_ID',
        'FIREBASE_PRIVATE_KEY_ID', 
        'FIREBASE_PRIVATE_KEY',
        'FIREBASE_CLIENT_EMAIL',
        'FIREBASE_CLIENT_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            # Show partial value for verification (don't show full private key)
            if 'PRIVATE_KEY' in var and len(value) > 50:
                display_value = f"{value[:20]}...{value[-20:]}"
            elif len(value) > 50:
                display_value = f"{value[:30]}..."
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
    
    if missing_vars:
        print(f"  ❌ Missing variables: {', '.join(missing_vars)}")
        return False
    
    print("  ✅ All environment variables are set!")
    return True

def test_firebase_initialization():
    """Test Firebase initialization"""
    print("\n🔥 Testing Firebase Initialization...")
    
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # Check if already initialized
        if firebase_admin._apps:
            print("  ℹ️  Firebase already initialized, deleting existing app...")
            firebase_admin.delete_app(firebase_admin.get_app())
        
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
        
        print("  ✅ Firebase initialized successfully!")
        return True
        
    except Exception as e:
        print(f"  ❌ Firebase initialization failed: {e}")
        return False

def test_add_retrieve_delete():
    """Simple test: Add data, retrieve it, then delete it"""
    print("\n📝 Testing Add/Retrieve/Delete Operations...")
    
    try:
        from firebase_admin import firestore
        
        # Get Firestore client
        db = firestore.client()
        
        # Test data
        collection_name = "test_crud"
        doc_id = f"test_doc_{int(datetime.now().timestamp())}"
        test_data = {
            'name': 'Solar Proxy Test',
            'timestamp': datetime.now(),
            'message': 'Hello from Firebase!',
            'number': 42,
            'active': True
        }
        
        print(f"  📄 Document ID: {doc_id}")
        print(f"  📊 Test Data: {test_data}")
        
        # STEP 1: ADD DATA
        print("\n  1️⃣ ADDING data to Firestore...")
        doc_ref = db.collection(collection_name).document(doc_id)
        doc_ref.set(test_data)
        print("     ✅ Data added successfully!")
        
        # STEP 2: RETRIEVE DATA
        print("\n  2️⃣ RETRIEVING data from Firestore...")
        doc = doc_ref.get()
        if doc.exists:
            retrieved_data = doc.to_dict()
            print(f"     ✅ Data retrieved successfully!")
            print(f"     📋 Retrieved: {retrieved_data['name']} - {retrieved_data['message']}")
            
            # Verify data matches
            if retrieved_data['name'] == test_data['name'] and retrieved_data['message'] == test_data['message']:
                print("     ✅ Data integrity verified!")
            else:
                print("     ❌ Data mismatch!")
                return False
        else:
            print("     ❌ Document not found!")
            return False
        
        # STEP 3: DELETE DATA
        print("\n  3️⃣ DELETING data from Firestore...")
        doc_ref.delete()
        print("     ✅ Data deleted successfully!")
        
        # Verify deletion
        print("\n  🔍 Verifying deletion...")
        doc_check = doc_ref.get()
        if not doc_check.exists:
            print("     ✅ Deletion verified - document no longer exists!")
        else:
            print("     ❌ Deletion failed - document still exists!")
            return False
        
        print("\n  🎉 All CRUD operations completed successfully!")
        return True
        
    except Exception as e:
        print(f"  ❌ CRUD operations failed: {e}")
        return False

def test_firestore_connection():
    """Test Firestore database connection"""
    print("\n📊 Testing Firestore Connection...")
    
    try:
        from firebase_admin import firestore
        
        # Get Firestore client
        db = firestore.client()
        
        # Test collection name
        test_collection = f"test_logs_{datetime.now().strftime('%Y_%m')}"
        test_doc_id = f"test_{int(datetime.now().timestamp())}"
        
        print(f"  📝 Using collection: {test_collection}")
        print(f"  📄 Using document ID: {test_doc_id}")
        
        # Test write
        print("  ✍️  Testing write operation...")
        test_data = {
            'timestamp': datetime.now(),
            'test_type': 'firestore_connectivity_test',
            'message': 'This is a test from the Solar proxy Firebase setup',
            'status': 'success'
        }
        
        doc_ref = db.collection(test_collection).document(test_doc_id)
        doc_ref.set(test_data)
        print("  ✅ Write operation successful!")
        
        # Test read
        print("  📖 Testing read operation...")
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            print(f"  ✅ Read operation successful! Data: {data['message']}")
        else:
            print("  ❌ Document not found after write!")
            return False
        
        # Test delete (cleanup)
        print("  🗑️  Cleaning up test document...")
        doc_ref.delete()
        print("  ✅ Cleanup successful!")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Firestore operation failed: {e}")
        return False

def test_proxy_logs_collection():
    """Test writing to the actual proxy logs collection format"""
    print("\n📋 Testing Proxy Logs Collection Format...")
    
    try:
        from firebase_admin import firestore
        
        db = firestore.client()
        
        # Use the same format as the proxy
        collection_name = f"proxy_logs_{datetime.now().strftime('%Y_%m')}"
        
        # Create sample proxy log data
        proxy_log_data = {
            'timestamp': datetime.now(),
            'request_id': 'test-request-123',
            'model_requested': 'gpt-4',
            'model_used': 'solar-pro2-preview',
            'request_type': 'chat_completion',
            'has_functions': False,
            'has_streaming': False,
            'response_time_ms': 150,
            'input_tokens': 25,
            'output_tokens': 15,
            'total_tokens': 40,
            'status': 'success',
            'test_log': True
        }
        
        print(f"  📝 Writing to collection: {collection_name}")
        doc_ref = db.collection(collection_name).add(proxy_log_data)
        doc_id = doc_ref[1].id
        print(f"  ✅ Proxy log written successfully! Document ID: {doc_id}")
        
        # Clean up
        db.collection(collection_name).document(doc_id).delete()
        print("  🗑️  Test log cleaned up")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Proxy logs test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Firebase/Firestore Configuration Test")
    print("=" * 50)
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Firebase Initialization", test_firebase_initialization),
        ("Add/Retrieve/Delete (CRUD)", test_add_retrieve_delete),
        ("Firestore Connection", test_firestore_connection),
        ("Proxy Logs Format", test_proxy_logs_collection)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  💥 Unexpected error in {test_name}: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Firebase logging is ready to go!")
        print("💡 Don't forget to update your Firestore security rules if you haven't already.")
    else:
        print("⚠️  SOME TESTS FAILED. Please check the errors above.")
        print("\n📋 Common issues:")
        print("  1. Missing or incorrect environment variables in .env.local")
        print("  2. Firestore security rules blocking writes")
        print("  3. Invalid Firebase service account credentials")
        print("  4. Network connectivity issues")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 