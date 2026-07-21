#!/usr/bin/env python3
"""
Fix flaky left-click / drag by debouncing the physical mouse button.

Worn switches often open for a few milliseconds while dragging. The OS sees that
as a release and drops the drag. This script intercepts left-button events and
ignores brief "up" blips so macOS keeps thinking you're still holding.

Setup (once):
  System Settings → Privacy & Security → Accessibility
  → enable your Terminal app (Terminal, iTerm, Cursor, etc.)

Run:
  .venv/bin/python mouse_debounce.py
  .venv/bin/python mouse_debounce.py --debounce-ms 120
  .venv/bin/python mouse_debounce.py --click-lock
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

try:
    import Quartz
except ImportError:
    print(
        "Missing Quartz bindings. From this folder run:\n"
        "  python3 -m venv .venv && .venv/bin/pip install pyobjc-framework-Quartz",
        file=sys.stderr,
    )
    raise SystemExit(1)


OUR_TAG = 0x4D4F5553  # 'MOUS' — marks events we inject so we don't re-process them
USER_DATA_FIELD = Quartz.kCGEventSourceUserData


class LeftClickDebouncer:
    def __init__(self, debounce_ms: int, click_lock: bool, lock_ms: int) -> None:
        self.debounce_s = max(debounce_ms, 1) / 1000.0
        self.click_lock = click_lock
        self.lock_s = max(lock_ms, 1) / 1000.0

        self._lock = threading.Lock()
        self._logical_down = False
        self._pending_up: threading.Timer | None = None
        self._down_at: float | None = None
        self._locked = False
        self._tap = None
        self._last_location = Quartz.CGPointMake(0, 0)

    def _cancel_pending_up(self) -> None:
        if self._pending_up is not None:
            self._pending_up.cancel()
            self._pending_up = None

    def _is_ours(self, event) -> bool:
        return Quartz.CGEventGetIntegerValueField(event, USER_DATA_FIELD) == OUR_TAG

    def _post(self, down: bool, location) -> None:
        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        etype = (
            Quartz.kCGEventLeftMouseDown if down else Quartz.kCGEventLeftMouseUp
        )
        event = Quartz.CGEventCreateMouseEvent(
            source, etype, location, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventSetIntegerValueField(event, USER_DATA_FIELD, OUR_TAG)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _commit_up(self) -> None:
        with self._lock:
            self._pending_up = None
            if not self._logical_down:
                return
            self._logical_down = False
            self._locked = False
            self._down_at = None
            location = self._last_location
        self._post(False, location)
        print("release", flush=True)

    def _on_event(self, proxy, event_type, event, refcon):
        if event_type in (
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        ):
            if self._tap is not None:
                Quartz.CGEventTapEnable(self._tap, True)
            return event

        if event_type not in (
            Quartz.kCGEventLeftMouseDown,
            Quartz.kCGEventLeftMouseUp,
        ):
            return event

        if self._is_ours(event):
            return event

        location = Quartz.CGEventGetLocation(event)
        now = time.monotonic()
        pressed = event_type == Quartz.kCGEventLeftMouseDown

        with self._lock:
            self._last_location = location

            if pressed:
                self._cancel_pending_up()

                if self._locked:
                    # Second click while locked → unlock.
                    self._locked = False
                    self._logical_down = False
                    self._down_at = None
                    threading.Thread(
                        target=self._post, args=(False, location), daemon=True
                    ).start()
                    print("click-lock off", flush=True)
                    return None

                if not self._logical_down:
                    self._logical_down = True
                    self._down_at = now
                    print("press", flush=True)
                    return event  # let real down through

                # Extra bounce-down while held: swallow.
                return None

            # Physical up
            if not self._logical_down:
                return event

            if self.click_lock and self._down_at is not None:
                if (now - self._down_at) >= self.lock_s and not self._locked:
                    self._locked = True
                    self._cancel_pending_up()
                    print("click-lock on (move, then click to release)", flush=True)
                    return None

            if self._locked:
                return None

            # Swallow this up; only release if it stays up past the debounce window.
            # If the switch bounces back down in time, _cancel_pending_up keeps the hold.
            self._cancel_pending_up()
            t = threading.Timer(self.debounce_s, self._commit_up)
            t.daemon = True
            self._pending_up = t
            t.start()
            return None

    def run(self) -> None:
        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseUp)
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
            f"Debouncing left click ({int(self.debounce_s * 1000)} ms). "
            f"Ctrl+C to stop."
            + (" Click-lock enabled." if self.click_lock else ""),
            flush=True,
        )
        Quartz.CFRunLoopRun()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Debounce left mouse button so drags don't drop on a worn switch."
    )
    p.add_argument(
        "--debounce-ms",
        type=int,
        default=80,
        help="Ignore button-up blips shorter than this (default: 80). Try 50–150.",
    )
    p.add_argument(
        "--click-lock",
        action="store_true",
        help="Hold briefly to lock the press; click again to release.",
    )
    p.add_argument(
        "--lock-ms",
        type=int,
        default=400,
        help="Hold duration to engage click-lock (default: 400).",
    )
    return p.parse_args()


def main() -> int:
    if sys.platform != "darwin":
        print("This script is for macOS only.", file=sys.stderr)
        return 1

    args = parse_args()
    try:
        LeftClickDebouncer(
            debounce_ms=args.debounce_ms,
            click_lock=args.click_lock,
            lock_ms=args.lock_ms,
        ).run()
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
