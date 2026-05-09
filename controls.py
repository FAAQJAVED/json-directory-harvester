"""
controls.py
===========
Cross-platform non-blocking keyboard listener and audio feedback.

On Windows : uses msvcrt for instant keypress detection.
On Unix/Mac: uses tty + select for raw keypress detection (no Enter needed).

Audio falls back to terminal bell on non-Windows platforms.
"""

import atexit
import logging
import sys
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)


class InputController:
    """
    Background-thread keyboard listener.

    Usage:
        controller = InputController()
        controller.start()
        key = controller.get_key()   # returns None if nothing pressed
        controller.stop()            # restores terminal, stops thread
    """

    def __init__(self) -> None:
        self._key: Optional[str] = None
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(
            target=self._listen, daemon=True, name="KeyboardListener"
        )
        self._unix_fd: Optional[int] = None
        self._unix_old_settings = None

    def start(self) -> None:
        """Initialise platform-specific terminal state and start the listener thread."""
        if sys.platform != "win32":
            self._init_unix_raw()
        self._thread.start()
        log.debug(
            "Input controller started (%s mode).",
            "Windows" if sys.platform == "win32" else "Unix",
        )

    def stop(self) -> None:
        """Stop the listener thread and restore the terminal to its original state."""
        self._running = False
        if sys.platform != "win32":
            self._restore_unix()
        log.debug("Input controller stopped.")

    # ── Unix terminal setup ───────────────────────────────────────────

    def _init_unix_raw(self) -> None:
        """Switch stdin to raw mode so individual keypresses are captured immediately."""
        try:
            import termios
            import tty
            self._unix_fd = sys.stdin.fileno()
            self._unix_old_settings = termios.tcgetattr(self._unix_fd)
            tty.setraw(self._unix_fd)
            atexit.register(self._restore_unix)
        except Exception as exc:
            log.warning(
                "Could not set raw terminal mode (%s). "
                "Key controls will require Enter on this platform.",
                exc,
            )

    def _restore_unix(self) -> None:
        """Restore stdin to its original cooked mode."""
        if self._unix_old_settings is not None:
            try:
                import termios
                termios.tcsetattr(
                    self._unix_fd, termios.TCSADRAIN, self._unix_old_settings
                )
                self._unix_old_settings = None
            except Exception:
                pass

    # ── Listener threads ──────────────────────────────────────────────

    def _listen(self) -> None:
        if sys.platform == "win32":
            self._listen_windows()
        else:
            self._listen_unix()

    def _listen_windows(self) -> None:
        import msvcrt
        while self._running:
            if msvcrt.kbhit():
                try:
                    ch = msvcrt.getch().decode("utf-8").lower()
                    with self._lock:
                        self._key = ch
                except Exception:
                    pass
            time.sleep(0.05)

    def _listen_unix(self) -> None:
        import select
        while self._running:
            try:
                readable, _, _ = select.select([sys.stdin], [], [], 0.05)
                if readable:
                    ch = sys.stdin.read(1).lower()
                    with self._lock:
                        self._key = ch
            except Exception:
                break

    # ── Public interface ──────────────────────────────────────────────

    def get_key(self) -> Optional[str]:
        """
        Return and clear the last key pressed.
        Returns None if no key has been pressed since the last call.
        """
        with self._lock:
            key = self._key
            self._key = None
            return key


# ── Audio helpers ─────────────────────────────────────────────────────

def beep(freq: int = 1000, duration_ms: int = 200) -> None:
    """
    Emit an audio alert.

    Windows : precise frequency tone via winsound.Beep.
    Other   : terminal bell character (behaviour depends on terminal config).
    Fails silently if audio hardware is unavailable.
    """
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(freq, duration_ms)
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
    except Exception:
        pass


def sound_sequence(
    freqs: list, duration_ms: int = 200, gap_s: float = 0.05
) -> None:
    """Play a sequence of tones with a short gap between each."""
    for freq in freqs:
        beep(freq, duration_ms)
        time.sleep(gap_s)
