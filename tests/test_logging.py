"""Tests for logging and session recording functionality."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from lumo_term.logging import (
    Session,
    SessionManager,
    SessionMetrics,
    Message,
    LogAnalyzer,
    setup_logger,
    get_logger,
    LogLevel,
)


# ============================================================================
# Message Tests
# ============================================================================

class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        """Message should be created with required fields."""
        msg = Message(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None
        assert msg.tokens_streamed == 0
        assert msg.response_time_ms == 0

    def test_message_with_metrics(self):
        """Message should accept optional metrics."""
        msg = Message(
            role="assistant",
            content="Response",
            tokens_streamed=50,
            response_time_ms=1500
        )

        assert msg.tokens_streamed == 50
        assert msg.response_time_ms == 1500


# ============================================================================
# SessionMetrics Tests
# ============================================================================

class TestSessionMetrics:
    """Test SessionMetrics dataclass."""

    def test_empty_metrics(self):
        """New metrics should have zero values."""
        metrics = SessionMetrics()

        assert metrics.startup_time_ms == 0
        assert metrics.total_messages == 0
        assert metrics.avg_response_time_ms == 0

    def test_add_response(self):
        """Adding responses should update metrics."""
        metrics = SessionMetrics()

        metrics.add_response(1000, 200)
        assert metrics.total_messages == 1
        assert metrics.avg_response_time_ms == 1000

        metrics.add_response(2000, 300)
        assert metrics.total_messages == 2
        assert metrics.avg_response_time_ms == 1500

    def test_add_error(self):
        """Adding errors should record them."""
        metrics = SessionMetrics()

        metrics.add_error("Test error")
        assert len(metrics.errors) == 1
        assert metrics.errors[0]["error"] == "Test error"


# ============================================================================
# Session Tests
# ============================================================================

class TestSession:
    """Test Session class."""

    def test_session_creation(self):
        """Session should be created with default values."""
        session = Session()

        assert session.session_id is not None
        assert session.started_at is not None
        assert session.ended_at is None
        assert session.messages == []

    def test_add_message(self):
        """Session should track messages."""
        session = Session()

        msg = session.add_message("user", "Hello")
        assert len(session.messages) == 1
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_end_session(self):
        """Ending session should set ended_at."""
        session = Session()
        assert session.ended_at is None

        session.end()
        assert session.ended_at is not None

    def test_to_dict(self):
        """Session should serialize to dict."""
        session = Session()
        session.add_message("user", "Test")

        data = session.to_dict()

        assert "session_id" in data
        assert "started_at" in data
        assert "messages" in data
        assert len(data["messages"]) == 1

    def test_save_and_load(self):
        """Session should save to and load from JSON."""
        session = Session()
        session.add_message("user", "Test message")
        session.add_message("assistant", "Test response")
        session.metrics.startup_time_ms = 5000
        session.end()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_session.json"
            session.save(path)

            assert path.exists()

            loaded = Session.load(path)

            assert loaded.session_id == session.session_id
            assert len(loaded.messages) == 2
            assert loaded.metrics.startup_time_ms == 5000
            assert loaded.ended_at is not None


# ============================================================================
# SessionManager Tests
# ============================================================================

class TestSessionManager:
    """Test SessionManager class."""

    def test_start_session(self):
        """Manager should create new sessions."""
        manager = SessionManager()

        session = manager.start_session()

        assert session is not None
        assert manager.current_session is session

    def test_end_session(self):
        """Manager should end and save sessions."""
        manager = SessionManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Session, 'save') as mock_save:
                mock_save.return_value = Path(tmpdir) / "test.json"

                manager.start_session()
                session = manager.end_session()

                assert session is not None
                assert manager.current_session is None
                mock_save.assert_called_once()

    def test_record_startup(self):
        """Manager should record startup time."""
        manager = SessionManager()
        manager.start_session()

        manager.record_startup(3000)

        assert manager.current_session.metrics.startup_time_ms == 3000

    def test_record_messages(self):
        """Manager should record user and assistant messages."""
        manager = SessionManager()
        manager.start_session()

        manager.record_user_message("Hello")
        manager.record_assistant_message("Hi there", tokens_streamed=10)

        assert len(manager.current_session.messages) == 2
        assert manager.current_session.messages[0].role == "user"
        assert manager.current_session.messages[1].role == "assistant"

    def test_message_timing(self):
        """Manager should track message timing."""
        manager = SessionManager()
        manager.start_session()

        manager.start_message()
        manager.record_first_token()
        manager.record_user_message("Test")
        manager.record_assistant_message("Response")

        # Should have recorded timing
        assert manager.current_session.messages[-1].response_time_ms >= 0


# ============================================================================
# LogAnalyzer Tests
# ============================================================================

class TestLogAnalyzer:
    """Test LogAnalyzer class."""

    def test_list_sessions_empty(self):
        """Analyzer should handle empty session directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = LogAnalyzer(Path(tmpdir))
            sessions = analyzer.list_sessions()

            assert sessions == []

    def test_list_sessions(self):
        """Analyzer should list session files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test session files
            for i in range(3):
                session = Session()
                session.save(tmpdir / f"session_{i}.json")

            analyzer = LogAnalyzer(tmpdir)
            sessions = analyzer.list_sessions()

            assert len(sessions) == 3

    def test_load_recent_sessions(self):
        """Analyzer should load recent sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test sessions
            for i in range(5):
                session = Session()
                session.add_message("user", f"Message {i}")
                session.save(tmpdir / f"session_test_{i}.json")

            analyzer = LogAnalyzer(tmpdir)
            sessions = analyzer.load_recent_sessions(3)

            assert len(sessions) == 3

    def test_get_session_summary(self):
        """Analyzer should generate session summaries."""
        session = Session()
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")
        session.add_message("user", "Bye")
        session.metrics.avg_response_time_ms = 1000

        analyzer = LogAnalyzer()
        summary = analyzer.get_session_summary(session)

        assert summary["message_count"] == 3
        assert summary["user_messages"] == 2
        assert summary["assistant_messages"] == 1
        assert summary["avg_response_time_ms"] == 1000

    def test_get_performance_stats(self):
        """Analyzer should calculate aggregate statistics."""
        sessions = []
        for i in range(3):
            session = Session()
            session.metrics.startup_time_ms = 1000 * (i + 1)
            session.metrics.add_response(500 * (i + 1), 100 * (i + 1))
            sessions.append(session)

        analyzer = LogAnalyzer()
        stats = analyzer.get_performance_stats(sessions)

        assert stats["sessions_analyzed"] == 3
        assert stats["startup_times_ms"]["count"] == 3


# ============================================================================
# Logger Tests
# ============================================================================

class TestLogger:
    """Test logger setup and functions."""

    def test_setup_logger(self):
        """Logger should be set up with correct level."""
        logger = setup_logger(
            name="test_logger",
            level=LogLevel.DEBUG,
            log_file=False,
            console=False
        )

        assert logger.name == "test_logger"
        assert logger.level == LogLevel.DEBUG.value

    def test_get_logger_singleton(self):
        """get_logger should return the same instance."""
        logger1 = get_logger()
        logger2 = get_logger()

        assert logger1 is logger2
