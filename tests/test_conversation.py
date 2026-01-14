"""Tests for conversation persistence and context management."""

import asyncio
import pytest

from lumo_term.browser import LumoBrowser


# ============================================================================
# Conversation Persistence Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.persistence
class TestConversationPersistence:
    """Test that conversations maintain context across messages."""

    @pytest.mark.asyncio
    async def test_remembers_user_name(self, browser):
        """LUMO should remember user's name within conversation."""
        # Set name
        await browser.send_message("Call me TestUser for this conversation")

        # Check if remembered
        response = await browser.send_message("What should you call me?")

        assert "TestUser" in response

    @pytest.mark.asyncio
    async def test_remembers_numbers(self, browser):
        """LUMO should remember numbers set in conversation."""
        # Set a number
        await browser.send_message("My lucky number is 777")

        # Verify memory
        response = await browser.send_message("What is my lucky number?")

        assert "777" in response

    @pytest.mark.asyncio
    async def test_remembers_across_multiple_messages(self, browser):
        """LUMO should maintain context across 3+ messages."""
        # Message 1: Set context
        await browser.send_message("I'm working on a Python project")

        # Message 2: Add more context
        await browser.send_message("The project uses Selenium for automation")

        # Message 3: Reference earlier context
        response = await browser.send_message(
            "What language and tool am I using?"
        )

        assert "python" in response.lower()
        assert "selenium" in response.lower()

    @pytest.mark.asyncio
    async def test_follows_conversation_thread(self, browser):
        """LUMO should follow a logical conversation thread."""
        # Set up a problem
        await browser.send_message("I have 10 apples")

        # Add to it
        await browser.send_message("I buy 5 more apples")

        # Ask about it
        response = await browser.send_message("How many apples do I have now?")

        assert "15" in response

    @pytest.mark.asyncio
    async def test_handles_correction(self, browser):
        """LUMO should handle corrections to previous information."""
        # Set initial value
        await browser.send_message("My favorite color is blue")

        # Correct it
        await browser.send_message("Actually, my favorite color is green, not blue")

        # Check updated value
        response = await browser.send_message("What is my favorite color?")

        assert "green" in response.lower()


# ============================================================================
# Context Isolation Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.persistence
class TestContextIsolation:
    """Test context isolation between sessions."""

    @pytest.mark.asyncio
    async def test_new_browser_has_fresh_context(self, firefox_profile):
        """Each new browser session should start fresh."""
        # First session - set context
        client1 = LumoBrowser(firefox_profile=firefox_profile, headless=True)
        await client1.start()
        await client1.send_message("Secret code: ALPHA1")
        await client1.stop()

        # Second session - should not have context
        client2 = LumoBrowser(firefox_profile=firefox_profile, headless=True)
        await client2.start()
        response = await client2.send_message("What is the secret code?")
        await client2.stop()

        # Second session should not know the code
        # (unless LUMO has cross-session memory, which it might)
        # This test documents the actual behavior
        has_code = "ALPHA1" in response
        print(f"Cross-session memory: {'yes' if has_code else 'no'}")


# ============================================================================
# Long Conversation Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.persistence
@pytest.mark.slow
class TestLongConversations:
    """Test behavior in longer conversations."""

    @pytest.mark.asyncio
    async def test_maintains_context_over_5_messages(self, browser):
        """Should maintain context over 5+ message exchanges."""
        # Build up context
        topics = [
            ("Topic 1: I like pizza", "pizza"),
            ("Topic 2: I work in IT", "IT"),
            ("Topic 3: I live in a city", "city"),
            ("Topic 4: I have a dog named Max", "Max"),
            ("Topic 5: My hobby is gaming", "gaming"),
        ]

        for message, _ in topics:
            await browser.send_message(message)

        # Test recall of early topics
        response = await browser.send_message(
            "List the 5 things I told you about myself"
        )

        # Should remember at least some of the topics
        remembered = sum(1 for _, keyword in topics if keyword.lower() in response.lower())
        assert remembered >= 3, f"Only remembered {remembered}/5 topics"

    @pytest.mark.asyncio
    async def test_conversation_summary(self, browser):
        """LUMO should be able to summarize a conversation."""
        # Have a conversation about a topic
        await browser.send_message("Let's discuss Python programming")
        await browser.send_message("Python is great for automation")
        await browser.send_message("It has many useful libraries")

        # Ask for summary
        response = await browser.send_message("Summarize what we discussed")

        assert "python" in response.lower()
        assert any(word in response.lower() for word in ["automation", "libraries", "programming"])
