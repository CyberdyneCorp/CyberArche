"""document-import spec: the pure markdown -> block-dict converter.

Covers headings (with levels), the three list kinds, quote, divider, fenced
code (+ mermaid), a GFM table, an image, and prose collapsing into paragraphs.
The block shapes must match the agent parser / file extractor so imported
content renders identically.
"""

from __future__ import annotations

from itertools import count

from cyberarche.domain.markdown_blocks import markdown_to_blocks


def _ids():
    counter = count()
    return lambda: f"b{next(counter)}"


def _convert(text: str) -> list[dict]:
    return markdown_to_blocks(text, _ids())


def _types(blocks: list[dict]) -> list[str]:
    return [b["type"] for b in blocks]


def test_ids_are_assigned_from_the_callable():
    blocks = _convert("# Title")
    assert blocks[0]["id"] == "b0"


def test_headings_carry_levels_capped_at_six():
    blocks = _convert("# One\n\n## Two\n\n###### Six")
    assert _types(blocks) == ["heading", "heading", "heading"]
    assert [b["data"]["level"] for b in blocks] == [1, 2, 6]
    assert blocks[0]["data"]["text"] == "One"


def test_bulleted_list_one_block_per_item():
    blocks = _convert("- apple\n* banana\n+ cherry")
    assert _types(blocks) == ["bulleted_list"] * 3
    assert [b["data"]["text"] for b in blocks] == ["apple", "banana", "cherry"]


def test_numbered_list_items():
    blocks = _convert("1. first\n2. second\n3) third")
    assert _types(blocks) == ["numbered_list"] * 3
    assert blocks[0]["data"]["text"] == "first"


def test_todo_items_track_checked_state():
    blocks = _convert("- [ ] todo\n- [x] done")
    assert _types(blocks) == ["todo", "todo"]
    assert blocks[0]["data"] == {"text": "todo", "checked": False}
    assert blocks[1]["data"] == {"text": "done", "checked": True}


def test_blockquote_joins_consecutive_lines():
    blocks = _convert("> line one\n> line two")
    assert _types(blocks) == ["quote"]
    assert blocks[0]["data"]["text"] == "line one\nline two"


def test_horizontal_rules_become_dividers():
    blocks = _convert("---\n\n***\n\n___")
    assert _types(blocks) == ["divider", "divider", "divider"]


def test_fenced_code_keeps_language_and_source():
    blocks = _convert("```python\nprint(1)\nprint(2)\n```")
    assert _types(blocks) == ["code"]
    assert blocks[0]["data"] == {"source": "print(1)\nprint(2)", "language": "python"}


def test_fenced_code_without_language_defaults_to_text():
    blocks = _convert("```\nplain\n```")
    assert blocks[0]["data"]["language"] == "text"


def test_fenced_mermaid_becomes_a_mermaid_block():
    blocks = _convert("```mermaid\ngraph TD; A-->B;\n```")
    assert _types(blocks) == ["mermaid"]
    assert blocks[0]["data"] == {"source": "graph TD; A-->B;"}


def test_unclosed_fence_still_produces_a_block():
    blocks = _convert("```py\nx = 1")
    assert _types(blocks) == ["code"]
    assert blocks[0]["data"]["source"] == "x = 1"


def test_gfm_table_becomes_a_table_block():
    text = "| Name | Age |\n| --- | --- |\n| Alice | 30 |\n| Bob | 25 |"
    blocks = _convert(text)
    assert _types(blocks) == ["table"]
    data = blocks[0]["data"]
    assert data["header"] == ["Name", "Age"]
    assert data["rows"] == [["Alice", "30"], ["Bob", "25"]]
    assert data["source"] == "markdown"


def test_table_with_alignment_separator_and_no_outer_pipes():
    text = "a | b\n:-- | --:\n1 | 2"
    blocks = _convert(text)
    assert _types(blocks) == ["table"]
    assert blocks[0]["data"]["header"] == ["a", "b"]
    assert blocks[0]["data"]["rows"] == [["1", "2"]]


def test_image_on_its_own_line_becomes_an_image_block():
    blocks = _convert("![a cat](https://example.com/cat.png)")
    assert _types(blocks) == ["image"]
    assert blocks[0]["data"] == {"url": "https://example.com/cat.png", "alt": "a cat"}


def test_prose_lines_collapse_into_paragraphs():
    text = "First line\nsame paragraph\n\nSecond paragraph"
    blocks = _convert(text)
    assert _types(blocks) == ["paragraph", "paragraph"]
    assert blocks[0]["data"]["text"] == "First line\nsame paragraph"
    assert blocks[1]["data"]["text"] == "Second paragraph"


def test_mixed_document_maps_each_construct():
    text = (
        "# Title\n\n"
        "Intro prose.\n\n"
        "- one\n- two\n\n"
        "> a quote\n\n"
        "```js\nconst x = 1;\n```\n\n"
        "Closing words."
    )
    blocks = _convert(text)
    assert _types(blocks) == [
        "heading",
        "paragraph",
        "bulleted_list",
        "bulleted_list",
        "quote",
        "code",
        "paragraph",
    ]


def test_empty_input_yields_no_blocks():
    assert _convert("") == []
    assert _convert("\n\n   \n") == []
