"""Full, reloadable knowledge snapshot for generation prompts."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Callable


KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"


@dataclass(frozen=True)
class KnowledgeSnapshot:
    """Exact complete knowledge set used by one generation plan."""

    text: str
    version: str
    documents: tuple[tuple[str, str], ...]


class KnowledgeCache:
    """Caches each knowledge document separately and assembles a full snapshot."""

    def __init__(
        self,
        root: Path = KNOWLEDGE_DIR,
        reader: Callable[[Path], str] | None = None,
    ) -> None:
        self._root = root
        self._reader = reader or (lambda item: item.read_text(encoding="utf-8"))
        self._fingerprint: tuple[tuple[str, int, int], ...] | None = None
        self._documents: dict[str, tuple[tuple[int, int], str]] = {}
        self._snapshot: KnowledgeSnapshot | None = None
        self._lock = Lock()

    def _paths_and_fingerprint(self) -> tuple[tuple[Path, ...], tuple[tuple[str, int, int], ...]]:
        paths = tuple(sorted(path for path in self._root.rglob("*.md") if path.is_file()))
        fingerprint = tuple(
            (str(path.relative_to(self._root)), path.stat().st_mtime_ns, path.stat().st_size)
            for path in paths
        )
        return paths, fingerprint

    def get(self) -> KnowledgeSnapshot:
        paths, fingerprint = self._paths_and_fingerprint()
        with self._lock:
            if self._snapshot is not None and self._fingerprint == fingerprint:
                return self._snapshot

            next_documents: dict[str, tuple[tuple[int, int], str]] = {}
            for path in paths:
                name = str(path.relative_to(self._root))
                stat = path.stat()
                file_fingerprint = (stat.st_mtime_ns, stat.st_size)
                cached = self._documents.get(name)
                if cached is None or cached[0] != file_fingerprint:
                    cached = (file_fingerprint, self._reader(path).strip())
                next_documents[name] = cached

            documents = tuple(sorted(
                (name, document[1]) for name, document in next_documents.items()
            ))
            text = "\n\n".join(
                f"# Source: {name}\n\n{document}"
                for name, document in documents
            )
            if not text:
                raise ValueError("Knowledge directory must contain at least one Markdown document.")
            self._snapshot = KnowledgeSnapshot(
                text=text,
                version=sha256(text.encode("utf-8")).hexdigest()[:12],
                documents=documents,
            )
            self._documents = next_documents
            self._fingerprint = fingerprint
            return self._snapshot


knowledge_cache = KnowledgeCache()
