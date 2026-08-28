# audio-tools
#
# The tools here are standalone PEP 723 scripts, so there is no build step and
# no dependency install: `uv run` resolves each script's dependencies from its
# own inline metadata.

RUFF_VERSION := 0.16.5

NULLTEST_BIN := $(CURDIR)/tools/sampler-nulltest/nulltest.py
MAKETEST_BIN := $(CURDIR)/tools/sampler-nulltest/maketest.py
SCRUT_TESTS := tests/scrut/

.PHONY: lint fmt fmt-fix text-lint test-scrut test-scrut-update test-all help

lint: ## Run ruff lint
	uvx ruff@$(RUFF_VERSION) check .

fmt: ## Check Python formatting
	uvx ruff@$(RUFF_VERSION) format --check .

fmt-fix: ## Apply ruff formatting and safe lint fixes
	uvx ruff@$(RUFF_VERSION) format .
	uvx ruff@$(RUFF_VERSION) check --fix .

text-lint: ## Run markdownlint, Prettier and cspell
	markdownlint-cli2 "**/*.md"
	prettier --check .
	cspell lint --no-progress .

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
