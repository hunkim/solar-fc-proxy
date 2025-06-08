"""
Firebase Logger for Solar Proxy

Asynchronously logs proxy requests and responses to Firebase Firestore
for analytics and monitoring purposes with robust error handling.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, firestore
from concurrent.futures import ThreadPoolExecutor
import uuid

logger = logging.getLogger(__name__)

class FirebaseLogger:
    def __init__(self):
        self.db = None
        self.executor = ThreadPoolExecutor(max_workers=2)  # Dedicated thread pool for Firebase
        self.initialized = False
        self.last_error_time = 0
        self.error_count = 0
        self.max_errors = 5  # Max consecutive errors before disabling
        self.error_window = 300  # 5 minutes error window
        self.connection_timeout = 30  # 30 seconds timeout
        self.retry_attempts = 3
        
        # Always attempt to initialize Firebase
        self._init_firebase()

    def _init_firebase(self):
        """Initialize Firebase Admin SDK using environment variables"""
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                # Try to use environment variables for service account
                project_id = os.getenv('FIREBASE_PROJECT_ID')
                private_key = os.getenv('FIREBASE_PRIVATE_KEY')
                client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
                
                if project_id and private_key and client_email:
                    # Create service account dict from environment variables
                    service_account_info = {
                        "type": "service_account",
                        "project_id": project_id,
                        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
                        "private_key": private_key.replace('\\n', '\n'),  # Handle escaped newlines
                        "client_email": client_email,
                        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                        "auth_uri": os.getenv('FIREBASE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
                        "token_uri": os.getenv('FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
                        "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_X509_CERT_URL', 'https://www.googleapis.com/oauth2/v1/certs'),
                        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL')
                    }
                    
                    cred = credentials.Certificate(service_account_info)
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase initialized with environment variables")
                else:
                    # Fallback to application default credentials
                    firebase_admin.initialize_app()
                    logger.info("Firebase initialized with default credentials")

            self.db = firestore.client()
            self.initialized = True
            logger.info("Firebase Firestore client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            self.initialized = False

    def _should_log(self) -> bool:
        """Check if we should attempt logging based on error history"""
        if not self.initialized:
            return False
            
        current_time = time.time()
        
        # Reset error count if enough time has passed
        if current_time - self.last_error_time > self.error_window:
            self.error_count = 0
            
        # Don't log if we've had too many consecutive errors
        if self.error_count >= self.max_errors:
            logger.debug(f"Firebase logging temporarily disabled due to {self.error_count} consecutive errors")
            return False
            
        return True

    def _record_error(self):
        """Record an error for rate limiting"""
        self.error_count += 1
        self.last_error_time = time.time()

    def _record_success(self):
        """Record a successful operation"""
        self.error_count = max(0, self.error_count - 1)  # Gradually reduce error count on success

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from payload"""
        sanitized = payload.copy()
        
        # Remove API keys and sensitive headers
        sensitive_keys = [
            'authorization', 'api_key', 'apikey', 'api-key', 
            'x-api-key', 'bearer', 'token', 'secret'
        ]
        
        # Remove sensitive keys from top level
        for key in list(sanitized.keys()):
            if key.lower() in sensitive_keys:
                sanitized[key] = "[REDACTED]"
        
        # Remove sensitive headers if present
        if 'headers' in sanitized:
            for key in list(sanitized['headers'].keys()):
                if key.lower() in sensitive_keys:
                    sanitized['headers'][key] = "[REDACTED]"
        
        return sanitized

    def _prepare_log_entry(self, 
                          request_payload: Dict[str, Any],
                          response_data: Dict[str, Any],
                          metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare log entry for Firebase"""
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Sanitize payloads
        sanitized_request = self._sanitize_payload(request_payload)
        sanitized_response = self._sanitize_payload(response_data)
        
        log_entry = {
            'request_id': request_id,
            'timestamp': timestamp,
            'request': {
                'model': sanitized_request.get('model'),
                'messages': sanitized_request.get('messages', []),
                'tools': sanitized_request.get('tools'),
                'tool_choice': sanitized_request.get('tool_choice'),
                'stream': sanitized_request.get('stream', False),
                'max_tokens': sanitized_request.get('max_tokens'),
                'temperature': sanitized_request.get('temperature'),
                'reasoning_effort': sanitized_request.get('reasoning_effort'),
                'message_count': len(sanitized_request.get('messages', [])),
                'has_tools': bool(sanitized_request.get('tools')),
                'has_function_calls': bool(sanitized_response.get('choices', [{}])[0].get('message', {}).get('tool_calls')),
                '_upstream_content': sanitized_request.get('_upstream_content'),  # Include upstream content for transparency
                'response_format': sanitized_request.get('response_format'),  # Include structured output info
                'structured_output_requested': metadata.get('structured_output_requested', False)
            },
            'response': {
                'model': sanitized_response.get('model'),
                'choices': sanitized_response.get('choices', []),
                'usage': sanitized_response.get('usage', {}),
                'response_time_ms': metadata.get('response_time_ms'),
                'status_code': metadata.get('status_code', 200),
                'is_streaming': metadata.get('is_streaming', False),
                'function_calls_detected': metadata.get('function_calls_detected', 0),
                'structured_output_valid': metadata.get('structured_output_valid'),
                'schema_name': metadata.get('structured_output_schema_name'),
                'content_length': len(str(sanitized_response))
            },
            'metadata': {
                'proxy_version': metadata.get('proxy_version', '1.0.0'),
                'original_model': metadata.get('original_model'),
                'mapped_model': metadata.get('mapped_model'),
                'client_ip': metadata.get('client_ip'),
                'user_agent': metadata.get('user_agent'),
                'endpoint': metadata.get('endpoint', '/v1/chat/completions'),
                'error': metadata.get('error')
            }
        }
        
        return log_entry

    def _write_to_firebase_with_retry(self, log_entry: Dict[str, Any]):
        """Synchronous Firebase write operation with retry logic"""
        for attempt in range(self.retry_attempts):
            try:
                if not self.initialized or not self.db:
                    logger.warning("Firebase not initialized, skipping log")
                    return

                # Write to Firestore collection with timeout
                collection_name = f"proxy_logs_{datetime.now().strftime('%Y_%m_%d')}"  # Daily collections
                doc_ref = self.db.collection(collection_name).document(log_entry['request_id'])
                
                # Set document with timeout
                doc_ref.set(log_entry)
                
                logger.debug(f"Successfully logged request {log_entry['request_id']} to Firebase (attempt {attempt + 1})")
                self._record_success()
                return
                
            except Exception as e:
                logger.warning(f"Firebase write attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
                if attempt == self.retry_attempts - 1:
                    # Last attempt failed
                    logger.error(f"Failed to write to Firebase after {self.retry_attempts} attempts: {e}")
                    self._record_error()
                else:
                    # Wait before retry with exponential backoff
                    wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                    time.sleep(wait_time)

    async def log_request_response(self,
                                 request_payload: Dict[str, Any],
                                 response_data: Dict[str, Any],
                                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Asynchronously log request and response to Firebase
        
        Args:
            request_payload: The incoming request payload (sanitized)
            response_data: The response data
            metadata: Additional metadata (response time, client info, etc.)
        """
        if not self._should_log():
            return
            
        try:
            # Prepare metadata
            if metadata is None:
                metadata = {}
                
            # Prepare log entry
            log_entry = self._prepare_log_entry(request_payload, response_data, metadata)
            
            # Write to Firebase asynchronously using thread pool with timeout
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(self.executor, self._write_to_firebase_with_retry, log_entry),
                timeout=self.connection_timeout
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"Firebase logging timed out after {self.connection_timeout}s")
            self._record_error()
        except Exception as e:
            logger.error(f"Error in async Firebase logging: {e}")
            self._record_error()

    async def log_error(self,
                       request_payload: Dict[str, Any],
                       error_details: Dict[str, Any],
                       metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Log error cases to Firebase
        
        Args:
            request_payload: The incoming request payload
            error_details: Error information
            metadata: Additional metadata
        """
        if not self._should_log():
            return
            
        try:
            if metadata is None:
                metadata = {}
                
            metadata['error'] = error_details
            metadata['status_code'] = error_details.get('status_code', 500)
            
            # Create error response format
            error_response = {
                'error': error_details,
                'model': request_payload.get('model'),
                'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
            }
            
            await self.log_request_response(request_payload, error_response, metadata)
            
        except Exception as e:
            logger.error(f"Error logging Firebase error: {e}")

    def close(self):
        """Clean up resources"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)

# Global Firebase logger instance
firebase_logger = FirebaseLogger() 