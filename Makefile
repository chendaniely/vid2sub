.PHONY: setup test lint live readme

setup:
	uv sync --group dev

test:
	uv run pytest

lint:
	uv run ruff check src tests

live:
	uv run pytest -m live

readme:
	uv run python -c "import re, pathlib; from vid2sub.catalog import readme_table; p = pathlib.Path('README.md'); t = p.read_text(encoding='utf-8'); p.write_text(re.sub(r'(<!-- models:start -->\n).*?(<!-- models:end -->)', lambda m: m.group(1) + readme_table() + m.group(2), t, flags=re.S), encoding='utf-8')"
