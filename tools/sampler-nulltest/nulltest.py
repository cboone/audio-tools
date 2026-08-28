#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy", "scipy", "soundfile"]
# ///
"""
nulltest.py: is B a bit-transparent pass-through of A?

Usage:  uv run nulltest.py source.wav bounced.wav [-o out.png]

Intended for questions like "does Logic's Sampler alter my sample when every
control is nominally off?" The philosophy differs from a general A/B compare:
time offset and gain are MEASURED and REPORTED, not silently corrected, because
in a transparency test they are findings rather than nuisances.

The four things it separates:
  * bit-identity          the only unambiguous pass
  * integer-sample delay  playback start offset / PDC, harmless in itself
  * fractional delay      a tell-tale of resampling or transposition
  * gain and filtering    via a direct estimate of the transfer function B/A

Two conventions, held to throughout:

  SIGN. Positive delay means the bounce arrives LATE relative to the source.
  Both the integer and the fractional figure use this, so they can be read
  together and added.

  CHANNELS. Every channel is analyzed separately and nothing is downmixed. A
  pan-law error or a one-sided polarity flip is exactly the kind of finding
  that averaging the channels together would hide.

`soundfile` is declared as a dependency because a DAW bounce is not always a
plain WAV: libsndfile reads AIFF and CAF too, and takes the LIST, bext and iXML
chunks Logic writes in its stride. `scipy.io.wavfile` remains a fallback for
environments without it. Both paths scale integer PCM by 2**(bits-1), so a
verdict never depends on which library happens to be present.
"""

import argparse
import os
import sys
import warnings

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

EPS = 1e-20


# ---------------------------------------------------------------- loading


def load(path):
    """Return (samples as (n, channels) float64 in [-1, 1], sample rate, subtype).

    Integer PCM is divided by 2**(bits-1) on both backends. scipy's own
    convention is to divide by iinfo.max, which is 2**(bits-1) - 1: a half-LSB
    difference, but enough to make a bit-identity test depend on which library
    happened to be importable. The conversion is exact either way, so comparing
    the float64 results is still a true test of sample equality.

    The stored subtype is returned rather than a raw array. A 24-bit source and
    a 32-bit float bounce holding the same values differ in format but not in
    signal, and for a transparency test that is a pass, not a failure."""
    # Deciding which backend to use is kept separate from reading the file, so
    # the two failures stay distinguishable. Import is caught broadly and not
    # just on ImportError: soundfile binds libsndfile through CFFI at import
    # time, so a missing or broken shared library arrives as OSError. Either way
    # the backend is unusable and scipy takes over, which is the entire point of
    # keeping a fallback. A failure from the READ is left to propagate, because
    # that one means the file is the problem rather than the backend, and main()
    # turns it into a clean message.
    try:
        import soundfile as sf
    except Exception:  # noqa: BLE001
        sf = None

    if sf is not None:
        x, sr = sf.read(path, always_2d=True, dtype="float64")
        return x, sr, sf.info(path).subtype

    from scipy.io import wavfile

    # A DAW writes chunks scipy has no opinion about (LIST, bext, iXML, cue
    # markers, and so on). Skipping them is correct here, since none of them
    # affect the sample data, so the warning is noise rather than news.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", wavfile.WavFileWarning)
        sr, raw = wavfile.read(path)
    if raw.ndim == 1:
        raw = raw[:, None]
    if raw.dtype == np.uint8:  # 8-bit PCM is unsigned
        x = (raw.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(raw.dtype, np.integer):
        x = raw.astype(np.float64) / (np.iinfo(raw.dtype).max + 1.0)
    else:
        x = raw.astype(np.float64)
    # Labelled as the decoded dtype rather than passed off as the container's
    # subtype, because on this path it is not one. scipy widens 24-bit PCM into
    # int32, so PCM_24 and PCM_32 both decode to int32: reporting that bare
    # would assert a stored format this path never read, and would also hide a
    # genuine difference between those two by giving them the same name.
    # Normalization is unaffected, since scipy leaves 24-bit data shifted into
    # the high bits and dividing by 2**31 recovers what 2**23 would.
    return x, sr, f"scipy:{raw.dtype}"


def db(x):
    """Amplitude ratio to dB with a floor, so digital silence reads as -240
    rather than -inf and doesn't blow up the plot limits. NaN is preserved, so
    bins deliberately excluded from an estimate stay excluded."""
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def rms(x):
    return float(np.sqrt(np.mean(x**2))) if x.size else 0.0


# ---------------------------------------------------------------- alignment


def integer_delay(a, b):
    """Delay of b relative to a in whole samples, by FFT cross-correlation.

    Positive means b arrives late. Zero-padded to len(a)+len(b) so the circular
    convolution implicit in the FFT does not wrap the tail of the correlation
    onto its head. The peak is taken on |xc| so a polarity-inverted bounce still
    aligns on its (negative) main peak instead of locking onto a sidelobe."""
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    xc = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    k = int(np.argmax(np.abs(xc)))
    shift = k - n if k > n // 2 else k
    return -shift


def align(a, b, delay):
    """Strip b's lead-in (or pad it) so the two line up, then trim to a common
    length. Accepts 1-D mono or (n, channels) arrays."""
    if delay > 0:
        b = b[delay:]
    elif delay < 0:
        b = np.concatenate([np.zeros((-delay, *b.shape[1:]), dtype=b.dtype), b])
    n = min(len(a), len(b))
    return a[:n], b[:n]


def fractional_delay(a, b, sr, floor_db=-60.0):
    """Estimate any residual sub-sample delay of b relative to a, in seconds.

    If b(t) = a(t - tau) then B(f) = A(f)*exp(-j2*pi*f*tau), so the cross
    spectrum A*conj(B) has phase +2*pi*f*tau: a straight line through the origin
    whose slope gives tau directly. Run this only AFTER integer alignment. With
    |tau| < 1 sample the phase stays inside +/-pi even at Nyquist, so there is
    nothing to unwrap and the fit is robust.

    Deliberately unwindowed. Windowing would suppress the edge discontinuity but
    would also break the exact b = delayed(a) relation inside the window, and
    measurement against known delays shows the unwindowed fit recovers tau to
    four decimal places.

    Weighted by |A|^2 so bins where the source has no energy, and therefore only
    noise-driven phase, contribute nothing."""
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
    return slope / (2.0 * np.pi)  # seconds


def transfer_function(a, b, sr, floor_db=-60.0):
    """Estimate H = B/A where the source actually has energy.

    Dividing spectra is only meaningful above the source's own noise floor;
    elsewhere you are dividing noise by noise and get garbage that dominates the
    plot. A Hann window keeps each partial's leakage skirt from smearing energy
    into neighboring bins and faking content that isn't there.

    Excluded bins are left as NaN rather than dropped, so a plot of the result
    breaks the trace across the gaps instead of drawing a straight line over
    them."""
    w = np.hanning(len(a))
    A, B = np.fft.rfft(a * w), np.fft.rfft(b * w)
    f = np.fft.rfftfreq(len(a), 1.0 / sr)
    mag = np.abs(A)
    keep = db(mag / max(mag.max(), EPS)) > floor_db
    H = np.full(len(f), np.nan, dtype=complex)
    H[keep] = B[keep] / A[keep]
    return f, H


# ---------------------------------------------------------------- analysis


def channel_pairs(xa, xb):
    """Decide which channel of the source to compare against which of the bounce.

    Returns (pairs, unpaired source channels, unpaired bounce channels). The
    leftovers are returned rather than silently dropped: a channel nobody
    compared must never be described as matching, and pairing only
    min(na, nb) of them would do exactly that for, say, a stereo source against
    a surround bounce.

    A mono sample coming back on a stereo bus is a normal sampler outcome rather
    than an error, so the single source channel is compared against every bounce
    channel and nothing is left over."""
    na, nb = xa.shape[1], xb.shape[1]
    if na == 1 and nb > 1:
        return [(f"ch{j}", xa[:, 0], xb[:, j]) for j in range(nb)], [], []
    if nb == 1 and na > 1:
        return [(f"ch{i}", xa[:, i], xb[:, 0]) for i in range(na)], [], []
    n = min(na, nb)
    names = ["mono"] if n == 1 else [f"ch{i}" for i in range(n)]
    pairs = [(names[i], xa[:, i], xb[:, i]) for i in range(n)]
    return pairs, list(range(n, na)), list(range(n, nb))


def named(idx):
    """Channel indices as a readable list, e.g. "ch2, ch3"."""
    return ", ".join(f"ch{i}" for i in idx)


def analyze(a, b, sr, floor_db):
    """Scalar findings for one already-aligned channel pair.

    Two different gain numbers, because they answer different questions and
    conflating them is how a level drop gets reported as a boost:

    `level` is the plain RMS ratio, which is what "how much louder or quieter
    is the bounce" actually means. It is unbiased whatever else changed.

    `fit` is the least-squares scalar h minimizing ||b - h*a||, that is, the
    single number that best explains the bounce as a rescaled source. It equals
    correlation * level, so it is pulled toward zero by anything a scalar cannot
    account for. When correlation is 1 the two agree exactly; when it is not,
    the gap between them is itself the message that no scalar explains this."""
    resid = a - b
    ra = rms(a)
    return {
        "tau": fractional_delay(a, b, sr, floor_db),
        "level": db(rms(b)) - db(ra),
        "fit": float(np.dot(a, b) / max(np.dot(a, a), EPS)),
        "corr": float(np.dot(a, b) / max(np.sqrt(np.dot(a, a) * np.dot(b, b)), EPS)),
        "resid": resid,
        "rel": db(rms(resid)) - db(ra),
        "a": a,
        "b": b,
    }


# ---------------------------------------------------------------- plotting


def plot(r, sr, delay, floor_db, out, src_path, bounce_path):
    a, b, resid = r["a"], r["b"], r["resid"]
    t = np.arange(len(a)) / sr * 1000.0
    fig, ax = plt.subplots(2, 2, figsize=(13, 8.0))
    # Name the files on the figure. These get saved, mailed around and compared
    # against each other, and a panel of anonymous noise is no use a week later.
    fig.suptitle(
        f"{os.path.basename(src_path)}  ->  "
        f"{os.path.basename(bounce_path)}\n"
        f"{r['label']}: residual {db(rms(resid)):.1f} dBFS "
        f"({r['rel']:+.1f} dB rel. source), "
        f"level {r['level']:+.3f} dB, "
        f"delay {delay:+d} {r['tau'] * sr:+.3f} samples",
        fontsize=10,
    )

    ax[0, 0].plot(t, a, lw=0.8, label="source")
    ax[0, 0].plot(t, b, lw=0.8, alpha=0.7, label="bounce")
    ax[0, 0].set(
        title=f"Overlay after {delay:+d}-sample alignment",
        xlabel="ms",
        ylabel="amplitude",
    )
    ax[0, 0].legend(fontsize=8)

    ax[0, 1].plot(t, resid, lw=0.8, color="crimson")
    ax[0, 1].set(
        title=f"Residual, peak {db(np.max(np.abs(resid))):.1f} dBFS", xlabel="ms"
    )
    # Share the overlay's scale so a small residual reads as small rather than
    # being autoscaled up to fill the panel, which is the common case and the
    # whole reason for tying the two together. Treat it as a floor rather than
    # a fixed scale, though: a polarity-inverted bounce leaves a residual at
    # twice the source amplitude, and holding that to the source's scale clips
    # the trace into a solid block that hides how large the difference is.
    lo, hi = ax[0, 0].get_ylim()
    span = max(abs(lo), abs(hi), float(np.max(np.abs(resid))) * 1.05)
    ax[0, 1].set_ylim(-span, span)

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
    ax[1, 0].semilogx(
        f[1:],
        guide + 20 * np.log10(f[1:] / 1000.0),
        ls=":",
        lw=0.9,
        color="gray",
        label="+6 dB/oct",
    )
    ax[1, 0].set(
        title="Residual vs. source spectrum",
        xlabel="Hz",
        ylabel="dB",
        xlim=(20, sr / 2),
        ylim=(-160, 5),
    )
    ax[1, 0].legend(fontsize=8)

    fh, H = transfer_function(a, b, sr, floor_db)
    mag = db(np.abs(H))
    axr = ax[1, 1]
    axr.semilogx(fh, mag, lw=0.7, color="navy")
    axr.axhline(0.0, ls=":", lw=0.9, color="gray")

    # Autoscale, floored at +/-6 dB so a transparent result still reads as a
    # flat line on a meaningful scale rather than being zoomed into its own
    # rounding noise. Fixing the limits at +/-6 would instead push an SRC
    # anti-imaging cliff, the whole point of this panel, off the bottom.
    finite = mag[np.isfinite(mag)]
    if finite.size:
        lo = max(-120.0, min(-6.0, float(np.floor(finite.min() / 6.0) * 6.0)))
        hi = min(60.0, max(6.0, float(np.ceil(finite.max() / 6.0) * 6.0)))
    else:
        lo, hi = -6.0, 6.0
    axr.set(
        title="Estimated transfer function |B/A| (flat 0 dB = transparent)",
        xlabel="Hz",
        ylabel="dB",
        xlim=(20, sr / 2),
        ylim=(lo, hi),
    )
    axp = axr.twinx()
    axp.semilogx(fh, np.degrees(np.angle(H)), lw=0.5, color="darkorange", alpha=0.6)
    axp.set_ylabel("phase (deg)", color="darkorange")
    axp.set_ylim(-180, 180)

    for row in ax:
        for cell in row:
            cell.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, dpi=140)
    print(f"\nwrote {out}")


# ---------------------------------------------------------------- main


def main():
    p = argparse.ArgumentParser(
        description="Measure whether a bounce is a transparent pass-through "
        "of its source."
    )
    # Not "wav": with libsndfile behind it this reads AIFF and CAF too, and a
    # DAW bounce is not always a WAV.
    p.add_argument("a", help="source audio file (what you fed the sampler)")
    p.add_argument("b", help="bounced audio file (what came back out)")
    p.add_argument("-o", "--out", default="nulltest.png")
    p.add_argument(
        "--floor",
        type=float,
        default=-60.0,
        help="dB below source peak spectrum to ignore (default -60)",
    )
    args = p.parse_args()

    # libsndfile reports a missing file as "System error", which is no help at
    # all when the real problem is a typo in a long bounce path.
    for path in (args.a, args.b):
        if not os.path.isfile(path):
            sys.exit(f"no such file: {path}")
    try:
        xa, sra, suba = load(args.a)
        xb, srb, subb = load(args.b)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"could not read audio: {exc}")

    if sra != srb:
        sys.exit(f"sample rates differ: {sra} vs {srb}. That alone is the answer.")
    sr = sra

    print(f"source           : {args.a}")
    print(f"                   {len(xa)} samples, {xa.shape[1]} ch, {sr} Hz, {suba}")
    print(f"bounce           : {args.b}")
    print(f"                   {len(xb)} samples, {xb.shape[1]} ch, {sr} Hz, {subb}")
    if min(len(xa), len(xb)) < 64:
        sys.exit("files are too short to analyze")

    shape_a, shape_b = xa.shape, xb.shape

    # Measure the delay on the channel pair where both sides carry the most
    # energy, rather than on the channel mean. Anti-phase content between
    # channels, which is exactly what a one-sided polarity inversion produces,
    # cancels in the mean and leaves the cross-correlation reading digital
    # silence. It then reports a delay of zero and every per-channel figure
    # downstream gets measured against a misalignment. Taking the minimum of
    # the two energies keeps the choice off a pair whose other side is silent,
    # since correlating against silence is the failure being avoided.
    prelim, _, _ = channel_pairs(xa, xb)
    ref_a, ref_b = max(
        ((ca, cb) for _, ca, cb in prelim),
        key=lambda p: min(float(np.dot(p[0], p[0])), float(np.dot(p[1], p[1]))),
    )
    delay = integer_delay(ref_a, ref_b)
    xa, xb = align(xa, xb, delay)
    print(
        f"integer delay    : {delay:+d} samples "
        f"({1000.0 * delay / sr:+.4f} ms)   [+ = bounce late]"
    )

    pairs, extra_a, extra_b = channel_pairs(xa, xb)

    # An unpaired bounce channel is harmless only when it carries digital
    # silence, which is what an unused output leg looks like. Anything else is
    # content this test never compared against anything, so it cannot count
    # toward a pass. An unpaired SOURCE channel is worse: that is audio the
    # bounce dropped outright.
    unchecked_b = [j for j in extra_b if np.any(xb[:, j])]

    # --- bit-identity ------------------------------------------------------
    # Tested per channel pair rather than on the whole arrays. Whole-array
    # equality would make any difference in shape disqualifying, and three of
    # those are routine and mean nothing on their own: a start offset, a bounce
    # region running past the end of the sample, and a mono sample coming back
    # on a stereo bus. What matters is whether every sample that lines up
    # matches, and that nothing was left unexamined.
    pairs_exact = all(np.array_equal(ca, cb) for _, ca, cb in pairs)

    if pairs_exact and not extra_a and not unchecked_b:
        # "The signal path", not "the sampler": this compares two files and has
        # no idea what produced the second one. The control test in the README
        # deliberately has no sampler in it at all.
        print("\nVERDICT: bit-identical. The signal path is transparent.")
        aside = []
        if delay:
            aside.append(
                f"a {delay:+d}-sample start offset, which is playback "
                "start position or plugin delay compensation"
            )
        if shape_a[0] != shape_b[0]:
            aside.append(
                "a length difference, the bounce region running past "
                "the end of the sample"
            )
        if shape_a[1] != shape_b[1] and extra_b:
            aside.append(
                f"a channel count of {shape_a[1]} against "
                f"{shape_b[1]}, where the bounce channels with no "
                f"source counterpart ({named(extra_b)}) carry digital "
                "silence"
            )
        elif shape_b[1] > shape_a[1]:
            aside.append(
                f"a {shape_a[1]}-to-{shape_b[1]} channel expansion, "
                "every bounce channel matching the source exactly"
            )
        elif shape_a[1] != shape_b[1]:
            # Reaching a pass with fewer bounce channels than source channels
            # means every source channel equalled the one bounce channel, so
            # the source was multi-mono and the fold-down lost nothing.
            aside.append(
                f"a {shape_a[1]}-to-{shape_b[1]} channel fold-down, "
                "every source channel matching the bounce exactly"
            )
        if suba != subb:
            aside.append(f"a change of sample format from {suba} to {subb}")
        if aside:
            print(
                "         Every sample that lines up matches. What differs "
                "is " + "; ".join(aside) + "."
            )
        return

    # Every paired channel matched, so the residual is not the story and the
    # usual verdict would bury the real one under a -240 dBFS reading. Say what
    # actually disqualified it instead.
    if pairs_exact:
        print(
            "\nVERDICT: not transparent. Every channel that could be paired "
            "matches the source exactly, but the channel layout leaves "
            "something unaccounted for."
        )
        if extra_a:
            print(
                f"  the bounce has no counterpart for source channels "
                f"{named(extra_a)}, so that audio was dropped rather than "
                "passed through."
            )
        if unchecked_b:
            print(
                f"  bounce channels {named(unchecked_b)} have no source "
                "counterpart and carry content, so they were compared "
                "against nothing and cannot count toward a pass."
            )
        return

    results = []
    for label, ca, cb in pairs:
        r = analyze(ca, cb, sr, args.floor)
        r["label"] = label
        results.append(r)
        print(f"\n{label}")
        print(
            f"  fractional delay : {r['tau'] * sr:+.4f} samples "
            f"({r['tau'] * 1e6:+.2f} us)"
        )
        print(f"  level (rms b/a)  : {r['level']:+.4f} dB")
        print(
            f"  best-fit gain    : {db(r['fit']):+.4f} dB"
            f"{'  (polarity inverted)' if r['fit'] < 0 else ''}"
        )
        print(f"  correlation      : {r['corr']:+.8f}")
        print(
            f"  residual RMS     : {db(rms(r['resid'])):.1f} dBFS  "
            f"({r['rel']:+.1f} dB rel. source)"
        )
        print(f"  residual peak    : {db(np.max(np.abs(r['resid']))):.1f} dBFS")

    worst = max(results, key=lambda r: r["rel"])
    print(
        f"\nVERDICT: not transparent. Largest residual is "
        f"{db(rms(worst['resid'])):.1f} dBFS on {worst['label']}, "
        f"{worst['rel']:+.1f} dB relative to the source."
    )

    flipped = [r["label"] for r in results if r["corr"] < 0]
    if flipped:
        print(
            f"  polarity inverted on {', '.join(flipped)}. The residual there "
            "is the sum of the two signals rather than their difference, so "
            "it reads about 6 dB high."
        )
    if any(abs(r["tau"] * sr) > 0.1 for r in results):
        print(
            "  a sub-sample offset this large implies resampling or "
            "transposition, or else a minimum-phase filter, whose group delay "
            "registers the same way. Check the |B/A| panel to tell them apart."
        )
    if any(abs(r["corr"]) < 0.9999 for r in results):
        print(
            "  correlation is short of 1, so no single scalar gain explains "
            "the bounce. Read the |B/A| panel rather than the gain figures."
        )
    exact = [r["label"] for r in results if not np.any(r["resid"])]
    if exact:
        print(
            f"  residual is exactly zero on {', '.join(exact)}, so whatever "
            "happened did not happen there."
        )
    if suba != subb:
        print(
            f"  sample formats differ ({suba} source, {subb} bounce), which "
            "is not by itself a change to the signal."
        )
    if xa.shape[1] != xb.shape[1]:
        if xa.shape[1] == 1 or xb.shape[1] == 1:
            print(
                f"  channel counts differ ({xa.shape[1]} source, "
                f"{xb.shape[1]} bounce), so the single channel was compared "
                "against every channel on the other side in turn."
            )
        else:
            print(
                f"  channel counts differ ({xa.shape[1]} source, "
                f"{xb.shape[1]} bounce), and channels were paired up by "
                "position."
            )
    if extra_a:
        print(
            f"  source channels with no counterpart in the bounce: "
            f"{named(extra_a)}. That audio was dropped rather than passed "
            "through, which is never transparent."
        )
    if unchecked_b:
        print(
            f"  bounce channels with no source counterpart, carrying content "
            f"that was compared against nothing: {named(unchecked_b)}."
        )
    if len(results) > 1:
        print(f"  plotting {worst['label']}, the channel with the largest residual.")

    plot(worst, sr, delay, args.floor, args.out, args.a, args.b)


if __name__ == "__main__":
    main()
