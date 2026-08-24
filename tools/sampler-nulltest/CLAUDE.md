# Sampler transparency null test

Read `README.md` first. It carries the problem statement, the method and why it is shaped that way, the Logic-side checklist, and the confirmed reporting defects in `nulltest.py`.

## Notes for agents

- Do not "fix" the analysis by applying the gain correction or the fractional-delay correction. Level and time offset are the findings here, not nuisances to divide out. See the Method section of `README.md`.
- There is no test suite. Validate any change by generating synthetic source/bounce pairs (identical, gain-shifted, fractionally delayed, band-limited, polarity-inverted, integer-delayed) and confirming the printed analysis identifies each one.
- `probe/*.wav` are committed build artifacts, reproducible from `maketest.py --sr 48000`. `probe_noise` and `probe_click` regenerate bit-identically. `probe_sweep` varies by roughly one float32 ULP on a handful of samples, depending on the libm behind `numpy`.
- System `python3` has no `scipy`. Use the `uv run --with ...` invocations shown in `README.md`.

## Status

The analysis is validated against synthetic cases only. It has not yet been run against an actual Logic bounce. The next step is to generate probes at the project's sample rate, load them into the sampler under test, bounce, and run `nulltest.py`.
