#!/usr/bin/env python3
"""
Hold modifier chords to make macOS think a mouse button is pressed.

  Control+Shift  → virtual left-button down (drag with left)
  Option+Shift   → virtual right-button down (drag with right)

Use this when a physical button is unreliable for dragging:
  1. Move the cursor into place
  2. Hold the chord     → virtual button down
  3. Move the mouse     → drag
  4. Release the keys   → virtual button up

Injected clicks have modifiers stripped, so Control+Shift does NOT become
a Control-click (right-click) on macOS.

Setup (once):
  System Settings → Privacy & Security → Accessibility
  → enable your Terminal / Cursor / iTerm

Run:
  python3 main.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _ensure_quartz() -> None:
    """Re-exec with project .venv if this interpreter lacks Quartz."""
    try:
        import Quartz  # noqa: F401

        return
    except ImportError:
        pass

    root = Path(__file__).resolve().parent
    venv_python = root / ".venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(
            str(venv_python),
            [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        )

    print(
        "Missing Quartz bindings. From this folder run:\n"
        "  /opt/homebrew/bin/python3.13 -m venv .venv\n"
        "  .venv/bin/pip install -r requirements.txt\n"
        "  .venv/bin/python main.py",
        file=sys.stderr,
    )
    raise SystemExit(1)


_ensure_quartz()
import Quartz  # noqa: E402


OUR_TAG = 0x4D4F5553  # 'MOUS'
USER_DATA_FIELD = Quartz.kCGEventSourceUserData

# Require the chord keys and exclude the other side's exclusive modifier so
# Control+Option+Shift does not activate both.
_MODS = (
    Quartz.kCGEventFlagMaskControl
    | Quartz.kCGEventFlagMaskAlternate
    | Quartz.kCGEventFlagMaskShift
)
LEFT_CHORD = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskShift
RIGHT_CHORD = Quartz.kCGEventFlagMaskAlternate | Quartz.kCGEventFlagMaskShift

LEFT = "left"
RIGHT = "right"

_BUTTON = {
    LEFT: (
        Quartz.kCGMouseButtonLeft,
        Quartz.kCGEventLeftMouseDown,
        Quartz.kCGEventLeftMouseUp,
        Quartz.kCGEventLeftMouseDragged,
    ),
    RIGHT: (
        Quartz.kCGMouseButtonRight,
        Quartz.kCGEventRightMouseDown,
        Quartz.kCGEventRightMouseUp,
        Quartz.kCGEventRightMouseDragged,
    ),
}


class ModifierClickHold:
    """Virtual left/right click while Control+Shift / Option+Shift are held."""

    def __init__(self) -> None:
        self._held: str | None = None
        self._tap = None

    def _cursor(self):
        # CGEventSourceCreate + CGEventGetLocation needs an event; use current position.
        event = Quartz.CGEventCreate(None)
        loc = Quartz.CGEventGetLocation(event)
        return loc

    def _post_button(self, which: str, down: bool) -> None:
        button, down_type, up_type, _drag_type = _BUTTON[which]
        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        etype = down_type if down else up_type
        event = Quartz.CGEventCreateMouseEvent(source, etype, self._cursor(), button)
        # Critical: no modifier flags, or macOS may remap clicks (e.g. Control-click).
        Quartz.CGEventSetFlags(event, 0)
        Quartz.CGEventSetIntegerValueField(event, USER_DATA_FIELD, OUR_TAG)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _set_held(self, which: str | None) -> None:
        if which == self._held:
            return
        if self._held is not None:
            self._post_button(self._held, False)
            print(f"{self._held} click UP", flush=True)
        self._held = which
        if which is not None:
            self._post_button(which, True)
            print(f"{which} click DOWN (drag now)", flush=True)

    def _desired_hold(self, flags: int) -> str | None:
        masked = flags & _MODS
        if masked == LEFT_CHORD:
            return LEFT
        if masked == RIGHT_CHORD:
            return RIGHT
        return None

    def _on_event(self, proxy, event_type, event, refcon):
        if event_type in (
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        ):
            if self._tap is not None:
                Quartz.CGEventTapEnable(self._tap, True)
            return event

        # Ignore our own injected mouse events.
        if event_type in (
            Quartz.kCGEventLeftMouseDown,
            Quartz.kCGEventLeftMouseUp,
            Quartz.kCGEventLeftMouseDragged,
            Quartz.kCGEventRightMouseDown,
            Quartz.kCGEventRightMouseUp,
            Quartz.kCGEventRightMouseDragged,
        ):
            if Quartz.CGEventGetIntegerValueField(event, USER_DATA_FIELD) == OUR_TAG:
                return event

        # While virtually held, turn plain moves into button-drags so apps track it.
        if self._held is not None and event_type == Quartz.kCGEventMouseMoved:
            _button, _down, _up, drag_type = _BUTTON[self._held]
            Quartz.CGEventSetType(event, drag_type)
            Quartz.CGEventSetFlags(event, 0)
            return event

        if event_type in (
            Quartz.kCGEventFlagsChanged,
            Quartz.kCGEventKeyDown,
            Quartz.kCGEventKeyUp,
        ):
            flags = Quartz.CGEventGetFlags(event)
            self._set_held(self._desired_hold(flags))

        return event

    def run(self) -> None:
        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
            | Quartz.CGEventMaskBit(Quartz.kCGEventMouseMoved)
            | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseUp)
            | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDragged)
            | Quartz.CGEventMaskBit(Quartz.kCGEventRightMouseDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventRightMouseUp)
            | Quartz.CGEventMaskBit(Quartz.kCGEventRightMouseDragged)
        )

        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGHIDEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            self._on_event,
            None,
        )
        if self._tap is None:
            raise RuntimeError(
                "CGEventTapCreate failed — grant Accessibility permission and retry."
            )

        Quartz.CGEventTapEnable(self._tap, True)
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            source,
            Quartz.kCFRunLoopCommonModes,
        )

        print(
            "Ready. Control+Shift = left hold, Option+Shift = right hold. "
            "Release keys = release click. Ctrl+C to quit.",
            flush=True,
        )
        Quartz.CFRunLoopRun()


def main() -> int:
    if sys.platform != "darwin":
        print("This script is for macOS only.", file=sys.stderr)
        return 1

    argparse.ArgumentParser(
        description=(
            "Hold Control+Shift / Option+Shift to virtually press "
            "the left / right mouse button."
        )
    ).parse_args()

    try:
        ModifierClickHold().run()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            f"\nFailed: {exc}\n\n"
            "On macOS, enable Accessibility for your terminal / Cursor:\n"
            "  System Settings → Privacy & Security → Accessibility\n"
            "Then run this script again.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
