.PHONY: help install install-dev dev-server test test-unit test-integration test-performance lint format type-check clean

help:
	@echo "Available commands:"
	@echo "  install         Install production dependencies"
	@echo "  install-dev     Install development dependencies"
	@echo "  dev-server      Start development server"
	@echo "  test            Run all tests"
	@echo "  test-unit       Run unit tests"
	@echo "  test-integration Run integration tests"  
	@echo "  test-performance Run performance tests"
	@echo "  lint            Run code linting"
	@echo "  format          Format code with black"
	@echo "  type-check      Run type checking with mypy"
	@echo "  clean           Clean build artifacts"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt
	pre-commit install

dev-server:
	uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-performance:
	pytest tests/performance/ -v

lint:
	flake8 src/
	black --check src/

format:
	black src/

type-check:
	mypy src/

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/