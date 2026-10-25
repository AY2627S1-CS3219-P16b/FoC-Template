"""Turn authored Markdown into stable question/answer chunks, without comments."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import EMBEDDING_PROFILE


@dataclass(frozen=True)
class Chunk:
    id: str
    source_file: str
    title: str
    question: str
    answer: str

    @property
    def text(self):
        return f"{self.title}\n{self.question}\n{self.answer}"


@dataclass(frozen=True)
class Corpus:
    chunks: list[Chunk]
    version: str


def strip_comments(markdown: str) -> str:
    cleaned = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    if "<!--" in cleaned or "-->" in cleaned:
        raise ValueError("Unclosed or unmatched HTML comment in FAQ documentation.")
    return cleaned


def load_corpus(directory: Path) -> Corpus:
    chunks = []
    ids = set()
    for path in sorted(directory.glob("*.md")):
        # The README contains authoring instructions, not student support facts.
        if path.name.lower() == "readme.md":
            continue
        markdown = strip_comments(path.read_text(encoding="utf-8"))
        title_match = re.search(r"^# (.+)$", markdown, flags=re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        sections = re.split(r"^## (.+)\s*$", markdown, flags=re.MULTILINE)
        for question, answer in zip(sections[1::2], sections[2::2]):
            question, answer = question.strip(), answer.strip()
            if not answer:
                continue
            identity = f"{path.name}\n{question}"
            chunk_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
            if chunk_id in ids:
                raise ValueError(f"Duplicate FAQ question in {path.name}: {question}")
            ids.add(chunk_id)
            chunks.append(Chunk(chunk_id, path.name, title, question, answer))
    if not chunks:
        raise ValueError("No non-empty FAQ question/answer sections were found.")
    snapshot = json.dumps(
        {"profile": EMBEDDING_PROFILE, "chunks": [asdict(chunk) for chunk in chunks]},
        sort_keys=True, ensure_ascii=False,
    )
    return Corpus(chunks, hashlib.sha256(snapshot.encode()).hexdigest())
