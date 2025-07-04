.PHONY: install run dev prod prod-simple test test-firebase test-advanced test-retry test-all clean help venv setup-firebase

# Virtual environment settings
VENV_DIR = .venv
PYTHON = $(VENV_DIR)/bin/python
PIP = $(VENV_DIR)/bin/pip
UVICORN = $(VENV_DIR)/bin/uvicorn

# Default target
help:
	@echo "Available commands:"
	@echo "  venv           Create virtual environment"
	@echo "  install        Install dependencies (creates venv if needed)"
	@echo "  setup-firebase Setup Firebase dependencies and create config template"
	@echo "  run            Run the application"
	@echo "  dev            Run the application in development mode with auto-reload"
	@echo "  prod           Run the application in production mode (4 workers)"
	@echo "  prod-simple    Run the application in production mode (single worker)"
	@echo "  test           Test the API endpoints"
	@echo "  test-firebase  Test Firebase logging functionality"
	@echo "  test-advanced  Run advanced function calling tests"
	@echo "  test-retry     Test structured output retry logic"
	@echo "  test-all       Run comprehensive test suite"
	@echo "  clean          Clean cache files and virtual environment"
	@echo "  help           Show this help message"
	@echo ""
	@echo "Setup:"
	@echo "  1. Create .env.local file with: UPSTAGE_API_KEY=your_key_here"
	@echo "  2. Run 'make install' to create venv and install dependencies"
	@echo "  3. Run 'make setup-firebase' to setup Firebase logging (optional)"
	@echo "  4. Run 'make dev' for development or 'make prod' for production"
	@echo ""
	@echo "Server modes:"
	@echo "  dev         - Development server with auto-reload (slower, for testing)"
	@echo "  prod        - Production server with 4 workers (fastest, best for load)"
	@echo "  prod-simple - Production server with 1 worker (reliable, good for testing)"
	@echo ""
	@echo "To activate virtual environment manually:"
	@echo "  source $(VENV_DIR)/bin/activate"

# Create virtual environment
venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv $(VENV_DIR); \
		echo "Virtual environment created in $(VENV_DIR)/"; \
	else \
		echo "Virtual environment already exists in $(VENV_DIR)/"; \
	fi

# Install dependencies
install: venv
	@echo "Installing dependencies in virtual environment..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Dependencies installed successfully!"

# Setup Firebase dependencies and config
setup-firebase: install
	@echo "Setting up Firebase logging..."
	@if [ ! -f ".env.local" ]; then \
		echo "Creating .env.local template..."; \
		echo "UPSTAGE_API_KEY=your_upstage_api_key_here" > .env.local; \
		echo "DEFAULT_MODEL_NAME=solar-pro2-preview" >> .env.local; \
		echo "FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json" >> .env.local; \
		echo "# Optional: Alternative Firebase config" >> .env.local; \
		echo "# GOOGLE_APPLICATION_CREDENTIALS=./firebase-service-account.json" >> .env.local; \
	else \
		echo ".env.local already exists, checking Firebase config..."; \
		if ! grep -q "FIREBASE_SERVICE_ACCOUNT_PATH" .env.local; then \
			echo "" >> .env.local; \
			echo "# Firebase Configuration" >> .env.local; \
			echo "FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json" >> .env.local; \
		fi; \
	fi
	@echo "Firebase setup completed!"
	@echo "Next steps:"
	@echo "1. Copy firebase-service-account.json.template to firebase-service-account.json"
	@echo "2. Update firebase-service-account.json with your Firebase credentials"
	@echo "3. Make sure your .env.local has the correct UPSTAGE_API_KEY"

# Run the application
run: install
	$(UVICORN) main:app --host 0.0.0.0 --port 8000

# Run in development mode with auto-reload
dev: install
	$(UVICORN) main:app --host 0.0.0.0 --port 8000 --reload

# Run in production mode (optimized)
prod: install
	@echo "Starting production server with 4 workers..."
	$(UVICORN) main:app --host 0.0.0.0 --port 8000 --workers 4 --loop uvloop --http httptools --log-level info

# Run in production mode (single worker, most reliable)
prod-simple: install
	@echo "Starting production server (single worker)..."
	$(UVICORN) main:app --host 0.0.0.0 --port 8000 --loop uvloop --http httptools --log-level info

# Test the API endpoints
test:
	@echo "Testing the Solar Proxy API..."
	@echo "Testing root endpoint:"
	curl -s http://localhost:8000/ | python -m json.tool
	@echo "\nTesting health check:"
	curl -s http://localhost:8000/health | python -m json.tool
	@echo "\nTesting models endpoint:"
	curl -s http://localhost:8000/v1/models | python -m json.tool
	@echo "\nTesting basic chat completion:"
	curl -s -X POST http://localhost:8000/v1/chat/completions \
		-H "Content-Type: application/json" \
		-d '{"model":"gpt-4","messages":[{"role":"user","content":"Hello, this is a test"}],"max_tokens":50}' \
		| python -m json.tool

# Test Firebase logging functionality
test-firebase: install
	@echo "Testing Firebase logging functionality..."
	$(PYTHON) test_firebase_logging.py

# Run advanced function calling tests
test-advanced: install
	@echo "Running advanced function calling tests..."
	$(PYTHON) test_advanced_function_calling.py

# Test structured output retry logic
test-retry: install
	@echo "Testing structured output retry logic..."
	$(PYTHON) test_retry_logic.py

# Run comprehensive test suite
test-all: install
	@echo "Running comprehensive test suite..."
	@echo "1. Testing basic API endpoints..."
	@make test
	@echo "\n2. Testing Firebase logging..."
	@make test-firebase
	@echo "\n3. Testing advanced function calling..."
	@make test-advanced  
	@echo "\n4. Testing structured output retry logic..."
	@make test-retry
	@echo "\n✅ All tests completed!"

# Clean cache files
clean:
	@echo "Cleaning cache files and virtual environment..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf $(VENV_DIR)
	@echo "Cleanup completed!" 