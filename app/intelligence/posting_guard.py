"""
Posting Guard: Integrity & Prompt Injection Defense for Scraped Job Postings.
Detects and strips adversarial payloads from third-party job descriptions
before they reach LLMs, STAIR matching, or resume tailoring.
Inspired by ai-job-search posting_guard architecture.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Tuple

ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"
BIDI = "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
BIDI_TAMPER = "\u202d\u202e\u2066\u2067\u2068\u2069"  # overrides and isolates
FORMAT_CHARS = "\u00ad\u2028\u2029"  # soft hyphen, line/paragraph separators

# Unicode tag characters block (U+E0000 - U+E007F)
TAG_RUN = re.compile("[\U000E0000-\U000E007F]+")

# UK subdivision flag emoji (the only legitimate use of tag characters)
RGI_TAG_FLAG = re.compile(
    "\U0001F3F4\U000E0067\U000E0062(?:\U000E0065\U000E006E\U000E0067"
    "|\U000E0073\U000E0063\U000E0074|\U000E0077\U000E006C\U000E0073)\U000E007F"
)

# Hidden CSS patterns
HIDDEN_STYLE = re.compile(
    r"(?:^|;)\s*(?:display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|opacity\s*:\s*0(?![.\d]*[1-9])"
    r"|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?(?![\d.])"
    r"|color\s*:\s*transparent"
    r"|clip\s*:\s*rect\(\s*0"
    r"|clip-path\s*:\s*inset\(\s*100%"
    r"|(?:(?:margin-)?(?:left|top)|text-indent)\s*:\s*-\d{4,}px)",
    re.I,
)

DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|svg|template|iframe)\b[^>]*>.*?(?:</\1\s*>|\Z)",
    re.I | re.S,
)
HTML_COMMENTS = re.compile(r"<!--.*?(?:-->|\Z)", re.S)

HTML_TAG = re.compile(r"<(/?)([a-zA-Z][\w:-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.S)
ATTR = re.compile(r"([^\s=/\"'>]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>\"']+)))?")
VOID = {"br", "img", "input", "meta", "link", "hr", "wbr", "source", "area", "base", "col", "embed", "param", "track"}
BLOCK = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "section", "article",
         "header", "footer", "table", "thead", "tbody", "blockquote", "pre", "dd", "dt", "dl", "nav", "main"}

INSTRUCTION_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\bignore\s+(all|any|the|previous|prior|above|earlier)\s+(instructions?|prompts?)\b",
        r"\b(disregard|forget)\s+(all|any|the|your|my)?\s*(previous|prior|above|earlier)\s+(instructions?|prompts?)\b",
        r"\byou\s+are\s+now\s+(an?|the)?\s*(ai|assistant|model|llm|hacker)\b",
        r"\bsystem\s+prompt\s*:",
        r"\bdo\s+not\s+(tell|inform|reveal|disclose\s+to)\s+the\s+user\b",
        r"\b(award|give)\s+this\s+candidate\s+(a\s+score\s+of\s+)?(100|maximum|perfect)\b",
        r"<\|(?:im_start|im_end|endoftext)\|>",
        r"\[INST\]|\[/INST\]",
        r"###\s*(system|instruction|human|assistant)",
        r"\b(curl|wget)\s+.*\|\s*(bash|sh)\b",
        r"\bexport\s+[A-Z_]+=",
    )
]


def _parse_attrs(raw: str) -> Dict[str, str]:
    out = {}
    for m in ATTR.finditer(raw):
        name = m.group(1).lower()
        val = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else (m.group(4) or ""))
        out[name] = val
    return out


def _is_hidden(raw_attrs: str) -> bool:
    attrs = _parse_attrs(raw_attrs)
    if "hidden" in attrs or attrs.get("aria-hidden", "").strip().lower() == "true":
        return True
    style = html.unescape(attrs.get("style", ""))
    if HIDDEN_STYLE.search(style):
        return True
    return False


def _fold(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\xa0\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class PostingGuard:
    """
    Sanitizes job descriptions and removes prompt injection vectors.
    """

    @classmethod
    def strip_hidden_html(cls, markup: str) -> Tuple[str, int, List[str]]:
        """
        Strips HTML comments, scripts, styles, and hidden CSS/attribute blocks
        along with their contents using a DOM element stack.
        """
        hidden_blocks: List[str] = []
        hidden_count = 0

        # Remove comments and script/style/noscript tags
        markup = HTML_COMMENTS.sub(" ", markup)
        markup = DROP_BLOCKS.sub(" ", markup)

        visible = []
        hidden_buf = []
        stack: List[str] = []
        hidden_at = None
        pos = 0

        def emit(chunk: str):
            (visible if hidden_at is None else hidden_buf).append(chunk)

        def flush_hidden():
            nonlocal hidden_at, hidden_count
            block = _fold(html.unescape("".join(hidden_buf)))
            hidden_buf.clear()
            hidden_at = None
            if block:
                hidden_blocks.append(block[:200])
                hidden_count += 1

        def pop_to(index: int):
            del stack[index:]
            if hidden_at is not None and hidden_at >= len(stack):
                flush_hidden()

        def last_index(name: str):
            for i in range(len(stack) - 1, -1, -1):
                if stack[i] == name:
                    return i
            return None

        for m in HTML_TAG.finditer(markup):
            emit(markup[pos:m.start()])
            pos = m.end()
            closing, name, raw_attrs = m.group(1), m.group(2).lower(), m.group(3)

            if name in BLOCK:
                emit("\n")

            if closing:
                idx = last_index(name)
                if idx is not None:
                    pop_to(idx)
                continue

            is_hid = (hidden_at is not None) or _is_hidden(raw_attrs)
            if is_hid and hidden_at is None:
                hidden_at = len(stack)

            if name in VOID:
                if is_hid and hidden_at == len(stack):
                    flush_hidden()
                continue

            stack.append(name)

        emit(markup[pos:])
        if hidden_at is not None:
            flush_hidden()

        text = html.unescape("".join(visible))
        return _fold(text), hidden_count, hidden_blocks

    @classmethod
    def clean(cls, text: str) -> Dict[str, Any]:
        """
        Cleans and scans text for prompt injection and hidden payloads.
        Returns detailed report and sanitized string.
        """
        if not text:
            return {
                "cleaned_text": "",
                "risk_level": "low",
                "flags": [],
                "invisible_chars_count": 0,
                "hidden_blocks_count": 0,
            }

        flags: List[str] = []

        # 1. HTML hidden elements stripping (including content)
        text_without_hidden, hidden_blocks_count, _ = cls.strip_hidden_html(text)
        if hidden_blocks_count > 0:
            flags.append(f"stripped_{hidden_blocks_count}_hidden_html_blocks")

        # 2. Check for tag characters (ASCII smuggling)
        unflagged_tags = RGI_TAG_FLAG.sub("", text_without_hidden)
        tag_matches = TAG_RUN.findall(unflagged_tags)
        tag_count = sum(len(m) for m in tag_matches)
        if tag_count > 0:
            flags.append(f"tag_characters_detected_{tag_count}")
            for run in tag_matches:
                decoded = "".join(
                    chr(ord(c) - 0xE0000)
                    for c in run
                    if 0x20 <= ord(c) - 0xE0000 < 0x7F
                ).strip()
                if decoded:
                    flags.append(f"smuggled_ascii:{decoded[:60]}")

        # 3. Check for zero-width characters and bidi overrides
        invisible_count = 0
        has_tamper_bidi = False
        has_intra_word_zw = False

        for i, ch in enumerate(text_without_hidden):
            if ch in ZERO_WIDTH or ch in FORMAT_CHARS:
                invisible_count += 1
                before = text_without_hidden[i - 1] if i > 0 else ""
                after = text_without_hidden[i + 1] if i + 1 < len(text_without_hidden) else ""
                if before.isalpha() and after.isalpha():
                    has_intra_word_zw = True
            elif ch in BIDI_TAMPER:
                has_tamper_bidi = True
                invisible_count += 1
            elif ch in BIDI:
                invisible_count += 1

        if has_intra_word_zw:
            flags.append("intra_word_zero_width_tampering")
        if has_tamper_bidi:
            flags.append("bidi_override_detected")

        # Strip all invisible chars and tag characters (preserving legitimate flag emoji)
        flags_emoji = RGI_TAG_FLAG.findall(text_without_hidden)
        text_cleaned = RGI_TAG_FLAG.sub("___TAG_FLAG_PLACEHOLDER___", text_without_hidden)

        chars_to_remove = set(ZERO_WIDTH + BIDI + FORMAT_CHARS + "".join(chr(c) for c in range(0xE0000, 0xE0080)))
        text_cleaned = "".join(ch for ch in text_cleaned if ch not in chars_to_remove)

        if flags_emoji:
            for flag in flags_emoji:
                text_cleaned = text_cleaned.replace("___TAG_FLAG_PLACEHOLDER___", flag, 1)

        # Unescape HTML entities
        text_cleaned = html.unescape(text_cleaned)

        # Remove residual HTML tags
        text_cleaned = re.sub(r"<[^>]+>", " ", text_cleaned)

        # Fold excessive whitespace
        text_cleaned = _fold(text_cleaned)

        # 4. Check for adversarial instruction patterns
        detected_instructions = []
        for pat in INSTRUCTION_PATTERNS:
            found = pat.findall(text_cleaned)
            if found:
                detected_instructions.append(pat.pattern)

        if detected_instructions:
            flags.append(f"adversarial_instruction_patterns:{len(detected_instructions)}")

        # Determine risk level
        risk_level = "low"
        if tag_count > 0 or has_intra_word_zw or has_tamper_bidi or detected_instructions:
            risk_level = "high"
        elif hidden_blocks_count > 0 or invisible_count > 5:
            risk_level = "medium"

        return {
            "cleaned_text": text_cleaned,
            "risk_level": risk_level,
            "flags": flags,
            "invisible_chars_count": invisible_count + tag_count,
            "hidden_blocks_count": hidden_blocks_count,
        }

    @classmethod
    def sanitize_for_llm(cls, text: str) -> str:
        """Convenience method returning sanitized text."""
        return cls.clean(text)["cleaned_text"]
