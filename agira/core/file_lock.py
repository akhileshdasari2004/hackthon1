"""File-based locking for job concurrency control.

Provides crash-safe, atomic lock acquisition per job_id to prevent:
- Double execution of the same job
- Race conditions across concurrent jobs
- Stale locks from crashing processes

Usage:
    from agira.core.file_lock import JobLock, acquire_lock, release_lock

    with JobLock(job_id, jobs_dir="/path/to/.agira-jobs") as lock:
        if lock.acquired:
            # Execute job safely
            pass
"""

from __future__ import annotations

import os
import signal
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


# Default stale lock threshold (seconds) — lock older than this is considered stale
DEFAULT_STALE_THRESHOLD = 3600  # 1 hour


@dataclass
class LockResult:
    """Result of a lock acquisition attempt."""

    acquired: bool
    job_id: str
    lock_path: Path
    holder_pid: int | None = None
    acquired_at: float | None = None
    stale: bool = False


class FileLock:
    """Atomic file-based lock with crash-safe semantics.

    Lock file format (.lock):
        <pid>:<timestamp>:<hostname>

    Features:
    - Atomic creation via O_CREAT | O_EXCL (no TOCTOU race)
    - Crash-safe: stale lock detection via timestamp
    - No external dependencies (pure stdlib)
    """

    def __init__(
        self,
        job_id: str,
        lock_dir: Path,
        stale_threshold: float = DEFAULT_STALE_THRESHOLD,
    ) -> None:
        self.job_id = job_id
        self.lock_dir = Path(lock_dir)
        self.stale_threshold = stale_threshold
        self._lock_path = self.lock_dir / f"{job_id}.lock"
        self._acquired = False
        self._holder_pid: int | None = None
        self._acquired_at: float | None = None

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    @property
    def acquired(self) -> bool:
        return self._acquired

    def try_acquire(self) -> LockResult:
        """Attempt to acquire lock atomically.

        Returns LockResult with acquired=True if lock was obtained.
        If lock exists, checks if it's stale before returning acquired=False.
        """
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        # Check existing lock first
        if self._lock_path.exists():
            existing = self._read_lock()
            if existing:
                holder_pid, acquired_at, _ = existing
                age = time.time() - acquired_at
                if age < self.stale_threshold:
                    # Lock is held by live process
                    return LockResult(
                        acquired=False,
                        job_id=self.job_id,
                        lock_path=self._lock_path,
                        holder_pid=holder_pid,
                        acquired_at=acquired_at,
                        stale=False,
                    )
                # Stale lock — remove it and retry
                self._remove_stale_lock()

        # Atomic lock creation
        try:
            fd = os.open(
                str(self._lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
        except FileExistsError:
            # Lost race — another process got it first
            return LockResult(
                acquired=False,
                job_id=self.job_id,
                lock_path=self._lock_path,
            )

        # Write lock metadata
        self._holder_pid = os.getpid()
        self._acquired_at = time.time()
        hostname = os.environ.get("HOSTNAME", "unknown")
        lock_content = f"{self._holder_pid}:{self._acquired_at}:{hostname}\n"
        os.write(fd, lock_content.encode("utf-8"))
        os.close(fd)

        self._acquired = True

        # Register cleanup on process exit
        self._register_cleanup_handler()

        return LockResult(
            acquired=True,
            job_id=self.job_id,
            lock_path=self._lock_path,
            holder_pid=self._holder_pid,
            acquired_at=self._acquired_at,
            stale=False,
        )

    def release(self) -> bool:
        """Release the lock if we are the holder.

        Returns True if lock was released, False if we didn't hold it.
        """
        if not self._acquired and not self._lock_path.exists():
            return True  # Already released

        if not self._lock_path.exists():
            return True

        try:
            existing = self._read_lock()
            if existing:
                holder_pid, _, _ = existing
                if holder_pid != os.getpid():
                    # Not our lock — don't remove
                    return False
        except Exception:
            pass

        return self._remove_stale_lock()

    def _read_lock(self) -> tuple[int, float, str] | None:
        """Read lock file contents. Returns (pid, timestamp, hostname) or None."""
        try:
            content = self._lock_path.read_text(encoding="utf-8").strip()
            if not content:
                return None
            parts = content.split(":", 2)
            if len(parts) >= 2:
                return int(parts[0]), float(parts[1]), parts[2] if len(parts) > 2 else "unknown"
        except (ValueError, OSError):
            pass
        return None

    def _remove_stale_lock(self) -> bool:
        """Remove lock file. Returns True if removed."""
        try:
            if self._lock_path.exists():
                self._lock_path.unlink()
            return True
        except OSError:
            return False

    def _register_cleanup_handler(self) -> None:
        """Register signal handlers to release lock on exit."""
        def cleanup_handler(signum, frame):
            self.release()
            raise SystemExit(signum)

        # Only register once per process
        if not hasattr(self, "_cleanup_registered"):
            signal.signal(signal.SIGTERM, cleanup_handler)
            signal.signal(signal.SIGINT, cleanup_handler)
            self._cleanup_registered = True  # type: ignore[attr-defined]


class JobLock:
    """Context manager for safe job lock acquisition.

    Usage:
        with JobLock(job_id, jobs_dir) as lock:
            if lock.acquired:
                # Safe to execute job
                pass
    """

    def __init__(
        self,
        job_id: str,
        jobs_dir: str | Path,
        stale_threshold: float = DEFAULT_STALE_THRESHOLD,
        timeout: float = 0.0,
        poll_interval: float = 0.1,
    ) -> None:
        self.jobs_dir = Path(jobs_dir)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._lock = FileLock(job_id, self.jobs_dir, stale_threshold)
        self._acquired = False

    @property
    def acquired(self) -> bool:
        return self._acquired

    def __enter__(self) -> "JobLock":
        start = time.monotonic()
        while True:
            result = self._lock.try_acquire()
            if result.acquired:
                self._acquired = True
                return self
            if self.timeout <= 0:
                break
            if time.monotonic() - start >= self.timeout:
                break
            time.sleep(self.poll_interval)
        self._acquired = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._acquired:
            self._lock.release()
            self._acquired = False


@contextmanager
def acquire_lock(
    job_id: str,
    jobs_dir: str | Path,
    stale_threshold: float = DEFAULT_STALE_THRESHOLD,
    timeout: float = 0.0,
) -> Iterator[LockResult]:
    """Convenience function for lock acquisition.

    Usage:
        result = acquire_lock("job-123", "/path/to/.agira-jobs")
        if result.acquired:
            # Execute job
            pass
        # Lock auto-released on exit
    """
    lock = FileLock(job_id, Path(jobs_dir), stale_threshold)
    start = time.monotonic()
    poll_interval = 0.1

    while True:
        result = lock.try_acquire()
        if result.acquired:
            try:
                yield result
            finally:
                lock.release()
            return
        if timeout <= 0:
            yield result
            return
        if time.monotonic() - start >= timeout:
            yield result
            return
        time.sleep(poll_interval)


def release_lock(job_id: str, jobs_dir: str | Path) -> bool:
    """Explicitly release a lock by job_id.

    Returns True if lock was released.
    """
    lock = FileLock(job_id, Path(jobs_dir))
    return lock.release()


def is_locked(job_id: str, jobs_dir: str | Path) -> bool:
    """Check if a job_id is currently locked.

    Returns True if lock exists and is not stale.
    """
    lock_path = Path(jobs_dir) / f"{job_id}.lock"
    if not lock_path.exists():
        return False
    lock = FileLock(job_id, Path(jobs_dir))
    result = lock.try_acquire()
    if result.acquired:
        lock.release()
        return False
    return not result.stale


def cleanup_stale_locks(jobs_dir: str | Path, threshold: float = DEFAULT_STALE_THRESHOLD) -> int:
    """Remove all stale locks from jobs directory.

    Returns count of locks removed.
    """
    jobs_dir = Path(jobs_dir)
    if not jobs_dir.exists():
        return 0

    removed = 0
    current_pid = os.getpid()

    for lock_file in jobs_dir.glob("*.lock"):
        job_id = lock_file.stem
        lock = FileLock(job_id, jobs_dir, threshold)
        try:
            existing = lock._read_lock()
            if existing:
                holder_pid, acquired_at, _ = existing
                age = time.time() - acquired_at
                if age >= threshold and holder_pid != current_pid:
                    if lock._remove_stale_lock():
                        removed += 1
        except Exception:
            pass

    return removed