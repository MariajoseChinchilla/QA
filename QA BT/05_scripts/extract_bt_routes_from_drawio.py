#!/usr/bin/env python3
"""Extract and expand the BT decision tree stored as a draw.io XML file."""

from __future__ import annotations

import csv
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parent
DRAWIO = BASE / "00_catalogos" / "Motor_BT.drawio.xml"
OUT_CATALOG = BASE / "00_catalogos" / "catalogo_rutas_arbol_bt_expandido.csv"
OUT_NODES = BASE / "00_catalogos" / "arbol_bt_nodos.csv"
OUT_EDGES = BASE / "00_catalogos" / "arbol_bt_aristas.csv"
OUT_SUMMARY = BASE / "04_validation" / "drawio_route_extraction_summary.json"

PAGE_PREFIX = {
    "Primera asignación": "BT-PA",
    "General_post_primera_asignacion": "BT-GPA",
    "Regla no. 1": "R1",
    "Regla no. 2": "R2",
    "Regla no. 3": "R3",
}

PRIMARY_PAGES = {"Primera asignación", "General_post_primera_asignacion"}
SUBRULE_PAGES = {"Regla no. 1", "Regla no. 2", "Regla no. 3"}


@dataclass
class Node:
    node_id: str
    page: str
    label: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class Edge:
    edge_id: str
    page: str
    source: str
    target: str
    label: str


@dataclass
class Route:
    route_id: str
    page: str
    decision_path: list[tuple[str, str]]
    leaf: str

    @property
    def path_text(self) -> str:
        parts = [f"{question} = {answer}" for question, answer in self.decision_path]
        return " > ".join([*parts, self.leaf])

    @property
    def decision_codes(self) -> str:
        return "; ".join(
            f"D{idx:02d}={answer}" for idx, (_question, answer) in enumerate(self.decision_path, 1)
        )


def clean_label(value: str | None) -> str:
    text = unescape(value or "")
    text = re.sub(
        r"<span[^>]*color:\s*rgba\(0, 0, 0, 0\)[^>]*>.*?</span>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"%3CmxGraphModel%3E.*", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text in {"í", "Si"}:
        return "Sí"
    return text


def normalize_edge_label(value: str) -> str:
    value = clean_label(value)
    if re.search(r"\bS[ií]\b", value, flags=re.IGNORECASE):
        return "Sí"
    if re.search(r"\bNo\b", value, flags=re.IGNORECASE):
        return "No"
    return value


def slug(value: str, max_len: int = 44) -> str:
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
        "ü": "u",
    }
    s = value.lower()
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_").upper()
    return s[:max_len].strip("_") or "SIN_CLASIFICAR"


def geometry(cell: ET.Element) -> dict[str, float] | None:
    geom = cell.find("mxGeometry")
    if geom is None:
        return None
    required = ("x", "y", "width", "height")
    if not all(k in geom.attrib for k in required):
        return None
    return {k: float(geom.attrib[k]) for k in required}


def edge_point(geom: ET.Element | None, point_name: str) -> tuple[float, float] | None:
    if geom is None:
        return None
    for point in geom.findall("mxPoint"):
        if point.attrib.get("as") == point_name and "x" in point.attrib and "y" in point.attrib:
            return float(point.attrib["x"]), float(point.attrib["y"])
    arr = geom.find("Array")
    if arr is None:
        return None
    points = [
        (float(point.attrib["x"]), float(point.attrib["y"]))
        for point in arr.findall("mxPoint")
        if "x" in point.attrib and "y" in point.attrib
    ]
    if not points:
        return None
    return points[0] if point_name == "sourcePoint" else points[-1]


def distance_to_node(point: tuple[float, float], node: Node) -> tuple[float, float]:
    x, y = point
    dx = max(node.x - x, 0, x - (node.x + node.width))
    dy = max(node.y - y, 0, y - (node.y + node.height))
    center_x = node.x + node.width / 2
    center_y = node.y + node.height / 2
    return math.hypot(dx, dy), math.hypot(x - center_x, y - center_y)


def nearest_node(
    point: tuple[float, float] | None,
    nodes: dict[str, Node],
    exclude: str | None = None,
) -> str | None:
    if point is None:
        return None
    best: tuple[tuple[float, float], str] | None = None
    for node_id, node in nodes.items():
        if node_id == exclude:
            continue
        score = distance_to_node(point, node)
        if best is None or score < best[0]:
            best = (score, node_id)
    return best[1] if best else None


def parse_drawio() -> tuple[dict[str, dict[str, Node]], list[Edge]]:
    tree = ET.parse(DRAWIO)
    pages: dict[str, dict[str, Node]] = {}
    all_edges: list[Edge] = []

    for diagram in tree.getroot().findall("diagram"):
        page = diagram.attrib["name"]
        root = diagram.find("mxGraphModel/root")
        if root is None:
            continue

        nodes: dict[str, Node] = {}
        edge_labels: dict[str, list[str]] = {}
        edge_cells: list[ET.Element] = []

        for cell in root.findall("mxCell"):
            if cell.attrib.get("vertex") == "1":
                label = clean_label(cell.attrib.get("value"))
                parent = cell.attrib.get("parent")
                if parent != "1":
                    if label:
                        edge_labels.setdefault(parent or "", []).append(label)
                    continue
                geom = geometry(cell)
                if label and geom:
                    nodes[cell.attrib["id"]] = Node(
                        node_id=cell.attrib["id"],
                        page=page,
                        label=label,
                        x=geom["x"],
                        y=geom["y"],
                        width=geom["width"],
                        height=geom["height"],
                    )
            elif cell.attrib.get("edge") == "1":
                edge_cells.append(cell)

        for cell in edge_cells:
            geom = cell.find("mxGeometry")
            source = cell.attrib.get("source")
            target = cell.attrib.get("target")
            if not source:
                source = nearest_node(edge_point(geom, "sourcePoint"), nodes, exclude=target)
            if not target:
                target = nearest_node(edge_point(geom, "targetPoint"), nodes, exclude=source)
            if not source or not target or source == target:
                continue
            if source not in nodes or target not in nodes:
                continue
            label = normalize_edge_label(cell.attrib.get("value", ""))
            if not label:
                label = " / ".join(
                    normalize_edge_label(item) for item in edge_labels.get(cell.attrib["id"], [])
                ).strip(" /")
            all_edges.append(
                Edge(
                    edge_id=cell.attrib["id"],
                    page=page,
                    source=source,
                    target=target,
                    label=label or "?",
                )
            )

        pages[page] = nodes

    return pages, dedupe_edges(all_edges)


def dedupe_edges(edges: Iterable[Edge]) -> list[Edge]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[Edge] = []
    for edge in edges:
        key = (edge.page, edge.source, edge.target, edge.label)
        if key not in seen:
            seen.add(key)
            out.append(edge)
    return out


def routes_for_page(page: str, nodes: dict[str, Node], edges: list[Edge]) -> list[Route]:
    page_edges = [edge for edge in edges if edge.page == page]
    outgoing: dict[str, list[Edge]] = {node_id: [] for node_id in nodes}
    incoming: dict[str, int] = {node_id: 0 for node_id in nodes}
    for edge in page_edges:
        outgoing.setdefault(edge.source, []).append(edge)
        incoming[edge.target] = incoming.get(edge.target, 0) + 1

    starts = [
        node_id
        for node_id in nodes
        if incoming.get(node_id, 0) == 0 and outgoing.get(node_id)
    ]
    starts.sort(key=lambda node_id: (nodes[node_id].x, nodes[node_id].y))

    routes: list[Route] = []

    def walk(node_id: str, path: list[tuple[str, str]], seen: set[str]) -> None:
        if node_id in seen:
            return
        children = outgoing.get(node_id, [])
        if not children:
            prefix = PAGE_PREFIX.get(page, slug(page))
            routes.append(
                Route(
                    route_id=f"{prefix}-{len(routes) + 1:03d}",
                    page=page,
                    decision_path=path,
                    leaf=nodes[node_id].label,
                )
            )
            return
        def edge_sort_key(item: Edge) -> tuple[int, float, float]:
            answer_order = {"Sí": 0, "No": 1}.get(item.label, 2)
            return answer_order, nodes[item.target].x, nodes[item.target].y

        for edge in sorted(children, key=edge_sort_key):
            walk(edge.target, [*path, (nodes[node_id].label, edge.label)], {*seen, node_id})

    for start in starts:
        walk(start, [], set())

    return routes


def classify_r1(route: Route) -> tuple[str, str, str]:
    answers = [answer for _question, answer in route.decision_path]
    if answers[:2] == ["Sí", "Sí"]:
        return (
            "R1_ASSIGN_DEFICIT_CLOSEST_UNIQUE",
            "EXACT",
            "Asignar el cliente al ABF en déficit con mayor cercanía única de edad.",
        )
    if answers[:2] == ["Sí", "No"]:
        return (
            "R1_RANDOM_DEFICIT_GROUP",
            "ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON",
            "Seleccionar aleatoriamente un ABF del grupo en déficit.",
        )
    if answers[:2] == ["No", "Sí"]:
        return (
            "R1_ASSIGN_CLOSEST_UNIQUE",
            "EXACT",
            "Asignar el cliente al ABF con mayor cercanía única de edad del grupo recibido.",
        )
    return (
        "R1_RANDOM_FULL_GROUP",
        "ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON",
        "Seleccionar aleatoriamente un ABF de entre el grupo recibido.",
    )


def candidate_scope_from_leaf(leaf: str) -> str:
    low = leaf.lower()
    if "regla no. 1" not in low:
        return ""
    if "vivienda" in low:
        location = "municipio de vivienda"
    elif "trabajo" in low:
        location = "municipio de trabajo"
    else:
        location = "grupo recibido"
    if "desembolsado" in low:
        hist = "con historial de desembolso"
    else:
        hist = "sin requisito de historial"
    if "comparten género" in low or "comparten genero" in low:
        gender = "filtrado por género del cliente"
    else:
        gender = "sin filtro de género"
    if "abfs de alta bt" in low:
        bank = "ABFs de alta BT"
    else:
        bank = "ABFs de alta"
    return f"{bank}; {location}; {hist}; {gender}"


def direct_class(leaf: str) -> tuple[str, str, str]:
    low = leaf.lower()
    if "árbol ped" in low or "arbol ped" in low:
        return "DIRECT_PED", "EXACT", "Ir a árbol PED."
    if "bolsón de pendientes" in low or "bolson de pendientes" in low:
        return "DIRECT_PENDING_BOLSON", "BOLSON", leaf
    if "bolsones de las características" in low or "bolsones de las caracteristicas" in low:
        return "DIRECT_MORA_BOLSONES", "BOLSON", leaf
    if "último abf" in low or "ultimo abf" in low:
        return "DIRECT_ASSIGN_LAST_ABF", "EXACT", leaf
    if "dejar al cliente en la asignación actual" in low:
        return "DIRECT_KEEP_CURRENT_ASSIGNMENT", "EXACT", leaf
    if "mantener la asignación de abf" in low or "mantener la asignacion de abf" in low:
        return "DIRECT_KEEP_CURRENT_ABF", "EXACT", leaf
    if "mantener la asignación" in low or "mantener la asignacion" in low:
        return "DIRECT_KEEP_ASSIGNMENT", "EXACT", leaf
    if "reasignar" in low:
        return "DIRECT_REASSIGN_DISBURSER_ABF", "EXACT", leaf
    return f"DIRECT_{slug(leaf)}", "EXACT", leaf


def expanded_rows(page_routes: dict[str, list[Route]]) -> list[dict[str, str]]:
    r1_routes = page_routes.get("Regla no. 1", [])
    r2_routes = page_routes.get("Regla no. 2", [])
    r3_routes = page_routes.get("Regla no. 3", [])
    rows: list[dict[str, str]] = []

    def add_direct(base: Route, source_tree: str) -> None:
        class_id, mode, expected = direct_class(base.leaf)
        rows.append(
            {
                "source_tree": source_tree,
                "base_route_id": base.route_id,
                "expanded_route_id": f"{base.route_id}__DIRECT",
                "route_depth": "1",
                "base_decision_path_codes": base.decision_codes,
                "base_decision_path_text": base.path_text,
                "subroute_path": "",
                "final_rule": source_tree,
                "final_output_class_id": class_id,
                "final_expected_output": expected,
                "expected_mode": mode,
                "candidate_scope": "",
                "notes": "Ruta directa extraída del draw.io BT.",
                "target_cases": "100",
            }
        )

    def add_r1(base: Route, source_tree: str, parent_path: str, parent_leaf: str, parent_id: str) -> None:
        scope = candidate_scope_from_leaf(parent_leaf)
        for r1 in r1_routes:
            r1_class, mode, expected = classify_r1(r1)
            rows.append(
                {
                    "source_tree": source_tree,
                    "base_route_id": base.route_id,
                    "expanded_route_id": f"{parent_id}__{r1.route_id}",
                    "route_depth": "2" if parent_id == base.route_id else "3",
                    "base_decision_path_codes": base.decision_codes,
                    "base_decision_path_text": base.path_text,
                    "subroute_path": " > ".join(part for part in [parent_path, r1.path_text] if part),
                    "final_rule": "Regla no. 1",
                    "final_output_class_id": f"{slug(parent_leaf, 28)}__{r1_class}",
                    "final_expected_output": expected,
                    "expected_mode": mode,
                    "candidate_scope": scope,
                    "notes": "Ruta expandida hacia Regla no. 1 desde el árbol BT.",
                    "target_cases": "100",
                }
            )

    for page in sorted(PRIMARY_PAGES):
        for base in page_routes.get(page, []):
            low = base.leaf.lower()
            if "regla no. 1" in low:
                add_r1(base, page, "", base.leaf, base.route_id)
            elif "regla no. 2" in low:
                for r2 in r2_routes:
                    add_r1(
                        base,
                        page,
                        r2.path_text,
                        r2.leaf,
                        f"{base.route_id}__{r2.route_id}",
                    )
            elif "regla no. 3" in low:
                for r3 in r3_routes:
                    if "regla no. 1" in r3.leaf.lower():
                        add_r1(
                            base,
                            page,
                            r3.path_text,
                            r3.leaf,
                            f"{base.route_id}__{r3.route_id}",
                        )
                    else:
                        class_id, mode, expected = direct_class(r3.leaf)
                        rows.append(
                            {
                                "source_tree": page,
                                "base_route_id": base.route_id,
                                "expanded_route_id": f"{base.route_id}__{r3.route_id}__DIRECT",
                                "route_depth": "2",
                                "base_decision_path_codes": base.decision_codes,
                                "base_decision_path_text": base.path_text,
                                "subroute_path": r3.path_text,
                                "final_rule": "Regla no. 3",
                                "final_output_class_id": f"R3__{class_id}",
                                "final_expected_output": expected,
                                "expected_mode": mode,
                                "candidate_scope": "",
                                "notes": "Ruta directa de Regla no. 3 expandida desde el árbol BT.",
                                "target_cases": "100",
                            }
                        )
            else:
                add_direct(base, page)

    rows.sort(key=lambda row: row["expanded_route_id"])
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    pages, edges = parse_drawio()
    page_routes = {
        page: routes_for_page(page, nodes, edges)
        for page, nodes in pages.items()
        if page in PRIMARY_PAGES | SUBRULE_PAGES
    }
    rows = expanded_rows(page_routes)

    node_rows = [
        {
            "page": node.page,
            "node_id": node.node_id,
            "label": node.label,
            "x": f"{node.x:g}",
            "y": f"{node.y:g}",
            "width": f"{node.width:g}",
            "height": f"{node.height:g}",
        }
        for nodes in pages.values()
        for node in nodes.values()
    ]
    edge_rows = [
        {
            "page": edge.page,
            "edge_id": edge.edge_id,
            "source_node_id": edge.source,
            "target_node_id": edge.target,
            "label": edge.label,
            "source_label": pages[edge.page][edge.source].label,
            "target_label": pages[edge.page][edge.target].label,
        }
        for edge in edges
    ]

    write_csv(
        OUT_CATALOG,
        rows,
        [
            "source_tree",
            "base_route_id",
            "expanded_route_id",
            "route_depth",
            "base_decision_path_codes",
            "base_decision_path_text",
            "subroute_path",
            "final_rule",
            "final_output_class_id",
            "final_expected_output",
            "expected_mode",
            "candidate_scope",
            "notes",
            "target_cases",
        ],
    )
    write_csv(OUT_NODES, node_rows, ["page", "node_id", "label", "x", "y", "width", "height"])
    write_csv(
        OUT_EDGES,
        edge_rows,
        ["page", "edge_id", "source_node_id", "target_node_id", "label", "source_label", "target_label"],
    )

    summary = {
        "drawio_file": str(DRAWIO),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pages": {page: len(nodes) for page, nodes in pages.items()},
        "edge_count": len(edges),
        "page_route_counts": {page: len(routes) for page, routes in page_routes.items()},
        "expanded_route_count": len(rows),
        "catalog": str(OUT_CATALOG),
        "notes": [
            "Las rutas que delegan a Regla no. 1 se expanden con las cuatro salidas de esa regla.",
            "Las rutas que delegan a Regla no. 2 o Regla no. 3 se expanden hasta su salida final.",
        ],
    }
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
