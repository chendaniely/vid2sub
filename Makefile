.PHONY: setup test lint live

setup:
	uv sync --group dev

test:
	uv run pytest

lint:
	uv run ruff check src tests

live:
	uv run pytest -m live
