VENV = .venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip3
STREAMLIT = $(VENV)/bin/streamlit
UVICORN = $(VENV)/bin/uvicorn

include .env
export

# Need to use python 3.9 for aws lambda
$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

proxy: $(VENV)/bin/activate
	$(UVICORN) proxy:app --reload --port 9097

clean:
	rm -rf __pycache__
	rm -rf $(VENV)