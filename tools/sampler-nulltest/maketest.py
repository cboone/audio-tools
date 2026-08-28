#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""
maketest.py: generate probe signals for a sampler transparency test.

Usage:  uv run maketest.py [--sr 48000] [--outdir .]

Writes three 32-bit float WAVs:

  probe_noise.wav   2 s of white noise. Excites every FFT bin, so the estimated
                    transfer function B/A is defined across the whole spectrum.
                    This is the file to load into the sampler.
  probe_sweep.wav   8 s logarithmic sine sweep, 20 Hz to just under Nyquist.
                    Concentrates energy per frequency rather than spreading it,
                    so it reveals narrow features and nonlinearity that noise
                    can smear. Slower to run but higher resolution.
  probe_click.wav   Single-sample impulse with silence around it. Any smearing
                    of this into a longer blob is direct visual evidence of
                    filtering or resampling.

32-bit float is deliberate: it removes quantization from the comparison
entirely, so anything the null test finds came from the sampler and not from
the file format. Match --sr to your Logic project's sample rate. A mismatch
forces sample rate conversion and is itself the most common cause of a failed
transparency test.
"""

import argparse
import os

import numpy as np
from scipy.io import wavfile


def fade(x, sr, ms=10.0):
    """Apply a short raised-cosine fade to both ends.

    Without this, the abrupt start and end are themselves broadband impulses;
    they would show up in the analysis as content the sampler did not create."""
    n = int(sr * ms / 1000.0)
    if n * 2 >= len(x):
        return x
    ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, n)))
    x = x.copy()
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x


def white_noise(sr, seconds=2.0, peak_dbfs=-6.0, seed=1):
    """Gaussian white noise scaled to peak at peak_dbfs, then faded at both ends.

    Scaling by observed peak rather than by standard deviation matters here:
    Gaussian samples have unbounded tails, so a sigma-based scaling would
    occasionally clip, and clipping is a nonlinearity that would contaminate
    the very measurement we are making.

    The scaling happens before the fade, so the guarantee is "no louder than
    peak_dbfs" rather than "exactly peak_dbfs": a peak landing inside either
    10 ms ramp would come out slightly under. With the default seed it does
    not, and the committed 48 kHz probe measures exactly -6.000 dBFS. Fading
    first and scaling afterwards would make the peak exact, but it would also
    change the generated samples, and the committed probes are the files real
    bounces were made from."""
    x = np.random.default_rng(seed).standard_normal(int(sr * seconds))
    x *= 10.0 ** (peak_dbfs / 20.0) / np.max(np.abs(x))
    return fade(x, sr)


def log_sweep(sr, seconds=8.0, f0=20.0, peak_dbfs=-6.0):
    """Exponential (log) sine sweep from f0 to just below Nyquist.

    Instantaneous frequency rises geometrically, so the phase is the integral
    of that exponential, hence the closed form below rather than a naive
    cumulative sum. Stopping at 0.95*Nyquist avoids the sweep running into the
    anti-alias region where any reconstruction filter, including a correct
    one, will legitimately attenuate."""
    f1 = 0.95 * sr / 2.0
    t = np.arange(int(sr * seconds)) / sr
    T = seconds
    k = np.log(f1 / f0)
    phase = 2.0 * np.pi * f0 * T / k * (np.exp(t * k / T) - 1.0)
    x = np.sin(phase) * 10.0 ** (peak_dbfs / 20.0)
    return fade(x, sr, ms=25.0)


def click(sr, seconds=0.5, peak_dbfs=-6.0):
    """One nonzero sample, centered in silence: a discrete-time impulse.

    Its spectrum is flat by construction, and its time-domain response after
    passing through the sampler is literally the impulse response of whatever
    the sampler did."""
    x = np.zeros(int(sr * seconds))
    x[len(x) // 2] = 10.0 ** (peak_dbfs / 20.0)
    return x


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sr", type=int, default=48000,
                   help="sample rate; MATCH YOUR LOGIC PROJECT")
    p.add_argument("--outdir", default=".")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    for name, sig in (("probe_noise", white_noise(args.sr)),
                      ("probe_sweep", log_sweep(args.sr)),
                      ("probe_click", click(args.sr))):
        path = os.path.join(args.outdir, f"{name}.wav")
        wavfile.write(path, args.sr, sig.astype(np.float32))
        print(f"wrote {path}  ({len(sig)/args.sr:.2f} s @ {args.sr} Hz, 32-bit float)")


if __name__ == "__main__":
    main()
