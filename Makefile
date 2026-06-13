.PHONY: install install-dev setup test lint format

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	playwright install chromium

setup: install-dev

test:
	pytest -q

lint:
	ruff check .

format:
	ruff format .
