#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""
maketones.py: render exact test signals and prove each file holds them.

Usage:  uv run maketones.py [--outdir .] [--only GROUP ...] [--levels L ...]

Writes 32-bit float stereo WAVs in five groups, any subset of which can be
selected with --only:

  sines        One file per frequency at a fixed level. For reading periods off
               a display: at 48 kHz a 20 ms window shows f * 0.020 of them, so
               the defaults give 1, 2, 4, 5, 8 and 20.
  levels       One frequency at many amplitudes, so only the vertical axis
               varies. The defaults run from a floor of 0.002 up to 2.000,
               which is a full octave above full scale.
  pans         The same tone hard left and hard right, with the opposite
               channel written as digital silence.
  saws         A rising ramp either side of full scale. A saw crosses a
               clipping threshold on a straight line rather than at a turning
               point, so an overshoot shows as a flat top with a vertical edge;
               a clipped sine's plateau can be mistaken for a rounded peak.
  transients   A repeating click and a gated burst, for anything whose
               behaviour only differs after the signal changes.

Four things about the output are decisions rather than defaults.

**32-bit float, not 24-bit integer.** Any test signal above 1.0 is
unrepresentable in an integer format, and testing what a meter or a scope does
above full scale is a normal thing to want. The default level sweep ends at
2.000 for exactly that reason.

**Do not reach for a DAW's gain knob instead.** REAPER's stock Tone Generator
and `JS: Volume Adjustment` both compute gain as `2 ^ (x / 6)`, a factor of two
per six decibels rather than 6.0206 dB, and the Tone Generator moves in whole
decibels and stops at +6. `JS: Volume/Pan Smoother` is the only one of the
three using true dB. Rendering the levels makes them exact and checkable.

**The pan is baked into the file rather than left to a knob.** REAPER applies
track pan *after* the FX chain, so panning a track never reaches the plugin
under test, and a channel check done that way passes against a plugin that
ignores the channel entirely.

**Every file is read back after it is written.** A generator that silently
clipped its own output would produce a level sweep that tested nothing. There
is no flag to switch that off.
"""

import argparse
import os
import sys

import numpy as np
from scipy.io import wavfile

GROUPS = ("sines", "levels", "pans", "saws", "transients")

# Peak comparisons are made in float32, which round-trips through a WAV exactly,
# so this absorbs the last bit of the float64 arithmetic that produced the
# expected bound rather than any real slack in the measurement.
TOLERANCE = 1e-6

# Smallest shortfall against the requested level worth printing, as a fraction:
# 0.01%, which is the first one the two-decimal figure can express.
REPORT_UNDER = 0.0001


# ------------------------------------------------------------------ waveforms


def timeline(sr, seconds):
    """Sample times in seconds, which every waveform below is a function of."""
    return np.arange(int(sr * seconds)) / float(sr)


def sine(t, hz, level):
    """A sine of the given amplitude, starting at phase zero."""
    return level * np.sin(2.0 * np.pi * hz * t)


def saw(t, hz, level):
    """A rising ramp from -level to +level, wrapping hz times a second.

    ffmpeg needed this written as `mod(f*t\\,1)` with the comma escaped, or it
    read the comma as an option separator and rejected the whole filterchain.
    That hazard is worth recording because it cost an afternoon, but it does
    not exist here: numpy's `%` takes no quoting."""
    return level * (2.0 * ((hz * t) % 1.0) - 1.0)


def gate(t, rate, ms):
    """One for the first ms of every 1/rate seconds, zero for the rest.

    Aligned to t = 0, so a waveform multiplied by this is gated from its own
    phase zero and the first sample of every burst is deterministic."""
    return ((t % (1.0 / rate)) < (ms / 1000.0)).astype(np.float64)


def stereo(left, right):
    """Two mono signals as the (n, 2) array wavfile.write wants."""
    return np.column_stack((left, right))


# ----------------------------------------------------------------- the bounds


def peaks(x):
    """Per-channel peak amplitude of an (n, ch) array."""
    return np.max(np.abs(x), axis=0)


def sine_floor(sr, hz, level):
    """The lowest peak a correctly generated sine can show at this frequency.

    A sampled sine only reaches its amplitude when a sample lands on the crest.
    The worst case is a crest falling exactly between two samples, leaving the
    larger of them at `cos(pi * f / sr)` of full amplitude: nothing at all for
    a frequency that divides the sample rate evenly, but 0.2% at 1 kHz against
    48 kHz and rising steeply from there.

    The bash script this replaces compared every peak against the requested
    level within 0.0005, which worked only because every frequency it shipped
    divides 48 kHz evenly. That test would reject a correct file the moment a
    caller asked for a frequency of its own. Checking against the bound keeps
    the check meaningful for any --sines the caller passes."""
    return level * np.cos(np.pi * hz / sr)


def saw_floor(sr, hz, level):
    """The lowest peak a correctly generated ramp can show.

    The ramp's maximum is the sample immediately before it wraps, which sits
    one step of `2 * level * hz / sr` below the top in the worst case."""
    return level * (1.0 - 2.0 * hz / sr)


def gated_floor(sr, hz, ms, level):
    """The lowest peak a gated sine can show, or zero for too short a window.

    The gate opens at the sine's phase zero, so the window covers phase up to
    `2 * pi * hz * ms / 1000` and contains a crest only once that reaches a
    quarter turn. Below that there is no crest to bound and the honest floor is
    zero: a shorter burst is a legitimate thing to ask for, and the readback
    check still proves the file holds whatever it does hold."""
    if ms / 1000.0 * hz < 0.25:
        return 0.0
    return sine_floor(sr, hz, level)


# ------------------------------------------------------------------ rendering


def render(outdir, sr, name, data, want, floor, silent=None):
    """Write one file, read it back, and check it against what was asked for.

    The readback splits two failures the bash script conflated into one
    tolerance. Comparing the file's peaks against the in-memory array's peaks
    is exact, because float32 round-trips through a WAV bit for bit, and it is
    the comparison that catches a clipped write, a narrower bit depth or the
    wrong codec. Comparing the in-memory peak against the requested level is a
    separate question with its own answer per waveform, which is what the
    floors above are for."""
    path = os.path.join(outdir, f"{name}.wav")
    samples = data.astype(np.float32)
    wavfile.write(path, sr, samples)

    back_sr, back = wavfile.read(path)
    if back_sr != sr or back.dtype != np.float32 or back.shape != samples.shape:
        sys.exit(f"{name}.wav came back as {back.shape} {back.dtype} at "
                 f"{back_sr} Hz, not {samples.shape} float32 at {sr} Hz")

    held = peaks(back)
    if not np.array_equal(held, peaks(samples)):
        sys.exit(f"{name}.wav peaks at {held} on disk and {peaks(samples)} in "
                 "memory; the write did not keep what it was given")

    got = float(np.max(held))
    if got > want + TOLERANCE:
        sys.exit(f"{name}.wav peaks at {got:.6f}, louder than the {want:.6f} "
                 "asked for")
    if got < floor - TOLERANCE:
        sys.exit(f"{name}.wav peaks at {got:.6f}, below the {floor:.6f} this "
                 f"waveform can reach at {sr} Hz")

    # A panned file's whole point is the channel that holds nothing, so that is
    # the half worth asserting. Reporting the loudest channel alone once let a
    # hard-panned file read as a generator failure, and reporting only the
    # first channel would let a plugin tapping channel 0 be tested against a
    # file that never exercised it.
    if silent is not None:
        side = 0 if silent == "left" else 1
        if held[side] != 0.0:
            sys.exit(f"{name}.wav has {held[side]:.6f} in its {silent} "
                     "channel, expected silence")

    # Reported only once it is large enough for the printed figure to say
    # something. Every frequency that does not divide the sample rate falls a
    # few parts per million short of its amplitude, and announcing that as
    # "0.00% under" would train the reader to skip the line that matters.
    note = f", {silent} silent" if silent is not None else ""
    under = ""
    if want > 0.0 and (want - got) / want >= REPORT_UNDER:
        under = f", {100.0 * (want - got) / want:.2f}% under {want:g}"
    print(f"wrote {path}  ({len(samples)/sr:.2f} s @ {sr} Hz, 32-bit float)  "
          f"peak {got:.6f}{note}{under}")


# --------------------------------------------------------------- the groups


def make_sines(args):
    """One file per frequency, identical in both channels."""
    t = timeline(args.sr, args.seconds)
    for hz in args.sines:
        tone = sine(t, hz, args.sine_level)
        yield (f"sine-{hz:g}hz-{args.sine_level:g}", stereo(tone, tone),
               args.sine_level, sine_floor(args.sr, hz, args.sine_level), None)


def make_levels(args):
    """The level sweep, all at one frequency so only the amplitude varies.

    The level is carried through as the literal token the caller typed, because
    the filename is made from it: `0.010` must not become `level-0.01.wav`, and
    a caller bracketing a threshold at three decimals needs the file it names
    in its own procedure to be the file that appears."""
    t = timeline(args.sr, args.seconds)
    for token in args.levels:
        level = float(token)
        tone = sine(t, args.level_hz, level)
        yield (f"level-{token}", stereo(tone, tone), level,
               sine_floor(args.sr, args.level_hz, level), None)


def make_pans(args):
    """The same tone hard left and hard right, silence in the other channel."""
    t = timeline(args.sr, args.seconds)
    tone = sine(t, args.level_hz, args.pan_level)
    quiet = np.zeros_like(tone)
    floor = sine_floor(args.sr, args.level_hz, args.pan_level)
    yield ("pan-hard-left", stereo(tone, quiet), args.pan_level, floor, "right")
    yield ("pan-hard-right", stereo(quiet, tone), args.pan_level, floor, "left")


def make_saws(args):
    """Ramps at the level sweep's frequency, named from the literal token."""
    t = timeline(args.sr, args.seconds)
    for token in args.saws:
        level = float(token)
        ramp = saw(t, args.level_hz, level)
        yield (f"saw-{token}", stereo(ramp, ramp), level,
               saw_floor(args.sr, args.level_hz, level), None)


def make_transients(args):
    """A repeating click and a gated burst.

    A click rather than a single-sample impulse: one sample is one column on
    most displays and vanishes into the rasterizer, while 1 ms at 48 kHz is 48
    samples and unmissable. Repeating it turns a decay into a count, since the
    number visible at once reads the time constant directly. The gated burst
    gives a rise and a decay in one file, which is the shape to watch when
    judging whether a fade looks like a phosphor or like a fade."""
    t = timeline(args.sr, args.seconds)
    click = gate(t, args.click_rate, args.click_ms) * \
        sine(t, args.click_hz, args.click_level)
    burst = gate(t, args.burst_rate, args.burst_ms) * \
        sine(t, args.level_hz, args.burst_level)
    yield (f"click-{args.click_rate:g}hz", stereo(click, click),
           args.click_level,
           gated_floor(args.sr, args.click_hz, args.click_ms, args.click_level),
           None)
    yield (f"burst-{args.level_hz:g}hz-gated", stereo(burst, burst),
           args.burst_level,
           gated_floor(args.sr, args.level_hz, args.burst_ms, args.burst_level),
           None)


# ----------------------------------------------------------------------- main


def main():
    p = argparse.ArgumentParser(
        description="render exact test signals and verify every file written")
    p.add_argument("--outdir", default=".")
    p.add_argument("--sr", type=int, default=48000, help="sample rate")
    p.add_argument("--seconds", type=float, default=20.0,
                   help="length of every file")
    p.add_argument("--only", nargs="+", choices=GROUPS, default=list(GROUPS),
                   metavar="GROUP", help=f"groups to render ({', '.join(GROUPS)})")

    p.add_argument("--sines", nargs="+", type=float,
                   default=[50.0, 100.0, 200.0, 250.0, 400.0, 1000.0],
                   help="frequencies for the sine group")
    p.add_argument("--sine-level", type=float, default=0.5)

    p.add_argument("--levels", nargs="+",
                   default=["0.002", "0.010", "0.100", "0.500", "1.000",
                            "2.000"],
                   help="amplitudes for the level sweep; the text is the name")
    p.add_argument("--level-hz", type=float, default=100.0,
                   help="frequency for the levels, pans, saws and burst")

    p.add_argument("--saws", nargs="+", default=["0.900", "1.100"],
                   help="amplitudes for the saw group; the text is the name")
    p.add_argument("--pan-level", type=float, default=0.5)

    p.add_argument("--click-hz", type=float, default=1000.0)
    p.add_argument("--click-ms", type=float, default=1.0)
    p.add_argument("--click-rate", type=float, default=2.0,
                   help="clicks per second")
    p.add_argument("--click-level", type=float, default=0.8)

    p.add_argument("--burst-ms", type=float, default=100.0)
    p.add_argument("--burst-rate", type=float, default=1.0,
                   help="bursts per second")
    p.add_argument("--burst-level", type=float, default=0.5)
    args = p.parse_args()

    for flag, tokens in (("--levels", args.levels), ("--saws", args.saws)):
        for token in tokens:
            try:
                float(token)
            except ValueError:
                sys.exit(f"{flag}: {token} is not a number")

    if args.sr <= 0 or args.seconds <= 0.0:
        sys.exit("--sr and --seconds must both be above zero")

    # Above Nyquist a sine aliases down to some other frequency and the file is
    # silently not the signal it is named after, which is worse than an error.
    for hz in list(args.sines) + [args.level_hz, args.click_hz]:
        if hz <= 0.0 or hz >= args.sr / 2.0:
            sys.exit(f"{hz:g} Hz is not below the {args.sr / 2.0:g} Hz Nyquist "
                     f"limit for --sr {args.sr}")

    builders = {"sines": make_sines, "levels": make_levels, "pans": make_pans,
                "saws": make_saws, "transients": make_transients}

    os.makedirs(args.outdir, exist_ok=True)
    # Iterating GROUPS rather than args.only keeps the output in a fixed order
    # whatever order --only was given in.
    for group in GROUPS:
        if group in args.only:
            for job in builders[group](args):
                render(args.outdir, args.sr, *job)

    print("every peak above was read back out of the finished file")


if __name__ == "__main__":
    main()
