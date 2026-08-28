# Sampler transparency null test

Read `README.md` first. It carries the problem statement, the step-by-step procedure for running a test against Logic, the method and why it is shaped that way, the Logic-side checklist, and the known limitations.

The procedure opens with a control test: bounce the probe through a plain audio track with no sampler involved, and confirm that nulls, before measuring any instrument. Do not let anyone skip it. A bounce chain fault and a sampler fault look identical in the residual, and without the control there is nothing to tell them apart.

## Notes for agents

- Do not "fix" the analysis by applying the gain correction or the fractional-delay correction. Level and time offset are the findings here, not nuisances to divide out. See the Method section of `README.md`.
- There is no test suite. Validate any change by generating synthetic source/bounce pairs and confirming the printed analysis identifies each. The cases that have caught real defects so far: identical, gain-shifted, fractionally delayed, integer-delayed both early and late, band-limited, polarity-inverted, trailing silence appended, int16 source against a float32 bounce holding the same values, stereo with opposite half-dB errors per channel, stereo with polarity inverted on one side only, a mono source against a stereo bounce that differs, a mono source against a stereo bounce that is exact, a 2-channel source against a 3-channel bounce whose extra channel carries content, the same with the extra channel silent, a dual-mono 2-channel source folded down to 1 channel, a true-stereo source folded down to 1 channel, a 3-channel source against a 2-channel bounce, and an anti-phase stereo bounce carrying a real integer delay.
- That last case guards the delay estimate. It is measured on the channel pair where both sides carry the most energy, not on the channel mean, because anti-phase channels cancel in the mean and leave the cross-correlation reading digital silence. It then returns a delay of zero and every per-channel figure downstream is measured against a misalignment. Do not simplify that back to a mean.
- Two of those got shipped broken, both the same mistake in different dimensions. A pass must survive every combination of start offset, trailing length, channel count and stored format, because a real Logic bounce arrives with several at once and none is a change to the signal. But a pass must never be granted over data nobody looked at: pairing only `min(na, nb)` channels once let a bounce with an unexamined third channel of unrelated noise be called bit-identical. Test the combination, not each difference on its own, and check that the verdict's claims cover every channel it implicates.
- Both gain figures are reported on purpose. `level` is the RMS ratio and `best-fit gain` is the least-squares scalar, and they diverge by exactly the correlation. Do not collapse them back into one number: a single figure is how a level drop previously got reported as a boost.
- `probe/*.wav` are committed build artifacts, reproducible from `maketest.py --sr 48000`. `probe_noise` and `probe_click` regenerate bit-identically. `probe_sweep` varies by roughly one float32 ULP on a handful of samples, depending on the libm behind `numpy`.
- The scripts carry PEP 723 inline metadata and a `uv run --script` shebang, so `uv run nulltest.py ...` or `./nulltest.py ...` needs no environment setup. System `python3` has no `scipy`, so plain `python3 nulltest.py` will fail.

## Status

The question this tool was built to answer has been answered. See the Findings section of `README.md` for the result: both Logic samplers are bit-transparent at the root key with velocity at 127, they are bit-identical to each other, and MIDI note velocity was the only control that broke transparency. Validated against synthetic cases first, then against real Logic bounces throughout.

A bit-identical result closes a configuration completely. There is no residual left for another probe to characterize, so running the sweep or the click against a configuration that already nulled adds nothing. `probe_sweep.wav` and `probe_click.wav` remain unused for that reason, not because they were skipped.

Open questions, each needing its own run because each exercises a different code path: transposition away from the root key, looping and loop crossfades, a sample whose rate differs from the project, and Flex. The tool is validated against real bounces and ready for any of them.

Two things to keep in mind when extending this work. Repeat the control test whenever the project or its settings change, since it is cheap and it once retroactively cleared a monitoring plugin that had been loaded on the output the whole time. And bounce with Bounce Region or Section rather than Bounce In Place, which was measured truncating to 24-bit regardless of the recording preference and the bounce dialog.
