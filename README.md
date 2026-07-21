# virtual-drag

Hold a modifier chord, then move the mouse, to virtually press and hold a mouse button on macOS.

| Chord | Action |
| --- | --- |
| **Control+Shift** + move | Left-button drag |
| **Option+Shift** + move | Right-button drag |

The chord alone does nothing until the mouse moves, so IDE shortcuts like Option+Shift+Arrow are not treated as a click.

Useful when a physical button is unreliable for dragging:

1. Move the cursor into place
2. Hold the chord
3. Move the mouse → virtual button down + drag
4. Release the keys → virtual button up

Injected clicks have modifiers stripped, so Control+Shift does **not** become a Control-click (right-click).

**macOS only** — uses Quartz / Core Graphics event taps.

## Requirements

- macOS
- Python 3.10+ (3.13 recommended)
- [Accessibility](https://support.apple.com/guide/mac-help/mh43185/mac) permission for the app that runs the script (Terminal, iTerm, Cursor, etc.)

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then grant Accessibility access:

**System Settings → Privacy & Security → Accessibility** → enable your Terminal / Cursor / iTerm

## Usage

```bash
.venv/bin/python main.py
```

Or from the project folder (re-execs into `.venv` if needed):

```bash
python3 main.py
```

Quit with **Ctrl+C**.

## How it works

Holding a bare chord only *arms* a drag. On the first mouse move:

- Posts a synthetic mouse-down for that button (with no modifier flags)
- Rewrites that move (and later moves) into drag events
- Posts mouse-up when the keys are released

If you press another key before moving (e.g. Option+Shift+Arrow), the arm is cancelled and the real shortcut runs. Extra modifiers (Command/fn) also block activation.

This requires a CGEvent tap, which is why Accessibility permission is needed.
