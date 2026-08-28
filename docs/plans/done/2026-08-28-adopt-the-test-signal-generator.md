# Adopt the test-signal generator from cboone/fosforo

Addresses [cboone/audio-tools#1](https://github.com/cboone/audio-tools/issues/1).

## Context

`cboone/fosforo` carries `scripts/make-test-tones`, 241 lines of bash driving `ffmpeg -f lavfi -i aevalsrc=...` to render the signals that plugin's manual host verification plays: sines at exact frequencies, a level sweep crossing full scale, two hard-panned files, two sawtooth ramps either side of a clipping threshold, and two transients. It writes 32-bit float stereo WAVs and reads every peak back out of the finished file.

Almost none of that is specific to one plugin. The design reasons generalize completely, and they are the part worth keeping:

- **32-bit float, not 24-bit integer.** Any test signal above 1.0 is unrepresentable otherwise, and testing what a meter or a scope does above full scale is a normal thing to want.
- **Do not use a DAW's gain knob.** REAPER's stock Tone Generator and `JS: Volume Adjustment` both compute gain as `2 ^ (x / 6)`, a factor of two per six decibels rather than 6.0206 dB, and the Tone Generator moves in whole-decibel steps capped at +6.
- **Pan has to be baked into the file.** REAPER applies track pan _after_ the FX chain, so panning a track never reaches the plugin under test, and a channel check done with the pan knob passes against a plugin that ignores the channel entirely.
- **Verify the generator.** Reading each peak back caught a bug in the script's own check: taking the first channel's peak reports zero for a hard-panned file.

The intended outcome is a parameterized generator in this repo that any instrument can point at with its own thresholds, with the readback verification unconditional, and `cboone/fosforo` reduced to a caller.

## Decisions taken before planning

Four questions were settled with the user:

1. **Port to Python** rather than importing the bash. This repo is entirely `uv` / PEP 723 / numpy / scipy, with no shell scripts, no ffmpeg, no CI and no linter config. `tools/sampler-nulltest/maketest.py` is already a signal generator and is the precedent to match. Porting also removes the ffmpeg dependency, makes the `mod()` comma-escaping hazard moot, and makes the peak readback exact instead of parsed out of `astats` text.
2. **CLI flags**, no preset file and no `--periods-per-window` concept. Fósforo's exact invocation goes in the README as the worked example.
3. **The screenshot analyzer is out of scope.** Issue #1 floats bringing `measure-trace` here too. [cboone/fosforo#64](https://github.com/cboone/fosforo/issues/64), opened three days later, found it, committed an improved version on fosforo's `chore/scripts` branch, and settled that it stays there. That is right: it restates `trace_full_scale`, `trace_rail`, and the background and beam color literals that it does not own, it cannot measure any other oscilloscope, and its only real safeguard is a Zig test reading the Python source, which can only exist in fosforo. Post a comment on #1 recording that #64 supersedes that paragraph.
4. **The fosforo-side cleanup is a follow-up issue**, not part of this branch.

## Scope

Create `tools/test-signals/`, matching the `tools/<tool-name>/` layout established by commit `f19d4ae`: self-contained, scripts and docs together.

| Path                              | Purpose                                                               |
| --------------------------------- | --------------------------------------------------------------------- |
| `tools/test-signals/maketones.py` | The generator, mode `100755`                                          |
| `tools/test-signals/README.md`    | Problem statement, usage, the design rationale above, worked examples |
| `tools/test-signals/AGENTS.md`    | Agent guidance, deferring to the README                               |
| `.gitignore`                      | One `tools/test-signals/*.wav` entry under a `# Tool output` comment  |

No committed output. The fosforo set is 20 files at roughly 7.7 MB each; unlike `sampler-nulltest/probe/*.wav` these are not fixtures anything compares against, so they are generated and ignored.

## `maketones.py`

House style is set by `maketest.py` and `nulltest.py` and must be matched exactly: `#!/usr/bin/env -S uv run --script` with a PEP 723 block declaring `requires-python = ">=3.10"` and alphabetized `dependencies = ["numpy", "scipy"]`; a module docstring opening `maketones.py: <lowercase purpose>` then `Usage:  uv run maketones.py ...`; no type hints, no classes, no dataclasses; `os.path` rather than `pathlib`; double quotes; explicit `.0` on floats; dense comments explaining _why_, including the bugs a decision was written against; plain `print()` to stdout with no color; `sys.exit("lowercase message")` for user errors; `def main():` with a local `p = argparse.ArgumentParser()`; `if __name__ == "__main__": main()`.

### Argument surface

```text
--outdir DIR          default "."
--sr HZ               default 48000
--seconds S           default 20
--only GROUP...       choose from sines levels pans saws transients; default all

--sines HZ...         default 50 100 200 250 400 1000
--sine-level L        default 0.5
--levels L...         default 0.002 0.010 0.100 0.500 1.000 2.000
--level-hz HZ         default 100, shared by levels, pans, saws and the burst
--saws L...           default 0.900 1.100
--pan-level L         default 0.5
--click-hz / --click-ms / --click-rate / --click-level    default 1000 / 1.0 / 2.0 / 0.8
--burst-ms / --burst-rate / --burst-level                 default 100 / 1.0 / 0.5
```

The two purely Fósforo-tuned levels, `1.050` and `1.089`, are deliberately **not** defaults. `1.089` is `trace_rail / trace_full_scale` = `0.98 / 0.9` = 1.08889 from that plugin's `src/gpu/iface.zig`; it is the first level that rails, clearing the threshold by 0.0001, and it is not a symmetric bracket around it. Fósforo passes both on the command line.

**Take `--levels` and `--saws` as strings, not floats.** The filenames carry the literal token, so `0.010` and `0.900` must not become `level-0.01.wav` and `saw-0.9.wav`. Parse with `float()` for the value and format the name from the token as given.

### Filenames

Preserve fosforo's names exactly, so its recorded measurement tables still line up: `sine-{hz}hz-{level}.wav`, `level-{token}.wav`, `pan-hard-left.wav`, `pan-hard-right.wav`, `saw-{token}.wav`, `click-{rate}hz.wav`, `burst-{hz}hz-gated.wav`.

### Synthesis

Reuse the shape of `maketest.py`'s generators: a small function per waveform returning a float64 array, a write loop casting to `np.float32` and calling `scipy.io.wavfile.write`. Stereo is an `(n, 2)` array. `wavfile.write` emits `WAVE_FORMAT_IEEE_FLOAT` for float32 input and applies no scaling or clipping, which is what lets levels above 1.0 survive.

Do **not** copy `maketest.py`'s `fade()`. These signals are meant to hold an exact peak for their whole length, and a fade would make the level check depend on where the peak landed.

Waveforms needed: sine; saw as `level * (2.0 * ((hz * t) % 1.0) - 1.0)`; a gated sine for the click and burst, gate on where `(t % (1.0 / rate)) < (ms / 1000.0)`. The saw and the gates are the two places ffmpeg needed `mod(` commas escaped as `\,`; in numpy the hazard does not exist, and the README records why it used to.

### Verification, which is the load-bearing part

The bash version compared one number to the requested level with a `0.0005` tolerance. That worked only because every fosforo frequency happens to land a sample on the crest at 48 kHz. **A parameterized generator accepting arbitrary frequencies cannot keep that check**: the largest sample of a sine need not land on the crest, and the peak can then sit as low as `cos(pi * f / sr)`, which is 0.2% at 1 kHz against 48 kHz and far outside 0.0005. A fixed tolerance would fail correct files.

Split it into the two failure modes it was conflating:

1. **Did the file keep what we put in it?** Read the written file back with `wavfile.read` and compare its per-channel peaks against the peaks of the in-memory array, exactly. Float32 round-trips bit-exactly, so this is an equality test with no tolerance, and it is the check that catches a silently clipped write, a wrong codec, or a narrower bit depth. This is the original intent: a generator that silently clipped its own output would produce a level sweep that tested nothing.
2. **Did we get the level we asked for?** Compare the in-memory peak against the requested level, and where it falls short, report the analytic bound rather than failing. Print the shortfall so an unlucky frequency is visible instead of silent.

Both are unconditional; there is no `--no-verify`. Keep the hard-panned assertion from the bash version and keep it per channel: the loud channel must hold the level and the silent channel must read exactly zero. That check exists because a first-channel peak reported zero for `pan-hard-right` and looked like a generator failure, and because a plugin tapping only channel 0 is exactly what the pan files are there to catch.

### Output

One line per file, extending `maketest.py`'s format with the verified peak:

```text
wrote ./level-1.089.wav  (20.00 s @ 48000 Hz, 32-bit float)  peak 1.089000
wrote ./pan-hard-right.wav  (20.00 s @ 48000 Hz, 32-bit float)  peak 0.500000, left silent
```

## Verification

Nothing in this repo has a test suite, and `tools/sampler-nulltest/AGENTS.md` says so outright; validation is manual and must be recorded. Run all of it before committing.

1. **Reproduce the fosforo set.** The 20 files the bash script produced are on disk at `~/Music/fosforo-test-tones/`. Render into a scratch directory with fosforo's parameters:

   ```bash
   uv run tools/test-signals/maketones.py --outdir /tmp/tones \
     --levels 0.002 0.010 0.100 0.500 1.000 1.050 1.089 2.000 \
     --saws 0.900 1.100
   ```

   Confirm the same 20 filenames appear, and compare each against its counterpart. Expect the sines to agree to float32 precision, and expect the saw and the two gated files to differ at boundary samples, because ffmpeg's `mod()` and numpy's `%` need not round a sample sitting exactly on a discontinuity the same way. Compare peaks and channel layout, not bit-identity, and record what differed.

   **Outcome: that expectation was wrong, in the useful direction.** All 20 files are bit-identical to their ffmpeg counterparts, saws and gated transients included. The two implementations agree at the discontinuities as well as everywhere else.

2. **Confirm the format.** Read `level-2.000.wav` back and check the peak really is 2.0, the dtype is `float32`, and the sample rate and channel count are 48000 and 2. This is the whole reason the tool exists; an integer format would silently clamp it.

3. **Prove the readback catches a real failure.** Temporarily make the write path cast to `np.int16`, or clamp to `[-1, 1]`, and confirm `level-2.000` fails loudly rather than being reported as written. Revert. A verification step nobody has seen fail is not evidence of anything.

4. **Prove the silent-channel assertion catches a real failure.** Temporarily render `pan-hard-right` into both channels and confirm it fails.

5. **Exercise the parameterization.** Run with `--only sines --sines 440 --sr 44100 --seconds 1` and confirm the odd frequency reports its shortfall against the analytic bound in step 2 of the verification design rather than failing.

6. **Check the filename tokens.** Confirm `--levels 0.010 1.000` produces `level-0.010.wav` and `level-1.000.wav`, not `level-0.01.wav`.

7. **Lint.** `uvx ruff check tools/test-signals/maketones.py`. The repo has no committed ruff config but `nulltest.py` carries `# noqa: BLE001`, so ruff is expected to pass.

## Commits

Conventional Commits, lowercase imperative subjects describing the effect, GPG signed, with the issue number for auto-linking. Bodies are long and hard-wrapped near 80 columns, explaining the reasoning and what was deliberately not changed. Smallest logical units:

1. `feat: add a parameterized test-signal generator (#1)`, the script and the `.gitignore` entry.
2. `docs: document the test-signal generator and its rationale (#1)`, `README.md` and `AGENTS.md`.

## Follow-ups, not part of this branch

Both are done.

- **Comment on audio-tools#1** recording that fosforo#64 supersedes the companion-analyzer paragraph. Posted.
- **File an issue in cboone/fosforo** to drop the script once this lands, filed as [cboone/fosforo#67](https://github.com/cboone/fosforo/issues/67): delete `scripts/make-test-tones`, delete the single `make-test-tones,` token from the brace list in `.editorconfig` lines 39–53, and add a pointer note to the two plan documents that reference it, `docs/plans/done/2026-08-20-draw-a-crude-aliased-trace.md` (lines 306 and 403) and `docs/plans/done/2026-08-26-accumulate-the-beam-into-a-persistent-texture.md` (lines 253 and 312). Both are in `done/` and are kept as historical records, so a note is more appropriate than a rewrite. If fosforo's `chore/scripts` branch merges first, its new `AGENTS.md` entry for the script needs the same treatment.

## Optional, flag if unwanted

The root `README.md` is 13 bytes and holds only `# audio-tools`. With a second tool landing, a two-row index table pointing at both tool directories would help. There is no existing pattern for it and issue #1 does not ask for it, so it is called out here rather than assumed. **Not done**, pending a decision.

## Outcome

Every verification step above was run and passed. Three things came out differently from the plan and are recorded here rather than left as stale predictions.

**The port is bit-identical to the original, not merely equivalent.** See step 1. This was worth more than the planned peak comparison: it means every measurement already recorded against the ffmpeg-rendered files still describes exactly the files this tool produces, so nothing measured with the old generator needs re-running.

**The shortfall report needed a threshold.** The plan said to report a peak falling short of the requested level. As first written it reported any shortfall above `TOLERANCE`, which printed `0.00% under 0.5` for the few parts per million a frequency whose crest falls between samples is short by. A line that says nothing trains the reader to skip the line that matters, so reporting now starts at 0.01%, the first shortfall the two-decimal figure can express. `REPORT_UNDER` carries that with the reasoning.

**Fault injection was done on copies, not by editing and reverting.** Steps 3 and 4 said to modify the script temporarily. Mutating a copy in the scratchpad instead means the working tree is never in a broken state, and it made it cheap to run four faults rather than two: `int16`, clamping to unity, a pan file rendered into both channels, and a level louder than requested. Each exits 1 with a message naming the file and both numbers; the unmodified control exits 0. The four cases are listed in `tools/test-signals/AGENTS.md` so the next change can repeat them.

**"Divides the sample rate evenly" was the wrong condition, and it was written into four files.** The plan and the first draft of the docs both explained the shortfall by saying a frequency dividing the sample rate loses nothing. That is false. The crest of a phase-zero sine sits at phase `pi/2`, so a sample lands on it exactly when `sr / (4 * f)`, in lowest terms, has an odd denominator. 1600 Hz divides 48 kHz exactly 30 times and still peaks 0.55% low, because `48000 / 6400` is 15/2. The prose also mixed the worst-case bound with measured shortfalls, quoting 0.2% at 1 kHz, which is the bound, beside 13.40% at 16 kHz, which is the actual. Both corrected everywhere; the code was always right, only the explanation was wrong.

Two additions beyond the plan, both small and both in response to something observed while testing. Frequencies at or above Nyquist are refused rather than allowed to alias, because an aliased sine is silently not the signal its filename claims and the filename is what a procedure refers to. And `--only` iterates the canonical group order rather than the order given on the command line, so output ordering is stable.
