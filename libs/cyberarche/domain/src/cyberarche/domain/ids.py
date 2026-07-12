"""Typed identifiers. IDs are opaque strings minted by an IdPort adapter."""

from __future__ import annotations

from typing import NewType

TenantId = NewType("TenantId", str)
UserId = NewType("UserId", str)
WorkspaceId = NewType("WorkspaceId", str)
TeamspaceId = NewType("TeamspaceId", str)
FolderId = NewType("FolderId", str)
DocumentId = NewType("DocumentId", str)
BlockId = NewType("BlockId", str)
SnapshotId = NewType("SnapshotId", str)
ShareLinkId = NewType("ShareLinkId", str)
AgentRunId = NewType("AgentRunId", str)
ConnectorId = NewType("ConnectorId", str)
NotificationId = NewType("NotificationId", str)
TemplateId = NewType("TemplateId", str)
CustomInstructionsId = NewType("CustomInstructionsId", str)
AgentMemoryId = NewType("AgentMemoryId", str)
AgentSkillId = NewType("AgentSkillId", str)
ScheduledAgentTaskId = NewType("ScheduledAgentTaskId", str)
AgentTaskRunId = NewType("AgentTaskRunId", str)
GoogleConnectionId = NewType("GoogleConnectionId", str)
