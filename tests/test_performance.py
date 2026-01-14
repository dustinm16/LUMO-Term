"""Performance benchmark tests for LUMO-Term."""

import asyncio
import time
import pytest
import statistics
from dataclasses import dataclass, field
from typing import List

from lumo_term.browser import LumoBrowser


# ============================================================================
# Performance Thresholds (in seconds)
# ============================================================================

THRESHOLDS = {
    "browser_startup": 30.0,      # Max time to start browser
    "page_load": 15.0,            # Max time for LUMO to load
    "first_token": 10.0,          # Max time to first response token
    "simple_response": 30.0,      # Max time for simple response
    "total_startup": 45.0,        # Max total time from start to ready
}


# ============================================================================
# Performance Data Structures
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Container for performance measurements."""
    startup_time: float = 0.0
    page_load_time: float = 0.0
    first_token_time: float = 0.0
    total_response_time: float = 0.0
    response_times: List[float] = field(default_factory=list)

    def add_response_time(self, time_seconds: float):
        self.response_times.append(time_seconds)

    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times)

    @property
    def p95_response_time(self) -> float:
        if len(self.response_times) < 2:
            return self.response_times[0] if self.response_times else 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def report(self) -> str:
        lines = [
            "=" * 50,
            "PERFORMANCE REPORT",
            "=" * 50,
            f"Startup time:        {self.startup_time:.2f}s",
            f"Page load time:      {self.page_load_time:.2f}s",
            f"First token time:    {self.first_token_time:.2f}s",
            f"Total response time: {self.total_response_time:.2f}s",
        ]
        if self.response_times:
            lines.extend([
                "-" * 50,
                f"Response times ({len(self.response_times)} samples):",
                f"  Average:           {self.avg_response_time:.2f}s",
                f"  P95:               {self.p95_response_time:.2f}s",
                f"  Min:               {min(self.response_times):.2f}s",
                f"  Max:               {max(self.response_times):.2f}s",
            ])
        lines.append("=" * 50)
        return "\n".join(lines)


# ============================================================================
# Benchmark Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestStartupPerformance:
    """Benchmark browser startup performance."""

    @pytest.mark.asyncio
    async def test_startup_time(self, firefox_profile):
        """Measure browser startup time."""
        client = LumoBrowser(firefox_profile=firefox_profile, headless=True)
        metrics = PerformanceMetrics()

        start = time.perf_counter()
        await client.start()
        metrics.startup_time = time.perf_counter() - start

        await client.stop()

        print(f"\nStartup time: {metrics.startup_time:.2f}s")
        assert metrics.startup_time < THRESHOLDS["total_startup"], \
            f"Startup too slow: {metrics.startup_time:.2f}s > {THRESHOLDS['total_startup']}s"

    @pytest.mark.asyncio
    async def test_startup_phases(self, firefox_profile):
        """Measure individual startup phases."""
        client = LumoBrowser(firefox_profile=firefox_profile, headless=True)
        phase_times = {}

        def track_phase(msg: str):
            phase_times[msg] = time.perf_counter()

        start = time.perf_counter()
        await client.start(progress_callback=track_phase)
        total = time.perf_counter() - start

        await client.stop()

        print("\nStartup phases:")
        prev_time = start
        for phase, timestamp in phase_times.items():
            duration = timestamp - prev_time
            print(f"  {phase}: {duration:.2f}s")
            prev_time = timestamp
        print(f"  Total: {total:.2f}s")


@pytest.mark.integration
@pytest.mark.slow
class TestResponsePerformance:
    """Benchmark response time performance."""

    @pytest.mark.asyncio
    async def test_simple_response_time(self, browser):
        """Measure time for simple response."""
        start = time.perf_counter()
        await browser.send_message("Say OK")
        elapsed = time.perf_counter() - start

        print(f"\nSimple response time: {elapsed:.2f}s")
        assert elapsed < THRESHOLDS["simple_response"], \
            f"Response too slow: {elapsed:.2f}s > {THRESHOLDS['simple_response']}s"

    @pytest.mark.asyncio
    async def test_first_token_latency(self, browser):
        """Measure time to first token."""
        first_token_time = None
        start = time.perf_counter()

        def on_token(token: str):
            nonlocal first_token_time
            if first_token_time is None:
                first_token_time = time.perf_counter() - start

        await browser.send_message("Count to 3", on_token=on_token)

        if first_token_time:
            print(f"\nTime to first token: {first_token_time:.2f}s")
            assert first_token_time < THRESHOLDS["first_token"], \
                f"First token too slow: {first_token_time:.2f}s"

    @pytest.mark.asyncio
    async def test_multiple_response_times(self, browser):
        """Benchmark multiple consecutive responses."""
        metrics = PerformanceMetrics()
        messages = [
            "What is 1+1?",
            "What is 2+2?",
            "What is 3+3?",
            "Say hello",
            "Say goodbye",
        ]

        for msg in messages:
            start = time.perf_counter()
            await browser.send_message(msg)
            elapsed = time.perf_counter() - start
            metrics.add_response_time(elapsed)

        print(f"\n{metrics.report()}")

        # Check average is reasonable
        assert metrics.avg_response_time < THRESHOLDS["simple_response"], \
            f"Average response too slow: {metrics.avg_response_time:.2f}s"


@pytest.mark.integration
@pytest.mark.slow
class TestThroughputPerformance:
    """Benchmark throughput for multiple messages."""

    @pytest.mark.asyncio
    async def test_conversation_throughput(self, browser):
        """Measure throughput of a multi-message conversation."""
        messages = [
            "My name is Test",
            "I like programming",
            "What's my name?",
            "What do I like?",
        ]

        start = time.perf_counter()
        for msg in messages:
            await browser.send_message(msg)
        total_time = time.perf_counter() - start

        throughput = len(messages) / total_time
        print(f"\nConversation throughput: {throughput:.2f} messages/second")
        print(f"Total time for {len(messages)} messages: {total_time:.2f}s")


# ============================================================================
# Memory and Resource Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestResourceUsage:
    """Test resource usage patterns."""

    @pytest.mark.asyncio
    async def test_profile_cleanup(self, firefox_profile):
        """Verify temp profiles are cleaned up."""
        import os
        from pathlib import Path

        cache_dir = Path.home() / ".cache" / "lumo-term"

        # Count profiles before
        profiles_before = len(list(cache_dir.glob("profile-*"))) if cache_dir.exists() else 0

        # Run a session
        client = LumoBrowser(firefox_profile=firefox_profile, headless=True)
        await client.start()
        await client.send_message("Test")
        await client.stop()

        # Count profiles after
        profiles_after = len(list(cache_dir.glob("profile-*"))) if cache_dir.exists() else 0

        # Should have cleaned up
        print(f"\nProfiles before: {profiles_before}, after: {profiles_after}")
        assert profiles_after <= profiles_before, "Temp profile not cleaned up"

    @pytest.mark.asyncio
    async def test_multiple_sessions_cleanup(self, firefox_profile):
        """Verify cleanup across multiple sessions."""
        from pathlib import Path

        cache_dir = Path.home() / ".cache" / "lumo-term"
        initial_count = len(list(cache_dir.glob("profile-*"))) if cache_dir.exists() else 0

        # Run multiple sessions
        for i in range(3):
            client = LumoBrowser(firefox_profile=firefox_profile, headless=True)
            await client.start()
            await client.send_message(f"Session {i}")
            await client.stop()

        final_count = len(list(cache_dir.glob("profile-*"))) if cache_dir.exists() else 0

        print(f"\nInitial profiles: {initial_count}, final: {final_count}")
        assert final_count <= initial_count + 1, "Profile leak detected"
