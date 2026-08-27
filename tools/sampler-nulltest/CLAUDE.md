# Sampler transparency null test

Read `README.md` first. It carries the problem statement, the step-by-step procedure for running a test against Logic, the method and why it is shaped that way, the Logic-side checklist, and the known limitations.

The procedure opens with a control test: bounce the probe through a plain audio track with no sampler involved, and confirm that nulls, before measuring any instrument. Do not let anyone skip it. A bounce chain fault and a sampler fault look identical in the residual, and without the control there is nothing to tell them apart.

## Notes for agents

- Do not "fix" the analysis by applying the gain correction or the fractional-delay correction. Level and time offset are the findings here, not nuisances to divide out. See the Method section of `README.md`.
- There is no test suite. Validate any change by generating synthetic source/bounce pairs and confirming the printed analysis identifies each. The cases that have caught real defects so far: identical, gain-shifted, fractionally delayed, integer-delayed both early and late, band-limited, polarity-inverted, trailing silence appended, int16 source against a float32 bounce holding the same values, stereo with opposite half-dB errors per channel, stereo with polarity inverted on one side only, a mono source against a stereo bounce that differs, and a mono source against a stereo bounce that is exact.
- That last case is the one that got shipped broken. A pass must survive every combination of start offset, trailing length, channel expansion and stored format, because a real Logic bounce arrives with several of them at once and none of them is a change to the signal. Test the combination, not each difference on its own.
- Both gain figures are reported on purpose. `level` is the RMS ratio and `best-fit gain` is the least-squares scalar, and they diverge by exactly the correlation. Do not collapse them back into one number: a single figure is how a level drop previously got reported as a boost.
- `probe/*.wav` are committed build artifacts, reproducible from `maketest.py --sr 48000`. `probe_noise` and `probe_click` regenerate bit-identically. `probe_sweep` varies by roughly one float32 ULP on a handful of samples, depending on the libm behind `numpy`.
- The scripts carry PEP 723 inline metadata and a `uv run --script` shebang, so `uv run nulltest.py ...` or `./nulltest.py ...` needs no environment setup. System `python3` has no `scipy`, so plain `python3 nulltest.py` will fail.

## Status

The question this tool was built to answer has been answered. See the Findings section of `README.md` for the result: both Logic samplers are bit-transparent at the root key with velocity at 127, they are bit-identical to each other, and MIDI note velocity was the only control that broke transparency. Validated against synthetic cases first, then against real Logic bounces throughout.

A bit-identical result closes a configuration completely. There is no residual left for another probe to characterize, so running the sweep or the click against a configuration that already nulled adds nothing. `probe_sweep.wav` and `probe_click.wav` remain unused for that reason, not because they were skipped.

Open questions, each needing its own run because each exercises a different code path: transposition away from the root key, looping and loop crossfades, a sample whose rate differs from the project, and Flex. The tool is validated against real bounces and ready for any of them.

Two things to keep in mind when extending this work. Repeat the control test whenever the project or its settings change, since it is cheap and it once retroactively cleared a monitoring plugin that had been loaded on the output the whole time. And bounce with Bounce Region or Section rather than Bounce In Place, which was measured truncating to 24-bit regardless of the recording preference and the bounce dialog.
