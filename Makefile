PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
RUN := $(VENV)/bin/python
STREAMLIT := $(VENV)/bin/streamlit

.PHONY: help setup run smoke clean

help:
	@echo "Targets:"
	@echo "  setup  - Create virtualenv and install requirements"
	@echo "  run    - Run Streamlit app locally"
	@echo "  smoke  - Run non-UI smoke checks"
	@echo "  clean  - Remove virtualenv and python caches"

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

run:
	$(STREAMLIT) run app.py

smoke:
	$(RUN) scripts/smoke_test.py

clean:
	rm -rf $(VENV) .venv_scratch __pycache__ src/__pycache__
