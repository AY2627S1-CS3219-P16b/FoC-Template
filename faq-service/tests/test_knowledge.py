from pathlib import Path

import pytest

from app.knowledge import load_corpus, strip_comments


def test_multiline_review_comments_and_authoring_readme_never_enter_chunks(tmp_path):
    (tmp_path / "README.md").write_text("## Internal instructions\nNever retrieve this.")
    path = tmp_path / "help.md"
    path.write_text("<!-- private header -->\n# Help\n## Can I book ahead?\nNot yet.\n"
                    "<!-- REVIEW: secret future\nimplementation plan -->\n## Unfinished?\n<!-- Pending -->")
    corpus = load_corpus(tmp_path)
    assert len(corpus.chunks) == 1
    assert corpus.chunks[0].answer == "Not yet."
    assert "secret" not in corpus.chunks[0].text
    previous = corpus.version
    path.write_text(path.read_text().replace("secret future", "different future"))
    assert load_corpus(tmp_path).version == previous
    path.write_text(path.read_text().replace("Not yet.", "Yes, now available."))
    assert load_corpus(tmp_path).version != previous
    assert load_corpus(tmp_path).chunks[0].id == corpus.chunks[0].id


@pytest.mark.parametrize("markdown", ["<!-- unclosed", "Unmatched -->"])
def test_malformed_comments_fail_closed(markdown):
    with pytest.raises(ValueError):
        strip_comments(markdown)


def test_duplicate_questions_are_rejected(tmp_path):
    (tmp_path / "help.md").write_text("## Same?\nFirst.\n## Same?\nSecond.")
    with pytest.raises(ValueError, match="Duplicate"):
        load_corpus(tmp_path)


def test_real_knowledge_base_contains_only_student_faqs():
    corpus = load_corpus(Path(__file__).resolve().parents[1] / "docs")
    assert len(corpus.chunks) == 59
    assert len({chunk.source_file for chunk in corpus.chunks}) == 6
    assert all("<!--" not in chunk.text and "REVIEW:" not in chunk.text for chunk in corpus.chunks)
    supplier = next(chunk for chunk in corpus.chunks if "isn't listed" in chunk.question)
    assert "not currently supported" in supplier.answer
