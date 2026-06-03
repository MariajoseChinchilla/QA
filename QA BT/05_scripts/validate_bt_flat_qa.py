#!/usr/bin/env python3
"""Validate the flat QA BT package and route-forcing constraints."""

from __future__ import annotations

import csv
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parent
MANIFEST = BASE / "01_manifest" / "case_manifest_100_bt.csv"
EXPECTED = BASE / "03_expected" / "expected_outputs.csv"
FLAT_DIR = BASE / "02_inputs_xml_flat"
OUTPUTS = BASE / "04_validation" / "outputs"

REQUIRED_DIRS = [
    "00_catalogos",
    "01_manifest",
    "02_inputs_xml_flat",
    "03_expected",
    "04_validation",
    "05_scripts",
    "docs",
]
FORBIDDEN_DIRS = ["02_inputs_xml"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def text_values(root: ET.Element, tag: str) -> set[str]:
    return {
        (elem.text or "").strip()
        for elem in root.iter()
        if elem.tag.split("}", 1)[-1] == tag
    }


def text_list(root: ET.Element, tag: str) -> list[str]:
    return [
        (elem.text or "").strip()
        for elem in root.iter()
        if elem.tag.split("}", 1)[-1] == tag
    ]


def first_text(root: ET.Element, tag: str) -> str:
    for elem in root.iter():
        if elem.tag.split("}", 1)[-1] == tag:
            return (elem.text or "").strip()
    return ""


def validate_structure() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rel in REQUIRED_DIRS:
        exists = (BASE / rel).is_dir()
        rows.append(
            {
                "check": f"required_dir:{rel}",
                "status": "PASS" if exists else "FAIL",
                "severity": "ERROR" if not exists else "INFO",
                "message": "Directorio requerido presente." if exists else "Directorio requerido faltante.",
            }
        )
    for rel in FORBIDDEN_DIRS:
        exists = (BASE / rel).exists()
        rows.append(
            {
                "check": f"forbidden_dir:{rel}",
                "status": "FAIL" if exists else "PASS",
                "severity": "ERROR" if exists else "INFO",
                "message": "No debe existir carpeta por reglas/rutas." if exists else "No existe carpeta separada por reglas.",
            }
        )
    return rows


def validate_manifest(manifest_rows: list[dict[str, str]], expected_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    expected_by_case = {row["case_id"]: row for row in expected_rows}
    seen: set[str] = set()
    for row in manifest_rows:
        case_id = row["case_id"]
        rel = row["input_xml_path"]
        path = BASE / rel
        status = "PASS"
        messages: list[str] = []
        if case_id in seen:
            status = "FAIL"
            messages.append("case_id duplicado")
        seen.add(case_id)
        if not rel.startswith("02_inputs_xml_flat/"):
            status = "FAIL"
            messages.append("input_xml_path no apunta a carpeta plana")
        if "02_inputs_xml/" in rel:
            status = "FAIL"
            messages.append("input_xml_path apunta a carpeta separada por ruta")
        if not path.exists():
            status = "FAIL"
            messages.append("XML no existe")
        if case_id not in expected_by_case:
            status = "FAIL"
            messages.append("case_id no existe en expected_outputs.csv")
        rows.append(
            {
                "case_id": case_id,
                "expanded_route_id": row["expanded_route_id"],
                "input_xml_path": rel,
                "status": status,
                "severity": "ERROR" if status == "FAIL" else "INFO",
                "message": "; ".join(messages) if messages else "OK",
            }
        )
    return rows


def validate_xmls(manifest_rows: list[dict[str, str]], expected_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    expected_by_case = {row["case_id"]: row for row in expected_rows}
    xml_rows: list[dict[str, object]] = []
    bt_rows: list[dict[str, object]] = []

    for row in manifest_rows:
        case_id = row["case_id"]
        rel = row["input_xml_path"]
        expected = expected_by_case.get(case_id, {})
        path = BASE / rel
        try:
            root = ET.parse(path).getroot()
            parse_error = ""
        except Exception as exc:  # noqa: BLE001 - report parser detail
            xml_rows.append(
                {
                    "case_id": case_id,
                    "expanded_route_id": row["expanded_route_id"],
                    "input_xml_path": rel,
                    "status": "FAIL",
                    "severity": "ERROR",
                    "cn_count": "",
                    "abf_count": "",
                    "parse_error": str(exc),
                    "message": "XML no parseable.",
                }
            )
            continue

        cn_count = len([elem for elem in root.iter() if elem.tag.split("}", 1)[-1] == "centroDeNegocio"])
        abf_count = len([elem for elem in root.iter() if elem.tag.split("}", 1)[-1] == "abf"])
        has_solicitud = any(elem.tag.split("}", 1)[-1] == "arg0" for elem in root.iter())
        has_creditos = any(elem.tag.split("}", 1)[-1] == "activoCrediticio" for elem in root.iter())
        has_financiero = any(elem.tag.split("}", 1)[-1] == "activoFinanciero" for elem in root.iter())
        asignado_generos = text_list(root, "asignadoGenero")
        has_genero = bool(first_text(root, "clienteGenero")) and len(asignado_generos) == abf_count and all(asignado_generos)
        xml_status = "PASS" if has_solicitud and has_creditos and has_financiero and cn_count > 0 and abf_count > 0 else "FAIL"
        if not has_genero:
            xml_status = "FAIL"
        xml_rows.append(
            {
                "case_id": case_id,
                "expanded_route_id": row["expanded_route_id"],
                "input_xml_path": rel,
                "status": xml_status,
                "severity": "ERROR" if xml_status == "FAIL" else "INFO",
                "cn_count": cn_count,
                "abf_count": abf_count,
                "parse_error": parse_error,
                "message": "OK" if xml_status == "PASS" else "Estructura XML incompleta o genero faltante.",
            }
        )

        credito_bancas = text_values(root, "creditoBanca")
        credito_estados = text_values(root, "creditoEstado")
        credito_tipos = text_values(root, "creditoTipoCliente")
        credito_region_values = text_values(root, "creditoRegion")
        participante_region_values = text_values(root, "participanteLaborRegion")
        cosecha_region_values = text_values(root, "cosechaRegionCn")
        cn_region_values = text_values(root, "cnRegion")
        cn_municipios = text_values(root, "cnMunicipio")
        cliente_municipios = []
        for field in ["clienteMunicipioVivienda", "clienteMunicipioTrabajo"]:
            value = first_text(root, field)
            if value and value != "SIN_MUNICIPIO":
                cliente_municipios.append(value)
        lowercase_values = []
        for elem in root.iter():
            value = (elem.text or "").strip()
            if any(char.isalpha() for char in value) and value != value.upper():
                lowercase_values.append(elem.tag.split("}", 1)[-1])
        expected_tree = expected.get("expected_control_tree", "")
        expected_tipo = expected.get("tipo_cliente_expected", "")
        messages: list[str] = []
        if expected_tree == "BT":
            bt_status = "PASS" if credito_bancas == {"BANCA_TRABAJADORES"} else "FAIL"
            if bt_status != "PASS":
                messages.append("Creditos BT con banca distinta.")
        elif expected_tree == "PED":
            bt_status = "PASS" if credito_bancas == {"BANCA_PERSONAS"} else "FAIL"
            if bt_status != "PASS":
                messages.append("Ruta PED con banca inesperada.")
        else:
            bt_status = "FAIL"
            messages.append("expected_control_tree invalido.")

        region_values = credito_region_values | participante_region_values | cosecha_region_values | cn_region_values
        if region_values != {"METROPOLITANA"}:
            bt_status = "FAIL"
            messages.append(f"Region distinta a Metropolitana: {'|'.join(sorted(region_values))}.")
        if expected_tipo and credito_tipos and credito_tipos != {expected_tipo}:
            bt_status = "FAIL"
            messages.append("creditoTipoCliente no coincide con expected.")
        if expected_tipo == "CE" and "D" not in credito_estados:
            bt_status = "FAIL"
            messages.append("Cliente existente CE sin credito en estado D.")
        if expected_tipo in {"CR", "CN"} and "D" in credito_estados:
            bt_status = "FAIL"
            messages.append("Cliente no existente no debe traer credito en estado D.")
        missing_municipios = sorted(m for m in cliente_municipios if m not in cn_municipios)
        if missing_municipios:
            bt_status = "FAIL"
            messages.append(f"Municipios de cliente sin CN: {'|'.join(missing_municipios)}.")
        if lowercase_values:
            bt_status = "FAIL"
            messages.append(f"Valores textuales sin mayuscula: {'|'.join(lowercase_values[:5])}.")
        if not messages:
            messages.append("OK")

        bt_rows.append(
            {
                "case_id": case_id,
                "expanded_route_id": row["expanded_route_id"],
                "input_xml_path": rel,
                "expected_control_tree": expected_tree,
                "credito_banca_values": "|".join(sorted(credito_bancas)),
                "credito_estado_values": "|".join(sorted(credito_estados)),
                "credito_tipo_cliente_values": "|".join(sorted(credito_tipos)),
                "region_values": "|".join(sorted(region_values)),
                "cliente_municipios": "|".join(cliente_municipios),
                "clienteCod": first_text(root, "clienteCod"),
                "clienteDpi": first_text(root, "clienteDpi"),
                "status": bt_status,
                "severity": "ERROR" if bt_status == "FAIL" else "INFO",
                "message": "; ".join(messages),
            }
        )

    return xml_rows, bt_rows


def main() -> int:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    structure_rows = validate_structure()
    manifest_rows = read_csv(MANIFEST) if MANIFEST.exists() else []
    expected_rows = read_csv(EXPECTED) if EXPECTED.exists() else []
    manifest_report = validate_manifest(manifest_rows, expected_rows) if manifest_rows and expected_rows else []
    xml_report, bt_report = validate_xmls(manifest_rows, expected_rows) if manifest_rows and expected_rows else ([], [])

    xml_files = list(FLAT_DIR.glob("*.xml")) if FLAT_DIR.exists() else []
    count_rows = [
        {
            "check": "manifest_vs_expected",
            "status": "PASS" if len(manifest_rows) == len(expected_rows) and manifest_rows else "FAIL",
            "severity": "ERROR" if len(manifest_rows) != len(expected_rows) or not manifest_rows else "INFO",
            "expected": len(manifest_rows),
            "found": len(expected_rows),
            "message": "Manifest y expected tienen el mismo número de filas.",
        },
        {
            "check": "manifest_vs_flat_xml",
            "status": "PASS" if len(manifest_rows) == len(xml_files) and manifest_rows else "FAIL",
            "severity": "ERROR" if len(manifest_rows) != len(xml_files) or not manifest_rows else "INFO",
            "expected": len(manifest_rows),
            "found": len(xml_files),
            "message": "La carpeta plana contiene un XML por caso.",
        },
    ]

    write_csv(OUTPUTS / "repo_structure_report.csv", structure_rows + count_rows, ["check", "status", "severity", "expected", "found", "message"])
    write_csv(
        OUTPUTS / "manifest_integrity_report.csv",
        manifest_report,
        ["case_id", "expanded_route_id", "input_xml_path", "status", "severity", "message"],
    )
    write_csv(
        OUTPUTS / "xml_wellformed_report.csv",
        xml_report,
        ["case_id", "expanded_route_id", "input_xml_path", "status", "severity", "cn_count", "abf_count", "parse_error", "message"],
    )
    write_csv(
        OUTPUTS / "bt_domain_validation_report.csv",
        bt_report,
        [
            "case_id",
            "expanded_route_id",
            "input_xml_path",
            "expected_control_tree",
            "credito_banca_values",
            "credito_estado_values",
            "credito_tipo_cliente_values",
            "region_values",
            "cliente_municipios",
            "clienteCod",
            "clienteDpi",
            "status",
            "severity",
            "message",
        ],
    )

    summary = {
        "validated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_rows": len(manifest_rows),
        "expected_rows": len(expected_rows),
        "flat_xml_count": len(xml_files),
        "structure_failures": sum(1 for row in structure_rows + count_rows if row["status"] != "PASS"),
        "manifest_failures": sum(1 for row in manifest_report if row["status"] != "PASS"),
        "xml_failures": sum(1 for row in xml_report if row["status"] != "PASS"),
        "bt_domain_failures": sum(1 for row in bt_report if row["status"] != "PASS"),
        "expected_control_tree_counts": dict(Counter(row.get("expected_control_tree", "") for row in expected_rows)),
        "reports_dir": str(OUTPUTS),
    }
    summary["overall_status"] = "PASS" if all(
        summary[key] == 0
        for key in ["structure_failures", "manifest_failures", "xml_failures", "bt_domain_failures"]
    ) else "FAIL"
    (OUTPUTS / "qa_bt_validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
