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

Both scripts carry [PEP 723](https://peps.python.org/pep-0723/) inline dependency metadata, so `uv` builds the environment on first run and there is nothing to install.

```bash
# Generate probes at your project's sample rate.
uv run maketest.py --sr 44100 --outdir probe-44100

# Compare a bounce against the source that produced it.
uv run nulltest.py source.wav bounced.wav -o nulltest.png
```

Both are executable, so `./nulltest.py source.wav bounced.wav` works as well.

`nulltest.py` prints its findings and writes a four-panel PNG. `--floor` sets the level below the source's own spectral peak at which a bin stops counting as signal, default -60 dB.

`soundfile` is a declared dependency because a DAW bounce is not always a plain WAV: libsndfile reads AIFF and CAF as well, and takes the LIST, bext and iXML chunks Logic writes in its stride. `scipy.io.wavfile` stays as a fallback for environments without it, and both paths scale integer PCM by the same factor, so a verdict never depends on which one is in play.

The committed `probe/` directory is 48 kHz. Point `--outdir` somewhere else when generating at another rate, rather than mixing rates in one directory.

## Method

A null test is not a general A/B comparison, and the difference matters. In a general comparison you divide out level and time offset as nuisances so you can see the shape difference underneath. In a transparency test, level and time offset *are* findings. So `nulltest.py` measures both and reports them, applies integer-sample alignment only (because you cannot compute a residual at all without it), and never applies the gain correction.

Four things get separated.

**Bit-identity.** Tested per channel pair after integer alignment, rather than on whole arrays. Whole-array equality would make any difference in shape disqualifying, and three of those are routine and mean nothing on their own: a start offset, a bounce region running past the end of the sample, and a mono sample coming back on a stereo bus. A difference in stored format is equally uninteresting, since a 24-bit source and a 32-bit float bounce holding the same values differ in container, not in signal. What matters is whether every sample that lines up matches, so that is what gets tested, and the verdict then names whichever of those differences was present. This is the only unambiguous pass. Everything below is forensics on a failure.

**Integer-sample lag.** Found by FFT cross-correlation. Harmless in itself: it is playback start offset or plugin delay compensation.

**Fractional lag.** Estimated from the slope of the cross-spectrum phase, run after integer alignment so `|tau| < 1` sample and the phase never wraps. This is the tell-tale of sample rate conversion or transposition. A minimum-phase filter's group delay registers the same way, so a non-zero fractional lag is a prompt to check the transfer function, not a conclusion.

**Gain and filtering.** Read off the estimated transfer function `H = B/A`, computed only in bins where the source has energy above the floor. Flat at 0 dB with zero phase means transparent. A cliff below Nyquist is an SRC anti-imaging filter. A tilt is frequency-dependent gain.

### Two residual signatures to recognize

A pure fractional time offset gives a residual that rises at a clean +6 dB/octave, because `a(t) - a(t-tau)` approximates `tau * da/dt` and differentiation is a 6 dB/oct tilt. The plot draws that reference slope. A residual parallel to it means "same signal, sub-sample offset", not "the sampler added noise".

A pure gain error gives a residual that is a scaled copy of the source spectrum, parallel to the source curve rather than to the 6 dB/oct guide.

### Use noise, not a kick

`H = B/A` is only defined where `A` has energy. A kick sample has essentially everything below a few hundred Hz plus a brief click, so it cannot tell you what the sampler does at 8 kHz. Load `probe/probe_noise.wav` into the sampler with the settings under test and bounce that: noise excites every bin and the transfer function becomes fully defined. Characterize the instrument with the probe first, then run the real sample through as confirmation.

When the transfer function is not flat, no single gain figure can describe what happened, because one number cannot summarize a frequency-dependent change. Read the panel instead.

## Reading the output

Delays are signed so that **positive means the bounce arrives late**, and both the integer and the fractional figure use that convention, so they can be read together and added.

Every channel is reported separately and nothing is downmixed, because a pan-law error or a one-sided polarity flip is exactly what averaging the channels together would hide. When the channel counts differ, which is what a mono sample played through a stereo instrument gives you, the single source channel is compared against each bounce channel in turn. The plot shows whichever channel has the largest residual.

There are two gain figures, and they answer different questions.

**`level (rms b/a)`** is the plain RMS ratio. It stays unbiased whatever else changed, so it is the real answer to "how much louder or quieter is the bounce".

**`best-fit gain`** is the least-squares scalar `h` minimizing `norm(b - h*a)`: the single number that best explains the bounce as a rescaled source. It works out to `correlation * level`, so anything a scalar cannot account for pulls it toward zero.

When correlation reads `1.00000000` the two agree and either one is the answer. When it does not, the gap between them is itself the finding, and the script says so. A 16 kHz lowpass reports a level of `-1.77 dB` against a best-fit gain of `-4.93 dB`, and neither number is a useful summary of what a brick-wall filter did. Read `|B/A|` instead.

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

## Limitations

- `|B/A|` comes from a single FFT over the whole file rather than a Welch average, so the estimate is noisy for short or non-stationary sources. The probe signals are long and stationary precisely to avoid this.
- The transfer function is a linear model. Nonlinearity such as clipping or saturation lifts the residual without producing any clean `H` to read, so the signature to watch for is an elevated residual alongside a flat `|B/A|` and a correlation short of 1.
- The integer delay is measured once from the channel mean and applied to every channel. Per-channel delay differences beyond that get absorbed into each channel's fractional figure, which is only meaningful within plus or minus one sample.
- The overlay and residual panels plot the whole file, which is a solid block for anything long and stationary. For a noise probe the printed numbers carry the finding, not those two panels.
