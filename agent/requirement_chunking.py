from __future__ import annotations

from dataclasses import dataclass
import re


DEFAULT_REQUIREMENT_CHUNK_CHARS = 5_000


@dataclass(frozen=True)
class RequirementChunk:
    chunk_id: str
    title: str
    content: str
    start_char: int
    end_char: int

    def __post_init__(self) -> None:
        if not self.chunk_id.strip():
            raise ValueError("requirement chunk ID cannot be empty")
        if not self.content.strip():
            raise ValueError("requirement chunk content cannot be empty")
        if self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("requirement chunk range is invalid")


class RequirementChunker:
    """Split long requirements at headings and paragraph boundaries."""

    _HEADING = re.compile(
        r"(?m)^(?P<heading>\s*(?:#{1,6}\s+.+|第[一二三四五六七八九十百\d]+[章节]\s*.*|"
        r"[一二三四五六七八九十]+、\s*.+|\d+(?:\.\d+)*[.、]\s*.+))\s*$"
    )
    _PARAGRAPH_END = re.compile(r"\n\s*\n")
    _SENTENCE_END = re.compile(r"[。！？；;]\s*|\n")

    def __init__(self, max_chars: int = DEFAULT_REQUIREMENT_CHUNK_CHARS):
        if max_chars < 500:
            raise ValueError("requirement chunk max_chars must be at least 500")
        self.max_chars = max_chars

    def split(self, requirement: str) -> tuple[RequirementChunk, ...]:
        if not isinstance(requirement, str) or not requirement.strip():
            raise ValueError("requirement cannot be empty")

        ranges = self._section_ranges(requirement)
        bounded_ranges: list[tuple[int, int, str]] = []
        pending_start: int | None = None
        pending_end = 0
        pending_titles: list[str] = []

        def flush_pending() -> None:
            nonlocal pending_start, pending_end, pending_titles
            if pending_start is not None:
                bounded_ranges.append(
                    (pending_start, pending_end, " / ".join(pending_titles))
                )
            pending_start = None
            pending_end = 0
            pending_titles = []

        for start, end, title in ranges:
            if end - start > self.max_chars:
                flush_pending()
                bounded_ranges.extend(
                    (part_start, part_end, title)
                    for part_start, part_end in self._split_oversized(
                        requirement, start, end
                    )
                )
                continue
            if pending_start is None:
                pending_start, pending_end = start, end
                pending_titles = [title] if title else []
                continue
            if end - pending_start <= self.max_chars:
                pending_end = end
                if title:
                    pending_titles.append(title)
                continue
            flush_pending()
            pending_start, pending_end = start, end
            pending_titles = [title] if title else []
        flush_pending()

        chunks = []
        for index, (start, end, title) in enumerate(bounded_ranges, start=1):
            content = requirement[start:end]
            if not content.strip():
                continue
            chunks.append(
                RequirementChunk(
                    chunk_id=f"chunk-{index:03d}",
                    title=title or f"片段{index}",
                    content=content,
                    start_char=start,
                    end_char=end,
                )
            )
        return tuple(chunks)

    def _section_ranges(self, text: str) -> list[tuple[int, int, str]]:
        headings = list(self._HEADING.finditer(text))
        if not headings:
            return [(0, len(text), "全文")]

        ranges: list[tuple[int, int, str]] = []
        if headings[0].start() > 0:
            ranges.append((0, headings[0].start(), "文档说明"))
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            ranges.append(
                (
                    heading.start(),
                    end,
                    heading.group("heading").strip().lstrip("#").strip(),
                )
            )
        return ranges

    def _split_oversized(
        self,
        text: str,
        start: int,
        end: int,
    ) -> list[tuple[int, int]]:
        parts: list[tuple[int, int]] = []
        cursor = start
        while end - cursor > self.max_chars:
            limit = cursor + self.max_chars
            split_at = self._last_boundary(
                text,
                cursor,
                limit,
                self._PARAGRAPH_END,
            )
            if split_at <= cursor:
                split_at = self._last_boundary(
                    text,
                    cursor,
                    limit,
                    self._SENTENCE_END,
                )
            if split_at <= cursor:
                split_at = limit
            parts.append((cursor, split_at))
            cursor = split_at
        if cursor < end:
            parts.append((cursor, end))
        return parts

    @staticmethod
    def _last_boundary(
        text: str,
        start: int,
        end: int,
        pattern: re.Pattern[str],
    ) -> int:
        matches = list(pattern.finditer(text, start, end))
        return matches[-1].end() if matches else start

