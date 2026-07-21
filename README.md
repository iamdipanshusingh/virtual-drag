# virtual-drag

Hold **Control+Shift** to virtually press and hold the left mouse button on macOS.

Useful when the physical left button is unreliable for dragging:

1. Move the cursor into place
2. Hold **Control+Shift** → virtual left-button down
3. Move the mouse → drag
4. Release the keys → virtual left-button up

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

While Control+Shift are held, the script:

- Posts a synthetic left-mouse-down (with no modifier flags)
- Rewrites mouse-move events into left-drag events so apps track the drag
- Posts left-mouse-up when the keys are released

This requires a CGEvent tap, which is why Accessibility permission is needed.
