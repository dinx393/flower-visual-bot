"""Episodic memory built from approved cases and recorded review history."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from threading import Lock
from typing import Callable


PROJECT_DIR = Path(__file__).resolve().parents[2]
APPROVED_CASES_DIR = PROJECT_DIR / "tests"
CASE_HISTORY_DIR = PROJECT_DIR / "database" / "case-history"

TOKEN_PATTERN = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
IMAGE_PATH_PATTERN = re.compile(r"`(tests/fixtures/approved/[^`]+\.png)`")
STOP_WORDS = {
    "без",
    "для",
    "или",
    "как",
    "над",
    "под",
    "при",
    "что",
    "это",
    "этот",
    "эта",
    "цена",
    "ценой",
    "руб",
    "создай",
    "сделай",
    "сторис",
}


def _tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in TOKEN_PATTERN.findall(value.casefold())
        if len(token) >= 3 and token not in STOP_WORDS and not token.isdigit()
    )


def _related(left: str, right: str) -> bool:
    """Small language-agnostic fallback for common inflection differences."""
    return left == right or (min(len(left), len(right)) >= 4 and left[:4] == right[:4])


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    kind: str
    source_path: str
    title: str
    text: str
    image_path: str | None
    title_tokens: frozenset[str]
    body_tokens: frozenset[str]


@dataclass(frozen=True)
class CaseMemorySnapshot:
    records: tuple[MemoryRecord, ...]
    version: str


class CaseMemoryCache:
    """Caches every memory record independently and reloads only changed files."""

    def __init__(
        self,
        project_dir: Path = PROJECT_DIR,
        reader: Callable[[Path], str] | None = None,
    ) -> None:
        self._project_dir = project_dir
        self._reader = reader or (lambda item: item.read_text(encoding="utf-8"))
        self._documents: dict[str, tuple[tuple[int, int], str]] = {}
        self._fingerprint: tuple[tuple[str, int, int], ...] | None = None
        self._snapshot: CaseMemorySnapshot | None = None
        self._lock = Lock()

    def _paths_and_fingerprint(self) -> tuple[tuple[Path, ...], tuple[tuple[str, int, int], ...]]:
        paths = tuple(
            sorted(
                (*self._project_dir.glob("tests/approved-case-*.md"),
                 *self._project_dir.glob("database/case-history/*.md"))
            )
        )
        fingerprint = tuple(
            (str(path.relative_to(self._project_dir)), path.stat().st_mtime_ns, path.stat().st_size)
            for path in paths
        )
        return paths, fingerprint

    def _record(self, source_path: str, text: str) -> MemoryRecord:
        first_line = next((line for line in text.splitlines() if line.startswith("# ")), source_path)
        title = first_line.removeprefix("# ").strip()
        image_match = IMAGE_PATH_PATTERN.search(text)
        image_path = image_match.group(1) if image_match else None
        kind = "approved_case" if source_path.startswith("tests/") else "case_history"
        return MemoryRecord(
            record_id=Path(source_path).stem,
            kind=kind,
            source_path=source_path,
            title=title,
            text=text,
            image_path=image_path,
            title_tokens=_tokens(title),
            body_tokens=_tokens(text),
        )

    def get(self) -> CaseMemorySnapshot:
        paths, fingerprint = self._paths_and_fingerprint()
        with self._lock:
            if self._snapshot is not None and self._fingerprint == fingerprint:
                return self._snapshot

            next_documents: dict[str, tuple[tuple[int, int], str]] = {}
            for path in paths:
                source_path = str(path.relative_to(self._project_dir))
                stat = path.stat()
                file_fingerprint = (stat.st_mtime_ns, stat.st_size)
                cached = self._documents.get(source_path)
                if cached is None or cached[0] != file_fingerprint:
                    cached = (file_fingerprint, self._reader(path).strip())
                next_documents[source_path] = cached

            records = tuple(
                self._record(source_path, document[1])
                for source_path, document in sorted(next_documents.items())
                if document[1]
            )
            version_source = "\n".join(
                f"{record.source_path}\n{record.text}" for record in records
            )
            self._snapshot = CaseMemorySnapshot(
                records=records,
                version=sha256(version_source.encode("utf-8")).hexdigest()[:12],
            )
            self._documents = next_documents
            self._fingerprint = fingerprint
            return self._snapshot

    def retrieve(self, query: str, limit: int = 4) -> tuple[MemoryRecord, ...]:
        query_tokens = _tokens(query)
        if not query_tokens or limit <= 0:
            return ()

        def score(record: MemoryRecord) -> int:
            title_matches = sum(
                1 for query_token in query_tokens
                if any(_related(query_token, token) for token in record.title_tokens)
            )
            body_matches = sum(
                1 for query_token in query_tokens
                if any(_related(query_token, token) for token in record.body_tokens)
            )
            return title_matches * 4 + body_matches

        ranked = sorted(
            ((score(record), record) for record in self.get().records),
            key=lambda item: (-item[0], item[1].source_path),
        )
        return tuple(record for value, record in ranked if value > 0)[:limit]

    def existing_image_paths(
        self,
        records: tuple[MemoryRecord, ...],
        limit: int = 3,
    ) -> tuple[str, ...]:
        paths: list[str] = []
        for record in records:
            if (
                record.image_path
                and record.image_path not in paths
                and (self._project_dir / record.image_path).is_file()
            ):
                paths.append(record.image_path)
            if len(paths) == limit:
                break
        return tuple(paths)


case_memory_cache = CaseMemoryCache()
