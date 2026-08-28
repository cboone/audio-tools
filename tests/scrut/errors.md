# Error handling

Tests the failure contract: which stream a diagnostic goes to, and which exit
code the caller sees. These matter more than the wording, because a script in a
pipeline is read by its exit code.

## Warm the uv cache before asserting on stderr

Every assertion below reads stderr, and that is exactly where `uv` writes
`Downloading ...` and `Installed N packages` the first time it resolves a
script's PEP 723 dependencies. On a warm cache it writes nothing, so this is
invisible locally after the first run; in CI the cache is always cold, so
without this step every stderr assertion here would fail on noise that has
nothing to do with the tool.

Every script is warmed, not just one: they declare different dependency sets,
so resolving one leaves the others cold. Output is discarded and the exit status
forced to 0, since this block is setup rather than an assertion.

```scrut
$ "${NULLTEST_BIN}" --help >/dev/null 2>&1; "${MAKETEST_BIN}" --help >/dev/null 2>&1; "${MAKETONES_BIN}" --help >/dev/null 2>&1; true
```

## A missing input file reports the path and exits 1

```scrut {output_stream: stderr}
$ "${NULLTEST_BIN}" "$TMPDIR/does-not-exist.wav" "$TMPDIR/also-missing.wav"
no such file: */does-not-exist.wav (glob)
[1]
```

## Nothing is written to stdout when the input is missing

```scrut
$ "${NULLTEST_BIN}" "$TMPDIR/does-not-exist.wav" "$TMPDIR/also-missing.wav" 2>/dev/null
[1]
```

## Missing arguments are an argparse usage error, exit 2

```scrut {output_stream: stderr}
$ "${NULLTEST_BIN}"
usage: nulltest.py [-h] [-o OUT] [--floor FLOOR] a b
nulltest.py: error: the following arguments are required: a, b
[2]
```

## maketest.py rejects a non-integer sample rate

```scrut {output_stream: stderr}
$ "${MAKETEST_BIN}" --sr not-a-number
usage: maketest.py [-h] [--sr SR] [--outdir OUTDIR]
maketest.py: error: argument --sr: invalid int value: 'not-a-number'
[2]
```

## maketones.py refuses a frequency at or above Nyquist

An aliased sine is silently not the signal its filename claims, which is worse
than an error, so this is refused rather than rendered.

```scrut {output_stream: stderr}
$ "${MAKETONES_BIN}" --outdir "$TMPDIR" --sines 30000 --sr 44100
30000 Hz is not below the 22050 Hz Nyquist limit for --sr 44100
[1]
```

## maketones.py refuses a non-finite value

NaN is false against every comparison, so a bare range test lets it through to
fail much later as a traceback. Each of these names the flag instead.

```scrut {output_stream: stderr}
$ "${MAKETONES_BIN}" --outdir "$TMPDIR" --seconds nan
--seconds: nan is not a finite number above zero
[1]
```

```scrut {output_stream: stderr}
$ "${MAKETONES_BIN}" --outdir "$TMPDIR" --click-rate 0
--click-rate: 0 is not a finite number above zero
[1]
```

## maketones.py refuses a duration that rounds to no samples

Both values are finite and above zero here; it is the product that is empty,
and an empty array reaches the peak check as a numpy traceback.

```scrut {output_stream: stderr}
$ "${MAKETONES_BIN}" --outdir "$TMPDIR" --seconds 1e-6
--seconds: 1e-06 s at --sr 48000 rounds to zero samples, so there would be no file to write
[1]
```

## maketones.py refuses a gate that would never close

`(t % period) < open` is true everywhere once the open time reaches the period,
which would render a continuous tone into a file named for a click.

```scrut {output_stream: stderr}
$ "${MAKETONES_BIN}" --outdir "$TMPDIR" --click-ms 500 --click-rate 2
--click-ms: 500 ms fills the 500 ms period of --click-rate 2, so the gate would never close
[1]
```

## maketones.py reports a level it cannot read against its own flag

`--levels` takes the literal text, because the filename is made from it, so a
bad value is caught here rather than by argparse.

```scrut {output_stream: stderr}
$ "${MAKETONES_BIN}" --outdir "$TMPDIR" --levels abc
--levels: abc is not a number
[1]
```

## maketones.py writes nothing to stdout when validation fails

```scrut
$ "${MAKETONES_BIN}" --outdir "$TMPDIR" --seconds nan 2>/dev/null
[1]
```
