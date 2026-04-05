# ARIA Makefile
# Run "make help" to see all available commands.

PYTHON = .venv/bin/python
PYTEST = .venv/bin/pytest
UVICORN = .venv/bin/uvicorn

.PHONY: help setup data run mcp test docker clean

help:
	@echo "ARIA - Automated Root-cause Intelligence for Analytical Laboratories"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup    Install all Python dependencies"
	@echo "  make data     Generate synthetic QC data + download MIMIC-IV demo"
	@echo "  make run      Start the web dashboard on http://localhost:8000"
	@echo "  make mcp      Start the MCP server"
	@echo "  make test     Run all tests"
	@echo "  make docker   Build and run with Docker Compose"
	@echo "  make clean    Remove generated data and cache files"

setup:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

data:
	$(PYTHON) data/synthetic/generate.py

run:
	$(UVICORN) src.api.main:app --host 0.0.0.0 --port 8000 --reload

mcp:
	$(PYTHON) src/mcp/server.py

test:
	$(PYTEST) tests/ -v --tb=short

docker:
	docker-compose up --build

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
