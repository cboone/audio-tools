# Realign the documentation with the shipped code

## Context

Two branches landed close together. `chore/bootstrap-repo` scaffolded the root documentation set, and `feature/test-signal-generator` added a second tool. They crossed, so the root `README.md` still describes a one-tool repository: its last edit is commit `931597f`, which predates every commit that shipped `tools/test-signals/`.

The adoption plan saw this coming and deferred it deliberately. `docs/plans/done/2026-08-28-adopt-the-test-signal-generator.md` line 142 records that a root index table pointing at both tools "would help", but that "there is no existing pattern for it and issue #1 does not ask for it", and marks it **Not done, pending a decision**. The pattern now exists, so the decision can be made.

The more serious half of this work is elsewhere. Three statements in `tools/sampler-nulltest/README.md` describe behavior the code does not have, and one of them directly contradicts that tool's own `AGENTS.md`, which is the file agents are told to read first. A stale README is a nuisance; a README that contradicts the guardrail file is a trap, because it invites exactly the "simplification" the guardrail exists to forbid. Separately, three live docs still say "There is no test suite" without qualification, written before `tests/scrut/` landed in commit `088554a`.

Intended outcome: every checkable claim in the documentation matches the code as shipped, and the two tools are equally discoverable from the repository root.

## Scope

Documentation and stale comments in configuration. No behavior changes and no changes to any Python script. If a discrepancy turns out to be a code defect rather than a doc defect, stop and raise it rather than editing the prose to match.

`docs/plans/done/*` are historical records and must not be touched. `.github/copilot-instructions.md:7` states this explicitly, and both done plans do carry claims that no longer hold. Leave them.

## A. Root discoverability

### A1. `README.md`: the Tools table omits `test-signals`

`README.md:9-11` lists a single row. `tools/test-signals/` has shipped, is documented, is covered by scrut tests, and is wired into `Makefile:11` and `.github/workflows/ci.yml:87`.

Add the second row, keeping the existing "Question it answers" framing:

| Tool                                            | Question it answers                                                                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| [`sampler-nulltest`](./tools/sampler-nulltest/) | Does a sampler pass a sample through unaltered, and if not, exactly what did it change?                       |
| [`test-signals`](./tools/test-signals/)         | Does a meter, scope or plugin display read a signal correctly, when the signal's true value is already known? |

Prettier owns Markdown table alignment, so run `make text-fix` rather than hand-aligning the pipes.

### A2. `README.md`: the run examples show only one tool

`README.md:20` and `README.md:26` both invoke `nulltest.py`. Add a `maketones.py` example so the PEP 723 point is made against both tools.

Pass `--outdir` in that example, and say why. `maketones.py` defaults `--outdir` to the current directory, and a default run writes 18 files of roughly 7.7 MB each, so an example copy-pasted at the repository root drops about 138 MB of untracked WAVs there. `.gitignore:222` covers only `tools/test-signals/*.wav`, which does not reach the root. Both `tools/test-signals/README.md:19` and its `AGENTS.md` already warn about this; the root README must not print an invocation that walks into it.

### A3. `README.md`: the Development block omits `make test-all`

`README.md:33-39` lists `lint`, `fmt`, `text-lint`, `test-scrut` and `help`. `Makefile:57` defines `test-all` as `lint fmt text-lint test-scrut`, and `CONTRIBUTING.md` tells contributors to run the checks before committing. Add `test-all`; it is the one line that replaces the other four. `fmt-fix`, `text-fix` and `node-tools` can stay unlisted, since the block already points at `make help`.

### A4. `AGENTS.md`: the structure tree has malformed branch characters

`AGENTS.md:12` and `AGENTS.md:18` are sibling entries under `tools/`, but both are drawn with `└──`, so the tree renders as two terminal branches and `test-signals/` appears to hang off nothing. `sampler-nulltest/` should be `├──`, with `│` continuation on its children. This is the tree every agent reads first, since `CLAUDE.md` resolves to this file.

Corrected shape:

```text
audio-tools/
├── tools/
│   ├── sampler-nulltest/    # Is a bounce a bit-transparent pass-through of its source?
│   │   ├── AGENTS.md        # Tool-specific agent instructions (CLAUDE.md symlinks here)
│   │   ├── README.md        # Problem statement, procedure, method, limitations
│   │   ├── nulltest.py      # The analysis
│   │   ├── maketest.py      # Probe signal generator
│   │   └── probe/           # Committed 48 kHz probes, reproducible from maketest.py
│   └── test-signals/        # Exact tones, levels, pans and transients for checking a display
│       ├── AGENTS.md        # Tool-specific agent instructions (CLAUDE.md symlinks here)
│       ├── README.md        # Usage, the four output decisions, how verification works
│       └── maketones.py     # The generator, which reads every file back after writing it
├── tests/scrut/             # Scrut CLI snapshot tests
└── docs/plans/              # Plan documents: todo/ is active, done/ is historical
```

## B. `tools/sampler-nulltest/README.md` corrections

### B1. The delay Limitation contradicts the code and `AGENTS.md`

`README.md:190` currently reads:

> The integer delay is measured once from the channel mean and applied to every channel.

`nulltest.py:412-425` does not use the channel mean. It selects the channel pair maximizing `min(energy_a, energy_b)` and measures the delay there. The comment at `nulltest.py:412-419` and `tools/sampler-nulltest/AGENTS.md:11` both explain why, and AGENTS.md ends with "Do not simplify that back to a mean." The commit that made the change is quoted as a message example in `CONTRIBUTING.md:85`; the README was never updated to match.

Rewrite the bullet so the surviving limitation is the real one: the delay is measured once, on the channel pair where both sides carry the most energy, and applied to every channel, so per-channel delay differences beyond that are absorbed into each channel's fractional figure, which is only meaningful within plus or minus one sample. Keep the anti-phase reasoning to a clause and leave the full account in `AGENTS.md`.

### B2. The PNG is not always written

`README.md:48` says `nulltest.py` "prints its findings and writes a four-panel PNG", unconditionally. It does not. `main()` returns at `nulltest.py:493` on the bit-identical verdict and at `nulltest.py:516` on the channel-layout verdict, both before the `plot()` call at `nulltest.py:603`.

This misleads a reader following the procedure. Step 0's control test is expected to pass, its example output at `README.md:64-68` is a bit-identical verdict, and that is the step the README first shows the flag on, so the reader gets no `nulltest.png` from it.

State the actual contract: the PNG is written only when there is a residual to plot, and it shows the channel with the largest residual (`nulltest.py:540`, `nulltest.py:601`). A pass writes no image because there is nothing to draw, which is consistent with the argument Step 5 already makes about a bit-identical result closing a configuration.

### B3. Step 4 omits the third verdict

`README.md:108-113` enumerates how to read the result: bit-identical, plus four residual signatures. The code emits a third verdict shape that is neither, at `nulltest.py:498-515`:

> VERDICT: not transparent. Every channel that could be paired matches the source exactly, but the channel layout leaves something unaccounted for.

with follow-up lines for source channels the bounce dropped and for unpaired bounce channels carrying content. That verdict is the shipped fix for a defect `AGENTS.md:12` records as having gone out broken, so it belongs in the list a user actually reads. Add a bullet: every paired channel matched but a channel was dropped or never compared, which is a layout finding rather than a signal one, and say what to check.

### B4. The Contents table omits the agent files

`README.md:28-32` lists `nulltest.py`, `maketest.py` and `probe/`. `tools/test-signals/README.md:11-15` also lists its `README.md` and `AGENTS.md` rows. Match the newer tool's table so the two are parallel and the `CLAUDE.md` symlink is discoverable.

## C. The "no test suite" claim

`tests/scrut/` exists and covers both tools: `help.md` pins usage lines, argument names and help text, and `errors.md` pins error strings, output stream and exit code across 11 blocks. Three live docs still deny it outright.

Qualify the claim in each, keeping the real point (nothing verifies the DSP or the analysis) and adding what `tests/scrut/` does cover, so a change that alters a flag name, a help string or an error message prompts a `make test-scrut` run rather than a surprise CI failure:

- `tools/sampler-nulltest/AGENTS.md:10` — leads the bullet that lists the synthetic validation cases. Keep that list intact.
- `tools/test-signals/AGENTS.md:16` — same shape, leads the bullet listing the render-and-inject cases. Keep that list intact.
- `tools/test-signals/README.md:112` — the Limitations bullet, which defers to `AGENTS.md`.

The shape agreed for the wording:

> **There is no test suite for the analysis.** `tests/scrut/` pins the CLI contract only: help text, error messages and exit codes. Nothing checks the numbers, so validate any change by rendering and checking the result, and run `make test-scrut` because a changed flag or message breaks a snapshot.

Adapt the second half to each file's existing sentence rather than pasting it verbatim; the two AGENTS.md bullets already continue into their own validation lists.

## D. `CONTRIBUTING.md`: the `node-tools` dependency claim

`CONTRIBUTING.md:22` says "`make node-tools` installs them, and the other targets depend on it." Only `text-lint` and `text-fix` depend on `node-tools` (`Makefile:34`, `Makefile:39`). `lint`, `fmt`, `test-scrut` and `test-all` do not, and `test-all` reaches them only through `text-lint`. Correct it to name the two targets.

## E. Stale comments in configuration

### E1. `.github/workflows/ci.yml:67`

Says "Both tools are `uv run --script` shebangs". There are now three scripts across two tools, and the job's own `scrut-env` block at `ci.yml:84-87` sets three binaries. Change "Both tools" to "Every tool". Comment only.

### E2. `.gitleaks.toml:6-8`

Says "This repo has no lockfiles and no vendored dependencies: each tool declares its own dependencies inline via PEP 723, so the usual lockfile exclusions do not apply." `package-lock.json` was committed afterwards, in commit `931597f`. The allowlist itself is still correct and must not change; only the reasoning is stale. Rewrite it to say the Python tools declare dependencies inline via PEP 723, and that the one lockfile present, `package-lock.json`, pins the text linters. Do not add a path exclusion for it unless a scan actually flags it.

## F. `CHANGELOG.md`: backfill both tools

`CHANGELOG.md:8` is an empty `## [Unreleased]` heading. There are no tags and no release, but two tools have landed and `.github/PULL_REQUEST_TEMPLATE.md:26` asks contributors to update this file for user-facing changes.

Add an `### Added` section under `[Unreleased]`:

```markdown
### Added

- `tools/sampler-nulltest`: null test measuring whether a bounce is a bit-transparent pass-through of its source.
- `tools/test-signals`: generator for exact tones, levels, pans and transients, verifying every file it writes.
```

Note that `CHANGELOG.md` is excluded from all three text linters, by `.prettierignore`, `.markdownlint-cli2.jsonc` and `cspell.jsonc`, so nothing will format or check this edit. Match the surrounding style by hand and keep the Keep a Changelog section names.

## Verified as already correct, so leave alone

Checked against the code and confirmed accurate. Recorded so a later pass does not re-audit them:

- `nulltest.py` flag documentation: `-o/--out` default `nulltest.png`, `--floor` default `-60.0` (`nulltest.py:379-383`).
- The four-panel figure, `plt.subplots(2, 2)` at `nulltest.py:266`, plotting the worst channel (`nulltest.py:540`, `nulltest.py:601`).
- `tools/test-signals/README.md` throughout: 18 default files at roughly 7.7 MB each, the five groups and their default filenames, the `cos(pi * f / sr)` bound giving 0.2% at 1 kHz and 50% at 16 kHz, the 1600 Hz / `15/2` case, the 0.01% reporting threshold against `REPORT_UNDER = 0.0001`, the seventeen flags.
- `probe/*.wav`: all three are WAV format tag 3 IEEE float, mono, 48 kHz, peaking at -6.0000 dBFS, matching `README.md:32` and `AGENTS.md:14`.
- `ruff.toml`, `package.json` and `.github/copilot-instructions.md` descriptions all match the current configuration, including the `N806` and `BLE` rationale repeated across three files.
- `tests/scrut/help.md` and `errors.md` match the current CLI surface exactly, including the "seventeen options" count.

## Files to change

| File                               | Items          |
| ---------------------------------- | -------------- |
| `README.md`                        | A1, A2, A3     |
| `AGENTS.md`                        | A4             |
| `tools/sampler-nulltest/README.md` | B1, B2, B3, B4 |
| `tools/sampler-nulltest/AGENTS.md` | C              |
| `tools/test-signals/README.md`     | C              |
| `tools/test-signals/AGENTS.md`     | C              |
| `CONTRIBUTING.md`                  | D              |
| `.github/workflows/ci.yml`         | E1             |
| `.gitleaks.toml`                   | E2             |
| `CHANGELOG.md`                     | F              |

`CLAUDE.md` files are symlinks to their sibling `AGENTS.md` and need no separate edit.

## Verification

1. `make text-fix` then `make text-lint`, for markdownlint, Prettier and cspell. Any new term goes in `cspell-words.txt`, not in an inline ignore.
2. `make test-scrut`. The docs pass should not disturb the snapshots; a green run also confirms the flag names and help text quoted in the READMEs still match what the tools advertise.
3. Re-read `tools/sampler-nulltest/README.md` against `nulltest.py:412-425` and `tools/sampler-nulltest/AGENTS.md:11`, and confirm the three now agree on the delay.
4. Confirm the B2 claim directly rather than trusting the read. Working outside the repository tree, generate a probe with `uv run tools/sampler-nulltest/maketest.py --outdir "$SCRATCH"`, then run `nulltest.py` twice: an identical copy should print the bit-identical verdict and write no PNG, and a gain-scaled copy should print a residual verdict and write one. If a PNG appears on the pass, B2 is a code defect and the plan is wrong; stop and say so.
5. Confirm the corrected Markdown table and the `AGENTS.md` tree render as intended, since Prettier rewrites tables and the tree is inside a `text` fence it will not touch.
6. `make test-all` before the final commit.

## Commits

Split by concern:

1. `docs: list both tools in the root README and fix the structure tree` (A1–A4)
2. `docs: correct the delay limitation and the PNG contract in nulltest` (B1–B4)
3. `docs: name the scrut tests where the docs say there is no test suite` (C, D)
4. `docs: record both tools in the changelog` (F)
5. `chore: correct two stale comments in ci.yml and .gitleaks.toml` (E1, E2)

## Outcome

Done as planned, on branch `docs/realign-docs-with-shipped-code`, in the five commits above. `make test-all` passes: ruff clean, 23 files formatted, markdownlint and Prettier and cspell clean, 18 of 18 scrut testcases succeeding.

**The three `nulltest.py` claims were verified against the running tool rather than read off the source.** The plan said to stop and raise it if any turned out to be a code defect; none was. Working outside the tree from a `maketest.py` probe:

- An identical copy printed `VERDICT: bit-identical` and wrote no PNG at the path given to `-o`.
- A copy scaled by 0.9 printed `level (rms b/a) : -0.9152 dB` against the expected `20 * log10(0.9) = -0.9151`, and did write the PNG.
- A 2-channel source against a 3-channel bounce whose third channel carried noise printed the layout verdict, named `ch2` specifically, and wrote no PNG. That confirmed both the B3 wording and that the layout path is a second silent-on-plot exit, which the B2 rewrite states.

**One wording decision worth recording.** The `no test suite` qualification (item C) reads as a bold lead-in in both `tools/test-signals` files, which use that style throughout, but as a plain sentence in `tools/sampler-nulltest/AGENTS.md`, whose bullets carry no bold. Matching each file's own convention was preferred over making the three identical.

**Not done, and deliberately.** `docs/plans/done/*` carry several claims that no longer hold: the bootstrap plan's Outcome table still says the text checks use the `lint-text.yml` reusable workflow, which `2ff5aeb` reversed, and it lists CI jobs under names `ci.yml` does not use; the adoption plan says the repo has no committed ruff config. `.github/copilot-instructions.md:7` states that done plans are historical records and that drift against them is not to be flagged, so they were left alone.

Two follow-ups noticed while working, neither in scope here and neither blocking:

- The root `README.md` development block still omits `fmt-fix`, `text-fix` and `node-tools`. That is a deliberate trim, not an oversight, since the block points at `make help`, but it is worth revisiting if the target list grows again.
- `tools/sampler-nulltest/README.md` describes the channel pairing only for the mono-into-stereo case in its Reading the output section. The `min(na, nb)` fan-out and its leftovers are covered in Method and now in Step 4, so nothing is wrong, but the three passages could be consolidated.
