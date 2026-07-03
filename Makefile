PYTHON ?= python
VENV ?= .venv
PY := $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,$(PYTHON))
PY_ABS := $(if $(wildcard $(VENV)/bin/python),$(abspath $(VENV)/bin/python),$(PYTHON))
PIP := $(VENV)/bin/pip

.PHONY: setup backend-dev frontend-dev validate-catalog test clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -e . pytest httpx2
	cd frontend && npm ci

backend-dev:
	PYTHONPATH=. $(PY) -m cloud_governance.cli web start --host 127.0.0.1 --port 8097

frontend-dev:
	cd frontend && npm run dev

validate-catalog:
	cd catalog && $(PY_ABS) scripts/validate.py by-service

test: validate-catalog
	$(PY) -m pytest
	$(PY) -m compileall cloud_governance
	cd frontend && npm run build

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache build dist *.egg-info frontend/node_modules frontend/dist frontend/.vite frontend/tsconfig.tsbuildinfo
