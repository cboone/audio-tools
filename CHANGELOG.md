# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tools/sampler-nulltest`: null test measuring whether a bounce is a bit-transparent pass-through of its source, and if not, what changed. Reports integer and fractional delay, two gain figures, correlation and the estimated transfer function, and writes a four-panel plot when there is a residual. Ships with `maketest.py` and committed 48 kHz probes.
- `tools/test-signals`: generator for exact tones, levels, pans and transients, reading every file back after writing it to prove it holds what was asked for. Renders 32-bit float so levels above full scale survive.
