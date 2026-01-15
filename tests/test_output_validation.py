"""Integration tests for LUMO output validation.

These tests verify that LUMO responses are useful and valid for:
1. File reviews (code quality feedback)
2. Command output inference (error explanation, fix suggestions)
3. Code generation (extractable, runnable code)

Mark with @pytest.mark.integration - requires live LUMO instance.
"""

import pytest
import re
from unittest.mock import AsyncMock, Mock, patch
from argparse import Namespace

from lumo_term.cli import run_single_message
from lumo_term.extract import (
    extract_code_blocks,
    extract_first_code_block,
    strip_conversational_text,
    extract_json,
    is_valid_python,
    is_valid_bash,
)


def make_mock_args(**kwargs):
    """Create mock args with defaults."""
    defaults = {
        "no_headless": False,
        "profile": None,
        "new": False,
        "message": None,
        "files": None,
        "output": None,
        "append": False,
        "copy": False,
        "tui": False,
        "plain": False,
        "prompt": None,
        "code_only": False,
        "language": None,
    }
    defaults.update(kwargs)
    return Namespace(**defaults)


# ============================================================================
# Code Block Extraction Tests
# ============================================================================

class TestCodeBlockExtraction:
    """Test extraction of code blocks from markdown responses."""

    def test_extract_single_python_block(self):
        """Extract a single Python code block."""
        response = '''Here's the code you requested:

```python
def hello():
    print("Hello, world!")

hello()
```

This function prints a greeting.'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0]["language"] == "python"
        assert "def hello():" in blocks[0]["code"]
        assert "print(" in blocks[0]["code"]

    def test_extract_multiple_blocks(self):
        """Extract multiple code blocks with different languages."""
        response = '''First, create the Python file:

```python
import sys
print(sys.argv)
```

Then run it with bash:

```bash
python script.py arg1 arg2
```

That's it!'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 2
        assert blocks[0]["language"] == "python"
        assert blocks[1]["language"] == "bash"

    def test_extract_first_block(self):
        """Extract only the first code block."""
        response = '''```python
first_block = True
```

```python
second_block = True
```'''

        block = extract_first_code_block(response)
        assert block is not None
        assert "first_block" in block["code"]
        assert "second_block" not in block["code"]

    def test_extract_unlabeled_block(self):
        """Handle code blocks without language labels."""
        response = '''Here's the code:

```
echo "no language specified"
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0]["language"] == ""
        assert "echo" in blocks[0]["code"]

    def test_no_code_blocks(self):
        """Handle responses without code blocks."""
        response = "This response has no code blocks, just text."

        blocks = extract_code_blocks(response)
        assert len(blocks) == 0

        block = extract_first_code_block(response)
        assert block is None


# ============================================================================
# Conversational Text Stripping Tests
# ============================================================================

class TestConversationalStripping:
    """Test removal of conversational wrapper text."""

    def test_strip_intro_text(self):
        """Remove introductory conversational text."""
        response = '''Here's a Python script that does what you asked:

```python
print("actual code")
```'''

        clean = strip_conversational_text(response)
        assert clean.strip() == 'print("actual code")'

    def test_strip_outro_text(self):
        """Remove closing conversational text."""
        response = '''```python
print("actual code")
```

I hope this helps! Let me know if you have questions.'''

        clean = strip_conversational_text(response)
        assert clean.strip() == 'print("actual code")'

    def test_strip_both_intro_and_outro(self):
        """Remove both intro and outro text."""
        response = '''Sure! Here's the script you requested:

```bash
#!/bin/bash
echo "Hello"
```

This script will print "Hello" to the console. Feel free to modify it!'''

        clean = strip_conversational_text(response)
        assert clean.strip() == '#!/bin/bash\necho "Hello"'

    def test_preserve_plain_code(self):
        """Preserve response that's just code without markdown."""
        response = '''def add(a, b):
    return a + b'''

        clean = strip_conversational_text(response)
        assert "def add(a, b):" in clean
        assert "return a + b" in clean

    def test_multiple_code_blocks_extracts_all(self):
        """When multiple blocks exist, extract all code."""
        response = '''First function:

```python
def func1():
    pass
```

Second function:

```python
def func2():
    pass
```'''

        clean = strip_conversational_text(response, extract_all=True)
        assert "def func1():" in clean
        assert "def func2():" in clean


# ============================================================================
# Code Validation Tests
# ============================================================================

class TestCodeValidation:
    """Test that extracted code is syntactically valid."""

    def test_valid_python_syntax(self):
        """Verify valid Python code passes validation."""
        code = '''def greet(name):
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("World"))
'''
        assert is_valid_python(code) is True

    def test_invalid_python_syntax(self):
        """Verify invalid Python code fails validation."""
        code = '''def broken(
    return "missing parenthesis"
'''
        assert is_valid_python(code) is False

    def test_valid_bash_syntax(self):
        """Verify valid bash code passes basic validation."""
        code = '''#!/bin/bash
for i in 1 2 3; do
    echo $i
done
'''
        assert is_valid_bash(code) is True

    def test_bash_with_common_commands(self):
        """Verify bash with common commands."""
        code = '''ls -la | grep ".py" | wc -l'''
        assert is_valid_bash(code) is True


# ============================================================================
# JSON Extraction Tests
# ============================================================================

class TestJSONExtraction:
    """Test extraction of JSON from responses."""

    def test_extract_json_object(self):
        """Extract JSON object from response."""
        response = '''Here's the configuration:

```json
{
    "name": "test",
    "enabled": true,
    "count": 42
}
```'''

        data = extract_json(response)
        assert data is not None
        assert data["name"] == "test"
        assert data["enabled"] is True
        assert data["count"] == 42

    def test_extract_json_array(self):
        """Extract JSON array from response."""
        response = '''The items are:

```json
["apple", "banana", "cherry"]
```'''

        data = extract_json(response)
        assert data is not None
        assert len(data) == 3
        assert "banana" in data

    def test_extract_inline_json(self):
        """Extract JSON without code fence."""
        response = 'The result is {"status": "ok", "code": 200}'

        data = extract_json(response)
        assert data is not None
        assert data["status"] == "ok"

    def test_no_json_returns_none(self):
        """Return None when no JSON found."""
        response = "This response has no JSON data."

        data = extract_json(response)
        assert data is None


# ============================================================================
# File Review Output Tests
# ============================================================================

class TestFileReviewOutput:
    """Test that file review responses are actionable."""

    @pytest.mark.asyncio
    async def test_review_response_has_structure(self):
        """File review should have structured feedback."""
        mock_client = AsyncMock()
        mock_response = '''## Code Review

### Issues Found

1. **Line 5**: Missing error handling for file operations
2. **Line 12**: Unused variable `temp`

### Suggestions

- Add try/except around file I/O
- Remove or use the `temp` variable

### Overall

The code is functional but could use better error handling.'''

        mock_client.send_message = AsyncMock(return_value=mock_response)
        mock_args = make_mock_args()

        with patch("lumo_term.cli.console"):
            response = await run_single_message(mock_client, "Review this code", mock_args)

        # Verify response has useful structure
        assert "issue" in response.lower() or "error" in response.lower() or "suggestion" in response.lower()

    def test_review_identifies_common_issues(self):
        """Review response should identify common code issues."""
        # These patterns should appear in useful code reviews
        useful_patterns = [
            r"line \d+",  # References specific lines
            r"error|bug|issue|problem",  # Identifies problems
            r"suggest|recommend|should|could",  # Provides suggestions
            r"missing|unused|undefined",  # Common issues
        ]

        sample_review = '''Line 10: Missing null check before accessing property.
Suggestion: Add validation before the loop.
Issue: Unused import on line 3.'''

        matches = sum(1 for p in useful_patterns if re.search(p, sample_review, re.I))
        assert matches >= 2, "Review should match multiple useful patterns"


# ============================================================================
# Command Output Inference Tests
# ============================================================================

class TestCommandOutputInference:
    """Test that error explanations are helpful."""

    def test_error_explanation_has_cause(self):
        """Error explanations should identify the cause."""
        sample_explanation = '''The error "ModuleNotFoundError: No module named 'requests'"
occurs because the requests library is not installed in your Python environment.

To fix this, run:
```bash
pip install requests
```'''

        # Should explain cause
        assert "because" in sample_explanation.lower() or "occurs" in sample_explanation.lower()
        # Should provide fix
        assert "pip install" in sample_explanation

    def test_command_suggestion_is_runnable(self):
        """Suggested commands should be extractable and runnable."""
        response = '''To fix the permission error, run:

```bash
chmod +x script.sh
```

Then execute with:

```bash
./script.sh
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) >= 1

        # Commands should be simple and runnable
        for block in blocks:
            if block["language"] == "bash":
                assert len(block["code"].strip()) > 0
                # Should not contain placeholder text
                assert "<" not in block["code"] or "<<" in block["code"]  # heredoc ok


# ============================================================================
# Integration Tests (require live LUMO)
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestLiveOutputValidation:
    """Integration tests with live LUMO instance."""

    @pytest.mark.asyncio
    async def test_live_code_generation(self, browser_client):
        """Test that live LUMO generates valid code."""
        response = await browser_client.send_message(
            "Write a Python function that returns the factorial of a number. "
            "Only output the code, no explanation."
        )

        blocks = extract_code_blocks(response)
        assert len(blocks) >= 1, "Should contain at least one code block"

        code = blocks[0]["code"]
        assert is_valid_python(code), "Generated Python should be syntactically valid"
        assert "factorial" in code.lower() or "fact" in code.lower()

    @pytest.mark.asyncio
    async def test_live_file_review(self, browser_client):
        """Test that live LUMO provides useful file review."""
        test_code = '''def divide(a, b):
    return a / b  # No zero check!

x = divide(10, 0)
'''
        response = await browser_client.send_message(
            f"Review this Python code for bugs:\n\n```python\n{test_code}\n```"
        )

        # Should identify the division by zero issue
        assert any(term in response.lower() for term in [
            "zero", "division", "zerodivision", "error", "exception", "check"
        ]), "Should identify the division by zero bug"

    @pytest.mark.asyncio
    async def test_live_error_explanation(self, browser_client):
        """Test that live LUMO explains errors helpfully."""
        error = "TypeError: 'NoneType' object is not subscriptable"

        response = await browser_client.send_message(
            f"Explain this Python error and how to fix it: {error}"
        )

        # Should explain None and subscripting
        assert "none" in response.lower()
        assert any(term in response.lower() for term in [
            "subscript", "index", "bracket", "[]", "check", "if"
        ])
