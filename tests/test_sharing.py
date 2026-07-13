"""permissions-sharing spec: invites, overrides, share links, comments."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from cyberarche.adapters.outbound.postgres.sharing import (
    PostgresCommentRepository,
    PostgresShareLinkRepository,
)
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthorized, NotFound
from cyberarche.domain.ids import DocumentId, ShareLinkId, UserId
from cyberarche.domain.memberships import Role
from cyberarche.domain.sharing import Comment, ShareLink, SharePermission
from tests.conftest import caller

BOB = caller("bob", "acme")
CAROL = caller("carol", "acme")
OUTSIDER = caller("dave", "globex")


async def setup(use_cases: UseCases, alice):
    # A shared (teamspace) document, so workspace-role inheritance applies —
    # teamspace-less documents are now private to their creator.
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Shared Doc", teamspace_id=teamspace.id
    )
    return workspace, document


BLOCK = {"id": "b1", "type": "paragraph", "data": {"text": "x"}}


async def test_invited_commenter_can_comment_but_not_edit(use_cases, alice):
    workspace, document = await setup(use_cases, alice)

    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.COMMENTER
    )

    comment = await use_cases.sharing.add_comment(
        BOB, document.id, block_id="b1", body="looks good"
    )
    assert comment.author_id == BOB.user_id
    with pytest.raises(NotAuthorized):
        await use_cases.agent.apply_blocks(BOB, document.id, [BLOCK])


async def test_document_grant_overrides_inherited_workspace_role(use_cases, alice):
    workspace, document = await setup(use_cases, alice)
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )
    # Editor everywhere in the teamspace...
    other = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Other", teamspace_id=document.teamspace_id
    )
    await use_cases.agent.apply_blocks(BOB, other.id, [BLOCK])

    # ...but demoted to viewer on this specific document.
    await use_cases.sharing.grant_on_document(
        alice, document.id, user_id=BOB.user_id, role=Role.VIEWER
    )
    with pytest.raises(NotAuthorized):
        await use_cases.agent.apply_blocks(BOB, document.id, [BLOCK])


async def test_only_owner_can_invite(use_cases, alice):
    workspace, _ = await setup(use_cases, alice)
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )
    with pytest.raises(NotAuthorized):  # editors cannot invite
        await use_cases.sharing.invite_to_workspace(
            BOB, workspace.id, user_id=CAROL.user_id, role=Role.VIEWER
        )


async def test_view_share_link_grants_read_only_access(use_cases, alice):
    _, document = await setup(use_cases, alice)
    link = await use_cases.sharing.create_share_link(
        alice, document.id, permission=SharePermission.VIEW
    )

    opened = await use_cases.sharing.open_share_link(OUTSIDER, link.id)

    assert opened.id == document.id
    comments = await use_cases.sharing.list_comments(OUTSIDER, document.id)
    assert comments == []  # read access works
    with pytest.raises(NotAuthorized):  # but not comment/edit
        await use_cases.sharing.add_comment(
            OUTSIDER, document.id, block_id="b1", body="hi"
        )


async def test_edit_share_link_grants_edit(use_cases, alice):
    _, document = await setup(use_cases, alice)
    link = await use_cases.sharing.create_share_link(
        alice, document.id, permission=SharePermission.EDIT
    )
    await use_cases.sharing.open_share_link(BOB, link.id)
    await use_cases.agent.apply_blocks(BOB, document.id, [BLOCK])  # allowed


async def test_redeeming_link_to_trashed_doc_creates_no_grant(use_cases, alice):
    """F-009: redeeming a usable link whose document was trashed must not leave
    a lingering grant that resurfaces if the document is restored."""
    _, document = await setup(use_cases, alice)
    link = await use_cases.sharing.create_share_link(
        alice, document.id, permission=SharePermission.VIEW
    )
    await use_cases.documents.trash(alice, document.id)

    with pytest.raises(NotFound):
        await use_cases.sharing.open_share_link(OUTSIDER, link.id)

    # No grant was written: the outsider sees nothing shared, even after restore.
    await use_cases.documents.restore(alice, document.id)
    assert await use_cases.sharing.list_shared_with_me(OUTSIDER) == []


async def test_revoked_link_is_denied(use_cases, alice):
    _, document = await setup(use_cases, alice)
    link = await use_cases.sharing.create_share_link(
        alice, document.id, permission=SharePermission.VIEW
    )
    await use_cases.sharing.revoke_share_link(alice, document.id, link.id)

    with pytest.raises(NotAuthorized):
        await use_cases.sharing.open_share_link(OUTSIDER, link.id)


async def test_expired_link_is_denied(use_cases, clock, alice):
    _, document = await setup(use_cases, alice)
    link = await use_cases.sharing.create_share_link(
        alice,
        document.id,
        permission=SharePermission.VIEW,
        expires_at=clock.now() + timedelta(hours=1),
    )
    clock.tick(seconds=2 * 3600)
    with pytest.raises(NotAuthorized):
        await use_cases.sharing.open_share_link(OUTSIDER, link.id)


async def test_comment_visible_to_other_participants_and_resolvable(use_cases, alice):
    workspace, document = await setup(use_cases, alice)
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.COMMENTER
    )

    comment = await use_cases.sharing.add_comment(
        BOB, document.id, block_id="b1", body="typo here"
    )
    seen_by_alice = await use_cases.sharing.list_comments(alice, document.id)
    assert [c.id for c in seen_by_alice] == [comment.id]

    resolved = await use_cases.sharing.resolve_comment(alice, document.id, comment.id)
    assert resolved.resolved_at is not None
    assert resolved.resolved_by == alice.user_id


async def test_commenter_cannot_resolve_others_comments(use_cases, alice):
    workspace, document = await setup(use_cases, alice)
    for user in (BOB, CAROL):
        await use_cases.sharing.invite_to_workspace(
            alice, workspace.id, user_id=user.user_id, role=Role.COMMENTER
        )
    comment = await use_cases.sharing.add_comment(
        BOB, document.id, block_id="b1", body="mine"
    )
    with pytest.raises(NotAuthorized):  # carol is neither author nor editor
        await use_cases.sharing.resolve_comment(CAROL, document.id, comment.id)
    # The author may resolve their own.
    await use_cases.sharing.resolve_comment(BOB, document.id, comment.id)


def test_share_flow_over_http(api):
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    workspace = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=auth("alice-token")
    ).json()
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Doc"},
        headers=auth("alice-token"),
    ).json()

    link = api.post(
        f"/api/v1/documents/{document['id']}/share-links",
        json={"permission": "view"},
        headers=auth("alice-token"),
    ).json()

    # Mallory (another tenant) opens the link and gains view access.
    opened = api.post(
        f"/api/v1/share-links/{link['id']}/open", headers=auth("mallory-token")
    )
    assert opened.status_code == 200
    assert opened.json()["document_id"] == document["id"]

    # Revoke, then subsequent opens are denied.
    revoked = api.delete(
        f"/api/v1/documents/{document['id']}/share-links/{link['id']}",
        headers=auth("alice-token"),
    ).json()
    assert revoked["revoked"] is True
    denied = api.post(
        f"/api/v1/share-links/{link['id']}/open", headers=auth("mallory-token")
    )
    assert denied.status_code == 403


def test_invite_and_document_grant_over_http(api):
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    workspace = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=auth("alice-token")
    ).json()
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Doc"},
        headers=auth("alice-token"),
    ).json()

    invited = api.post(
        f"/api/v1/workspaces/{workspace['id']}/invites",
        json={"user_id": "bob", "role": "editor"},
        headers=auth("alice-token"),
    )
    assert invited.status_code == 201
    assert invited.json()["user_id"] == "bob"
    assert invited.json()["role"] == "editor"
    assert invited.json()["granted_at"]

    granted = api.post(
        f"/api/v1/documents/{document['id']}/grants",
        json={"user_id": "mallory", "role": "viewer"},
        headers=auth("alice-token"),
    )
    assert granted.status_code == 201
    assert granted.json()["user_id"] == "mallory"
    assert granted.json()["role"] == "viewer"

    # The grant is what makes the document reachable -> it shows under /shared.
    shared = api.get("/api/v1/shared", headers=auth("mallory-token"))
    assert [d["id"] for d in shared.json()] == [document["id"]]
    # The owner reaches it by role, not by grant -> not "shared with" her.
    assert api.get("/api/v1/shared", headers=auth("alice-token")).json() == []


def test_invite_and_grant_error_mapping_over_http(api):
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    workspace = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=auth("alice-token")
    ).json()

    # A non-member cannot invite -> 403.
    denied = api.post(
        f"/api/v1/workspaces/{workspace['id']}/invites",
        json={"user_id": "carol", "role": "viewer"},
        headers=auth("mallory-token"),
    )
    assert denied.status_code == 403

    # A grant on an unknown document -> 404.
    missing = api.post(
        "/api/v1/documents/no-such-doc/grants",
        json={"user_id": "bob", "role": "viewer"},
        headers=auth("alice-token"),
    )
    assert missing.status_code == 404

    # An unknown role never reaches the use case -> 422 from validation.
    bad_role = api.post(
        f"/api/v1/workspaces/{workspace['id']}/invites",
        json={"user_id": "bob", "role": "sudo"},
        headers=auth("alice-token"),
    )
    assert bad_role.status_code == 422


def test_share_link_listing_and_errors_over_http(api):
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    workspace = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=auth("alice-token")
    ).json()
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Doc"},
        headers=auth("alice-token"),
    ).json()

    api.post(
        f"/api/v1/documents/{document['id']}/share-links",
        json={"permission": "view"},
        headers=auth("alice-token"),
    )
    expiring = api.post(
        f"/api/v1/documents/{document['id']}/share-links",
        json={"permission": "edit", "expires_at": "2999-01-01T00:00:00Z"},
        headers=auth("alice-token"),
    )
    assert expiring.status_code == 201
    assert expiring.json()["expires_at"] is not None

    listed = api.get(
        f"/api/v1/documents/{document['id']}/share-links", headers=auth("alice-token")
    )
    assert listed.status_code == 200
    links = listed.json()
    assert {link["permission"] for link in links} == {"view", "edit"}
    assert all(link["document_id"] == document["id"] for link in links)
    assert all(link["revoked"] is False for link in links)

    # Cross-tenant: the document does not exist for mallory -> 404, not 403.
    foreign = api.get(
        f"/api/v1/documents/{document['id']}/share-links", headers=auth("mallory-token")
    )
    assert foreign.status_code == 404

    # Revoking an unknown link -> 404; opening one -> 403 (invalid link).
    assert (
        api.delete(
            f"/api/v1/documents/{document['id']}/share-links/no-such-link",
            headers=auth("alice-token"),
        ).status_code
        == 404
    )
    assert (
        api.post("/api/v1/share-links/no-such-link/open", headers=auth("mallory-token"))
        .status_code
        == 403
    )


def test_comment_flow_over_http(api):
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    workspace = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=auth("alice-token")
    ).json()
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Doc"},
        headers=auth("alice-token"),
    ).json()

    created = api.post(
        f"/api/v1/documents/{document['id']}/comments",
        json={"block_id": "b1", "body": "typo here"},
        headers=auth("alice-token"),
    )
    assert created.status_code == 201
    comment = created.json()
    assert comment["block_id"] == "b1"
    assert comment["author_id"] == "alice"
    assert comment["body"] == "typo here"
    assert comment["resolved"] is False

    listed = api.get(
        f"/api/v1/documents/{document['id']}/comments", headers=auth("alice-token")
    )
    assert [c["id"] for c in listed.json()] == [comment["id"]]

    resolved = api.post(
        f"/api/v1/documents/{document['id']}/comments/{comment['id']}/resolve",
        headers=auth("alice-token"),
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved"] is True

    missing = api.post(
        f"/api/v1/documents/{document['id']}/comments/no-such-comment/resolve",
        headers=auth("alice-token"),
    )
    assert missing.status_code == 404


def test_view_link_visitor_can_read_but_not_comment_over_http(api):
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    workspace = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=auth("alice-token")
    ).json()
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Doc"},
        headers=auth("alice-token"),
    ).json()
    link = api.post(
        f"/api/v1/documents/{document['id']}/share-links",
        json={"permission": "view"},
        headers=auth("alice-token"),
    ).json()

    opened = api.post(
        f"/api/v1/share-links/{link['id']}/open", headers=auth("mallory-token")
    )
    assert opened.status_code == 200
    assert opened.json() == {"document_id": document["id"], "title": "Doc"}

    # View access reads the comment thread, but cannot add to it.
    listed = api.get(
        f"/api/v1/documents/{document['id']}/comments", headers=auth("mallory-token")
    )
    assert listed.status_code == 200
    assert listed.json() == []
    denied = api.post(
        f"/api/v1/documents/{document['id']}/comments",
        json={"block_id": "b1", "body": "hi"},
        headers=auth("mallory-token"),
    )
    assert denied.status_code == 403


# ---- shared-with-me listing (permissions-sharing spec) ----------------------


async def test_shared_with_me_lists_documents_reachable_only_by_grant(use_cases, alice):
    _, document = await setup(use_cases, alice)
    # Dave is in another tenant entirely — no workspace role at all.
    assert await use_cases.sharing.list_shared_with_me(OUTSIDER) == []

    await use_cases.sharing.grant_on_document(
        alice, document.id, user_id=OUTSIDER.user_id, role=Role.VIEWER
    )

    shared = await use_cases.sharing.list_shared_with_me(OUTSIDER)
    assert [d.id for d in shared] == [document.id]


async def test_shared_with_me_excludes_documents_reachable_by_workspace_role(
    use_cases, alice
):
    workspace, document = await setup(use_cases, alice)
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )
    # Even with an explicit grant, Bob inherits access -> not "shared with" him.
    await use_cases.sharing.grant_on_document(
        alice, document.id, user_id=BOB.user_id, role=Role.VIEWER
    )

    assert await use_cases.sharing.list_shared_with_me(BOB) == []


async def test_shared_with_me_excludes_trashed_documents(use_cases, alice):
    _, document = await setup(use_cases, alice)
    await use_cases.sharing.grant_on_document(
        alice, document.id, user_id=OUTSIDER.user_id, role=Role.VIEWER
    )
    assert len(await use_cases.sharing.list_shared_with_me(OUTSIDER)) == 1

    await use_cases.documents.trash(alice, document.id)

    assert await use_cases.sharing.list_shared_with_me(OUTSIDER) == []


async def test_shared_with_me_is_scoped_to_the_calling_user(use_cases, alice):
    _, document = await setup(use_cases, alice)
    await use_cases.sharing.grant_on_document(
        alice, document.id, user_id=OUTSIDER.user_id, role=Role.VIEWER
    )

    # Carol was granted nothing; Dave's grant must not leak to her.
    assert await use_cases.sharing.list_shared_with_me(CAROL) == []


# ---- private documents (add-folders-and-private) ----------------------------


async def test_teamspaceless_document_is_private_to_its_creator(use_cases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    private = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="My private notes"
    )
    # Bob is an editor of the whole workspace...
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )

    # ...but a workspace role does not reach a private (teamspace-less) doc.
    with pytest.raises(NotAuthorized):
        await use_cases.agent.apply_blocks(BOB, private.id, [BLOCK])
    # The creator has full access.
    await use_cases.agent.apply_blocks(alice, private.id, [BLOCK])


async def test_grant_reaches_a_private_document(use_cases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    private = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Private"
    )
    await use_cases.sharing.grant_on_document(
        alice, private.id, user_id=BOB.user_id, role=Role.VIEWER
    )

    # The grant reaches the private doc: Bob can read it...
    assert await use_cases.sharing.list_comments(BOB, private.id) == []
    # ...but a viewer grant is read-only.
    with pytest.raises(NotAuthorized):
        await use_cases.agent.apply_blocks(BOB, private.id, [BLOCK])


async def test_comment_mention_notifies_workspace_member(use_cases: UseCases, alice):
    workspace, document = await setup(use_cases, alice)
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )
    # Alice mentions Bob (a member) and Dave (an outsider) in one comment.
    await use_cases.sharing.add_comment(
        alice,
        document.id,
        block_id="b1",
        body=f"hey @[{BOB.user_id}] and @[{OUTSIDER.user_id}] look at this",
    )
    # Bob is notified; the outsider (not a workspace member) is not.
    bob_inbox = await use_cases.notifications.list(BOB)
    assert len(bob_inbox) == 1
    assert bob_inbox[0].kind == "mention"
    assert bob_inbox[0].actor_id == alice.user_id
    assert bob_inbox[0].document_id == document.id
    assert await use_cases.notifications.unread_count(BOB) == 1
    assert await use_cases.notifications.list(OUTSIDER) == []


async def test_self_mention_creates_no_notification(use_cases: UseCases, alice):
    _, document = await setup(use_cases, alice)
    await use_cases.sharing.add_comment(
        alice, document.id, block_id="b1", body=f"note to self @[{alice.user_id}]"
    )
    assert await use_cases.notifications.list(alice) == []


async def test_marking_a_notification_read_clears_unread(use_cases: UseCases, alice):
    workspace, document = await setup(use_cases, alice)
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )
    await use_cases.sharing.add_comment(
        alice, document.id, block_id="b1", body=f"@[{BOB.user_id}] hi"
    )
    inbox = await use_cases.notifications.list(BOB)
    await use_cases.notifications.mark_read(BOB, inbox[0].id)
    assert await use_cases.notifications.unread_count(BOB) == 0
    # A different user cannot mark Bob's notification (it isn't theirs) — no-op.
    await use_cases.notifications.mark_all_read(CAROL)
    assert (await use_cases.notifications.list(BOB))[0].read is True


# ---- Postgres adapters (stubbed pool) ----------------------------------------


class FakePool:
    """Records queries/args; returns pre-programmed rows (dicts stand in for
    asyncpg.Record, which is only read via ``row[key]``)."""

    def __init__(self, *, row=None, rows=()):
        self.row = row
        self.rows = list(rows)
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query, *args):
        self.calls.append((query, args))

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self.row

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return list(self.rows)


PG_NOW = datetime(2026, 7, 12, 9, 0, tzinfo=UTC)


def pg_link(**overrides) -> ShareLink:
    fields = dict(
        id=ShareLinkId("link-1"),
        document_id=DocumentId("doc-1"),
        permission=SharePermission.VIEW,
        created_by=UserId("alice"),
        created_at=PG_NOW,
        expires_at=None,
        revoked_at=None,
    )
    fields.update(overrides)
    return ShareLink(**fields)


def pg_comment(**overrides) -> Comment:
    fields = dict(
        id="c-1",
        document_id=DocumentId("doc-1"),
        block_id="b1",
        author_id=UserId("bob"),
        body="looks good",
        created_at=PG_NOW,
        resolved_at=None,
        resolved_by=None,
    )
    fields.update(overrides)
    return Comment(**fields)


async def test_pg_share_link_add_binds_permission_value():
    pool = FakePool()
    link = pg_link(permission=SharePermission.COMMENT, expires_at=PG_NOW)
    await PostgresShareLinkRepository(pool).add(link)
    _, args = pool.calls[0]
    assert args == (
        link.id, link.document_id, "comment", link.created_by,
        link.created_at, link.expires_at, link.revoked_at,
    )


async def test_pg_share_link_get_round_trips_row():
    link = pg_link(
        permission=SharePermission.EDIT,
        expires_at=PG_NOW + timedelta(days=7),
        revoked_at=PG_NOW,
    )
    row = dataclasses.asdict(link) | {"permission": "edit"}
    pool = FakePool(row=row)
    repo = PostgresShareLinkRepository(pool)
    assert await repo.get(link.id) == link
    _, args = pool.calls[0]
    assert args == (link.id,)


async def test_pg_share_link_get_returns_none_when_missing():
    repo = PostgresShareLinkRepository(FakePool(row=None))
    assert await repo.get(ShareLinkId("nope")) is None


async def test_pg_share_link_list_for_document_maps_rows():
    a = pg_link()
    b = pg_link(id=ShareLinkId("link-2"), permission=SharePermission.COMMENT)
    pool = FakePool(rows=[dataclasses.asdict(a), dataclasses.asdict(b)])
    repo = PostgresShareLinkRepository(pool)
    assert await repo.list_for_document(a.document_id) == [a, b]
    _, args = pool.calls[0]
    assert args == (a.document_id,)


async def test_pg_share_link_update_binds_expiry_and_revocation():
    pool = FakePool()
    link = pg_link(expires_at=PG_NOW + timedelta(days=1), revoked_at=PG_NOW)
    await PostgresShareLinkRepository(pool).update(link)
    _, args = pool.calls[0]
    assert args == (link.id, link.expires_at, link.revoked_at)


async def test_pg_comment_add_binds_every_column_in_order():
    pool = FakePool()
    comment = pg_comment(resolved_at=PG_NOW, resolved_by=UserId("alice"))
    await PostgresCommentRepository(pool).add(comment)
    _, args = pool.calls[0]
    assert args == (
        comment.id, comment.document_id, comment.block_id, comment.author_id,
        comment.body, comment.created_at, comment.resolved_at, comment.resolved_by,
    )


async def test_pg_comment_get_round_trips_resolved_row():
    comment = pg_comment(resolved_at=PG_NOW, resolved_by=UserId("alice"))
    pool = FakePool(row=dataclasses.asdict(comment))
    repo = PostgresCommentRepository(pool)
    assert await repo.get(comment.document_id, comment.id) == comment
    _, args = pool.calls[0]
    assert args == (comment.id, comment.document_id)


async def test_pg_comment_row_with_null_resolver_maps_to_none():
    comment = pg_comment()
    pool = FakePool(row=dataclasses.asdict(comment))
    loaded = await PostgresCommentRepository(pool).get(comment.document_id, comment.id)
    assert loaded == comment
    assert loaded.resolved_by is None and loaded.resolved_at is None


async def test_pg_comment_get_returns_none_when_missing():
    repo = PostgresCommentRepository(FakePool(row=None))
    assert await repo.get(DocumentId("doc-1"), "nope") is None


async def test_pg_comment_list_for_document_maps_rows():
    a, b = pg_comment(), pg_comment(id="c-2", body="second")
    pool = FakePool(rows=[dataclasses.asdict(a), dataclasses.asdict(b)])
    repo = PostgresCommentRepository(pool)
    assert await repo.list_for_document(a.document_id) == [a, b]
    _, args = pool.calls[0]
    assert args == (a.document_id,)


async def test_pg_comment_update_binds_resolution_fields():
    pool = FakePool()
    comment = pg_comment().resolve(by=UserId("alice"), now=PG_NOW)
    await PostgresCommentRepository(pool).update(comment)
    _, args = pool.calls[0]
    assert args == (comment.id, comment.resolved_at, comment.resolved_by)
