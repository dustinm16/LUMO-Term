"""Response extraction and cleaning utilities.

This module provides functions to extract clean, usable content from
LUMO responses, removing conversational wrapper text and extracting
code blocks, JSON, and other structured content.
"""

import ast
import json
import re
from typing import TypedDict


class CodeBlock(TypedDict):
    """A code block extracted from a response."""
    language: str
    code: str


# Regex pattern for markdown code fences
CODE_FENCE_PATTERN = re.compile(
    r"```(\w*)\n(.*?)```",
    re.DOTALL
)

# Patterns that indicate conversational intro text
INTRO_PATTERNS = [
    r"^(?:here(?:'s| is)|sure[,!]|okay[,!]|certainly[,!]|of course[,!]).*?[:]\s*\n",
    r"^(?:i(?:'ll| will)|let me).*?[:]\s*\n",
    r"^.*?(?:you (?:asked|requested|wanted)).*?[:]\s*\n",
    r"^.*?(?:the (?:code|script|function|solution)).*?[:]\s*\n",
]

# Patterns that indicate conversational outro text
OUTRO_PATTERNS = [
    r"\n\s*(?:i hope|let me know|feel free|if you (?:have|need)).*$",
    r"\n\s*(?:this (?:will|should|code)).*?[.!]\s*$",
    r"\n\s*(?:you can (?:run|execute|use|modify)).*$",
    r"\n\s*(?:note:|note that|remember).*$",
]


def extract_code_blocks(text: str) -> list[CodeBlock]:
    """Extract all code blocks from markdown-formatted text.

    Args:
        text: The response text containing markdown code fences.

    Returns:
        List of CodeBlock dicts with 'language' and 'code' keys.

    Example:
        >>> text = '```python\\nprint("hi")\\n```'
        >>> blocks = extract_code_blocks(text)
        >>> blocks[0]["code"]
        'print("hi")'
    """
    blocks = []
    for match in CODE_FENCE_PATTERN.finditer(text):
        language = match.group(1).lower()
        code = match.group(2).strip()
        blocks.append(CodeBlock(language=language, code=code))
    return blocks


def extract_first_code_block(text: str) -> CodeBlock | None:
    """Extract only the first code block from text.

    Args:
        text: The response text.

    Returns:
        First CodeBlock found, or None if no code blocks exist.
    """
    blocks = extract_code_blocks(text)
    return blocks[0] if blocks else None


def strip_conversational_text(
    text: str,
    extract_all: bool = False
) -> str:
    """Remove conversational wrapper text, keeping only the code/content.

    This function strips common AI response patterns like:
    - "Here's the code you requested:"
    - "I hope this helps!"
    - "Let me know if you have questions."

    Args:
        text: The full response text.
        extract_all: If True and multiple code blocks exist, concatenate all.
                    If False, return only the first code block.

    Returns:
        Clean content with conversational text removed.
    """
    # First, try to extract code blocks
    blocks = extract_code_blocks(text)

    if blocks:
        if extract_all:
            # Concatenate all code blocks with newlines
            return "\n\n".join(block["code"] for block in blocks)
        else:
            # Return just the first code block
            return blocks[0]["code"]

    # No code blocks - try to strip intro/outro patterns from plain text
    result = text

    # Remove intro patterns
    for pattern in INTRO_PATTERNS:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE | re.MULTILINE)

    # Remove outro patterns
    for pattern in OUTRO_PATTERNS:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE | re.MULTILINE)

    return result.strip()


def extract_code_for_file(
    text: str,
    language: str | None = None
) -> str | None:
    """Extract code suitable for saving to a file.

    Prioritizes code blocks matching the specified language.
    Strips all conversational text.

    Args:
        text: The response text.
        language: Optional language to prefer (e.g., "python", "bash").

    Returns:
        Clean code string, or None if no code found.
    """
    blocks = extract_code_blocks(text)

    if not blocks:
        # Try to detect if the whole response is code
        stripped = strip_conversational_text(text)
        if stripped and _looks_like_code(stripped):
            return stripped
        return None

    # If language specified, prefer matching blocks
    if language:
        for block in blocks:
            if block["language"] == language.lower():
                return block["code"]

    # Return first block
    return blocks[0]["code"]


def _looks_like_code(text: str) -> bool:
    """Heuristic check if text looks like code."""
    code_indicators = [
        r"^(?:def|class|import|from|if|for|while|return|function|const|let|var)\s",
        r"^#!",  # Shebang
        r"[{};]\s*$",  # Braces/semicolons at end of lines
        r"^\s*(?:public|private|protected)\s",  # Java/C# modifiers
        r"=\s*(?:function|\(.*?\)\s*=>)",  # JS functions
    ]
    return any(re.search(p, text, re.MULTILINE) for p in code_indicators)


def extract_json(text: str) -> dict | list | None:
    """Extract JSON data from a response.

    Looks for JSON in code fences first, then tries to find
    inline JSON objects or arrays.

    Args:
        text: The response text.

    Returns:
        Parsed JSON data, or None if no valid JSON found.
    """
    # Try code blocks first
    blocks = extract_code_blocks(text)
    for block in blocks:
        if block["language"] in ("json", ""):
            try:
                return json.loads(block["code"])
            except json.JSONDecodeError:
                continue

    # Try to find inline JSON object
    obj_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
    if obj_match:
        try:
            return json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass

    # Try to find inline JSON array
    arr_match = re.search(r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]", text)
    if arr_match:
        try:
            return json.loads(arr_match.group())
        except json.JSONDecodeError:
            pass

    return None


def is_valid_python(code: str) -> bool:
    """Check if code is syntactically valid Python.

    Args:
        code: Python code string.

    Returns:
        True if the code parses without syntax errors.
    """
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def is_valid_bash(code: str) -> bool:
    """Basic validation for bash/shell code.

    This is a heuristic check - not a full parser.
    Checks for common shell patterns and balanced quotes.

    Args:
        code: Bash/shell code string.

    Returns:
        True if the code looks like valid bash.
    """
    # Check for balanced quotes (simple check)
    single_quotes = code.count("'") - code.count("\\'")
    double_quotes = code.count('"') - code.count('\\"')

    if single_quotes % 2 != 0 or double_quotes % 2 != 0:
        return False

    # Check for common bash patterns
    bash_patterns = [
        r"^\s*#",  # Comments
        r"^\s*\w+=",  # Variable assignment
        r"^\s*(?:if|then|else|fi|for|do|done|while|case|esac)\b",  # Keywords
        r"^\s*(?:echo|cd|ls|cat|grep|awk|sed|chmod|mkdir|rm|cp|mv)\b",  # Commands
        r"\|",  # Pipes
        r"&&|\|\|",  # Logic operators
        r"\$\w+|\$\{",  # Variables
    ]

    # At least one bash pattern should match
    return any(re.search(p, code, re.MULTILINE) for p in bash_patterns)


def get_file_extension(language: str) -> str:
    """Get appropriate file extension for a language.

    Args:
        language: The language identifier (e.g., "python", "javascript").

    Returns:
        File extension including the dot (e.g., ".py", ".js").
    """
    extensions = {
        "python": ".py",
        "py": ".py",
        "javascript": ".js",
        "js": ".js",
        "typescript": ".ts",
        "ts": ".ts",
        "bash": ".sh",
        "sh": ".sh",
        "shell": ".sh",
        "zsh": ".zsh",
        "ruby": ".rb",
        "rb": ".rb",
        "rust": ".rs",
        "go": ".go",
        "java": ".java",
        "c": ".c",
        "cpp": ".cpp",
        "c++": ".cpp",
        "csharp": ".cs",
        "cs": ".cs",
        "php": ".php",
        "sql": ".sql",
        "json": ".json",
        "yaml": ".yaml",
        "yml": ".yml",
        "toml": ".toml",
        "xml": ".xml",
        "html": ".html",
        "css": ".css",
        "markdown": ".md",
        "md": ".md",
    }
    return extensions.get(language.lower(), ".txt")
