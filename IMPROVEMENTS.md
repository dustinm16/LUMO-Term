# LUMO-Term Potential Improvements

A prioritized list of potential enhancements to bring LUMO-Term closer to Claude Code functionality.

## Current State

| Feature | Status |
|---------|--------|
| REPL Mode | ✅ Working |
| Single Message Mode | ✅ Working |
| Headless Browser | ✅ Working |
| Streaming Responses | ✅ Working |
| Session Persistence | ✅ Within session |
| Security (injection safe) | ✅ 30 tests passing |
| Logging Infrastructure | ✅ Basic |

---

## High Priority

### 1. Pipe/Stdin Support
**Effort:** Low | **Impact:** High

Allow piping file contents to LUMO:
```bash
cat script.py | lumo "Review this code"
lumo "Explain this" < error.log
```

**Implementation:**
- Check `sys.stdin.isatty()`
- Read stdin and append to message
- Handle binary vs text detection

---

### 2. File Context (`-f` flag)
**Effort:** Low | **Impact:** High

Include file contents in prompt:
```bash
lumo -f src/main.py "Add error handling to this"
lumo -f *.py "Find bugs in these files"
```

**Implementation:**
- Add `-f/--file` argument (supports globs)
- Read and concatenate file contents
- Add file markers for context

---

### 3. Conversation History Persistence
**Effort:** Medium | **Impact:** High

Save/resume conversations across sessions:
```bash
lumo --continue          # Resume last conversation
lumo --history           # List past conversations
lumo --load <id>         # Load specific conversation
```

**Implementation:**
- Store conversations in `~/.local/share/lumo-term/conversations/`
- JSON format with metadata
- Link to browser session IDs if possible

---

### 4. Output to File (`-o` flag)
**Effort:** Low | **Impact:** Medium

Save responses directly to file:
```bash
lumo -m "Write a Python script for X" -o script.py
lumo -m "Generate README" -o README.md
```

**Implementation:**
- Add `-o/--output` argument
- Write response to file
- Optional `--append` mode

---

### 5. Improved TUI (Textual)
**Effort:** High | **Impact:** High

Full terminal UI like Claude Code:
- Split pane (input/output)
- Scrollable history
- Syntax highlighting for code blocks
- Keyboard shortcuts
- Status bar (connection, model, tokens)

**Current:** Basic `ui.py` exists but needs work.

---

## Medium Priority

### 6. Code Block Extraction
**Effort:** Low | **Impact:** Medium

Extract and save code blocks from responses:
```bash
lumo -m "Write a bash script" --extract-code script.sh
lumo -m "Create a class" --run-code  # Execute extracted code
```

**Implementation:**
- Parse markdown code fences
- Detect language from fence
- Save with appropriate extension

---

### 7. System Prompt / Persona
**Effort:** Medium | **Impact:** Medium

Customize LUMO's behavior:
```bash
lumo --system "You are a Python expert"
lumo --persona code-reviewer
```

**Implementation:**
- Prepend system message
- Store personas in config
- Note: May need to inject via first message

---

### 8. Multi-turn Context Window
**Effort:** Medium | **Impact:** Medium

Better context management:
- Show token count
- Warn on context limit
- Auto-summarize old messages
- `/context` command to show usage

---

### 9. Response Formatting Options
**Effort:** Low | **Impact:** Medium

Control output format:
```bash
lumo -m "List files" --format plain    # No markdown
lumo -m "Explain X" --format json      # JSON output
lumo -m "Code" --format code-only      # Just code blocks
```

---

### 10. Retry/Regenerate
**Effort:** Low | **Impact:** Medium

REPL commands for retry:
```
/retry              # Resend last message
/regen              # Regenerate last response
/edit               # Edit and resend last message
```

---

## Lower Priority

### 11. Multiple Conversations (Tabs)
**Effort:** High | **Impact:** Medium

Manage parallel conversations:
```bash
lumo --new-tab "Project A context"
/switch 2           # Switch to conversation 2
/list               # List open conversations
```

---

### 12. Clipboard Integration
**Effort:** Low | **Impact:** Low

```bash
lumo --clipboard    # Use clipboard content as input
lumo -m "X" --copy  # Copy response to clipboard
```

---

### 13. Shell Integration
**Effort:** Medium | **Impact:** Medium

Execute shell commands from LUMO suggestions:
```
LUMO: Try running `pytest -v`
> /run              # Execute suggested command
> /run pytest -v    # Run specific command
```

**Security:** Require confirmation, sandbox options.

---

### 14. Watch Mode
**Effort:** Medium | **Impact:** Low

Monitor files and auto-query:
```bash
lumo --watch src/ "Review changes"  # Query on file change
```

---

### 15. API Metrics Dashboard
**Effort:** Low | **Impact:** Low

Expand logging to show:
- Response times over time
- Token usage estimates
- Error rates
- Session duration

Use existing `LogAnalyzer` class.

---

### 16. Themes
**Effort:** Low | **Impact:** Low

Customizable colors:
```bash
lumo --theme dark
lumo --theme light
lumo --theme monokai
```

Store in config file.

---

### 17. Aliases/Shortcuts
**Effort:** Low | **Impact:** Low

Custom command aliases:
```toml
# ~/.config/lumo-term/config.toml
[aliases]
review = "-f {file} 'Review this code for bugs and improvements'"
explain = "'Explain this simply:'"
```

---

## Experimental / Research

### 18. Local Context Injection
**Effort:** High | **Impact:** High

Inject codebase context like Claude Code:
- Project structure awareness
- Relevant file detection
- Semantic search over codebase

Requires: embeddings, vector store, chunking.

---

### 19. Tool Use Emulation
**Effort:** Very High | **Impact:** Very High

Let LUMO execute tools (Claude Code style):
- File read/write
- Shell commands
- Web search

**Challenge:** LUMO doesn't have native tool use. Would require:
- Response parsing for "intents"
- Local tool execution
- Result injection back to conversation

---

### 20. Voice Input/Output
**Effort:** High | **Impact:** Low

```bash
lumo --voice         # Voice input via whisper
lumo --speak         # TTS for responses
```

---

## Quick Wins (< 1 hour each)

1. [ ] `-f` file flag
2. [ ] Stdin pipe support
3. [ ] `-o` output flag
4. [ ] `--copy` clipboard output
5. [ ] `/retry` command
6. [ ] `--format plain` option
7. [ ] Token count estimate display
8. [ ] `--verbose` for debug output

---

## Implementation Order Recommendation

**Phase 1 - CLI Enhancements:**
1. Pipe/stdin support
2. File context flag
3. Output to file

**Phase 2 - REPL Improvements:**
4. Retry/regenerate commands
5. Conversation history
6. Better error messages

**Phase 3 - TUI:**
7. Full Textual UI
8. Syntax highlighting
9. Keyboard shortcuts

**Phase 4 - Advanced:**
10. Code extraction
11. Shell integration
12. Context injection
