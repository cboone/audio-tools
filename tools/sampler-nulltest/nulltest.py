#!/usr/bin/env python3
"""
nulltest.py — is B a bit-transparent pass-through of A?

Usage:  python3 nulltest.py source.wav bounced.wav [-o out.png]

Intended for questions like "does Logic's Sampler alter my sample when every
control is nominally off?" The philosophy differs from a general A/B compare:
time offset and gain are MEASURED and REPORTED, not silently corrected, because
in a transparency test they are findings rather than nuisances.

The four things it separates:
  * bit-identity          — the only unambiguous pass
  * integer-sample lag    — playback start offset / PDC, harmless in itself
  * fractional lag        — a tell-tale of resampling or transposition
  * gain and filtering    — via a direct estimate of the transfer function B/A
"""

import argparse
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EPS = 1e-20


# ---------------------------------------------------------------- loading

def load(path):
    """Return (float64 samples in [-1,1] as (n, channels), sample_rate, raw).

    `raw` is the untouched array as stored, kept so we can test bit-identity
    before any conversion has a chance to introduce rounding of its own."""
    try:
        import soundfile as sf
        x, sr = sf.read(path, always_2d=True, dtype="float64")
        return x, sr, x
    except ImportError:
        from scipy.io import wavfile
        sr, raw = wavfile.read(path)
        if raw.ndim == 1:
            raw = raw[:, None]
        if np.issubdtype(raw.dtype, np.integer):
            x = raw.astype(np.float64) / np.iinfo(raw.dtype).max
        else:
            x = raw.astype(np.float64)
        return x, sr, raw


def db(x):
    """Amplitude ratio to dB with a floor, so digital silence reads as -240
    rather than -inf and doesn't blow up the plot limits."""
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def rms(x):
    return float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0


# ---------------------------------------------------------------- alignment

def integer_lag(a, b):
    """Lag in whole samples that best aligns b to a, by FFT cross-correlation.

    Zero-padded to len(a)+len(b) so the circular convolution implicit in the
    FFT does not wrap the tail of the correlation onto its head."""
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    xc = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    k = int(np.argmax(np.abs(xc)))
    return k - n if k > n // 2 else k


def shift_and_trim(a, b, lag):
    if lag > 0:
        b = np.concatenate([np.zeros(lag), b])
    elif lag < 0:
        b = b[-lag:]
    n = min(len(a), len(b))
    return a[:n], b[:n]


def fractional_lag(a, b, sr, floor_db=-60.0):
    """Estimate any residual sub-sample delay of b relative to a.

    If b(t) = a(t - tau) then B(f) = A(f)·exp(-j2*pi*f*tau), so the cross
    spectrum A·conj(B) has phase +2*pi*f*tau — a straight line through the
    origin whose slope gives tau directly. Run this only AFTER integer
    alignment: with |tau| < 1 sample the phase stays inside +/-pi even at
    Nyquist, so there is nothing to unwrap and the fit is robust.

    Weighted by |A|^2 so bins where the source has no energy — and therefore
    only noise-driven phase — contribute nothing."""
    n = len(a)
    A, B = np.fft.rfft(a), np.fft.rfft(b)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    mag = np.abs(A)
    keep = db(mag / max(mag.max(), EPS)) > floor_db
    if keep.sum() < 8:
        return 0.0
    phase = np.angle(A[keep] * np.conj(B[keep]))
    w = mag[keep] ** 2
    # Weighted least squares through the origin: slope = sum(w*x*y)/sum(w*x*x).
    slope = np.sum(w * f[keep] * phase) / max(np.sum(w * f[keep] ** 2), EPS)
    return slope / (2.0 * np.pi)          # seconds


def transfer_function(a, b, sr, floor_db=-60.0):
    """Estimate H = B/A where the source actually has energy.

    Dividing spectra is only meaningful above the source's own noise floor;
    elsewhere you are dividing noise by noise and get garbage that dominates
    the plot. A Hann window keeps each partial's leakage skirt from smearing
    energy into neighbouring bins and faking content that isn't there."""
    w = np.hanning(len(a))
    A, B = np.fft.rfft(a * w), np.fft.rfft(b * w)
    f = np.fft.rfftfreq(len(a), 1.0 / sr)
    mag = np.abs(A)
    keep = db(mag / max(mag.max(), EPS)) > floor_db
    H = np.full(len(f), np.nan, dtype=complex)
    H[keep] = B[keep] / A[keep]
    return f, H, keep


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    p.add_argument("a", help="source wav (what you fed the sampler)")
    p.add_argument("b", help="bounced wav (what came back out)")
    p.add_argument("-o", "--out", default="nulltest.png")
    p.add_argument("--floor", type=float, default=-60.0,
                   help="dB below source peak spectrum to ignore (default -60)")
    args = p.parse_args()

    xa, sra, rawa = load(args.a)
    xb, srb, rawb = load(args.b)
    if sra != srb:
        sys.exit(f"sample rates differ: {sra} vs {srb} — that alone is the answer")
    sr = sra

    # --- bit-identity, tested before anything else touches the data --------
    if (rawa.shape == rawb.shape and rawa.dtype == rawb.dtype
            and np.array_equal(rawa, rawb)):
        print("VERDICT: bit-identical. The sampler is transparent.")
        return

    a = xa.mean(axis=1)
    b = xb.mean(axis=1)
    print(f"lengths          : {len(a)} vs {len(b)} samples @ {sr} Hz")

    lag = integer_lag(a, b)
    a, b = shift_and_trim(a, b, lag)
    tau = fractional_lag(a, b, sr, args.floor)

    # Projection of a onto b: the single scalar closest to explaining b as a
    # rescaled a. Reported, deliberately NOT applied.
    g = float(np.dot(a, b) / max(np.dot(b, b), EPS))
    corr = float(np.dot(a, b) / max(np.sqrt(np.dot(a, a) * np.dot(b, b)), EPS))

    resid = a - b
    rel = db(rms(resid)) - db(rms(a))

    print(f"integer lag      : {lag} samples ({1000.0*lag/sr:+.4f} ms)")
    print(f"residual sub-lag : {tau*sr:+.4f} samples ({tau*1e6:+.2f} us)")
    print(f"gain fit (a->b)  : {db(1.0/g):+.4f} dB")
    print(f"correlation      : {corr:+.8f}")
    print(f"residual RMS     : {db(rms(resid)):.1f} dBFS  ({rel:+.1f} dB rel. source)")
    print(f"residual peak    : {db(np.max(np.abs(resid))):.1f} dBFS")
    if abs(tau * sr) > 0.1:
        print("  note: a sub-sample offset this large implies resampling or "
              "transposition — or a minimum-phase filter, whose group delay "
              "registers the same way. Check the |B/A| panel to tell them apart.")

    # ------------------------------------------------------------- plotting
    t = np.arange(len(a)) / sr * 1000.0
    fig, ax = plt.subplots(2, 2, figsize=(13, 7.5))

    ax[0, 0].plot(t, a, lw=0.8, label="source")
    ax[0, 0].plot(t, b, lw=0.8, alpha=0.7, label="bounce")
    ax[0, 0].set(title=f"Overlay after {lag}-sample alignment",
                 xlabel="ms", ylabel="amplitude")
    ax[0, 0].legend(fontsize=8)

    ax[0, 1].plot(t, resid, lw=0.8, color="crimson")
    ax[0, 1].set(title=f"Residual, peak {db(np.max(np.abs(resid))):.1f} dBFS "
                       f"({rel:+.1f} dB rel. source)", xlabel="ms")
    ax[0, 1].set_ylim(ax[0, 0].get_ylim())   # same scale, so small looks small

    # Residual spectrum against the source, with a 6 dB/oct guide. A residual
    # parallel to that guide is a pure fractional delay (the difference of two
    # slightly shifted copies approximates a derivative); a residual parallel
    # to the source itself is a pure gain error.
    w = np.hanning(len(a))
    f = np.fft.rfftfreq(len(a), 1.0 / sr)
    Sa = np.abs(np.fft.rfft(a * w))
    Sr = np.abs(np.fft.rfft(resid * w))
    ref = max(Sa.max(), EPS)
    ax[1, 0].semilogx(f, db(Sa / ref), lw=0.8, label="source")
    ax[1, 0].semilogx(f, db(Sr / ref), lw=0.8, color="crimson", label="residual")
    guide = db(Sr / ref)[np.argmin(np.abs(f - 1000.0))]
    ax[1, 0].semilogx(f[1:], guide + 20 * np.log10(f[1:] / 1000.0),
                      ls=":", lw=0.9, color="gray", label="+6 dB/oct")
    ax[1, 0].set(title="Residual vs. source spectrum", xlabel="Hz", ylabel="dB",
                 xlim=(20, sr / 2), ylim=(-160, 5))
    ax[1, 0].legend(fontsize=8)

    fh, H, keep = transfer_function(a, b, sr, args.floor)
    axr = ax[1, 1]
    axr.semilogx(fh[keep], db(np.abs(H[keep])), lw=0.7, color="navy")
    axr.axhline(0.0, ls=":", lw=0.9, color="gray")
    axr.set(title="Estimated transfer function |B/A| (flat 0 dB = transparent)",
            xlabel="Hz", ylabel="dB", xlim=(20, sr / 2), ylim=(-6, 6))
    axp = axr.twinx()
    axp.semilogx(fh[keep], np.degrees(np.angle(H[keep])), lw=0.5,
                 color="darkorange", alpha=0.6)
    axp.set_ylabel("phase (deg)", color="darkorange")
    axp.set_ylim(-180, 180)

    for row in ax:
        for cell in row:
            cell.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(args.out, dpi=140)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
