# Requirements --- Rush Royale Desktop Summon Lab

This document describes the environment and dependencies required by the
Rush Royale desktop GUI.

> **Tested:** the supplied project version was reported working on the
> targeted **September 2026** Rush Royale PC build.

## Required platform

This project requires **Windows**.

It is written for the **Rush Royale desktop/PC client installed through
the MY.GAMES / MyGames launcher**.

The supplied source expects:

``` text
D:\MY.GAMES\Rush Royale PC\WinRR.exe
```

and:

``` text
D:\MY.GAMES\Rush Royale PC\GameAssembly.dll
```

It is not intended for Android, iOS or an Android emulator.

## Python

Install **Python 3** for Windows.

Check it with:

``` powershell
python --version
```

or:

``` powershell
py --version
```

## External Python dependency

The GUI imports one external Python package:

``` text
frida
```

Install it with:

``` powershell
pip install frida
```

For a normal GitHub repository, also keep a machine-readable
`requirements.txt` containing:

``` text
frida
```

Then installation can be done with:

``` powershell
pip install -r requirements.txt
```

### Why both REQUIREMENTS.md and requirements.txt?

`REQUIREMENTS.md` is documentation for humans.

`requirements.txt` is the conventional file that
`pip install -r requirements.txt` can consume directly.

Renaming the pip dependency file itself to `.md` is therefore not
recommended.

## Python standard-library modules

The GUI also uses modules including:

``` text
ctypes
hashlib
json
pathlib
queue
tkinter
```

These are not dependencies that should be added to `requirements.txt`.

`tkinter` is part of standard CPython Windows distributions. If you are
using an unusual/minimal Python distribution, make sure Tk support is
included.

## Required project files

The minimum GUI setup is:

``` text
rush_summon_gui.py
forced_summon_lab.js
requirements.txt
README.md
```

`REQUIREMENTS.md` is recommended documentation.

The original GUI filename was:

``` text
rush_summon_gui.py
```

The GUI and `forced_summon_lab.js` should remain together unless you
modify the path used by the Python source.

## Optional files

These are not required for the current GUI:

``` text
forced_summon_lab.py
summon_probe.py
```

They are older command-line/research tools.

`summon_probe.py` additionally expects `summon_probe.js`, which is not
the same file as `forced_summon_lab.js`.

`card_mapping.json` is generated/updated by the GUI and does not have to
exist on first launch.

## Build compatibility

The September 2026 code is bound to a specific `GameAssembly.dll`.

Expected SHA-256:

``` text
EF0D77A0660949397CAA287D951BDD86B39651797B5B36CEFDC2331DD6B9E425
```

The matching JavaScript contains build-specific values such as:

``` text
EXPECTED_CALLER_RVA = 0x389a8b7
MPD_TYPE_INDEX      = 64704
MPP_TYPE_INDEX      = 64729
```

and an IL2CPP types lookup based on:

``` text
GameAssembly base + 0x6f0c700 + 0x38
```

The supplied build resolves the following obfuscated method names:

``` text
DQQW
SMND
SMBR
SMBT
```

These are **not universal Rush Royale constants**.

After a Rush Royale update, the assembly hash, offsets/RVAs, type
indexes, IL2CPP layout or method names can change.

A hash mismatch therefore means the current build should be investigated
before using the old instrumentation.

## Recommended installation

From PowerShell:

``` powershell
git clone https://github.com/moody-nl/rush-royale-hacks.git
cd rush-royale-hacks

py -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Then start Rush Royale through the **MY.GAMES / MyGames launcher**.

Once `WinRR.exe` is running:

``` powershell
python rush_summon_gui.py
```

If the source still has its original development filename:

``` powershell
python rush_summon_gui.py
```

## Mana/no-cost warning

The no-summon-cost feature is the most experimental part of this
version.

It hooks cost-related methods associated with the calibrated player/mana
state and replaces matching cost return values with zero.

It was reported to work on the targeted September 2026 build, but should
be treated with additional caution because game/server validation,
anti-cheat behavior and cost logic may change.

The summon/merge functionality was reported to work very well on the
tested September 2026 build. This is historical tested status, not a
guarantee for future game versions.

## Quick checklist

Before running the GUI, verify:

-   Windows is being used.
-   Rush Royale is the MY.GAMES desktop version.
-   Python 3 is installed.
-   `frida` is installed.
-   `forced_summon_lab.js` is beside the GUI Python file.
-   Rush Royale is already running.
-   `EXPECTED_EXE` points to the real `WinRR.exe`.
-   The current `GameAssembly.dll` matches the supported build, or you
    have correctly updated and validated the build-specific
    instrumentation.

See [README.md](README.md) for the complete usage guide and safety
notes.
