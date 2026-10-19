# -*- coding: utf-8 -*-
"""
🌸 Kazumi Persistent Restart-Loop Protector
Tracks rapid startup failure timestamps across process restarts to prevent
continuous crash-reboot hammering on hosting platforms (Bot-Hosting.net, Docker, Render).
Atomically persists minimal timestamp metadata to a Git-ignored state file.
Quarantines corrupted state files without leaking sensitive information.
"""

import os
import json
import time
import random
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("RestartLoopProtector")


class RestartLoopProtector:
    """
    Manages persistent startup failure state to apply exponential backoff with jitter
    when consecutive rapid process crashes or restarts occur.
    """

    def __init__(
        self,
        state_file: str = ".crash_loop_state.json",
        window_seconds: float = 120.0,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 30.0,
        max_rapid_failures: int = 3,
    ):
        self.state_file = state_file
        self.window_seconds = window_seconds
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.max_rapid_failures = max_rapid_failures

    def _read_state(self) -> Dict[str, Any]:
        """Safely loads state. Quarantines corrupt state files as *.corrupted.<timestamp>."""
        if not os.path.exists(self.state_file):
            return {"failures": []}

        try:
            if os.path.getsize(self.state_file) > 0:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and isinstance(data.get("failures"), list):
                        return data
        except Exception as e:
            logger.warning(f"Failed to read crash state {self.state_file}: {e}. Quarantining corrupt state.")
            corrupt_dest = f"{self.state_file}.corrupted.{int(time.time())}"
            try:
                os.rename(self.state_file, corrupt_dest)
            except Exception:
                pass

        return {"failures": []}

    def _write_state(self, state: Dict[str, Any]) -> bool:
        """Atomically writes state to a temporary file and replaces target."""
        try:
            dirname = os.path.dirname(self.state_file)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            tmp_path = f"{self.state_file}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            for attempt in range(4):
                try:
                    os.replace(tmp_path, self.state_file)
                    return True
                except (PermissionError, OSError):
                    if attempt < 3:
                        time.sleep(0.05 * (attempt + 1))
                    else:
                        raise
            return True
        except Exception as e:
            logger.warning(f"Could not write crash loop state: {e}")
            if os.path.exists(f"{self.state_file}.tmp"):
                try:
                    os.remove(f"{self.state_file}.tmp")
                except Exception:
                    pass
            return False

    def record_boot_and_get_delay(self, now: Optional[float] = None) -> float:
        """
        Records a startup event.
        Returns the backoff delay in seconds (0.0 if normal, >0.0 if in rapid crash loop).
        """
        curr = now if now is not None else time.time()
        state = self._read_state()
        failures: List[float] = [
            t for t in state.get("failures", [])
            if isinstance(t, (int, float)) and curr - t <= self.window_seconds
        ]

        failures.append(curr)
        state["failures"] = failures
        self._write_state(state)

        count = len(failures)
        if count <= self.max_rapid_failures:
            return 0.0

        excess = count - self.max_rapid_failures
        raw_delay = self.base_delay_seconds * (2 ** (excess - 1))
        jitter = random.uniform(0.1, 0.5)
        delay = min(self.max_delay_seconds, raw_delay + jitter)
        logger.warning(
            f"⚠️ [RESTART_LOOP_PROTECTION] Rapid crash loop detected ({count} restarts in {self.window_seconds}s). "
            f"Backing off for {delay:.2f}s before attempting gateway reconnection..."
        )
        return delay

    def record_healthy(self) -> None:
        """Clears or decays failure records after a verified healthy boot."""
        state = {"failures": []}
        self._write_state(state)
