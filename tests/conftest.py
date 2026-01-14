"""Pytest fixtures for LUMO-Term tests."""

import asyncio
import pytest
import time
from pathlib import Path
from typing import AsyncGenerator

from lumo_term.browser import LumoBrowser
from lumo_term.config import load_config


# ============================================================================
# Configuration
# ============================================================================

# Timeouts (in seconds)
BROWSER_START_TIMEOUT = 120
MESSAGE_RESPONSE_TIMEOUT = 60
SHORT_MESSAGE_TIMEOUT = 30

# Test messages
TEST_MESSAGES = {
    "simple": "Say 'test passed'",
    "math": "What is 2 + 2?",
    "memory_set": "Remember: my secret code is ALPHA-7",
    "memory_check": "What is my secret code?",
    "long": "Explain the concept of recursion in programming in 2-3 sentences.",
}


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def firefox_profile() -> Path | None:
    """Get Firefox profile path from config or auto-detect."""
    config = load_config()
    if config.firefox_profile:
        return Path(config.firefox_profile)
    return None


@pytest.fixture
async def browser(firefox_profile: Path | None) -> AsyncGenerator[LumoBrowser, None]:
    """Create a fresh browser instance for each test.

    This fixture creates a new browser session, yields it for testing,
    and ensures cleanup after the test completes.
    """
    client = LumoBrowser(firefox_profile=firefox_profile, headless=True)

    startup_logs = []
    def log_progress(msg: str):
        startup_logs.append(msg)

    try:
        await asyncio.wait_for(
            client.start(progress_callback=log_progress),
            timeout=BROWSER_START_TIMEOUT
        )
        yield client
    except asyncio.TimeoutError:
        pytest.fail(f"Browser startup timed out. Logs: {startup_logs}")
    finally:
        await client.stop()


@pytest.fixture
async def persistent_browser(firefox_profile: Path | None) -> AsyncGenerator[LumoBrowser, None]:
    """Create a browser instance that persists across multiple tests in a class.

    Use this for conversation persistence tests where we need to maintain
    state across multiple messages.
    """
    client = LumoBrowser(firefox_profile=firefox_profile, headless=True)

    await asyncio.wait_for(
        client.start(),
        timeout=BROWSER_START_TIMEOUT
    )

    yield client

    await client.stop()


@pytest.fixture
def test_messages() -> dict:
    """Provide standard test messages."""
    return TEST_MESSAGES.copy()


# ============================================================================
# Markers
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests that require network access"
    )
    config.addinivalue_line(
        "markers", "persistence: marks tests for conversation persistence"
    )


# ============================================================================
# Helpers
# ============================================================================

class TestTimer:
    """Context manager for timing test operations."""

    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.duration = self.end_time - self.start_time

    def __str__(self):
        if self.duration is not None:
            return f"{self.name}: {self.duration:.2f}s"
        return f"{self.name}: not completed"


@pytest.fixture
def timer():
    """Provide a timer factory for performance tests."""
    def create_timer(name: str = "operation") -> TestTimer:
        return TestTimer(name)
    return create_timer


class ResponseCollector:
    """Collect streaming response tokens."""

    def __init__(self):
        self.tokens = []
        self.first_token_time = None
        self.start_time = None

    def start(self):
        self.start_time = time.perf_counter()

    def on_token(self, token: str):
        if self.first_token_time is None:
            self.first_token_time = time.perf_counter()
        self.tokens.append(token)

    @property
    def full_response(self) -> str:
        return "".join(self.tokens)

    @property
    def token_count(self) -> int:
        return len(self.tokens)

    @property
    def time_to_first_token(self) -> float | None:
        if self.first_token_time and self.start_time:
            return self.first_token_time - self.start_time
        return None


@pytest.fixture
def response_collector():
    """Provide a response collector for streaming tests."""
    def create_collector() -> ResponseCollector:
        return ResponseCollector()
    return create_collector
