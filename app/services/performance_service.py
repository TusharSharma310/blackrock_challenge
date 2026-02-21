"""
Performance Service: Tracks and reports system execution metrics.
Monitors response time, memory usage, and thread counts.
"""
import time
import threading
import psutil
import os
from datetime import datetime, timezone
from typing import Optional


class PerformanceTracker:
    """Thread-safe singleton for tracking system performance metrics."""

    _instance: Optional["PerformanceTracker"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.start_time = time.time()
        self.request_times: list = []
        self.request_count = 0
        self._lock = threading.Lock()
        self.process = psutil.Process(os.getpid())

    def record_request(self, duration_seconds: float):
        """Record the duration of a completed request."""
        with self._lock:
            self.request_times.append(duration_seconds)
            self.request_count += 1
            # Keep only last 1000 request times to avoid memory growth
            if len(self.request_times) > 1000:
                self.request_times = self.request_times[-1000:]

    def get_metrics(self) -> dict:
        """Retrieve current performance metrics."""
        with self._lock:
            # Response time: average of recent requests, or uptime if no requests yet
            if self.request_times:
                avg_ms = sum(self.request_times) / len(self.request_times) * 1000
                last_ms = self.request_times[-1] * 1000
                # Format as duration in milliseconds
                total_seconds = last_ms / 1000
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                milliseconds = int((total_seconds % 1) * 1000)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            else:
                uptime = time.time() - self.start_time
                hours = int(uptime // 3600)
                minutes = int((uptime % 3600) // 60)
                seconds = int(uptime % 60)
                milliseconds = 0
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

            # Memory usage
            try:
                mem_info = self.process.memory_info()
                mem_mb = mem_info.rss / (1024 * 1024)
                memory_str = f"{mem_mb:.2f} MB"
            except Exception:
                memory_str = "N/A"

            # Thread count
            try:
                thread_count = threading.active_count()
            except Exception:
                thread_count = 1

            return {
                "time": time_str,
                "memory": memory_str,
                "threads": thread_count,
            }


# Global performance tracker instance
performance_tracker = PerformanceTracker()
