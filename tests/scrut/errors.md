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

Both scripts are warmed, not just one: they declare different dependency sets,
so resolving one leaves the other cold. Output is discarded and the exit status
forced to 0, since this block is setup rather than an assertion.

```scrut
$ "${NULLTEST_BIN}" --help >/dev/null 2>&1; "${MAKETEST_BIN}" --help >/dev/null 2>&1; true
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
