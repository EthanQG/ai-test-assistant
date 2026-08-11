from __future__ import annotations

from dataclasses import dataclass
import re

from .requirement_chunking import RequirementChunk


@dataclass(frozen=True)
class RequirementStatement:
    statement_id: str
    text: str
    section: str
    chunk_id: str
    start_char: int
    end_char: int

    def __post_init__(self) -> None:
        if not re.fullmatch(r"S\d{3,}", self.statement_id):
            raise ValueError("statement_id must use the S001 format")
        if not self.text.strip():
            raise ValueError("statement text cannot be empty")
        if not self.section.strip() or not self.chunk_id.strip():
            raise ValueError("statement source cannot be empty")
        if self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("statement range is invalid")

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "id": self.statement_id,
            "section": self.section,
            "text": self.text,
        }


class RequirementStatementExtractor:
    """Extract stable, source-aware statements without using an LLM."""

    _MARKDOWN_HEADING = re.compile(r"^\s*#{1,6}\s+(?P<title>.+?)\s*$")
    _PLAIN_HEADING = re.compile(
        r"^\s*(?:第[一二三四五六七八九十百\d]+[章节]|"
        r"[一二三四五六七八九十]+、|\d+(?:\.\d+)*[.、])\s*"
        r"(?P<title>.+?)\s*$"
    )
    _LIST_PREFIX = re.compile(
        r"^\s*(?:[-*+]\s+|\d+(?:\.\d+)*[.)、]\s*)"
    )
    _SENTENCE = re.compile(r".+?(?:[。！？；;]|$)")
    _TABLE_SEPARATOR = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")

    def extract(
        self,
        chunks: tuple[RequirementChunk, ...],
    ) -> tuple[RequirementStatement, ...]:
        if not chunks:
            raise ValueError("requirement chunks cannot be empty")

        drafts: list[tuple[str, str, str, int, int]] = []
        for chunk in chunks:
            drafts.extend(self._extract_chunk(chunk))

        return tuple(
            RequirementStatement(
                statement_id=f"S{index:03d}",
                text=text,
                section=section,
                chunk_id=chunk_id,
                start_char=start,
                end_char=end,
            )
            for index, (text, section, chunk_id, start, end) in enumerate(
                drafts,
                start=1,
            )
        )

    def _extract_chunk(
        self,
        chunk: RequirementChunk,
    ) -> list[tuple[str, str, str, int, int]]:
        current_section = chunk.title
        statements: list[tuple[str, str, str, int, int]] = []
        offset = 0
        for raw_line in chunk.content.splitlines(keepends=True):
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()
            line_start = chunk.start_char + offset
            offset += len(raw_line)
            if not stripped or stripped.startswith("```"):
                continue

            heading = self._heading_title(stripped)
            if heading is not None:
                current_section = heading
                continue
            if self._TABLE_SEPARATOR.fullmatch(stripped):
                continue

            prefix = self._LIST_PREFIX.match(line)
            content_start = prefix.end() if prefix else len(line) - len(line.lstrip())
            content = line[content_start:].strip()
            if not content:
                continue
            is_table_row = content.startswith("|") and content.endswith("|")
            if is_table_row:
                content = "；".join(
                    cell.strip()
                    for cell in content.strip("|").split("|")
                    if cell.strip()
                )

            matches = (
                [(content, 0, len(content))]
                if is_table_row
                else [
                    (match.group(0), match.start(), match.end())
                    for match in self._SENTENCE.finditer(content)
                ]
            )
            search_from = 0
            for raw_statement, match_start, match_end in matches:
                statement = raw_statement.strip()
                if not statement:
                    continue
                relative = line.find(statement, content_start + search_from)
                if relative < 0:
                    relative = content_start + match_start
                start = line_start + relative
                end = start + len(statement)
                statements.append(
                    (
                        statement,
                        current_section,
                        chunk.chunk_id,
                        start,
                        end,
                    )
                )
                search_from = match_end
        return statements

    @classmethod
    def _heading_title(cls, line: str) -> str | None:
        markdown = cls._MARKDOWN_HEADING.fullmatch(line)
        if markdown:
            return markdown.group("title").strip()
        plain = cls._PLAIN_HEADING.fullmatch(line)
        if (
            plain
            and len(line) <= 60
            and not line.endswith(("。", "！", "？", ";", "；"))
        ):
            return plain.group("title").strip()
        return None
