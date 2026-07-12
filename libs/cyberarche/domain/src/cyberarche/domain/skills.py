"""Agent skills (ai-agent spec): a named, reusable agent instruction template.

A skill's `instruction` may contain single-brace `{variable}` placeholders.
`instantiate` expands the declared variables into a concrete instruction string
run through the normal agent tool-loop — a skill only ever yields text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from cyberarche.domain.ids import AgentSkillId, TenantId, UserId, WorkspaceId

_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def parse_variables(instruction: str) -> list[str]:
    """Ordered, de-duplicated `{variable}` names declared in the instruction."""
    seen: dict[str, None] = {}
    for match in _VAR_RE.finditer(instruction):
        seen.setdefault(match.group(1), None)
    return list(seen)


def expand(instruction: str, variables: list[str], values: dict[str, str]) -> str:
    """Replace each declared `{name}` with its supplied value (empty if missing).
    Placeholders that are not declared variables are left verbatim, so literal
    braces survive."""
    declared = set(variables)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in declared:
            return str(values.get(name, ""))
        return match.group(0)

    return _VAR_RE.sub(replace, instruction)


@dataclass(frozen=True, slots=True)
class AgentSkill:
    id: AgentSkillId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    name: str
    instruction: str
    created_by: UserId
    created_at: datetime
    description: str = ""
    variables: list[str] = field(default_factory=list)
