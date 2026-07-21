#!/usr/bin/env python3
"""
Hold Control+Shift to make macOS think left-click is pressed.

Use this when the physical left button is unreliable for dragging:
  1. Move the cursor into place
  2. Hold Control+Shift  → virtual left-button down
  3. Move the mouse      → drag
  4. Release the keys    → virtual left-button up

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
CHORD = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskShift


class ModifierClickHold:
    """Virtual left-click while Control+Shift are held."""

    def __init__(self) -> None:
        self._held = False
        self._tap = None

    def _cursor(self):
        # CGEventSourceCreate + CGEventGetLocation needs an event; use current position.
        event = Quartz.CGEventCreate(None)
        loc = Quartz.CGEventGetLocation(event)
        return loc

    def _post_button(self, down: bool) -> None:
        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        etype = (
            Quartz.kCGEventLeftMouseDown if down else Quartz.kCGEventLeftMouseUp
        )
        event = Quartz.CGEventCreateMouseEvent(
            source, etype, self._cursor(), Quartz.kCGMouseButtonLeft
        )
        # Critical: no Control/Shift flags, or macOS treats it as Control-click.
        Quartz.CGEventSetFlags(event, 0)
        Quartz.CGEventSetIntegerValueField(event, USER_DATA_FIELD, OUR_TAG)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _set_held(self, held: bool) -> None:
        if held == self._held:
            return
        self._held = held
        self._post_button(held)
        print("click DOWN (drag now)" if held else "click UP", flush=True)

    def _chord_active(self, flags: int) -> bool:
        return (flags & CHORD) == CHORD

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
        ):
            if Quartz.CGEventGetIntegerValueField(event, USER_DATA_FIELD) == OUR_TAG:
                return event

        # While virtually held, turn plain moves into left-drags so apps track it.
        if self._held and event_type == Quartz.kCGEventMouseMoved:
            Quartz.CGEventSetType(event, Quartz.kCGEventLeftMouseDragged)
            Quartz.CGEventSetFlags(event, 0)
            return event

        if event_type in (
            Quartz.kCGEventFlagsChanged,
            Quartz.kCGEventKeyDown,
            Quartz.kCGEventKeyUp,
        ):
            flags = Quartz.CGEventGetFlags(event)
            self._set_held(self._chord_active(flags))

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
            "Ready. Hold Control+Shift = left click held. "
            "Release keys = release click. Ctrl+C to quit.",
            flush=True,
        )
        Quartz.CFRunLoopRun()


def main() -> int:
    if sys.platform != "darwin":
        print("This script is for macOS only.", file=sys.stderr)
        return 1

    argparse.ArgumentParser(
        description="Hold Control+Shift to virtually press the left mouse button."
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
