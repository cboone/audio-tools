# audio-tools

## Overview

Command-line tools for measuring what a digital audio signal path does to a signal.

## Structure

```text
audio-tools/
├── tools/
│   └── sampler-nulltest/    # Is a bounce a bit-transparent pass-through of its source?
│       ├── AGENTS.md        # Tool-specific agent instructions (CLAUDE.md symlinks here)
│       ├── README.md        # Problem statement, procedure, method, limitations
│       ├── nulltest.py      # The analysis
│       ├── maketest.py      # Probe signal generator
│       └── probe/           # Committed 48 kHz probes, reproducible from maketest.py
├── tests/scrut/             # Scrut CLI snapshot tests
└── docs/plans/              # Plan documents: todo/ is active, done/ is historical
```

Each tool owns its own `README.md` and `AGENTS.md`. **Read the tool's own `AGENTS.md` before changing anything inside its directory.** Those files record which past defects were shipped and why, and several carry explicit instructions not to "simplify" specific code back into a form that was already found to be wrong.

## Tools are standalone scripts, not a package

Every tool is a single executable script with a `#!/usr/bin/env -S uv run --script` shebang and a [PEP 723](https://peps.python.org/pep-0723/) inline metadata block declaring its own dependencies.

This is deliberate. Do not convert the repository into an installable package, and do not add a `pyproject.toml`:

- `uv run tools/<tool>/<script>.py` works with nothing installed and nothing to sync.
- Each tool pins its own dependencies, so one tool's requirements cannot constrain another's.
- `requires-python` belongs in each script's PEP 723 block, which is where the runtime actually reads it.

Ruff is configured in `ruff.toml` for this reason: `pyproject.toml` would imply a package that does not exist.

System `python3` will not have the dependencies. `python3 nulltest.py` fails; `uv run nulltest.py` works.

## Development

```bash
make lint               # ruff check .
make fmt                # ruff format --check .
make test-scrut         # run scrut CLI snapshot tests
make test-scrut-update  # regenerate scrut snapshots after intentional changes
make test-all           # everything
```

Ruff configuration lives in `ruff.toml`. Two rule choices are intentional and should not be "cleaned up":

- **`N806` is disabled.** Spectral-domain variables (`A`, `B`, `H`, `Sa`, `Sr`, `T`) match the notation in the tool READMEs, where the transfer function is written `H = B/A`. Lowercasing them breaks the correspondence between the code and its documentation.
- **`BLE` is selected.** Selecting it is what makes the existing `# noqa: BLE001` directives meaningful. Those bare `except Exception` handlers are load-bearing; see `tools/sampler-nulltest/AGENTS.md` for the specific reason.

## Conventions

- Conventional Commits for commit messages and PR titles.
- All commits are GPG signed.
- Never `git commit --amend`; create a new commit instead.
- Prefer frequent small commits at each logical boundary.
