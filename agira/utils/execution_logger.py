"""Execution timeline logger — tracks node timing, batches, and parallel overlap."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class NodeEvent:
    node_name: str
    batch: int
    event: str  # "start" | "end" | "skip" | "retry" | "fail"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float | None = None


@dataclass
class BatchSummary:
    batch_id: int
    nodes: list[str]
    start_ms: float = 0.0
    end_ms: float = 0.0
    wallclock_ms: float = 0.0
    is_parallel: bool = True

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms


class ExecutionLogger:
    """Thread-safe execution timeline logger.
    
    Tracks:
    - Per-node start/end times and duration
    - Batch execution grouping
    - Parallel overlap detection
    - Total parallelism gain
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._node_events: dict[str, list[NodeEvent]] = {}
        self._batch_summaries: list[BatchSummary] = []
        self._node_start_times: dict[str, float] = {}
        self._batch_start_times: dict[int, float] = {}
        self._absolute_start: float = 0.0
        self._absolute_end: float = 0.0

    def start_execution(self) -> None:
        with self._lock:
            self._absolute_start = time.perf_counter() * 1000

    def end_execution(self) -> None:
        with self._lock:
            self._absolute_end = time.perf_counter() * 1000

    def log_node_start(self, node_name: str, batch: int) -> None:
        with self._lock:
            self._node_start_times[node_name] = time.perf_counter() * 1000
            if node_name not in self._node_events:
                self._node_events[node_name] = []
            self._node_events[node_name].append(NodeEvent(
                node_name=node_name,
                batch=batch,
                event="start",
            ))
            # Track batch start
            if batch not in self._batch_start_times:
                self._batch_start_times[batch] = time.perf_counter() * 1000

    def log_node_end(
        self,
        node_name: str,
        batch: int,
        status: str,
        error: str | None = None,
    ) -> None:
        with self._lock:
            end_ms = time.perf_counter() * 1000
            start_ms = self._node_start_times.get(node_name, end_ms)
            duration = end_ms - start_ms
            if node_name not in self._node_events:
                self._node_events[node_name] = []
            self._node_events[node_name].append(NodeEvent(
                node_name=node_name,
                batch=batch,
                event=status.lower(),
                duration_ms=round(duration, 2),
            ))

    def log_node_skip(self, node_name: str, reason: str) -> None:
        with self._lock:
            if node_name not in self._node_events:
                self._node_events[node_name] = []
            self._node_events[node_name].append(NodeEvent(
                node_name=node_name,
                batch=-1,
                event="skip",
            ))

    def finalize_batch(self, batch_id: int, nodes: list[str], is_parallel: bool = True) -> None:
        with self._lock:
            batch_start = self._batch_start_times.get(batch_id, 0)
            now = time.perf_counter() * 1000
            self._batch_summaries.append(BatchSummary(
                batch_id=batch_id,
                nodes=nodes,
                start_ms=batch_start,
                end_ms=now,
                wallclock_ms=now - batch_start,
                is_parallel=is_parallel,
            ))

    # ─── Report Generation ───────────────────────────────────────────────────

    def get_node_timeline(self) -> list[dict[str, Any]]:
        """Return timeline of all node events ordered by time."""
        with self._lock:
            result = []
            for node_name, events in self._node_events.items():
                for ev in events:
                    result.append({
                        "node": node_name,
                        "batch": ev.batch,
                        "event": ev.event,
                        "timestamp": ev.timestamp,
                        "duration_ms": ev.duration_ms,
                    })
            return sorted(result, key=lambda x: x["timestamp"])

    def get_batch_timings(self) -> list[dict[str, Any]]:
        """Return batch timings with parallel gain analysis."""
        with self._lock:
            total_sequential = sum(b.duration_ms for b in self._batch_summaries)
            total_wallclock = self._absolute_end - self._absolute_start
            overlap_saved = total_sequential - total_wallclock
            parallel_gain_pct = (overlap_saved / total_sequential * 100) if total_sequential > 0 else 0.0

            return [
                {
                    "batch_id": b.batch_id,
                    "nodes": b.nodes,
                    "duration_ms": round(b.wallclock_ms, 2),
                    "is_parallel": b.is_parallel,
                    "node_count": len(b.nodes),
                }
                for b in sorted(self._batch_summaries, key=lambda x: x.batch_id)
            ] + [{
                "total_sequential_ms": round(total_sequential, 2),
                "total_wallclock_ms": round(total_wallclock, 2),
                "overlap_saved_ms": round(overlap_saved, 2),
                "parallel_gain_pct": round(parallel_gain_pct, 1),
                "total_nodes": len(self._node_events),
            }]

    def print_timeline_report(self) -> None:
        """Print a human-readable execution timeline report."""
        print("\n" + "=" * 60)
        print("EXECUTION TIMELINE REPORT")
        print("=" * 60)

        # Per-node table
        print(f"\n{'Node':<30} {'Batch':>6} {'Event':>8} {'Duration':>12}")
        print("-" * 60)
        for entry in self.get_node_timeline():
            duration = f"{entry['duration_ms']:.2f}ms" if entry['duration_ms'] else "—"
            print(f"{entry['node']:<30} {entry['batch']:>6} {entry['event']:>8} {duration:>12}")

        # Batch summary
        print("\n" + "-" * 60)
        print("BATCH EXECUTION SUMMARY")
        print("-" * 60)
        timings = self.get_batch_timings()
        last = timings[-1]
        for b in timings[:-1]:
            parallel_marker = "∥" if b["is_parallel"] else "→"
            print(f"  Batch {b['batch_id']:>2}: {parallel_marker} {b['node_count']} nodes, "
                  f"{b['duration_ms']:>8.2f}ms")

        print("-" * 60)
        print(f"  Sequential equivalent:  {last['total_sequential_ms']:>10.2f}ms")
        print(f"  Actual wall-clock:      {last['total_wallclock_ms']:>10.2f}ms")
        print(f"  Parallel overlap saved: {last['overlap_saved_ms']:>10.2f}ms "
              f"({last['parallel_gain_pct']:.1f}% speedup)")
        print(f"  Total nodes executed:   {last['total_nodes']:>10}")
        print("=" * 60 + "\n")

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_timeline": self.get_node_timeline(),
            "batch_timings": self.get_batch_timings(),
            "parallel_gain_pct": self.get_batch_timings()[-1]["parallel_gain_pct"],
        }


# Global singleton
_execution_logger: ExecutionLogger | None = None
_logger_lock = threading.Lock()


def get_execution_logger() -> ExecutionLogger:
    global _execution_logger
    if _execution_logger is None:
        with _logger_lock:
            if _execution_logger is None:
                _execution_logger = ExecutionLogger()
    return _execution_logger


def reset_execution_logger() -> None:
    global _execution_logger
    with _logger_lock:
        _execution_logger = ExecutionLogger()