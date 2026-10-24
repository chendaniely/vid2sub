.PHONY: setup test test-utc lint leaks check hooks live readme help

setup: ## Install the dev environment
	uv sync --group dev

test: ## Run the test suite
	uv run pytest

test-utc: ## Run the test suite under TZ=UTC, as on CI's Ubuntu runners
	TZ=UTC uv run pytest

lint: ## Lint with ruff
	uv run ruff check src tests

leaks: ## Scan the whole git history for secrets with gitleaks
	gitleaks git --redact --no-banner .

# CI sets VID2SUB_REQUIRE_FFMPEG=1, so check does too: a media test fails instead of skipping.
check: export VID2SUB_REQUIRE_FFMPEG = 1
check: test test-utc lint leaks ## Everything CI checks: the suite, again under UTC, lint, leaks

hooks: ## Install the git hooks (none are built yet)
	@echo "no git hooks are installed yet: plan-driven-development has not built them"

live: ## The opt-in live tests against real models (tests/README.md)
	uv run pytest -m live

readme: ## Refresh the README's model table from the catalog
	uv run python -c "import re, pathlib; from vid2sub.catalog import readme_table; p = pathlib.Path('README.md'); t = p.read_text(encoding='utf-8'); p.write_text(re.sub(r'(<!-- models:start -->\n).*?(<!-- models:end -->)', lambda m: m.group(1) + readme_table() + m.group(2), t, flags=re.S), encoding='utf-8')"

help: ## List the targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-9s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
