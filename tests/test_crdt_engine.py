"""PycrdtEngine.replace_blocks — the reconciliation behind snapshot restore.

Design D-2: reconcile by block id. Clearing and re-appending would churn every
block id (orphaning comments, which anchor to block ids) and would clobber a
concurrent peer's insert.
"""

from __future__ import annotations

from cyberarche.adapters.outbound.crdt.pycrdt_engine import PycrdtEngine


def block(block_id: str, text: str = "", block_type: str = "paragraph") -> dict:
    return {"id": block_id, "type": block_type, "data": {"text": text}}


def state_with(*blocks: dict) -> bytes:
    engine = PycrdtEngine()
    return engine.append_blocks(b"", list(blocks))


def read(state: bytes) -> list[dict]:
    return PycrdtEngine().read_blocks(state)


def apply(state: bytes, update: bytes) -> bytes:
    return PycrdtEngine().merge([state, update])


def test_replace_inserts_deletes_and_merges():
    engine = PycrdtEngine()
    state = state_with(block("b1", "one"), block("b2", "two"))

    # Snapshot had b1 (different text) and b3; b2 is gone.
    update = engine.replace_blocks(state, [block("b1", "restored"), block("b3", "three")])
    result = read(apply(state, update))

    assert [b["id"] for b in result] == ["b1", "b3"]
    assert result[0]["data"]["text"] == "restored"
    assert result[1]["data"]["text"] == "three"


def test_surviving_blocks_keep_their_identity_and_extra_data():
    engine = PycrdtEngine()
    # A block carrying data the snapshot's materialized JSON does not mention.
    rich = {"id": "b1", "type": "paragraph", "data": {"text": "hi", "scene": {"x": 1}}}
    state = state_with(rich)

    update = engine.replace_blocks(state, [block("b1", "restored")])
    result = read(apply(state, update))

    assert result[0]["id"] == "b1"  # same id -> comments stay anchored
    assert result[0]["data"]["text"] == "restored"
    assert result[0]["data"]["scene"] == {"x": 1}  # merged, not dropped


def test_replace_reorders_to_match_the_snapshot():
    engine = PycrdtEngine()
    state = state_with(block("b1"), block("b2"), block("b3"))

    update = engine.replace_blocks(state, [block("b3"), block("b1"), block("b2")])
    result = read(apply(state, update))

    assert [b["id"] for b in result] == ["b3", "b1", "b2"]


def test_type_change_replaces_wholesale_rather_than_merging():
    engine = PycrdtEngine()
    state = state_with({"id": "b1", "type": "table", "data": {"rows": [[1]]}})

    update = engine.replace_blocks(state, [block("b1", "now a paragraph")])
    result = read(apply(state, update))

    assert result[0]["type"] == "paragraph"
    assert "rows" not in result[0]["data"]  # table data must not survive


def test_replacing_with_identical_blocks_is_an_empty_update():
    # Design D-5: restoring twice must not pollute the update log.
    engine = PycrdtEngine()
    blocks = [block("b1", "one"), block("b2", "two")]
    state = state_with(*blocks)

    update = engine.replace_blocks(state, blocks)

    assert engine.is_empty(update)
    assert read(apply(state, update)) == read(state)


def test_is_empty_distinguishes_a_real_update():
    engine = PycrdtEngine()
    state = state_with(block("b1", "one"))
    assert not engine.is_empty(engine.replace_blocks(state, [block("b1", "two")]))
    assert not engine.is_empty(engine.replace_blocks(state, []))


def test_replace_onto_an_empty_document():
    engine = PycrdtEngine()
    update = engine.replace_blocks(b"", [block("b1", "hello")])
    assert [b["id"] for b in read(apply(b"", update))] == ["b1"]


def test_replace_to_empty_clears_the_body():
    engine = PycrdtEngine()
    state = state_with(block("b1"), block("b2"))
    update = engine.replace_blocks(state, [])
    assert read(apply(state, update)) == []


def test_no_op_replace_is_empty_even_when_the_document_has_tombstones():
    """Yjs re-emits the whole delete set in `get_update(sv)`, so a document that
    has ever deleted a block yields a non-empty blob even when replace_blocks
    changed nothing. Comparing bytes alone would append empty updates to the
    log on every repeated restore.
    """
    engine = PycrdtEngine()
    state = state_with(block("b1", "one"), block("b2", "two"))
    state = apply(state, engine.delete_block(state, "b2"))  # leaves a tombstone

    update = engine.replace_blocks(state, [block("b1", "one")])

    assert engine.is_empty(update)
    assert [b["id"] for b in read(apply(state, update))] == ["b1"]


def test_blocks_without_an_id_are_inserted_not_matched():
    # The snapshot endpoint accepts free-form content; an id-less block has no
    # identity, so it must be inserted rather than crash the reconciliation.
    engine = PycrdtEngine()
    state = state_with(block("b1", "one"))
    update = engine.replace_blocks(state, [{"type": "paragraph", "data": {"text": "x"}}])
    result = read(apply(state, update))
    assert [b.get("id") for b in result] == [None]
