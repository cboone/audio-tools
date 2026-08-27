# Sampler transparency null test

Does a sampler pass a sample through unaltered when every control is nominally off? Not "do these two files sound similar": the question is whether the difference is *zero*, and if not, exactly what non-zero thing it is.

Written against Logic Pro's Sampler and Quick Sampler, but nothing in the analysis is Logic-specific.

## Findings

Measured against Logic Pro 12.3.1, with the project and the probe both at 48 kHz, the sample at its root key, filter off, envelope flat, and the result bounced to 32-bit float via Bounce Region or Section. The version matters for the Bounce In Place behavior below, which is a defect rather than a design decision and may not survive.

**Sampler and Quick Sampler are bit-transparent.** Both return the source unaltered, sample for sample, and they are bit-identical to each other, so there is no transparency reason to prefer one over the other.

The only control that broke transparency was **MIDI note velocity**. It applies a pure scalar gain and does nothing else: no resampling, no filtering, no envelope shaping, no dither, no nonlinearity. At velocity 80 the gain measured -6.8116 dB, a factor of 0.4564784468, and the residual after removing that one scalar was half a float32 ULP. At velocity 127 both instruments are bit-identical to the source.

This is worth calling out because velocity is never "nominally off". A drawn note carries whatever velocity it was drawn with, and that silently scales the output while looking like nothing at all.

One data point does not determine the velocity curve. Fitting `gain = (v/127)**k` gives `k = 1.697`, so the mapping is neither linear in amplitude nor square-law, but that is a fit rather than a determination: a sensitivity parameter cannot be separated from the exponent without bouncing at several velocities.

Two incidental findings about the bounce path itself:

- **Bounce In Place truncates to 24-bit**, with the recording preference set to 32-bit float and the bounce dialog set to 32-bit float, so it appears to honor neither. The error is strictly non-negative and uniform on `[0, 1)` LSB, which is `floor()` rather than rounding, and no dither is applied. That leaves a DC offset near -145 dBFS and an error correlated with the signal. Inaudible, but it puts a floor under every measurement, so use Bounce Region or Section.
- **Bounce Region or Section is bit-identical**, which is what makes the control test in the procedure worth running at all.

These results hold for this configuration only. Transposition away from the root key, looping and loop crossfades, a sample rate that differs from the project, and Flex are all separate questions, and each one needs its own run.

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

## Procedure

### Step 0: prove the bounce chain before measuring the sampler

Load `probe_noise.wav` onto a plain audio track at unity, bounce it, and null that against the source. No sampler involved.

This is not a formality. It separates "the sampler changed my sample" from "my bounce chain changed my sample", and those two look identical in the residual. Skip it and you can spend a long time attributing pan law or dither to the instrument. Repeat it whenever the project or its settings change.

A pass reads like this:

```text
VERDICT: bit-identical. The sampler is transparent.
         Every sample that lines up matches. What differs is a 1-to-2 channel
         expansion, every bounce channel matching the source exactly.
```

Anything else is the chain, not the instrument. Likely causes in rough order of frequency: pan law, dither, project rate not matching the file, a plugin on the output, a fader not quite at 0.0.

### Step 1: match the sample rate

Check the project rate first, then generate probes to match. A mismatch forces SRC and you will be measuring the sample rate converter rather than the sampler.

```bash
uv run maketest.py --sr 48000 --outdir probe-48000
```

### Step 2: set up the instrument

Work through the [Logic-side checklist](#logic-side-checklist) below. The entries that most often bite:

- **Set the note velocity to 127.** This is the one that actually broke transparency in practice, and it is worth doing first. Velocity is never "nominally off": a drawn note simply carries whatever velocity it was drawn with, and that silently scales the output. Zeroing the instrument's velocity sensitivity would work too, but the note velocity is a control you can always find, and at maximum velocity the mapping is at unity regardless of how the sensitivity is set.
- Pan law at 0 dB. A compensated setting subtracts level from a centered signal, and that looks exactly like the sampler applying a gain.
- Play the zone's root key. Any other note is transposition, which is resampling wearing a different hat.
- Flex off, and Quick Sampler's import-time gain optimization off. Drop the sample on **Original**, not Optimized.
- A MIDI note comfortably longer than the probe, so you are not measuring the release stage.

### Step 3: bounce

Use **Bounce Region or Section**, not Bounce In Place. BIP was measured writing truncated 24-bit output while the recording preference was set to 32-bit float and the bounce dialog was set to 32-bit float, so it appears to ignore both. The signal survives it exactly, but the requantization puts a floor under every measurement for no reason. Bounce Region or Section honors the dialog and comes back bit-identical.

WAV, 32-bit float, sample rate equal to the project rate, dithering off, normalize off. Offline rather than realtime, since offline is deterministic and realtime can vary between runs. Bypass any monitoring plugin on the output, such as a headphone room simulator, rather than trusting it to exclude itself from an offline render.

A start offset, trailing silence, and a mono probe coming back stereo are all fine. The analysis removes the offset, trims to the overlap, and compares each channel separately, and none of those differences costs a pass.

Mono or stereo makes no difference to the verdict, and stereo is marginally the better test: it exercises both sides of the path at once, so a pan-law error or a one-sided polarity flip shows up where a mono bounce would hide it. Logic follows the channel strip's output format, so a strip feeding the stereo bus bounces stereo. Feed a single output instead if you want mono.

### Step 4: read the result

```bash
uv run nulltest.py probe-48000/probe_noise.wav bounce.wav -o sampler.png
```

- **Bit-identical**, with or without offsets named in the verdict: done. The sampler is transparent under those settings.
- **Fractional delay near zero and `|B/A|` flat at 0 dB**: transparent apart from level. Read `level` for how much.
- **Fractional delay non-zero plus a cliff below Nyquist**: sample rate conversion or transposition. The cliff is the anti-imaging filter.
- **Fractional delay non-zero but `|B/A|` flat**: more likely a minimum-phase filter's group delay than resampling. The panel is what tells them apart.
- **Residual concentrated at the very start and end, flat in between**: declick fades at the zone boundaries, not a global change. This is why the residual time panel earns its place even though it is a solid block for stationary noise.
- **Residual raised, `|B/A|` flat, correlation short of 1**: nonlinearity, so saturation or clipping somewhere. The linear model has nothing to say about it, which is itself the finding.

### Step 5: then the real sample

If the noise probe came back bit-identical, stop. That result closes the configuration: there is no residual left for another probe to characterize, so the sweep, the click and the real sample can tell you nothing further about it. Move on to a configuration that has not been tested instead.

Otherwise, characterize the instrument with the noise probe first, then run the actual sample through as confirmation. The reason is in [Use noise, not a kick](#use-noise-not-a-kick) below.

`probe_click.wav` is worth a run when something did change. Its output is literally the impulse response of whatever the sampler did, so smearing of one sample into a longer blob is direct visual evidence of filtering or resampling, with no interpretation needed.

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
- Velocity-to-amplitude scaling. Measured as the one that actually breaks transparency in practice, so trigger at 127. A note drawn at the default velocity of 80 cost 6.8116 dB.
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
