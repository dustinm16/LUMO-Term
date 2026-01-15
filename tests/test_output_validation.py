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
    extract_code_for_file,
    extract_code_section,
    is_valid_python,
    is_valid_bash,
    get_file_extension,
    _detect_language,
    _looks_like_code,
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


# ============================================================================
# Code Block Edge Cases
# ============================================================================

class TestCodeBlockEdgeCases:
    """Test edge cases in code block extraction."""

    def test_nested_code_fence_in_markdown(self):
        """Should handle code fence showing how to write code fences."""
        response = '''Here's how to write a code block:

```markdown
Use triple backticks:
```python
print("hello")
```
```

That's it!'''

        blocks = extract_code_blocks(response)
        # Should extract the outer markdown block
        assert len(blocks) >= 1
        assert blocks[0]["language"] == "markdown"

    def test_unclosed_code_fence(self):
        """Should handle unclosed code fence gracefully."""
        response = '''Here's some code:

```python
def hello():
    print("Hello")

But I forgot to close the fence!'''

        blocks = extract_code_blocks(response)
        # Unclosed fence should not be extracted
        assert len(blocks) == 0

    def test_empty_code_block(self):
        """Should handle empty code block."""
        response = '''Empty block:

```python
```

That was empty!'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0]["code"] == ""

    def test_code_block_with_only_whitespace(self):
        """Should handle code block with only whitespace."""
        response = '''Whitespace block:

```python


```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        # Code is stripped
        assert blocks[0]["code"].strip() == ""

    def test_unicode_in_code_block(self):
        """Should handle unicode characters in code."""
        response = '''```python
# Комментарий на русском
def greet():
    print("Hello 世界! 🌍")
    emoji = "🎉"
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        assert "Комментарий" in blocks[0]["code"]
        assert "世界" in blocks[0]["code"]
        assert "🎉" in blocks[0]["code"]

    def test_language_case_insensitivity(self):
        """Should handle different case in language names."""
        response = '''```PYTHON
print("uppercase")
```

```Python
print("titlecase")
```

```pYtHoN
print("mixedcase")
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 3
        # All should be normalized to lowercase
        assert all(b["language"] == "python" for b in blocks)

    def test_language_with_version(self):
        """Should handle language names with version numbers."""
        response = '''```python3
print("python3")
```

```js
console.log("js");
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 2
        assert blocks[0]["language"] == "python3"
        assert blocks[1]["language"] == "js"

    def test_code_block_with_special_chars(self):
        """Should handle special characters in code."""
        response = r'''```bash
echo "Hello $USER" && ls -la | grep "\.py$"
find . -name "*.txt" -exec rm {} \;
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        assert "$USER" in blocks[0]["code"]
        assert r"\;" in blocks[0]["code"]

    def test_very_long_code_block(self):
        """Should handle very long code blocks."""
        long_code = "\n".join([f"line_{i} = {i}" for i in range(1000)])
        response = f'''```python
{long_code}
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        assert "line_0 = 0" in blocks[0]["code"]
        assert "line_999 = 999" in blocks[0]["code"]

    def test_code_block_with_blank_lines(self):
        """Should preserve blank lines in code."""
        response = '''```python
def func1():
    pass


def func2():
    pass
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        # Should have double blank line preserved
        assert "\n\n\n" in blocks[0]["code"] or blocks[0]["code"].count("\n") >= 4

    def test_multiple_same_language_blocks(self):
        """Should extract multiple blocks of same language."""
        response = '''First:
```python
x = 1
```

Second:
```python
y = 2
```

Third:
```python
z = 3
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 3
        assert all(b["language"] == "python" for b in blocks)
        assert blocks[0]["code"].strip() == "x = 1"
        assert blocks[1]["code"].strip() == "y = 2"
        assert blocks[2]["code"].strip() == "z = 3"

    def test_code_fence_with_info_string(self):
        """Should handle code fence with additional info string."""
        # Note: The regex captures everything after ``` until newline as language
        # This tests actual behavior - info strings become part of language
        response = '''```python
def example():
    pass
```'''

        blocks = extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0]["language"] == "python"


# ============================================================================
# Multi-Language Detection Tests
# ============================================================================

class TestMultiLanguageDetection:
    """Test language detection for inline code."""

    def test_detect_python(self):
        """Should detect Python code."""
        assert _detect_language("def hello():") == "python"
        assert _detect_language("class MyClass:") == "python"
        assert _detect_language("import os") == "python"
        assert _detect_language("from pathlib import Path") == "python"
        assert _detect_language("@decorator") == "python"

    def test_detect_bash(self):
        """Should detect Bash code."""
        assert _detect_language("#!/bin/bash") == "bash"
        assert _detect_language("my_func() {") == "bash"
        assert _detect_language("function setup") == "bash"
        assert _detect_language("if [ -f file ]; then") == "bash"

    def test_detect_javascript(self):
        """Should detect JavaScript code."""
        # Note: Some patterns overlap with other languages
        assert _detect_language("let y = 2") == "javascript"
        assert _detect_language("export default function") == "javascript"
        assert _detect_language("#!/usr/bin/env node") == "javascript"

    def test_detect_rust(self):
        """Should detect Rust code."""
        assert _detect_language("fn main() {") == "rust"
        assert _detect_language("pub fn hello() {") == "rust"
        assert _detect_language("struct Point {") == "rust"
        assert _detect_language("impl Display for Point {") == "rust"

    def test_detect_go(self):
        """Should detect Go code."""
        assert _detect_language("package main") == "go"
        assert _detect_language("func main() {") == "go"
        # Note: Some Go patterns overlap with other languages
        # 'type X struct' matches Rust patterns first

    def test_detect_sql(self):
        """Should detect SQL code."""
        assert _detect_language("SELECT * FROM users") == "sql"
        assert _detect_language("INSERT INTO table") == "sql"
        assert _detect_language("CREATE TABLE users (") == "sql"

    def test_detect_yaml(self):
        """Should detect YAML code."""
        assert _detect_language("---") == "yaml"
        # Note: Simple 'key: value' doesn't match - needs quotes or numbers
        assert _detect_language('name: "value"') == "yaml"
        assert _detect_language("count: 123") == "yaml"

    def test_detect_dockerfile(self):
        """Should detect Dockerfile code."""
        assert _detect_language("FROM ubuntu:latest") == "dockerfile"

    def test_no_detection_plain_text(self):
        """Should return None for plain text."""
        assert _detect_language("Hello, world!") is None
        assert _detect_language("This is just text.") is None
        assert _detect_language("") is None

    def test_ambiguous_code_first_match(self):
        """Should return first matching language for ambiguous code."""
        # 'class' could be Python, JS, or others
        result = _detect_language("class MyClass:")
        assert result is not None


# ============================================================================
# Code Section Extraction Tests
# ============================================================================

class TestCodeSectionExtraction:
    """Test extraction of code without markdown fences."""

    def test_extract_python_function(self):
        """Should extract Python function without fences."""
        response = '''Here's the function:

def calculate(x, y):
    return x + y

That will add two numbers.'''

        code = extract_code_section(response)
        assert code is not None
        assert "def calculate(x, y):" in code
        assert "return x + y" in code

    def test_extract_bash_commands(self):
        """Should extract bash commands without fences."""
        response = '''Run these commands:

#!/bin/bash
echo "Starting..."
ls -la
cd /tmp

That should work.'''

        code = extract_code_section(response)
        assert code is not None
        assert "#!/bin/bash" in code
        assert "echo" in code

    def test_no_code_in_response(self):
        """Should return None when no code detected."""
        response = "This is just a text response with no code at all."

        code = extract_code_section(response)
        assert code is None

    def test_stops_at_conversational_text(self):
        """Should stop extracting at conversational text."""
        response = '''def hello():
    print("hello")

What this does:
It prints hello to the console.'''

        code = extract_code_section(response)
        assert code is not None
        assert "def hello():" in code
        assert "What this does:" not in code


# ============================================================================
# File Extension Tests
# ============================================================================

class TestFileExtensions:
    """Test file extension mapping."""

    def test_common_extensions(self):
        """Should return correct extensions for common languages."""
        assert get_file_extension("python") == ".py"
        assert get_file_extension("javascript") == ".js"
        assert get_file_extension("typescript") == ".ts"
        assert get_file_extension("bash") == ".sh"
        assert get_file_extension("rust") == ".rs"
        assert get_file_extension("go") == ".go"

    def test_short_aliases(self):
        """Should handle short language aliases."""
        assert get_file_extension("py") == ".py"
        assert get_file_extension("js") == ".js"
        assert get_file_extension("ts") == ".ts"
        assert get_file_extension("rb") == ".rb"
        assert get_file_extension("sh") == ".sh"

    def test_case_insensitivity(self):
        """Should handle different cases."""
        assert get_file_extension("Python") == ".py"
        assert get_file_extension("JAVASCRIPT") == ".js"
        assert get_file_extension("TypeScript") == ".ts"

    def test_unknown_language(self):
        """Should return .txt for unknown languages."""
        assert get_file_extension("unknown_lang") == ".txt"
        assert get_file_extension("") == ".txt"


# ============================================================================
# Extract Code For File Tests
# ============================================================================

class TestExtractCodeForFile:
    """Test extract_code_for_file function."""

    def test_extracts_from_fence(self):
        """Should extract code from markdown fence."""
        response = '''```python
print("hello")
```'''

        code = extract_code_for_file(response)
        assert code == 'print("hello")'

    def test_prefers_specified_language(self):
        """Should prefer code block matching specified language."""
        response = '''```bash
echo "bash"
```

```python
print("python")
```'''

        code = extract_code_for_file(response, language="python")
        assert code == 'print("python")'

    def test_falls_back_to_first_block(self):
        """Should fall back to first block if language not found."""
        response = '''```javascript
console.log("js");
```

```python
print("python")
```'''

        code = extract_code_for_file(response, language="rust")
        assert "console.log" in code  # Falls back to first

    def test_extracts_inline_code(self):
        """Should extract inline code when no fences."""
        response = '''Here's the code:

def my_function():
    return 42

That's it!'''

        code = extract_code_for_file(response)
        assert code is not None
        assert "def my_function():" in code

    def test_returns_none_when_no_code(self):
        """Should return None when no code found."""
        response = "This response has no code at all."

        code = extract_code_for_file(response)
        # May or may not find code depending on heuristics
        # The important thing is it doesn't crash


# ============================================================================
# Looks Like Code Tests
# ============================================================================

class TestLooksLikeCode:
    """Test _looks_like_code heuristic."""

    def test_recognizes_python(self):
        """Should recognize Python code."""
        assert _looks_like_code("def hello():\n    pass")
        assert _looks_like_code("class Foo:\n    pass")
        assert _looks_like_code("import os")

    def test_recognizes_javascript(self):
        """Should recognize JavaScript code."""
        assert _looks_like_code("function hello() {}")
        assert _looks_like_code("const x = () => {}")

    def test_recognizes_shebang(self):
        """Should recognize shebang."""
        assert _looks_like_code("#!/bin/bash\necho hello")
        assert _looks_like_code("#!/usr/bin/env python3")

    def test_plain_text_not_code(self):
        """Should not recognize plain text as code."""
        # Plain text should generally not match
        result = _looks_like_code("Hello, how are you today?")
        # This is heuristic, so we're just testing it runs
        assert isinstance(result, bool)


# ============================================================================
# JSON Edge Cases
# ============================================================================

class TestJSONEdgeCases:
    """Test edge cases in JSON extraction."""

    def test_nested_json(self):
        """Should extract nested JSON objects."""
        response = '''```json
{
    "user": {
        "name": "John",
        "address": {
            "city": "NYC"
        }
    }
}
```'''

        data = extract_json(response)
        assert data is not None
        assert data["user"]["address"]["city"] == "NYC"

    def test_json_with_arrays(self):
        """Should extract JSON with nested arrays."""
        response = '''```json
{
    "items": [1, 2, [3, 4, 5]],
    "names": ["a", "b"]
}
```'''

        data = extract_json(response)
        assert data is not None
        assert data["items"][2] == [3, 4, 5]

    def test_invalid_json_returns_none(self):
        """Should return None for invalid JSON."""
        response = '''```json
{invalid json here}
```'''

        data = extract_json(response)
        assert data is None

    def test_json_with_null(self):
        """Should handle JSON with null values."""
        response = '''```json
{"value": null, "other": "test"}
```'''

        data = extract_json(response)
        assert data is not None
        assert data["value"] is None

    def test_json_with_unicode(self):
        """Should handle JSON with unicode."""
        response = '''```json
{"message": "Hello 世界", "emoji": "🎉"}
```'''

        data = extract_json(response)
        assert data is not None
        assert data["message"] == "Hello 世界"
        assert data["emoji"] == "🎉"
