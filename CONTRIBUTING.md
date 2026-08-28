# Contributing to audio-tools

Thank you for your interest in contributing to audio-tools.

Please note that this project has a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold it.

## Reporting Issues

- **Bug reports and feature requests:** Use the [issue tracker](https://github.com/cboone/audio-tools/issues/new/choose)
- **Security vulnerabilities:** See [SECURITY.md](.github/SECURITY.md)

## Development Setup

### Requirements

- [`uv`](https://docs.astral.sh/uv/) (the only hard requirement to _run_ the tools)
- [`scrut`](https://github.com/facebookincubator/scrut) to run the CLI tests
- Node and `npm` to run the text checks, which come from this repo's `package-lock.json`

There is no Python dependency install step. Every tool is a standalone script carrying [PEP 723](https://peps.python.org/pep-0723/) inline metadata, so `uv` resolves each script's dependencies on first run.

The `package.json` at the root does not make this a JavaScript project. It exists only to pin `markdownlint-cli2`, `prettier` and `cspell`, so that `make text-lint` and CI run byte-identical versions. `make node-tools` installs them, and `make text-lint` and `make text-fix` depend on it, so it runs on its own when needed. The Python and scrut targets do not use it.

### Getting Started

```bash
# Clone the repository
git clone https://github.com/cboone/audio-tools.git
cd audio-tools

# Run a tool. Nothing to install first.
uv run tools/sampler-nulltest/nulltest.py source.wav bounced.wav

# Run the CLI tests
make test-scrut

# Run the linters. text-lint installs the pinned Node tools on first use.
make lint
make text-lint
```

`make help` lists every target.

## Adding a Tool

Each tool lives in its own directory under `tools/` and owns:

- A `README.md` covering the problem it solves, how to run it, and how to read its output.
- An `AGENTS.md` with a `CLAUDE.md` symlink beside it, recording anything a future contributor or agent would otherwise get wrong.
- One or more executable scripts with a `#!/usr/bin/env -S uv run --script` shebang and a PEP 723 dependency block.

Do not add a `pyproject.toml` or otherwise convert the repository into an installable package. The self-contained-script layout is deliberate; see [AGENTS.md](AGENTS.md) for why.

## Code Style

- Run `make lint` and `make fmt` before committing. `make fmt-fix` applies both.
- Run `make text-lint` for Markdown, formatting and spelling.

Python style is enforced by [Ruff](https://docs.astral.sh/ruff/), configured in `ruff.toml`. Two rule choices there are deliberate and documented in that file: `N806` is disabled so spectral-domain variables can keep the notation used in the tool READMEs, and `BLE` is selected so the existing `# noqa: BLE001` directives stay meaningful.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```text
<type>: <description>
```

**Types:**

- `feat`: new feature
- `fix`: bug fix
- `docs`: documentation changes
- `refactor`: code refactoring (no functional change)
- `test`: adding or updating tests
- `build`: build system or dependency changes
- `ci`: CI configuration changes
- `chore`: maintenance tasks
- `style`: formatting only, no functional change

**Examples:**

```text
feat: add a test signal generator
fix: measure delay on the strongest channel pair, not the channel mean
docs: record the Logic version the findings were measured against
chore: import sampler null test into tools/
```

## Pull Request Process

1. Fork the repository
1. Create a feature branch
1. Make your changes
1. Ensure tests pass: `make test-scrut`
1. Ensure linting passes: `make lint` and `make text-lint`
1. Submit a pull request

### Branch Naming

Use descriptive branch names with a type prefix:

- `feature/*`: new features
- `fix/*`: bug fixes
- `docs/*`: documentation changes
- `refactor/*`: code refactoring
- `test/*`: test additions or fixes
- `chore/*`: maintenance tasks
