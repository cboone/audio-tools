# GitHub Copilot Instructions for audio-tools

For full project conventions, see AGENTS.md in the repository root.

## PR Review

- **Done plans are historical records**: Files in `docs/plans/done/` are completed plan documents preserved for reference. They may not match the final implementation. Do not flag discrepancies between done plan content and the actual codebase.
- **Tools are standalone scripts, not a package**: Every tool under `tools/` is a single executable script with a `uv run --script` shebang and a PEP 723 inline dependency block. Do not suggest adding a `pyproject.toml`, consolidating dependencies, or converting the repository into an installable package.
- **`N806` is disabled on purpose**: Uppercase variables such as `A`, `B`, `H`, `Sa`, `Sr` and `T` are spectral-domain quantities matching the notation in the tool READMEs (`H = B/A`). Do not suggest renaming them to lowercase.
- **Bare `except Exception` with `# noqa: BLE001` is intentional**: Those handlers catch backend import failures that do not arrive as `ImportError`. See `tools/sampler-nulltest/AGENTS.md`. Do not suggest narrowing them.
