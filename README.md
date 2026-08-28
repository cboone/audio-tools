# audio-tools

Command-line tools for measuring what a digital audio signal path does to a signal.

Each tool is self-contained and lives in its own directory under `tools/`, with its own README covering the problem it solves, how to run it, and what its output means.

## Tools

| Tool                                            | Question it answers                                                                     |
| ----------------------------------------------- | --------------------------------------------------------------------------------------- |
| [`sampler-nulltest`](./tools/sampler-nulltest/) | Does a sampler pass a sample through unaltered, and if not, exactly what did it change? |

## Installation

There is nothing to install beyond [`uv`](https://docs.astral.sh/uv/).

Every tool is a standalone script carrying [PEP 723](https://peps.python.org/pep-0723/) inline dependency metadata, so `uv` builds the environment on first run:

```bash
uv run tools/sampler-nulltest/nulltest.py source.wav bounced.wav
```

The scripts are executable and use a `uv run --script` shebang, so running them directly works too:

```bash
./tools/sampler-nulltest/nulltest.py source.wav bounced.wav
```

System `python3` will not work: the dependencies are resolved per-script by `uv`, not installed globally.

## Development

```bash
make lint        # ruff check
make fmt         # ruff format --check
make text-lint   # markdownlint, Prettier and cspell
make test-scrut  # scrut CLI snapshot tests
make help        # list all targets
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full development setup.

## License

[MIT License](./LICENSE). TL;DR: Do whatever you want with this software, just keep the copyright notice included. The authors aren't liable if something goes wrong.
