# audio-tools
#
# The tools here are standalone PEP 723 scripts, so there is no build step and
# no dependency install: `uv run` resolves each script's dependencies from its
# own inline metadata.

RUFF_VERSION := 0.16.5

NULLTEST_BIN := $(CURDIR)/tools/sampler-nulltest/nulltest.py
MAKETEST_BIN := $(CURDIR)/tools/sampler-nulltest/maketest.py
SCRUT_TESTS := tests/scrut/

.PHONY: node-tools lint fmt fmt-fix text-lint text-fix test-scrut test-scrut-update test-all help

node-tools: node_modules ## Install the pinned text linters

node_modules: package-lock.json
	npm ci --ignore-scripts --include=dev --no-audit --no-fund
	@touch node_modules

lint: ## Run ruff lint
	uvx ruff@$(RUFF_VERSION) check .

fmt: ## Check Python formatting
	uvx ruff@$(RUFF_VERSION) format --check .

fmt-fix: ## Apply ruff formatting and safe lint fixes
	uvx ruff@$(RUFF_VERSION) format .
	uvx ruff@$(RUFF_VERSION) check --fix .

# The text linters run from node_modules rather than whatever is on PATH, so
# these match CI byte for byte. CI installs the same package-lock.json.
text-lint: node-tools ## Run markdownlint, Prettier and cspell
	npm run --silent lint:md
	npm run --silent format:check
	npm run --silent spell

text-fix: node-tools ## Apply Prettier formatting and markdownlint fixes
	npm run --silent format:write
	npm run --silent lint:md:fix

test-scrut: ## Run scrut CLI tests
	@if ! command -v scrut >/dev/null 2>&1; then \
		echo "scrut not installed. Install from https://github.com/facebookincubator/scrut"; \
		exit 1; \
	fi
	NULLTEST_BIN="$(NULLTEST_BIN)" MAKETEST_BIN="$(MAKETEST_BIN)" \
		scrut test $(SCRUT_TESTS)

test-scrut-update: ## Update scrut test expectations
	NULLTEST_BIN="$(NULLTEST_BIN)" MAKETEST_BIN="$(MAKETEST_BIN)" \
		scrut update --replace --assume-yes $(SCRUT_TESTS)

test-all: lint fmt text-lint test-scrut ## Run every check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'
