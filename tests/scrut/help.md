# Help output

Tests that each tool's `--help` runs, exits 0, and advertises its interface.

A note on the globs below. Python 3.13 changed how `argparse` renders an option
with both a short and a long form: `-o OUT, --out OUT` became `-o, --out OUT`,
which also narrows the help-text column. These scripts declare
`requires-python = ">=3.10"`, so `uv` may resolve any version from 3.10 up and
the column width is not ours to control. The expectations therefore pin the
argument names and their help text exactly, and glob only the whitespace and
the short-option spelling. `maketest.py` needs no globs: it has no short/long
pair with a metavar, so its output is identical on every version.

## nulltest.py help

```scrut
$ "${NULLTEST_BIN}" --help
usage: nulltest.py [-h] [-o OUT] [--floor FLOOR] a b

Measure whether a bounce is a transparent pass-through of its source.

positional arguments:
  a *source audio file (what you fed the sampler) (glob)
  b *bounced audio file (what came back out) (glob)

options:
  -h, --help*show this help message and exit (glob)
  -o*--out OUT (glob)
  --floor FLOOR*dB below source peak spectrum to ignore (default -60) (glob)
```

## nulltest.py short help flag

```scrut
$ "${NULLTEST_BIN}" -h | head -3
usage: nulltest.py [-h] [-o OUT] [--floor FLOOR] a b

Measure whether a bounce is a transparent pass-through of its source.
```

## maketest.py help

```scrut
$ "${MAKETEST_BIN}" --help
usage: maketest.py [-h] [--sr SR] [--outdir OUTDIR]

options:
  -h, --help       show this help message and exit
  --sr SR          sample rate; MATCH YOUR LOGIC PROJECT
  --outdir OUTDIR
```

## maketest.py short help flag

```scrut
$ "${MAKETEST_BIN}" -h | head -1
usage: maketest.py [-h] [--sr SR] [--outdir OUTDIR]
```

## maketones.py advertises every flag

`maketones.py` has seventeen options against the other tools' two, and
`argparse` wraps the usage line to the terminal width, which is not ours to
control: at `COLUMNS=40` the first line is just `usage: maketones.py [-h]`.
Snapshotting the layout would therefore pin the environment rather than the
interface. This pins the interface instead, and the extracted list is identical
at 40, 80 and 200 columns.

```scrut
$ "${MAKETONES_BIN}" --help | grep -oE '^  --[a-z-]+' | sed 's/^ *//' | sort
--burst-level
--burst-ms
--burst-rate
--click-hz
--click-level
--click-ms
--click-rate
--level-hz
--levels
--only
--outdir
--pan-level
--saws
--seconds
--sine-level
--sines
--sr
```

## maketones.py short help flag

```scrut
$ "${MAKETONES_BIN}" -h | head -1 | cut -c1-19
usage: maketones.py
```
