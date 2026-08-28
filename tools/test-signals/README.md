# Exact test signals

Anything that displays or measures audio has to be checked against a signal whose value you already know. A meter reading -6.0 dBFS is evidence of nothing until the file really is at -6.0 dBFS, a scope showing four periods across its window is evidence of nothing until the tone really is 200 Hz against a 20 ms window, and a plugin that appears to handle a signal above full scale is evidence of nothing until the file actually holds one.

This renders those signals, and then reads every file back to prove it holds what was asked for.

Written for verifying an audio plugin's display by playing files through REAPER, but nothing in the generator is specific to that plugin or to REAPER. Every frequency, level and duration is an argument.

## Contents

| Path           | Purpose                                                    |
| -------------- | ---------------------------------------------------------- |
| `maketones.py` | The generator. Renders each group and verifies every file. |
| `README.md`    | This file.                                                 |
| `CLAUDE.md`    | Notes for agents.                                          |

Output is not committed. A default run is 18 files of roughly 7.7 MB each, they are regenerated in seconds, and nothing compares against a stored copy.

`.gitignore` carries `tools/test-signals/*.wav`, which covers output written into the tool's own directory. Note that `--outdir` defaults to the current directory, following `maketest.py` next door, so a run started from the repository root writes 18 large files into the root where that entry does not reach them. Pass `--outdir` and send them somewhere outside the tree.

## Usage

The script carries [PEP 723](https://peps.python.org/pep-0723/) inline metadata and a `uv run --script` shebang, so it needs no environment setup:

```bash
# every group, into the current directory
uv run maketones.py

# one group, somewhere else
./maketones.py --outdir ~/Music/tones --only levels
```

System `python3` has no `scipy`, so plain `python3 maketones.py` will fail. Use `uv`.

Five groups are rendered by default and any subset can be chosen with `--only`:

| Group        | Default files                                        | What it is for                                                                                           |
| ------------ | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `sines`      | `sine-50hz-0.5` through `sine-1000hz-0.5`, six files | Counting periods. At 48 kHz a 20 ms window shows `f * 0.020`, so the defaults give 1, 2, 4, 5, 8 and 20. |
| `levels`     | `level-0.002` through `level-2.000`, six files       | One frequency at many amplitudes, so only the vertical axis varies.                                      |
| `pans`       | `pan-hard-left`, `pan-hard-right`                    | Proving a channel is read, rather than assumed.                                                          |
| `saws`       | `saw-0.900`, `saw-1.100`                             | Showing an overshoot as a flat top with a vertical edge.                                                 |
| `transients` | `click-2hz`, `burst-100hz-gated`                     | Anything whose behaviour only differs after the signal changes.                                          |

The full flag list is in `--help`. The ones that matter most are `--sines`, `--levels`, `--saws` and `--level-hz` for content, and `--sr`, `--seconds` and `--outdir` for everything else.

## Why the output is shaped this way

Four things are decisions rather than defaults, and they are the part worth carrying to any other instrument.

**32-bit float, not 24-bit integer.** Any test signal above 1.0 is unrepresentable in an integer format, and testing what a meter or a scope does above full scale is a normal thing to want. The default sweep ends at 2.000 for that reason. `scipy.io.wavfile` writes WAV format tag 3, IEEE float, for a float32 array and applies no scaling or clipping, which is what lets those samples survive.

**Do not reach for a DAW's gain knob instead.** REAPER's stock Tone Generator and `JS: Volume Adjustment` both compute gain as `2 ^ (x / 6)`, which is a factor of two per six decibels rather than 6.0206 dB. The Tone Generator additionally moves in whole decibels and stops at +6. `JS: Volume/Pan Smoother` is the only one of the three using true dB. Rendering the levels makes them exact and, more usefully, makes them checkable. The Tone Generator is still the better source when an integer Hz field that nudges by one matters more than an exact level.

**The pan is baked into the file rather than left to a knob.** REAPER applies track pan *after* the FX chain, so panning a track never reaches the plugin under test. A channel check done with the pan knob passes against a plugin that ignores the channel entirely, which is the exact bug the check exists to find.

**Every file is read back after it is written.** A generator that silently clipped its own output would produce a level sweep that tested nothing, which is the same class of failure as an install that was never confirmed. There is no flag to switch it off.

## How the verification works

The readback answers two separate questions, and keeping them separate is the whole design.

**Did the file keep what we put in it?** The written file's per-channel peaks are compared against the in-memory array's peaks, exactly, with no tolerance. float32 round-trips through a WAV bit for bit, so an inequality here is a real fault: a clipped write, a narrower bit depth, the wrong codec, the wrong channel count. This is the check that makes the output trustworthy.

**Did we get the level we asked for?** That is a different question with a different answer per waveform, because a sampled sine only reaches its amplitude when a sample lands on its crest. The worst case over phase leaves the largest sample at `cos(pi * f / sr)` of full amplitude, and that is the bound the check uses: 0.2% down at 1 kHz against 48 kHz, 50% down at 16 kHz.

What a given frequency actually loses is a separate matter, and it is not simply whether the frequency divides the sample rate. The crest sits at phase `pi/2`, so a sample lands on it exactly when `sr / (4 * f)`, in lowest terms, has an odd denominator. All six default frequencies satisfy that at 48 kHz and lose nothing at all. 1600 Hz divides 48 kHz exactly 30 times and still peaks 0.55% low, because `48000 / 6400` is 15/2. 16 kHz peaks 13.40% low. Both of those are correct files, not faults.

So the requested level is bracketed rather than matched. A peak louder than requested is a synthesis error and fails. A peak below the bound for that waveform at that frequency is a fault and fails. A peak between the two is reported, with the shortfall printed once it reaches 0.01%, so an unlucky frequency is visible rather than silent.

The predecessor to this script compared every peak against the requested level within 0.0005. That worked only because every frequency it shipped happens to land a sample on the crest at 48 kHz, and it would have rejected a correct file the moment a caller asked for a frequency of its own.

The hard-panned files get one check more: the loud channel must hold the level and the silent channel must read exactly zero. That exists because taking the first channel's peak once reported zero for `pan-hard-right` and looked like a generator failure, and because a plugin that taps only channel 0 is precisely what the pan pair is there to catch.

Output is one line per file:

```text
wrote ./level-2.000.wav  (20.00 s @ 48000 Hz, 32-bit float)  peak 2.000000
wrote ./pan-hard-right.wav  (20.00 s @ 48000 Hz, 32-bit float)  peak 0.500000, left silent
wrote ./sine-16000hz-0.5.wav  (0.50 s @ 48000 Hz, 32-bit float)  peak 0.433013, 13.40% under 0.5
```

Any failure exits 1 with a message naming the file, what it holds and what was expected. Nothing partial is reported as written.

## Worked example

The signal set this tool was adopted from belongs to [cboone/fosforo](https://github.com/cboone/fosforo), an oscilloscope plugin. Its two plugin-specific parameters are levels, not structure:

```bash
uv run maketones.py --outdir ~/Music/fosforo-test-tones \
  --levels 0.002 0.010 0.100 0.500 1.000 1.050 1.089 2.000 \
  --saws 0.900 1.100
```

`1.089` is `trace_rail / trace_full_scale`, or `0.98 / 0.9`, from that plugin's `src/gpu/iface.zig`: the ratio at which its trace stops climbing. `1.050` is the last level below it that does not rail and `1.089` is the first that does, so the pair brackets the threshold. Note that it is a bracket and not a symmetric one; `1.089` clears `1.08889` by 0.0001, and what the pair makes observable is the peak ceasing to climb rather than any visible flattening. The saws at `0.900` and `1.100` straddle the same threshold, and the `0.002` floor is the level below which a sine moves that plugin's trace less than one backing pixel.

None of those numbers are defaults here, and no other instrument should expect them to be. That is what the flags are for.

## Findings

The port was validated against the 20 files the original bash-and-ffmpeg script left on disk. Rendering with the parameters above reproduces all 20 filenames, and every file is **bit-identical** to its ffmpeg counterpart, saws and gated transients included. That was more than expected: ffmpeg's `mod()` and numpy's `%` need not round a sample sitting exactly on a discontinuity the same way, and here they do.

`level-2.000.wav` reads back as WAV format tag 3 at 32 bits, 48 kHz, two channels, with 1,272,000 of its 1,920,000 samples above unity.

Four injected faults each fail with exit 1: writing `int16`, clamping to unity, rendering a pan file into both channels, and rendering a level louder than requested.

## Limitations

- **Peak amplitude is the only thing verified.** Nothing checks the frequency of what was written, so a synthesis bug that produced the right peak at the wrong frequency would pass. Counting periods on a display is currently the only thing that catches that.
- **The lower bound is loose at high frequencies.** `cos(pi * f / sr)` is the worst case over phase, and a real file usually lands much closer to the crest than that: at 16 kHz against 48 kHz the bound allows 50% while the actual peak is 13.40% low. The bound never rejects a correct file, which is what it is for; it is not a tight estimate.
- **Nothing fades.** These signals hold an exact peak for their whole length on purpose, so they start and stop abruptly. That is correct for a level check and wrong for anything measuring a transfer function, where the discontinuity is itself broadband content. `tools/sampler-nulltest/maketest.py` is the tool for that case, and it fades for exactly this reason.
- **There is no test suite.** See `CLAUDE.md` for how to validate a change.
