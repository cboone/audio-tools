# Sampler transparency null test

Does a sampler pass a sample through unaltered when every control is nominally off? Not "do these two files sound similar": the question is whether the difference is *zero*, and if not, exactly what non-zero thing it is.

Written against Logic Pro's Sampler and Quick Sampler, but nothing in the analysis is Logic-specific.

## Contents

| Path          | Purpose                                                                                      |
| ------------- | -------------------------------------------------------------------------------------------- |
| `nulltest.py` | Compares a source WAV against a bounced WAV and reports what, if anything, changed.          |
| `maketest.py` | Generates the probe signals to feed the sampler.                                             |
| `probe/`      | Pre-generated probes at 48 kHz: noise, log sweep, single-sample impulse. Mono, 32-bit float. |

## Usage

Dependencies are `numpy`, `scipy`, and `matplotlib`. `soundfile` is used if present, and the scripts fall back to `scipy.io.wavfile` without it.

```bash
# Generate probes at your project's sample rate.
uv run --with numpy --with scipy maketest.py --sr 44100 --outdir probe-44100

# Compare a bounce against the source that produced it.
uv run --with numpy --with scipy --with matplotlib \
  nulltest.py source.wav bounced.wav -o nulltest.png
```

`nulltest.py` prints its findings and writes a four-panel PNG. `--floor` sets the level below the source's own spectral peak at which a bin stops counting as signal, default -60 dB.

The committed `probe/` directory is 48 kHz. Point `--outdir` somewhere else when generating at another rate, rather than mixing rates in one directory.

## Method

A null test is not a general A/B comparison, and the difference matters. In a general comparison you divide out level and time offset as nuisances so you can see the shape difference underneath. In a transparency test, level and time offset *are* findings. So `nulltest.py` measures both and reports them, applies integer-sample alignment only (because you cannot compute a residual at all without it), and never applies the gain correction.

Four things get separated.

**Bit-identity.** Checked first, on the arrays as loaded, before alignment or any other processing. This is the only unambiguous pass. Everything below is forensics on a failure.

**Integer-sample lag.** Found by FFT cross-correlation. Harmless in itself: it is playback start offset or plugin delay compensation.

**Fractional lag.** Estimated from the slope of the cross-spectrum phase, run after integer alignment so `|tau| < 1` sample and the phase never wraps. This is the tell-tale of sample rate conversion or transposition. A minimum-phase filter's group delay registers the same way, so a non-zero fractional lag is a prompt to check the transfer function, not a conclusion.

**Gain and filtering.** Read off the estimated transfer function `H = B/A`, computed only in bins where the source has energy above the floor. Flat at 0 dB with zero phase means transparent. A cliff below Nyquist is an SRC anti-imaging filter. A tilt is frequency-dependent gain.

### Two residual signatures to recognize

A pure fractional time offset gives a residual that rises at a clean +6 dB/octave, because `a(t) - a(t-tau)` approximates `tau * da/dt` and differentiation is a 6 dB/oct tilt. The plot draws that reference slope. A residual parallel to it means "same signal, sub-sample offset", not "the sampler added noise".

A pure gain error gives a residual that is a scaled copy of the source spectrum, parallel to the source curve rather than to the 6 dB/oct guide.

### Use noise, not a kick

`H = B/A` is only defined where `A` has energy. A kick sample has essentially everything below a few hundred Hz plus a brief click, so it cannot tell you what the sampler does at 8 kHz. Load `probe/probe_noise.wav` into the sampler with the settings under test and bounce that: noise excites every bin and the transfer function becomes fully defined. Characterize the instrument with the probe first, then run the real sample through as confirmation.

When the transfer function is not flat, the scalar gain figure the script prints is meaningless, because one number cannot describe a frequency-dependent change. Read the panel instead.

## Logic-side checklist

Things that break transparency with everything nominally off.

Signal path into and through the sampler:

- Sample rate mismatch between file and project forces SRC. This is the most common cause, and it is why `maketest.py` takes `--sr`. Match the project.
- The played note must equal the zone's root key, or you get transposition, which is resampling under another name.
- Quick Sampler does things on import that are not labeled as processing: gain optimization and normalization, declick fades at zone boundaries, loop crossfades. Flex mode time-stretches unconditionally, even at ratio 1.
- Amp envelope: a nominally instant attack may still be a short ramp.
- Velocity-to-amplitude scaling. Trigger at 127 and check the velocity-to-volume amount, or you are measuring the mod matrix.
- Filter genuinely bypassed, not just at maximum cutoff.

Channel strip and bounce:

- Fader at exactly 0.0, not -0.1. Pan centered. Check the project's pan law, because a compensated setting subtracts level from a centered signal.
- No region gain, no track plugins, master fader at unity.
- Bounce to 32-bit float with dither explicitly off. Logic's dither plants noise around -90 dBFS and will look like a mystery noise floor in the residual.

## Faster in-Logic version

You can null without exporting. Put the original file on one audio track at unity and the sampler on another, add a Gain plugin with polarity inverted on one of them, and sum. If the meter does not hit -inf, something is happening, and the reading tells you roughly how much. Use the scripts when you need to know *what*.

## Known issues

Confirmed by running the scripts against synthetic source/bounce pairs. The analysis itself is sound; these are reporting defects, and none of them affect the residual, which is computed correctly in every case tested.

- **`gain fit (a->b)` is biased upward and can invert the sign of a real level change.** The printed figure works out to `db(rms(b)/rms(a)) - db(correlation)`, and the second term is always positive, so any decorrelation inflates it. A 16 kHz lowpass that actually drops level by 1.76 dB reports `+1.39 dB`. A pure fractional delay, which changes level not at all, reports `+0.92 dB`. The figure is only trustworthy when correlation reads `1.00000000`.
- **`integer lag` uses the opposite sign convention from `residual sub-lag`.** A bounce arriving 100 samples late reports `integer lag: -100 samples`, while a bounce 0.25 samples late reports `residual sub-lag: +0.2500 samples`. Both describe the same physical direction. The alignment itself is correct; only the printed sign misleads.
- **The `|B/A|` panel is hard-clipped to plus or minus 6 dB.** A filter cliff, the exact signature the method tells you to look for, runs off the bottom of the axis. You can see that a cliff starts but not how deep or how steep it gets.
- **Bit-identity requires equal array lengths.** A bounce with trailing silence, which is routine in Logic, never earns the bit-identical verdict even when every overlapping sample is exact. It reports a residual RMS of -240 dBFS instead, which is the same finding stated less clearly.
- **Polarity inversion has no named verdict.** It shows up only as `correlation: -1.00000000`, alongside a gain fit of `+0.0000 dB` that reads as a pass.
- **Stereo files are mean-downmixed before analysis.** Anything channel-dependent, including the pan-law error the checklist above warns about, partly or wholly cancels in the mean.
- **The `raw` array used for the bit-identity check is not raw when `soundfile` is installed.** It is the float64 conversion, so the accompanying dtype guard is a no-op on that path. An int16 file and a float32 file holding equal values are called bit-identical with `soundfile` present and not without it.
