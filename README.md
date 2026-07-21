# virtual-drag

Hold a modifier chord to virtually press and hold a mouse button on macOS.

| Chord | Action |
| --- | --- |
| **Control+Shift** | Left-button down (left drag) |
| **Option+Shift** | Right-button down (right drag) |

Useful when a physical button is unreliable for dragging:

1. Move the cursor into place
2. Hold the chord → virtual button down
3. Move the mouse → drag
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

While a chord is held, the script:

- Posts a synthetic mouse-down for that button (with no modifier flags)
- Rewrites mouse-move events into the matching drag events so apps track the drag
- Posts mouse-up when the keys are released

Control+Option+Shift does not activate either chord (chords are mutually exclusive).

This requires a CGEvent tap, which is why Accessibility permission is needed.
