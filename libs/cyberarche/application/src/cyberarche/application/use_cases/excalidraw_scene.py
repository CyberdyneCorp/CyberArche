"""Build and describe `.excalidraw` scenes (native-excalidraw-canvas spec).

Pure functions: no I/O, no engine dependency. `build_mindmap` emits a v2
`.excalidraw` document the frontend `ExcalidrawBlock` hydrates from `data.scene`;
`describe_scene` turns a scene (agent- or user-authored) into a compact text
summary for the agent's document context.

Every element carries the full base field set because the engine's `restore()`
only backfills the fractional `index` — it does not default missing fields.
"""

from __future__ import annotations

import json
import math
from typing import Any

_FONT_DEFAULT = 5  # Excalifont (engine's DEFAULT_FONT_FAMILY)
_ROUNDED = {"type": 3}  # ADAPTIVE_RADIUS — rounded rectangle corners


def _base(element_id: str, seq: int, **overrides: Any) -> dict[str, Any]:
    """Full `BaseProperties` for one element (parity: engine `defaultBase`)."""
    base = {
        "id": element_id,
        "x": 0.0,
        "y": 0.0,
        "width": 0.0,
        "height": 0.0,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roundness": None,
        "roughness": 1,
        "opacity": 100,
        # Deterministic (no RNG) so the same request yields the same scene.
        "seed": seq + 1,
        "version": 1,
        "versionNonce": seq + 1,
        "index": None,
        "isDeleted": False,
        "groupIds": [],
        "frameId": None,
        "boundElements": None,
        "updated": 0,
        "link": None,
        "locked": False,
    }
    base.update(overrides)
    return base


def _text_width(label: str, font_size: int) -> float:
    return max(len(label), 1) * font_size * 0.55


def _node(
    element_id: str,
    text_id: str,
    seq: int,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    font_size: int,
    fill: str,
    stroke: str,
) -> list[dict[str, Any]]:
    """A rounded rectangle plus a text label centred in it."""
    container = _base(
        element_id,
        seq,
        type="rectangle",
        x=x,
        y=y,
        width=w,
        height=h,
        backgroundColor=fill,
        strokeColor=stroke,
        roundness=_ROUNDED,
        boundElements=[{"id": text_id, "type": "text"}],
    )
    tw = min(_text_width(label, font_size), w - 12)
    th = font_size * 1.25
    text = _base(
        text_id,
        seq,
        type="text",
        x=x + (w - tw) / 2,
        y=y + (h - th) / 2,
        width=tw,
        height=th,
        strokeColor=stroke,
        text=label,
        originalText=label,
        fontSize=font_size,
        fontFamily=_FONT_DEFAULT,
        textAlign="center",
        verticalAlign="middle",
        containerId=element_id,
        autoResize=True,
        lineHeight=1.25,
    )
    return [container, text]


def _center(node: dict[str, Any]) -> tuple[float, float]:
    return node["x"] + node["width"] / 2, node["y"] + node["height"] / 2


def _edge_point(node: dict[str, Any], toward: tuple[float, float]) -> tuple[float, float]:
    """Where the segment from `node`'s centre to `toward` crosses its border."""
    cx, cy = _center(node)
    dx, dy = toward[0] - cx, toward[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy
    hw, hh = node["width"] / 2, node["height"] / 2
    scale = min(
        hw / abs(dx) if dx else math.inf,
        hh / abs(dy) if dy else math.inf,
    )
    return cx + dx * scale, cy + dy * scale


def _arrow(
    element_id: str, seq: int, source: dict[str, Any], target: dict[str, Any]
) -> dict[str, Any]:
    """A bound arrow from `source`'s edge to `target`'s edge."""
    sx, sy = _edge_point(source, _center(target))
    ex, ey = _edge_point(target, _center(source))
    for node, key in ((source, "boundElements"), (target, "boundElements")):
        bound = node.get(key) or []
        node[key] = [*bound, {"id": element_id, "type": "arrow"}]
    return _base(
        element_id,
        seq,
        type="arrow",
        x=sx,
        y=sy,
        width=abs(ex - sx),
        height=abs(ey - sy),
        strokeColor="#495057",
        points=[[0.0, 0.0], [ex - sx, ey - sy]],
        startBinding={"elementId": source["id"], "focus": 0, "gap": 4},
        endBinding={"elementId": target["id"], "focus": 0, "gap": 4},
        startArrowhead=None,
        endArrowhead="arrow",
        elbowed=False,
    )


_PALETTE = ["#e7f5ff", "#fff9db", "#ebfbee", "#fff0f6", "#f3f0ff", "#fff4e6"]
_STROKES = ["#1971c2", "#f08c00", "#2f9e44", "#e64980", "#7048e8", "#e8590c"]


def build_mindmap(central: str, branches: list[Any]) -> dict[str, Any]:
    """A radial mind map: a central node with connected branch nodes. A branch
    may be a string, or ``{"label": str, "children": [str, ...]}`` for one level
    of sub-branches."""
    central = (central or "Topic").strip()
    cx, cy = 520.0, 380.0
    elements: list[dict[str, Any]] = []
    seq = 0

    center = _node(
        "n0",
        "t0",
        seq,
        x=cx - 100,
        y=cy - 34,
        w=200,
        h=68,
        label=central,
        font_size=20,
        fill="#e7f5ff",
        stroke="#1971c2",
    )
    elements.extend(center)
    seq += 1
    center_rect = center[0]

    count = max(len(branches), 1)
    radius = 280.0
    for i, branch in enumerate(branches):
        label = branch["label"] if isinstance(branch, dict) else str(branch)
        children = branch.get("children", []) if isinstance(branch, dict) else []
        angle = -math.pi / 2 + (2 * math.pi * i) / count
        bx = cx + radius * math.cos(angle)
        by = cy + radius * math.sin(angle)
        rect_id, text_id, arrow_id = f"n{seq}", f"t{seq}", f"a{seq}"
        node = _node(
            rect_id,
            text_id,
            seq,
            x=bx - 80,
            y=by - 26,
            w=160,
            h=52,
            label=label.strip() or f"Branch {i + 1}",
            font_size=16,
            fill=_PALETTE[i % len(_PALETTE)],
            stroke=_STROKES[i % len(_STROKES)],
        )
        elements.extend(node)
        elements.append(_arrow(arrow_id, seq, center_rect, node[0]))
        seq += 1

        for j, child in enumerate(children):
            child_label = str(child).strip() or f"Item {j + 1}"
            cxp = bx + (radius * 0.7) * math.cos(angle)
            cyp = by + (radius * 0.7) * math.sin(angle) + (j - (len(children) - 1) / 2) * 60
            crect_id, ctext_id, carrow_id = f"n{seq}", f"t{seq}", f"a{seq}"
            child_node = _node(
                crect_id,
                ctext_id,
                seq,
                x=cxp - 70,
                y=cyp - 22,
                w=140,
                h=44,
                label=child_label,
                font_size=14,
                fill="#f8f9fa",
                stroke="#868e96",
            )
            elements.extend(child_node)
            elements.append(_arrow(carrow_id, seq, node[0], child_node[0]))
            seq += 1

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "cyberarche-agent",
        "elements": elements,
        "appState": {},
        "files": {},
    }


def describe_scene(scene: Any) -> str:
    """A compact description of an `.excalidraw` scene: shape labels and the
    connections between them. Accepts a JSON string or a parsed dict; tolerant of
    partial/user-authored scenes."""
    if isinstance(scene, str):
        if not scene.strip():
            return "(empty canvas)"
        try:
            scene = json.loads(scene)
        except (ValueError, TypeError):
            return "(unreadable canvas)"
    if not isinstance(scene, dict):
        return "(empty canvas)"
    elements = [e for e in scene.get("elements", []) if isinstance(e, dict) and not e.get("isDeleted")]
    if not elements:
        return "(empty canvas)"

    # A shape's label is its bound text (containerId) or overlapping free text.
    label_by_container: dict[str, str] = {}
    free_labels: list[str] = []
    for el in elements:
        if el.get("type") == "text":
            text = (el.get("text") or "").strip()
            if not text:
                continue
            container = el.get("containerId")
            if container:
                label_by_container[container] = text
            else:
                free_labels.append(text)

    def label_of(element_id: str | None) -> str:
        if not element_id:
            return "?"
        return label_by_container.get(element_id, element_id)

    shapes = [
        label_by_container.get(el["id"], "(unlabelled)")
        for el in elements
        if el.get("type") in {"rectangle", "ellipse", "diamond"}
    ]
    connections = []
    for el in elements:
        if el.get("type") != "arrow":
            continue
        start = (el.get("startBinding") or {}).get("elementId")
        end = (el.get("endBinding") or {}).get("elementId")
        if start or end:
            connections.append(f"{label_of(start)} → {label_of(end)}")

    parts: list[str] = []
    named = shapes + free_labels
    if named:
        parts.append("shapes: " + ", ".join(named))
    if connections:
        parts.append("connections: " + "; ".join(connections))
    return " | ".join(parts) if parts else "(canvas with unlabelled elements)"
