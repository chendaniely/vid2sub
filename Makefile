.PHONY: setup build test test-utc test-js e2e lint leaks check hooks live readme brand skills help

FRONTEND := frontend
# Each recipe line runs in its own shell, so nvm is loaded per line when it is there, and switched
# to the Node in frontend/.nvmrc (as recordings' Makefile does). Without nvm (CI), whatever Node is
# on PATH runs, and frontend/scripts/check-node.mjs refuses one older than 22.
NVM := if [ -s "$$HOME/.nvm/nvm.sh" ]; then . "$$HOME/.nvm/nvm.sh" && nvm use --silent "$$(cat $(CURDIR)/$(FRONTEND)/.nvmrc)"; fi;

setup: ## Install the dev environment, the frontend's packages included
	uv sync --group dev
	cd $(FRONTEND) && $(NVM) npm ci

build: ## Build the frontend into src/vid2sub/web/www/ (vid2sub serve needs it)
	cd $(FRONTEND) && $(NVM) npm run build

test: ## Run the test suite
	uv run pytest

test-utc: ## Run the test suite under TZ=UTC, as on CI's Ubuntu runners
	TZ=UTC uv run pytest

test-js: ## Typecheck the frontend and run its Vitest tests
	cd $(FRONTEND) && $(NVM) npm run typecheck && VID2SUB_REQUIRE_SHINYREACT=1 npm test

e2e: build ## The browser tests against vid2sub serve (installs Playwright's Chromium first)
	uv run playwright install chromium
	uv run pytest -m e2e

lint: ## Lint with ruff
	uv run ruff check src tests

leaks: ## Scan the whole git history for secrets with gitleaks
	gitleaks git --redact --no-banner .

# CI sets VID2SUB_REQUIRE_FFMPEG=1, so check does too: a media test fails instead of skipping.
check: export VID2SUB_REQUIRE_FFMPEG = 1
check: test test-utc test-js lint leaks ## Everything CI checks: the suite, again under UTC, the frontend's tests, lint, leaks

hooks: ## Install the git hooks (none are built yet)
	@echo "no git hooks are installed yet: plan-driven-development has not built them"

live: ## The opt-in live tests against real models (tests/README.md)
	uv run pytest -m live

readme: ## Refresh the README's model table from the catalog
	uv run python -c "import re, pathlib; from vid2sub.catalog import readme_table; p = pathlib.Path('README.md'); t = p.read_text(encoding='utf-8'); p.write_text(re.sub(r'(<!-- models:start -->\n).*?(<!-- models:end -->)', lambda m: m.group(1) + readme_table() + m.group(2), t, flags=re.S), encoding='utf-8')"

brand: ## Regenerate frontend/src/theme.css from _brand.yml
	uv run scripts/brand_css.py

skills: ## Install the shinyreact and shadcn agent skills (local tooling, never committed)
	uvx library-skills install --claude --yes --skill shinyreact-build-app --skill shinyreact-convert-app
	$(NVM) npx skills add shadcn/ui --skill shadcn --agent claude-code --yes

help: ## List the targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z0-9-]+:.*## / {printf "  %-9s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
