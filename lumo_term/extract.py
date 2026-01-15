"""Response extraction and cleaning utilities.

This module provides functions to extract clean, usable content from
LUMO responses, removing conversational wrapper text and extracting
code blocks, JSON, and other structured content.

Supported languages for inline code detection:
- Python, Bash, PowerShell, Rust, Batch
- JavaScript, TypeScript, Go, Ruby
- C, C++, Java, SQL, YAML, Dockerfile
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

# Language detection patterns - maps language to (start_patterns, continuation_patterns)
# Start patterns detect the beginning of code blocks
# Continuation patterns help identify lines that are still part of code
LANGUAGE_PATTERNS: dict[str, tuple[list[str], list[str]]] = {
    "python": (
        [
            r'^def\s+\w+\s*\(',           # def func(
            r'^async\s+def\s+\w+\s*\(',   # async def func(
            r'^class\s+\w+[\s:(]',        # class Foo: or class Foo(
            r'^(import|from)\s+\w+',      # import/from statements
            r'^@\w+\s*(\(|$)',            # Decorators: @foo or @foo(...)
            r'^#!.*python',
        ],
        [
            r'^(def|class|import|from|if|elif|else|for|while|try|except|finally|with|return|yield|raise|assert|pass|break|continue|lambda)\s',
            r'^(print|input|open|len|range|enumerate|zip|map|filter|sorted|list|dict|set|tuple)\s*\(',
            r'^\s+',  # Indented lines
            r'^#(?!.*python)',  # Comments (but not shebangs)
            r'^@\w+\s*(\(|$)',  # Decorators
        ],
    ),
    "bash": (
        [
            r'^[a-zA-Z_][a-zA-Z0-9_]*\s*\(\)\s*\{',  # func() {
            r'^function\s+[a-zA-Z_]',                 # function name
            r'^#!.*(bash|sh|zsh)',                    # Shebang
            r'^(if|for|while|case|select)\s+.*;\s*(then|do)',  # Control flow
        ],
        [
            r'^(if|then|else|elif|fi|for|do|done|while|until|case|esac|function)\b',
            r'^(echo|printf|read|cd|ls|cat|grep|awk|sed|chmod|mkdir|rm|cp|mv|find|xargs)\b',
            r'^\s*\w+\s*=',           # Variable assignment
            r'\||\&\&|\|\|',          # Pipes and logic
            r'\$\(|\$\{|\$\w',        # Variables/subshells
            r'^#',                     # Comments
            r'^\s+',                   # Indented
        ],
    ),
    "powershell": (
        [
            r'^function\s+[A-Za-z]',
            r'^(Get|Set|New|Remove|Add|Clear|Import|Export|Invoke|Start|Stop|Write|Read)-[A-Za-z]',
            r'^\$\w+\s*=',
            r'^#!.*pwsh',
            r'^param\s*\(',
        ],
        [
            r'^(function|if|else|elseif|switch|for|foreach|while|do|try|catch|finally|return|throw|param)\b',
            r'^(Get|Set|New|Remove|Add|Clear|Import|Export|Invoke|Start|Stop|Write|Read)-',
            r'^\$\w+',                 # Variables
            r'^\s+',                   # Indented
            r'^#',                     # Comments
            r'\|',                     # Pipes
        ],
    ),
    "rust": (
        [
            r'^(pub\s+)?(fn|struct|enum|impl|trait|mod|type|const|static|use)\s',
            r'^#!\[',                  # Inner attributes
            r'^#\[',                   # Outer attributes
        ],
        [
            r'^(pub\s+)?(fn|struct|enum|impl|trait|mod|type|const|static|use|let|mut|if|else|match|for|while|loop|return|break|continue)\b',
            r'^(println!|print!|format!|vec!|panic!|assert!)',
            r'^\s+',                   # Indented
            r'^//',                    # Comments
            r'^#\[',                   # Attributes
        ],
    ),
    "batch": (
        [
            r'^@echo\s+(off|on)',
            r'^rem\s',
            r'^set\s+\w+=',
            r'^::\s',                  # Comment style
        ],
        [
            r'^(echo|set|if|else|for|goto|call|exit|pause|rem|setlocal|endlocal|pushd|popd)\b',
            r'^:\w+',                  # Labels
            r'^@',                     # @ prefix
            r'^::\s',                  # Comments
            r'%\w+%',                  # Variables
        ],
    ),
    "javascript": (
        [
            r'^(const|let|var|function|class|import|export)\s',
            r'^(async\s+)?function\s*\*?\s*\w*\s*\(',
            r'^#!.*node',
            r'^\s*\(\s*\)\s*=>\s*\{',  # Arrow function
        ],
        [
            r'^(const|let|var|function|class|import|export|if|else|for|while|do|switch|try|catch|finally|return|throw|new|async|await)\b',
            r'^(console|document|window|require|module)\.',
            r'^\s+',                   # Indented
            r'^//',                    # Comments
            r'=>',                     # Arrow functions
        ],
    ),
    "typescript": (
        [
            r'^(const|let|var|function|class|import|export|interface|type|enum|namespace)\s',
            r'^(async\s+)?function\s*\*?\s*\w*\s*[<(]',
        ],
        [
            r'^(const|let|var|function|class|import|export|interface|type|enum|namespace|if|else|for|while|return|async|await)\b',
            r'^\s*\w+\s*[?:]',         # Property: type annotations
            r':\s*(string|number|boolean|any|void|never|unknown|object|null)\b',
            r'^\s+',
            r'^//',
            r'^[{};\[\]]\s*$',         # Braces
        ],
    ),
    "go": (
        [
            r'^package\s+\w+',
            r'^func\s+(\(\w+\s+\*?\w+\)\s*)?\w+\s*\(',
            r'^import\s+[("]+',
            r'^type\s+\w+\s+(struct|interface)',
        ],
        [
            r'^(package|import|func|type|struct|interface|var|const|if|else|for|range|switch|case|return|go|defer|chan|select)\b',
            r'^(fmt|log|os|io|net|http|strings|strconv)\.',
            r'^\s+',
            r'^//',
        ],
    ),
    "ruby": (
        [
            r'^(def|class|module)\s+\w+',
            r'^require\s+[\'"]',
            r'^#!.*ruby',
        ],
        [
            r'^(def|class|module|if|elsif|else|unless|case|when|while|until|for|begin|rescue|ensure|end|return|yield|do|require|include|extend)\b',
            r'^(puts|print|gets|p)\s',
            r'^\s+',
            r'^#',
        ],
    ),
    "c": (
        [
            r'^#include\s*[<"]',
            r'^(int|void|char|float|double|long|short|unsigned|signed|struct|enum|typedef)\s+\w+\s*[(\[]',
            r'^(int|void)\s+main\s*\(',
        ],
        [
            r'^#(include|define|ifdef|ifndef|endif|pragma)',
            r'^(int|void|char|float|double|long|short|unsigned|signed|struct|enum|typedef|if|else|for|while|do|switch|case|return|break|continue|sizeof)\b',
            r'^\s+',
            r'^//',
            r'^/\*',
        ],
    ),
    "cpp": (
        [
            r'^#include\s*[<"]',
            r'^(class|struct|namespace|template)\s+\w+',
            r'^(int|void)\s+main\s*\(',
            r'^using\s+(namespace|std)',
        ],
        [
            r'^#(include|define|ifdef|ifndef|endif|pragma)',
            r'^(class|struct|namespace|template|public|private|protected|virtual|override|const|static|int|void|auto|if|else|for|while|return|new|delete|try|catch|throw)\b',
            r'^(std|cout|cin|endl|vector|string|map|set)::',
            r'^\s+',
            r'^//',
        ],
    ),
    "java": (
        [
            r'^(public|private|protected)?\s*(static\s+)?(class|interface|enum)\s+\w+',
            r'^package\s+[\w.]+;',
            r'^import\s+[\w.*]+;',
        ],
        [
            r'^(public|private|protected|static|final|abstract|class|interface|enum|extends|implements|new|return|if|else|for|while|do|switch|try|catch|finally|throw|throws|void|int|long|double|float|boolean|char|String)\b',
            r'^(System|String|Integer|List|Map|Set|ArrayList|HashMap)\.',
            r'^\s+',
            r'^//',
            r'^@\w+',  # Annotations
        ],
    ),
    "sql": (
        [
            r'^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|GRANT|REVOKE)\s',
            r'^--\s',
            r'^WITH\s+\w+\s+AS',
        ],
        [
            r'^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|EXISTS|GROUP|ORDER|BY|HAVING|LIMIT|OFFSET|AS|SET|VALUES|INTO|TABLE|INDEX|VIEW|GRANT|REVOKE|UNION|DISTINCT)\b',
            r'^\s+',
            r'^--',
        ],
    ),
    "yaml": (
        [
            r'^---\s*$',                           # Document start
            r'^\w+:\s+[\'"\d\[\{]',                # key: "value" or key: 123 (not key: type)
            r'^\w+:\s*$',                          # key: (no value, block follows)
        ],
        [
            r'^\s+-\s+',
            r'^\s+\w+:',
            r'^\w+:\s',
            r'^#',
        ],
    ),
    "dockerfile": (
        [
            r'^FROM\s+\w+',
            r'^#\s*syntax\s*=',
        ],
        [
            r'^(FROM|RUN|CMD|LABEL|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL)\s',
            r'^#',
        ],
    ),
}

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
    Falls back to extracting inline code without fences.

    Args:
        text: The response text.
        language: Optional language to prefer (e.g., "python", "bash").

    Returns:
        Clean code string, or None if no code found.
    """
    blocks = extract_code_blocks(text)

    if blocks:
        # If language specified, prefer matching blocks
        if language:
            for block in blocks:
                if block["language"] == language.lower():
                    return block["code"]
        # Return first block
        return blocks[0]["code"]

    # No code fences - try to extract inline code section
    code_section = extract_code_section(text)
    if code_section:
        return code_section

    # Last resort: check if stripped text looks like code
    stripped = strip_conversational_text(text)
    if stripped and _looks_like_code(stripped):
        return stripped

    return None


def _looks_like_code(text: str) -> bool:
    """Heuristic check if text looks like code."""
    # Collect all start patterns from all languages
    for lang, (start_patterns, _) in LANGUAGE_PATTERNS.items():
        for pattern in start_patterns:
            if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                return True

    # Additional generic code indicators
    generic_indicators = [
        r"^#!",                    # Shebang
        r"[{};]\s*$",              # Braces/semicolons at end of lines
        r"^\s*\w+\s*\([^)]*\)\s*[{:]",  # Function definitions
        r"=\s*(?:function|\(.*?\)\s*=>)",  # JS functions
    ]
    return any(re.search(p, text, re.MULTILINE) for p in generic_indicators)


def _detect_language(line: str) -> str | None:
    """Detect which language a line of code belongs to.

    Args:
        line: A single line of text.

    Returns:
        Language name if detected, None otherwise.
    """
    stripped = line.strip()

    # Languages where keywords are case-insensitive
    case_insensitive_langs = {"sql", "batch", "powershell"}

    for lang, (start_patterns, _) in LANGUAGE_PATTERNS.items():
        flags = re.IGNORECASE if lang in case_insensitive_langs else 0
        for pattern in start_patterns:
            if re.match(pattern, stripped, flags):
                return lang
    return None


def _is_code_continuation(line: str, language: str | None) -> bool:
    """Check if a line continues a code block in the given language.

    Args:
        line: The line to check.
        language: The detected language, or None for generic check.

    Returns:
        True if line looks like code continuation.
    """
    stripped = line.strip()

    # Empty lines and indented lines are usually continuations
    if not stripped or line.startswith('    ') or line.startswith('\t'):
        return True

    # Check language-specific continuation patterns
    if language and language in LANGUAGE_PATTERNS:
        _, continuation_patterns = LANGUAGE_PATTERNS[language]
        case_insensitive_langs = {"sql", "batch", "powershell"}
        flags = re.IGNORECASE if language in case_insensitive_langs else 0
        for pattern in continuation_patterns:
            if re.match(pattern, stripped, flags):
                return True

    # Generic code patterns (work for most languages)
    generic_patterns = [
        r'^\s+',                        # Indented
        r'^[{}()\[\]];?\s*$',           # Braces only
        r'^\w+\s*[=(]',                 # Assignment or call
        r'^(//|#|--|/\*|\*)',           # Comments
        r'[{};]\s*$',                   # Ends with brace/semicolon
    ]
    for pattern in generic_patterns:
        if re.match(pattern, stripped):
            return True

    return False


def extract_code_section(text: str) -> str | None:
    """Extract code section from response without code fences.

    Supports multiple languages: Python, Bash, PowerShell, Rust, Batch,
    JavaScript, TypeScript, Go, Ruby, C, C++, Java, SQL, YAML, Dockerfile.

    Args:
        text: Response text that may contain inline code.

    Returns:
        Extracted code section, or None if no code found.
    """
    lines = text.split('\n')
    code_lines: list[str] = []
    in_code = False
    detected_language: str | None = None
    empty_line_count = 0

    # Patterns that indicate we're leaving code (conversational text)
    non_code_patterns = [
        r'^what\s+(changed|this|the)',
        r'^(note|notes|explanation|output|result|example|usage|issue|bug|warning|tip|important):?\s*$',
        r'^(here|this|the|it|that)\s+(is|are|will|should|would|can|could|may|might)',
        r'^-\s+[A-Z]',       # Markdown list items starting with capital
        r'^\d+\.\s+[A-Z]',   # Numbered lists starting with capital
        r'^(now|next|then|finally|also|and|or|but|however|therefore)\s+',
        r'^(you|we|i|they|he|she|it)\s+(can|could|should|will|would|may|might|must)',
        r'^(how|why|what|when|where|which)\s+(it|this|the|to)\s+',
        r'^(save|copy|run|execute|compile|install|download|open|click)\s+(this|the|it|to)',
    ]
    non_code_regex = re.compile('|'.join(non_code_patterns), re.IGNORECASE)

    for line in lines:
        stripped = line.strip()

        # Detect start of code block
        if not in_code:
            detected_language = _detect_language(stripped)
            if detected_language:
                in_code = True
                code_lines.append(line)
                empty_line_count = 0
            continue

        # In code block - check for end markers
        if non_code_regex.match(stripped) and empty_line_count > 0:
            # Hit non-code explanatory text after blank line
            break

        if stripped == '':
            empty_line_count += 1
            if empty_line_count >= 3:
                # Three consecutive empty lines = end of code
                break
            code_lines.append(line)
        elif _is_code_continuation(line, detected_language):
            code_lines.append(line)
            empty_line_count = 0
        else:
            # Check if this could be a new code construct in same language
            new_lang = _detect_language(stripped)
            if new_lang == detected_language or new_lang is None:
                # Continue if it looks like code
                if re.match(r'^[a-zA-Z_]\w*\s*[=({\[]', stripped):
                    code_lines.append(line)
                    empty_line_count = 0
                else:
                    # End of code block
                    break
            else:
                # Different language detected - end current block
                break

    if code_lines:
        # Remove trailing empty lines
        while code_lines and code_lines[-1].strip() == '':
            code_lines.pop()

        # Return code if we have meaningful content
        if len(code_lines) >= 2:
            return '\n'.join(code_lines)
        elif len(code_lines) == 1:
            line = code_lines[0].strip()
            # Single-line constructs that are complete
            # Bash function: name() { ... }
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*\(\)\s*\{.*\}', line):
                return line
            # Single-line with pipes/logic/subshells
            if '|' in line or '&&' in line or '$(' in line or ';' in line:
                return line
            # PowerShell one-liner
            if re.match(r'^(Get|Set|New|Remove|Invoke)-\w+', line, re.IGNORECASE):
                return line

    return None


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
