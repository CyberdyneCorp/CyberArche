"""permissions-sharing spec: invites, overrides, share links, comments."""

from __future__ import annotations

from datetime import timedelta

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.memberships import Role
from cyberarche.domain.sharing import SharePermission
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
