# Sampler transparency null test

Read `README.md` first. It carries the problem statement, the method and why it is shaped that way, the Logic-side checklist, and the confirmed reporting defects in `nulltest.py`.

## Notes for agents

- Do not "fix" the analysis by applying the gain correction or the fractional-delay correction. Level and time offset are the findings here, not nuisances to divide out. See the Method section of `README.md`.
- There is no test suite. Validate any change by generating synthetic source/bounce pairs and confirming the printed analysis identifies each. The cases that have caught real defects so far: identical, gain-shifted, fractionally delayed, integer-delayed both early and late, band-limited, polarity-inverted, trailing silence appended, int16 source against a float32 bounce holding the same values, stereo with opposite half-dB errors per channel, stereo with polarity inverted on one side only, a mono source against a stereo bounce that differs, and a mono source against a stereo bounce that is exact.
- That last case is the one that got shipped broken. A pass must survive every combination of start offset, trailing length, channel expansion and stored format, because a real Logic bounce arrives with several of them at once and none of them is a change to the signal. Test the combination, not each difference on its own.
- Both gain figures are reported on purpose. `level` is the RMS ratio and `best-fit gain` is the least-squares scalar, and they diverge by exactly the correlation. Do not collapse them back into one number: a single figure is how a level drop previously got reported as a boost.
- `probe/*.wav` are committed build artifacts, reproducible from `maketest.py --sr 48000`. `probe_noise` and `probe_click` regenerate bit-identically. `probe_sweep` varies by roughly one float32 ULP on a handful of samples, depending on the libm behind `numpy`.
- The scripts carry PEP 723 inline metadata and a `uv run --script` shebang, so `uv run nulltest.py ...` or `./nulltest.py ...` needs no environment setup. System `python3` has no `scipy`, so plain `python3 nulltest.py` will fail.

## Status

Validated against synthetic cases, and against one real Logic bounce: `probe_noise.wav` on a plain audio track at 48 kHz, bounced to 32-bit float, came back bit-identical on both channels of the stereo output bus. That run is the control test. It establishes that the bounce chain itself is transparent, so anything a later measurement turns up belongs to the instrument rather than to the export, and it is worth repeating whenever the project or its settings change.

The sampler itself has not been measured yet. The next step is to load the probe into Sampler or Quick Sampler with the checklist in `README.md` satisfied, trigger it at the zone's root key, bounce, and compare.
