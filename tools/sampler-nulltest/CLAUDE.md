# Sampler transparency null test

Read `README.md` first. It carries the problem statement, the method and why it is shaped that way, the Logic-side checklist, and the confirmed reporting defects in `nulltest.py`.

## Notes for agents

- Do not "fix" the analysis by applying the gain correction or the fractional-delay correction. Level and time offset are the findings here, not nuisances to divide out. See the Method section of `README.md`.
- There is no test suite. Validate any change by generating synthetic source/bounce pairs and confirming the printed analysis identifies each. The cases that have caught real defects so far: identical, gain-shifted, fractionally delayed, integer-delayed both early and late, band-limited, polarity-inverted, trailing silence appended, int16 source against a float32 bounce holding the same values, stereo with opposite half-dB errors per channel, stereo with polarity inverted on one side only, and a mono source against a stereo bounce.
- Both gain figures are reported on purpose. `level` is the RMS ratio and `best-fit gain` is the least-squares scalar, and they diverge by exactly the correlation. Do not collapse them back into one number: a single figure is how a level drop previously got reported as a boost.
- `probe/*.wav` are committed build artifacts, reproducible from `maketest.py --sr 48000`. `probe_noise` and `probe_click` regenerate bit-identically. `probe_sweep` varies by roughly one float32 ULP on a handful of samples, depending on the libm behind `numpy`.
- The scripts carry PEP 723 inline metadata and a `uv run --script` shebang, so `uv run nulltest.py ...` or `./nulltest.py ...` needs no environment setup. System `python3` has no `scipy`, so plain `python3 nulltest.py` will fail.

## Status

The analysis is validated against synthetic cases only. It has not yet been run against an actual Logic bounce. The next step is to generate probes at the project's sample rate, load them into the sampler under test, bounce, and run `nulltest.py`.
