# Bootstrap the audio-tools repository

## Context

`cboone/audio-tools` is a public repository holding one working tool (`tools/sampler-nulltest`) and almost nothing else. It has a LICENSE, a full Python `.gitignore`, and a one-line README. There is no CI, no linter configuration, no secret scanning, no agent config at the root, no community files, and no test suite.

The tool inside it is not a rough draft. `nulltest.py` is 531 lines of signal-processing code with a documented method, a documented set of validation cases, and a `CLAUDE.md` that records which past defects were shipped and why. That work currently has nothing guarding it: any change to the analysis can silently regress a verdict, and the only thing standing between a regression and a wrong answer is whoever remembers to re-run the synthetic cases by hand.

The goal is to put the standard scaffolding underneath the repository so that the existing tool is protected and the next tool added under `tools/` inherits the same guarantees.

### What makes this repo unusual

The tools are standalone [PEP 723](https://peps.python.org/pep-0723/) scripts with `#!/usr/bin/env -S uv run --script` shebangs. There is no `pyproject.toml`, no `setup.py`, and no `requirements.txt`, so **every scaffolding skill's Python auto-detection will fail on this repo** and fall through to "no language detected" or Shell. Each skill must be told the language explicitly.

This is not a packaging gap to be fixed. Self-contained scripts with inline dependency metadata are the point: `uv run nulltest.py` works with nothing installed. The scaffolding must adapt to that rather than converting the repo into a package.

## Decisions already made

| Decision            | Choice                                                                                              |
| ------------------- | --------------------------------------------------------------------------------------------------- |
| Python formatting   | Adopt `ruff format` fully, with a one-time `style:` reformat commit up front                        |
| Test scope          | Starter scrut tests only (`--help` snapshots); the 18 documented validation cases become an issue   |
| Optional extras     | All four: secret scanning, community files, cspell, expanded root README                            |
| Ruff config file    | `ruff.toml` at the root, not `pyproject.toml`, because this repo is not and will not be a package   |
| Installers          | Not applicable: `uv run --script` tools produce no distributable binary                             |

## Verified findings that shape the plan

These were measured against the working tree, not assumed.

- **`ruff format` touches ~283 of 649 lines.** Not line-length driven: the longest source line is 87 columns, already under 88. Ruff converts the aligned-continuation call style to vertical hanging indents. Confirmed by `uvx ruff format --diff` at line lengths 88, 100 and 120 (283, 270 and 230 changed lines respectively).
- **`N806` must be disabled.** All nine findings are spectral-domain variables (`A`, `B`, `H`, `Sa`, `Sr`, `T`) that mirror the README's notation (`H = B/A`, `|B/A|`). Lowercasing them would break the correspondence between code and documentation.
- **`BLE` must be selected, not ignored.** The two `# noqa: BLE001` directives are reported as unused (`RUF100`) only because `BLE` is unselected. Those bare-`Exception` catches are load-bearing and explained in `tools/sampler-nulltest/CLAUDE.md`: `soundfile` binds libsndfile through CFFI at import time, so a broken shared library arrives as `OSError` and a narrower catch would skip the scipy fallback. Selecting `BLE` makes the author's directives meaningful instead of deleting them.
- **With `select = [E, F, I, N, UP, B, SIM, RUF, BLE]` and `ignore = [N806]`, exactly two findings remain**: one `I001` import sort (auto-fixable) and one `RUF005` tuple concatenation (one-line manual fix).
- **The import-sort fix is safe.** Verified on a scratch copy: it preserves `import matplotlib` → `matplotlib.use("Agg")` → `import matplotlib.pyplot as plt`, the ordering that selects the Agg backend before pyplot loads. `E402` does not fire, `ruff format --check` passes, and the reformatted script still runs.
- **`uv`'s "Installed N packages" line goes to stderr, not stdout.** Scrut validates stdout by default, so `--help` snapshots are deterministic on both cold and warm caches. Exit code is 0.
- **Neither script has `--version`.** The `add-scrut-cli-tests` starter `version.md` does not apply and is skipped, as that skill explicitly permits.
- **markdownlint's default `MD013` floods the prose.** The Markdown here is written as single long lines per paragraph. The skill's own template already sets `"MD013": false`, which resolves it.
- **`cboone/gh-actions` is at `91f9abd25d4f82354c0f950dfc8b6d7525b0f5b5 # v3.0.0`** as of 2026-08-28. Current pins: `uv` 0.12.7, `ruff` 0.16.5. Note that `set-up-linters/references/languages/python.md` pins ruff 0.15.12, which is stale.

## Execution plan

Work in order. Commit at each numbered step.

### 1. Scaffold the repository foundation

Invoke the `scaffold-new-repo` skill, telling it explicitly: project name `audio-tools`, project type **python**, description supplied below. It must not re-detect the type from `.gitignore` inference alone.

Generate:

- `AGENTS.md` at the root, describing the repo as a collection of independent audio analysis tools under `tools/`, each self-contained with PEP 723 metadata, each owning its own README and AGENTS.md.
- `CLAUDE.md` as a symlink to `AGENTS.md`.
- `.claude/settings.json` (minimal permissions scaffold).
- `.github/copilot-instructions.md`.
- `CHANGELOG.md`.
- `docs/plans/todo/.gitkeep` and `docs/plans/done/.gitkeep`.

Keep as-is:

- `LICENSE` (MIT, 2026, Christopher Boone) is correct. Do not regenerate.
- `.gitignore` is already the full Python template plus the `tools/sampler-nulltest/*.png` output rule. Nothing to merge.

Replace:

- `README.md`, currently the one-line stub `# audio-tools`. Write a real root README: what the repo is, a tools table pointing at `tools/sampler-nulltest`, and how to run a `uv run --script` tool with no install step. Link out to the tool's own README rather than duplicating its findings.

Also normalize the existing tool-level agent config to the hub-and-spoke pattern the root now uses:

```bash
git mv tools/sampler-nulltest/CLAUDE.md tools/sampler-nulltest/AGENTS.md
ln -sfn AGENTS.md tools/sampler-nulltest/CLAUDE.md
```

The content is preserved verbatim; only the canonical filename changes.

### 2. Configure ruff and apply the one-time reformat

Create `ruff.toml` at the root:

```toml
target-version = "py310"
line-length = 88

[lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF", "BLE"]
# Spectral-domain variables (A, B, H, Sa, Sr, T) match the notation in the
# tool READMEs (H = B/A). Lowercasing them would break that correspondence.
ignore = ["N806"]

[format]
quote-style = "double"
indent-style = "space"
```

`target-version = "py310"` matches the `requires-python = ">=3.10"` already declared in both scripts' PEP 723 blocks.

Then, as a **separate `style:` commit** so the reformat is reviewable in isolation from the config:

```bash
uvx ruff@0.16.5 check --fix .   # applies the I001 import sort
uvx ruff@0.16.5 format .        # reformats both scripts
```

Fix the one remaining `RUF005` by hand at `tools/sampler-nulltest/nulltest.py:141`, changing `(-delay,) + b.shape[1:]` to `(-delay, *b.shape[1:])`.

Verify before committing:

```bash
uvx ruff@0.16.5 check .
uvx ruff@0.16.5 format --check .
./tools/sampler-nulltest/maketest.py --sr 48000 --outdir "$TMPDIR/probe"
./tools/sampler-nulltest/nulltest.py "$TMPDIR/probe/probe_noise.wav" \
  tools/sampler-nulltest/probe/probe_noise.wav -o "$TMPDIR/out.png"
```

The second command is a real regression check, not a smoke test: `probe_noise` regenerates bit-identically per `tools/sampler-nulltest/AGENTS.md`, so the verdict must read bit-identical. If it does not, the reformat broke something.

### 3. Set up linters

Invoke the `set-up-linters` skill, telling it the project is **Python** (its own detection will miss it) and that ruff is already configured in `ruff.toml` from step 2, so it must not create a second ruff config or a `pyproject.toml`.

Request:

| Tool               | Config file                                   | Notes                                                        |
| ------------------ | --------------------------------------------- | ------------------------------------------------------------ |
| Prettier           | `.prettierrc.json`, `.prettierignore`         | `printWidth: 10000`, `proseWrap: preserve`                   |
| EditorConfig       | `.editorconfig`                               | Adapted to Python and Markdown                               |
| markdownlint-cli2  | `.markdownlint-cli2.jsonc`                    | `MD013: false`; add `MD014: false` in step 7                 |
| cspell             | `cspell.jsonc`, `cspell-words.txt`            | Seed the word list, see below                                |
| Actionlint         | (no config)                                   | Once `.github/workflows/` exists                             |
| Taplo              | `taplo.toml`                                  | For `ruff.toml`, `.gitleaks.toml`, `cspell` TOML if any      |

Seed `cspell-words.txt` with the domain vocabulary actually used in the prose, at minimum: `nyquist`, `libsndfile`, `iXML`, `bext`, `declick`, `dBFS`, `argparse`, `scipy`, `numpy`, `matplotlib`, `soundfile`, `resampling`, `passthrough`, `nulltest`, `maketest`, `Logic`'s `Flex`, and the `ULP`, `SRC`, `PDC`, `BIP` initialisms.

`.prettierignore` must exclude `tools/sampler-nulltest/probe/` so Prettier never touches the committed WAV artifacts.

### 4. Set up CI

Invoke the `set-up-ci` skill for **Python**, but the stock Python template does not apply as written: its test job runs `uv run pytest`, and this repo has no pytest suite and no `pyproject.toml` for `uv run` to resolve. That job must be dropped, not carried through with a failing command.

Produce `.github/workflows/ci.yml` with these jobs:

| Job          | Command                                    | Source                                    |
| ------------ | ------------------------------------------ | ----------------------------------------- |
| `lint`       | `uvx ruff check .`                         | Python CI template, unchanged             |
| `format`     | `uvx ruff format --check .`                | Python CI template, unchanged             |
| `markdown`   | `markdownlint-cli2 "**/*.md"`              | set-up-linters CI reference               |
| `spelling`   | `cboone/gh-actions` run-cspell             | set-up-linters CI reference               |
| `actionlint` | `raven-actions/actionlint`                 | set-up-linters CI reference               |
| `test-scrut` | reusable workflow                          | Added in step 7                           |

Keep the template's `paths-ignore`, concurrency group, `permissions: contents: read`, and `timeout-minutes`. Note that `paths-ignore` only ignores root-level `*.md`, so `tests/scrut/*.md` still triggers CI, which is what we want.

Skip the "Ensure a Language Version File" step's instruction to add `requires-python` to `pyproject.toml`. No `pyproject.toml` is being created; `requires-python` already lives in each script's PEP 723 block, which is where it belongs.

Create a `Makefile` with `lint`, `fmt`, `test-scrut`, `test-scrut-update`, `test-all` and `help` targets. Omit `test` (there is no unit test suite) and `clean`.

Refresh the `cboone/gh-actions` SHA before writing any workflow, per each skill's standing instruction.

### 5. Set up secret scanning

Invoke the `set-up-secret-scanning` skill and request **both** tools plus a `.gitleaks.toml`.

Adapt the allowlist: this repo has no lockfiles, so remove the `go.sum` / `package-lock.json` / `Gemfile.lock` entries. Add `tools/sampler-nulltest/probe/.*\.wav` so gitleaks does not flag the committed binary probe artifacts on entropy.

### 6. Add community files

Invoke the `add-community-files` skill. The repo is public, so all four files apply.

It will detect the `Makefile` from step 4 and use `make lint` / `make fmt`. Supply the missing pieces it cannot infer:

- `TEST-COMMAND` is `make test-scrut`, not `make test`.
- `INSTALL-COMMAND` is none. Requirements are `uv` only; dependencies resolve per-script from PEP 723 metadata.
- Ask which Code of Conduct contact method to use before writing `CODE_OF_CONDUCT.md`.
- `CHANGELOG.md` exists after step 1, so the PR template gets the changelog checklist item.

### 7. Add starter scrut tests

Invoke the `add-scrut-cli-tests` skill. Both scripts are interpreted CLIs with no build step, so drop the `build` dependency from the Makefile targets.

| Setting          | Value                                     |
| ---------------- | ----------------------------------------- |
| Binaries         | `nulltest.py`, `maketest.py`              |
| Env var names    | `NULLTEST_BIN`, `MAKETEST_BIN`            |
| Binary paths     | `./tools/sampler-nulltest/<script>.py`    |
| Test directory   | `tests/scrut/`                            |
| Build required   | No                                        |

Create `tests/scrut/help.md` only, covering `--help` for both scripts. Skip `version.md`: neither script has a `--version` flag.

Populate the snapshots with `make test-scrut-update`, then confirm with `make test-scrut`. Scrut is already installed locally at `~/.cargo/bin/scrut`.

Add the CI job, refreshing the SHA first:

```yaml
test-scrut:
  uses: cboone/gh-actions/.github/workflows/run-scrut-tests.yml@<current-sha> # <current-tag>
  with:
    scrut-test-dir: "tests/scrut/"
    scrut-setup-cmd: >-
      python3 -m pip install --user 'uv==0.12.7' &&
      echo "$HOME/.local/bin" >> "$GITHUB_PATH"
    scrut-env: |
      NULLTEST_BIN=./tools/sampler-nulltest/nulltest.py
      MAKETEST_BIN=./tools/sampler-nulltest/maketest.py
```

The `scrut-setup-cmd` exists because `ubuntu-latest` does not ship `uv`, and the scripts' shebangs need it. A pinned `pip install` is used rather than the upstream `curl | sh` installer, per the pinning rule in `set-up-linters`. `$GITHUB_PATH` persists across steps within the job, so the later scrut step finds `uv`.

Finally, add `"MD014": false` to `.markdownlint-cli2.jsonc`: scrut files use `$ command` notation, which trips that rule.

### 8. Follow-up issue

File an issue on `cboone/audio-tools` to encode the validation matrix that `tools/sampler-nulltest/AGENTS.md` documents: the ~18 synthetic source/bounce cases (identical, gain-shifted, fractionally delayed, integer-delayed early and late, band-limited, polarity-inverted, trailing silence, int16 vs float32, stereo with per-channel errors, one-sided polarity flip, mono against stereo both exact and differing, extra channel with content and silent, dual-mono fold-down, true-stereo fold-down, 3-channel against 2-channel, anti-phase stereo with integer delay).

Quote the two warnings from that file verbatim in the issue body: that two of these shipped broken as the same mistake in different dimensions, and that the delay estimate must stay on the strongest channel pair rather than the channel mean.

Also file an issue on `cboone/gh-actions` requesting a first-class language-setup input on `run-scrut-tests.yml`, so projects whose CLIs need a runtime (`uv`, `bun`, `deno`) can get it from a SHA-pinned action instead of a shell command in `scrut-setup-cmd`.

## Files created or modified

| Path                                     | Action   | Step |
| ---------------------------------------- | -------- | ---- |
| `README.md`                              | Replaced | 1    |
| `AGENTS.md`, `CLAUDE.md`                 | Created  | 1    |
| `CHANGELOG.md`                           | Created  | 1    |
| `.claude/settings.json`                  | Created  | 1    |
| `.github/copilot-instructions.md`        | Created  | 1    |
| `docs/plans/{todo,done}/.gitkeep`        | Created  | 1    |
| `tools/sampler-nulltest/AGENTS.md`       | Renamed  | 1    |
| `ruff.toml`                              | Created  | 2    |
| `tools/sampler-nulltest/*.py`            | Modified | 2    |
| `.editorconfig`, `.prettierrc.json`      | Created  | 3    |
| `.markdownlint-cli2.jsonc`               | Created  | 3, 7 |
| `cspell.jsonc`, `cspell-words.txt`       | Created  | 3    |
| `taplo.toml`                             | Created  | 3    |
| `.github/workflows/ci.yml`               | Created  | 4, 7 |
| `Makefile`                               | Created  | 4, 7 |
| `.github/workflows/gitleaks.yml`         | Created  | 5    |
| `.github/workflows/trufflehog.yml`       | Created  | 5    |
| `.gitleaks.toml`                         | Created  | 5    |
| `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`  | Created  | 6    |
| `.github/SECURITY.md`                    | Created  | 6    |
| `.github/PULL_REQUEST_TEMPLATE.md`       | Created  | 6    |
| `tests/scrut/help.md`                    | Created  | 7    |

## Verification

Run locally before pushing:

```bash
uvx ruff@0.16.5 check .
uvx ruff@0.16.5 format --check .
make test-scrut
markdownlint-cli2 "**/*.md"
cspell lint --no-progress .
prettier --check .
```

Confirm the reformatted tool still produces the correct verdict end to end:

```bash
./tools/sampler-nulltest/maketest.py --sr 48000 --outdir "$TMPDIR/probe"
./tools/sampler-nulltest/nulltest.py "$TMPDIR/probe/probe_noise.wav" \
  tools/sampler-nulltest/probe/probe_noise.wav -o "$TMPDIR/out.png"
```

This must report **bit-identical**. `probe_noise` is documented as regenerating bit-identically, so any other verdict means the reformat changed behavior.

Then open a PR and confirm every CI job passes, paying particular attention to `test-scrut`: the `uv` install in `scrut-setup-cmd` is the one part of this plan that cannot be validated locally, since it exists specifically to compensate for what the GitHub runner lacks.
