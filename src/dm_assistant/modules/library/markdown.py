"""Deterministic Markdown parsing and chunking for immutable source revisions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

_FRONT_MATTER_DELIMITER = "---"
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+)")
_FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
_TABLE_ROW_PATTERN = re.compile(r"^\s*\|")


@dataclass(frozen=True)
class MarkdownChunk:
    """A deterministic chunk for a revision with exact source offsets."""

    source_content_hash: str
    ordinal: int
    heading_path: tuple[str, ...]
    start_offset: int
    end_offset: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def chunk_id(self) -> str:
        identity = ":".join(
            (
                _CHUNKER_VERSION,
                self.source_content_hash,
                str(self.ordinal),
                str(self.start_offset),
                str(self.end_offset),
                self.content_hash,
            )
        )
        return hashlib.sha256(identity.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class ParsedMarkdownDocument:
    """Parsed Markdown with front matter and deterministic chunks."""

    front_matter: dict[str, str]
    chunks: tuple[MarkdownChunk, ...]
    source_content_hash: str
    diagnostics: tuple[str, ...] = ()


def parse_markdown_document(
    content: str,
    *,
    max_chunk_chars: int = 240,
    overlap_chars: int = 32,
) -> ParsedMarkdownDocument:
    """Parse Markdown into front matter, semantic chunks, and exact offsets."""

    if max_chunk_chars < 1:
        raise ValueError("max_chunk_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chunk_chars:
        raise ValueError("overlap_chars must be between 0 and max_chunk_chars - 1")

    front_matter, body_content, body_start_offset, diagnostics = _split_front_matter(
        content
    )
    blocks, block_diagnostics = _parse_blocks(body_content, body_start_offset)
    chunks = tuple(
        _chunk_block(block, body_content, body_start_offset, max_chunk_chars, overlap_chars)
        for block in blocks
    )
    source_content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    flattened_chunks = tuple(
        MarkdownChunk(
            source_content_hash=source_content_hash,
            ordinal=ordinal,
            heading_path=chunk.heading_path,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            content=chunk.content,
            metadata=chunk.metadata,
        )
        for ordinal, chunk in enumerate(
            chunk for block_chunks in chunks for chunk in block_chunks
        )
    )
    return ParsedMarkdownDocument(
        front_matter=front_matter,
        chunks=flattened_chunks,
        source_content_hash=source_content_hash,
        diagnostics=diagnostics + block_diagnostics,
    )


_PARSER_VERSION = "markdown-parser-v1"
_CHUNKER_VERSION = "markdown-chunker-v1"


def parser_version() -> str:
    return _PARSER_VERSION


def chunker_version() -> str:
    return _CHUNKER_VERSION


def _split_front_matter(content: str) -> tuple[dict[str, str], str, int, tuple[str, ...]]:
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FRONT_MATTER_DELIMITER:
        return {}, content, 0, ()

    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONT_MATTER_DELIMITER:
            front_text = "".join(lines[1:index])
            front_matter: dict[str, str] = {}
            for raw_line in front_text.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                front_matter[key.strip()] = value.strip()
            body_text = "".join(lines[index + 1 :])
            return front_matter, body_text, len(content) - len(body_text), ()
    return {}, content, 0, ()


def _parse_blocks(
    body_content: str, body_start_offset: int
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    if not body_content.strip():
        return [], ()

    lines = body_content.splitlines(keepends=True)
    line_starts = [0]
    offset = 0
    for line in lines:
        offset += len(line)
        line_starts.append(offset)

    blocks: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    headings: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        heading_match = _HEADING_PATTERN.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            while len(headings) >= level:
                headings.pop()
            headings.append(text)
            start_offset = body_start_offset + line_starts[index]
            end_offset = body_start_offset + line_starts[index + 1] if index + 1 < len(lines) else body_start_offset + len(body_content)
            blocks.append(
                {
                    "kind": "heading",
                    "heading_path": tuple(headings),
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "content": line,
                }
            )
            index += 1
            continue

        if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
            fence_marker = line.lstrip()[:3]
            start_index = index
            index += 1
            while index < len(lines):
                if lines[index].lstrip().startswith(fence_marker):
                    index += 1
                    break
                index += 1
            if index == len(lines) and not lines[-1].lstrip().startswith(fence_marker):
                diagnostics.append("unterminated_fenced_code")
            end_index = index
            start_offset = body_start_offset + line_starts[start_index]
            end_offset = body_start_offset + line_starts[end_index] if end_index < len(lines) else body_start_offset + len(body_content)
            content = "".join(lines[start_index:end_index])
            blocks.append(
                {
                    "kind": "code",
                    "heading_path": tuple(headings),
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "content": content,
                }
            )
            continue

        if line.lstrip().startswith("|"):
            start_index = index
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                index += 1
            end_index = index
            start_offset = body_start_offset + line_starts[start_index]
            end_offset = body_start_offset + line_starts[end_index] if end_index < len(lines) else body_start_offset + len(body_content)
            content = "".join(lines[start_index:end_index])
            blocks.append(
                {
                    "kind": "table",
                    "heading_path": tuple(headings),
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "content": content,
                }
            )
            continue

        if _LIST_PATTERN.match(stripped):
            start_index = index
            while index < len(lines) and _LIST_PATTERN.match(lines[index].strip()):
                index += 1
            end_index = index
            start_offset = body_start_offset + line_starts[start_index]
            end_offset = body_start_offset + line_starts[end_index] if end_index < len(lines) else body_start_offset + len(body_content)
            content = "".join(lines[start_index:end_index])
            blocks.append(
                {
                    "kind": "list",
                    "heading_path": tuple(headings),
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "content": content,
                }
            )
            continue

        start_index = index
        while index < len(lines) and lines[index].strip() and not _LIST_PATTERN.match(lines[index].strip()) and not lines[index].lstrip().startswith("|") and not lines[index].lstrip().startswith("```") and not lines[index].lstrip().startswith("~~~") and not _HEADING_PATTERN.match(lines[index].strip()):
            index += 1
        end_index = index
        start_offset = body_start_offset + line_starts[start_index]
        end_offset = body_start_offset + line_starts[end_index] if end_index < len(lines) else body_start_offset + len(body_content)
        content = "".join(lines[start_index:end_index])
        blocks.append(
            {
                "kind": "paragraph",
                "heading_path": tuple(headings),
                "start_offset": start_offset,
                "end_offset": end_offset,
                "content": content,
            }
        )
    return blocks, tuple(diagnostics)


def _chunk_block(
    block: dict[str, Any],
    body_content: str,
    body_start_offset: int,
    max_chunk_chars: int,
    overlap_chars: int,
) -> list[MarkdownChunk]:
    content = block["content"]
    if not content:
        return []

    if len(content) <= max_chunk_chars:
        return [
            MarkdownChunk(
                source_content_hash="",
                ordinal=-1,
                heading_path=block["heading_path"],
                start_offset=block["start_offset"],
                end_offset=block["end_offset"],
                content=content,
                metadata={"kind": block["kind"]},
            )
        ]

    chunks: list[MarkdownChunk] = []
    cursor = 0
    while cursor < len(content):
        end = min(len(content), cursor + max_chunk_chars)
        slice_text = content[cursor:end]
        if slice_text and slice_text.strip():
            chunk_start_offset = block["start_offset"] + cursor
            chunk_end_offset = block["start_offset"] + end
            chunks.append(
                MarkdownChunk(
                    source_content_hash="",
                    ordinal=-1,
                    heading_path=block["heading_path"],
                    start_offset=chunk_start_offset,
                    end_offset=chunk_end_offset,
                    content=slice_text,
                    metadata={"kind": block["kind"], "split": True},
                )
            )
        if end >= len(content):
            break
        cursor = max(cursor + 1, end - overlap_chars)
    return chunks
