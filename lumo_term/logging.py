"""Logging and session recording for LUMO-Term.

This module provides:
- Structured logging with configurable levels
- Session recording for conversation history
- Log analysis utilities
- Performance metrics tracking
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Any
from enum import Enum


# ============================================================================
# Configuration
# ============================================================================

LOG_DIR = Path.home() / ".local" / "share" / "lumo-term" / "logs"
SESSION_DIR = Path.home() / ".local" / "share" / "lumo-term" / "sessions"

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class LogLevel(Enum):
    """Log levels for LUMO-Term."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class Message:
    """A single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tokens_streamed: int = 0
    response_time_ms: int = 0


@dataclass
class SessionMetrics:
    """Performance metrics for a session."""
    startup_time_ms: int = 0
    total_messages: int = 0
    total_response_time_ms: int = 0
    avg_response_time_ms: int = 0
    first_token_times_ms: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def add_response(self, response_time_ms: int, first_token_ms: int = 0):
        self.total_messages += 1
        self.total_response_time_ms += response_time_ms
        self.avg_response_time_ms = self.total_response_time_ms // self.total_messages
        if first_token_ms:
            self.first_token_times_ms.append(first_token_ms)

    def add_error(self, error: str):
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "error": error
        })


@dataclass
class Session:
    """A complete conversation session."""
    session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str | None = None
    messages: list = field(default_factory=list)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    metadata: dict = field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs) -> Message:
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        return msg

    def end(self):
        self.ended_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "messages": [asdict(m) for m in self.messages],
            "metrics": asdict(self.metrics),
            "metadata": self.metadata,
        }

    def save(self, path: Path | None = None):
        """Save session to JSON file."""
        if path is None:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            path = SESSION_DIR / f"session_{self.session_id}.json"

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def load(cls, path: Path) -> "Session":
        """Load session from JSON file."""
        with open(path) as f:
            data = json.load(f)

        session = cls(
            session_id=data["session_id"],
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            metadata=data.get("metadata", {}),
        )
        session.messages = [Message(**m) for m in data.get("messages", [])]

        metrics_data = data.get("metrics", {})
        session.metrics = SessionMetrics(
            startup_time_ms=metrics_data.get("startup_time_ms", 0),
            total_messages=metrics_data.get("total_messages", 0),
            total_response_time_ms=metrics_data.get("total_response_time_ms", 0),
            avg_response_time_ms=metrics_data.get("avg_response_time_ms", 0),
            first_token_times_ms=metrics_data.get("first_token_times_ms", []),
            errors=metrics_data.get("errors", []),
        )
        return session


# ============================================================================
# Logger Setup
# ============================================================================

def setup_logger(
    name: str = "lumo_term",
    level: LogLevel = LogLevel.INFO,
    log_file: bool = True,
    console: bool = True,
) -> logging.Logger:
    """Set up and return a configured logger.

    Args:
        name: Logger name
        level: Logging level
        log_file: Whether to log to file
        console: Whether to log to console

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level.value)

    # Clear existing handlers
    logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"lumo_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Global logger instance
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


# ============================================================================
# Session Manager
# ============================================================================

class SessionManager:
    """Manages conversation sessions and logging."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or get_logger()
        self.current_session: Session | None = None
        self._message_start_time: float | None = None
        self._first_token_time: float | None = None

    def start_session(self, metadata: dict | None = None) -> Session:
        """Start a new session."""
        self.current_session = Session(metadata=metadata or {})
        self.logger.info(f"Session started: {self.current_session.session_id}")
        return self.current_session

    def end_session(self) -> Session | None:
        """End the current session and save it."""
        if self.current_session:
            self.current_session.end()
            path = self.current_session.save()
            self.logger.info(f"Session ended and saved to: {path}")
            session = self.current_session
            self.current_session = None
            return session
        return None

    def record_startup(self, startup_time_ms: int):
        """Record browser startup time."""
        if self.current_session:
            self.current_session.metrics.startup_time_ms = startup_time_ms
            self.logger.debug(f"Startup time: {startup_time_ms}ms")

    def start_message(self):
        """Mark the start of a message send."""
        self._message_start_time = time.perf_counter()
        self._first_token_time = None

    def record_first_token(self):
        """Record when first token is received."""
        if self._message_start_time and self._first_token_time is None:
            self._first_token_time = time.perf_counter()

    def record_user_message(self, content: str):
        """Record a user message."""
        if self.current_session:
            self.current_session.add_message("user", content)
            self.logger.debug(f"User: {content[:100]}...")

    def record_assistant_message(self, content: str, tokens_streamed: int = 0):
        """Record an assistant response."""
        if self.current_session:
            response_time_ms = 0
            first_token_ms = 0

            if self._message_start_time:
                response_time_ms = int((time.perf_counter() - self._message_start_time) * 1000)

            if self._first_token_time and self._message_start_time:
                first_token_ms = int((self._first_token_time - self._message_start_time) * 1000)

            self.current_session.add_message(
                "assistant",
                content,
                tokens_streamed=tokens_streamed,
                response_time_ms=response_time_ms,
            )
            self.current_session.metrics.add_response(response_time_ms, first_token_ms)

            self.logger.debug(
                f"Assistant response: {len(content)} chars, "
                f"{response_time_ms}ms total, {first_token_ms}ms to first token"
            )

    def record_error(self, error: str):
        """Record an error."""
        if self.current_session:
            self.current_session.metrics.add_error(error)
        self.logger.error(error)


# ============================================================================
# Log Analysis
# ============================================================================

class LogAnalyzer:
    """Analyze session logs for insights."""

    def __init__(self, session_dir: Path | None = None):
        self.session_dir = session_dir or SESSION_DIR

    def list_sessions(self) -> list[Path]:
        """List all saved sessions."""
        if not self.session_dir.exists():
            return []
        return sorted(self.session_dir.glob("session_*.json"), reverse=True)

    def load_recent_sessions(self, count: int = 10) -> list[Session]:
        """Load the most recent sessions."""
        paths = self.list_sessions()[:count]
        return [Session.load(p) for p in paths]

    def get_session_summary(self, session: Session) -> dict:
        """Get a summary of a session."""
        return {
            "session_id": session.session_id,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "message_count": len(session.messages),
            "user_messages": sum(1 for m in session.messages if m.role == "user"),
            "assistant_messages": sum(1 for m in session.messages if m.role == "assistant"),
            "avg_response_time_ms": session.metrics.avg_response_time_ms,
            "errors": len(session.metrics.errors),
        }

    def get_performance_stats(self, sessions: list[Session] | None = None) -> dict:
        """Get aggregate performance statistics."""
        if sessions is None:
            sessions = self.load_recent_sessions()

        if not sessions:
            return {"error": "No sessions found"}

        all_response_times = []
        all_first_token_times = []
        all_startup_times = []
        total_messages = 0
        total_errors = 0

        for session in sessions:
            all_startup_times.append(session.metrics.startup_time_ms)
            total_messages += session.metrics.total_messages
            total_errors += len(session.metrics.errors)

            for msg in session.messages:
                if msg.role == "assistant" and msg.response_time_ms:
                    all_response_times.append(msg.response_time_ms)

            all_first_token_times.extend(session.metrics.first_token_times_ms)

        def calc_stats(values: list) -> dict:
            if not values:
                return {"count": 0}
            import statistics
            return {
                "count": len(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            }

        return {
            "sessions_analyzed": len(sessions),
            "total_messages": total_messages,
            "total_errors": total_errors,
            "startup_times_ms": calc_stats(all_startup_times),
            "response_times_ms": calc_stats(all_response_times),
            "first_token_times_ms": calc_stats(all_first_token_times),
        }

    def print_report(self, sessions: list[Session] | None = None):
        """Print a human-readable analysis report."""
        stats = self.get_performance_stats(sessions)

        print("=" * 60)
        print("LUMO-TERM PERFORMANCE ANALYSIS")
        print("=" * 60)

        if "error" in stats:
            print(stats["error"])
            return

        print(f"\nSessions analyzed: {stats['sessions_analyzed']}")
        print(f"Total messages: {stats['total_messages']}")
        print(f"Total errors: {stats['total_errors']}")

        print("\n--- Startup Times ---")
        startup = stats["startup_times_ms"]
        if startup["count"]:
            print(f"  Mean:   {startup['mean']:.0f}ms")
            print(f"  Median: {startup['median']:.0f}ms")
            print(f"  Range:  {startup['min']:.0f}ms - {startup['max']:.0f}ms")

        print("\n--- Response Times ---")
        response = stats["response_times_ms"]
        if response["count"]:
            print(f"  Mean:   {response['mean']:.0f}ms")
            print(f"  Median: {response['median']:.0f}ms")
            print(f"  Range:  {response['min']:.0f}ms - {response['max']:.0f}ms")

        print("\n--- Time to First Token ---")
        first_token = stats["first_token_times_ms"]
        if first_token["count"]:
            print(f"  Mean:   {first_token['mean']:.0f}ms")
            print(f"  Median: {first_token['median']:.0f}ms")
            print(f"  Range:  {first_token['min']:.0f}ms - {first_token['max']:.0f}ms")

        print("=" * 60)


# ============================================================================
# Convenience Functions
# ============================================================================

def log_debug(msg: str):
    """Log a debug message."""
    get_logger().debug(msg)


def log_info(msg: str):
    """Log an info message."""
    get_logger().info(msg)


def log_warning(msg: str):
    """Log a warning message."""
    get_logger().warning(msg)


def log_error(msg: str):
    """Log an error message."""
    get_logger().error(msg)


# Global session manager
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
