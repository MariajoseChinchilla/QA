#!/usr/bin/env python3
"""Validation helpers for the QA ABF XML suite.

The module is intentionally dependency-free. It scans the manifest, parses XML
inputs once per run, and writes CSV/JSON reports under 04_validation/outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


EXPECTED_CASES_PER_ROUTE = 1000
MAX_EXPECTED_ABF_SLOTS = 4

REQUIRED_DIRS = [
    "00_catalogos",
    "01_manifest",
    "02_inputs_xml_flat",
    "03_expected",
    "04_validation",
    "05_scripts",
]

PATHS = {
    "manifest": Path("01_manifest/case_manifest_1000_full_v6.csv"),
    "expected": Path("03_expected/expected_outputs.csv"),
    "route_catalog": Path("00_catalogos/catalogo_rutas_arbol_expandido_general_post_full_with_bt_control.csv"),
    "patrono_catalog": Path("00_catalogos/patrono_catalog.csv"),
    "random_case_id": Path("04_validation/random_case_id.csv"),
    "random_candidates": Path("04_validation/random_candidates.csv"),
    "outputs": Path("04_validation/outputs"),
}

REPORT_FILES = {
    "repo_structure": "repo_structure_report.csv",
    "xml_wellformed": "xml_wellformed_report.csv",
    "manifest_integrity": "manifest_integrity_report.csv",
    "domains": "domain_validation_report.csv",
    "sales_force_static": "sales_force_static_report.csv",
    "tipo_cliente": "tipo_cliente_validation_report.csv",
    "patrono": "patrono_validation_report.csv",
    "rule2": "rule2_validation_report.csv",
    "random": "random_validation_report.csv",
    "expected_outputs": "expected_output_validation_report.csv",
}

REPORT_FIELDS = {
    "repo_structure": [
        "check",
        "status",
        "severity",
        "expected",
        "found",
        "message",
    ],
    "manifest_integrity": [
        "check",
        "status",
        "severity",
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "message",
    ],
    "xml_wellformed": [
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "status",
        "severity",
        "parse_error",
        "has_envelope",
        "has_body",
        "has_solicitud",
        "has_activo_crediticio",
        "has_activo_financiero",
        "cn_count",
        "abf_count",
        "message",
    ],
    "domains": [
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "status",
        "severity",
        "location",
        "field",
        "value",
        "allowed",
        "message",
    ],
    "sales_force_static": [
        "hash_type",
        "activo_financiero_hash",
        "status",
        "severity",
        "case_count",
        "sample_case_id",
        "sample_input_xml_path",
        "cn_count",
        "abf_count",
        "message",
    ],
    "tipo_cliente": [
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "status",
        "severity",
        "inferred_tipo_cliente",
        "expected_tipo_cliente",
        "credito_tipo_cliente_values",
        "credito_estado_values",
        "credito_count",
        "message",
    ],
    "patrono": [
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "status",
        "severity",
        "patrono_cliente",
        "patrono_in_catalog",
        "route_requires_patrono",
        "patrono_decision_no",
        "candidates_checked",
        "candidates_with_patrono",
        "candidates_missing_patrono",
        "invalid_specialist_values",
        "message",
    ],
    "rule2": [
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "status",
        "severity",
        "r2_decisions",
        "clienteMunicipioVivienda",
        "clienteMunicipioTrabajo",
        "has_hist_vivienda",
        "has_hist_trabajo",
        "target_cn_vivienda",
        "target_cn_trabajo",
        "message",
    ],
    "random": [
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "status",
        "severity",
        "candidate_count",
        "missing_candidate_count",
        "expected_mode",
        "accepted_cn_match",
        "accepted_abf_match",
        "message",
    ],
    "expected_outputs": [
        "check",
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "status",
        "severity",
        "expected_mode",
        "codCnActual",
        "codAbfActual1",
        "codAbfActual2",
        "codAbfActual3",
        "codAbfActual4",
        "expected_control_tree",
        "message",
    ],
}

SCAN_REPORTS = {
    "xml_wellformed",
    "domains",
    "sales_force_static",
    "tipo_cliente",
    "patrono",
    "rule2",
    "random",
    "expected_outputs",
}

DOMAIN_ALLOWED = {
    "creditoEstado": {"V", "C", "D"},
    "creditoBanca": {"BANCA_PERSONAS", "BANCA_TRABAJADORES"},
    "creditoTipoCliente": {"CN", "CE", "CR"},
    "creditoRegion": {"METROPOLITANA", "NOR_ORIENTE", "SUR_OCCIDENTE"},
    "participanteLaborEstado": {"ALTA", "BAJA"},
    "participanteLaborBanca": {"BANCA_PERSONAS", "BANCA_TRABAJADORES"},
    "participanteLaborRegion": {"METROPOLITANA", "NOR_ORIENTE", "SUR_OCCIDENTE"},
    "participanteLaborVacacion": {"0", "1"},
    "participanteLaborTipo": {"ABF", "CN", "CP"},
    "clienteEsSugerido": {"SI", "NO"},
    "clienteEstabaAsignadoAbf": {"SI", "NO"},
    "clienteFueDesembolsadoEnElUltimoMes": {"SI", "NO"},
    "clienteGenero": {"MASCULINO", "FEMENINO"},
    "clienteesTrabajadorBt": {"S", "N"},
    "esTrabajadorInterno": {"S", "N"},
    "cnEstado": {"ALTA", "BAJA"},
    "cnRegion": {"METROPOLITANA", "NOR_ORIENTE", "SUR_OCCIDENTE"},
    "asignadoEstado": {"ALTA", "BAJA"},
    "asignadoEnVacacion": {"0", "1"},
    "asignadoBanca": {"BANCA_PERSONAS", "BANCA_TRABAJADORES"},
    "asignadoGenero": {"MASCULINO", "FEMENINO"},
    "asignadoBolsonEstado": {"EXCESO", "EQUILIBRIO", "DEFICIT"},
    "abfSugeridoOportunidad": {"SUGERIDO", "NO_SUGERIDO"},
}

SOLICITUD_DOMAIN_FIELDS = [
    "clienteEsSugerido",
    "clienteEstabaAsignadoAbf",
    "clienteFueDesembolsadoEnElUltimoMes",
    "clienteGenero",
    "clienteesTrabajadorBt",
    "abfSugeridoOportunidad",
]

CREDITO_DOMAIN_FIELDS = [
    "creditoEstado",
    "creditoBanca",
    "creditoTipoCliente",
    "creditoRegion",
    "participanteLaborEstado",
    "participanteLaborBanca",
    "participanteLaborRegion",
    "participanteLaborVacacion",
    "participanteLaborTipo",
]

CN_DOMAIN_FIELDS = ["cnEstado", "cnRegion"]
ABF_DOMAIN_FIELDS = [
    "asignadoEstado",
    "asignadoEnVacacion",
    "asignadoBanca",
    "asignadoGenero",
    "asignadoBolsonEstado",
]

UNKNOWN_MUNICIPIO = {
    "",
    "-1",
    "NA",
    "N/A",
    "NONE",
    "NULL",
    "SIN_MUNICIPIO",
    "DESCONOCIDO",
    "SIN_DATO",
}

SENTINEL_EMPTY = {"", "-1", "NA", "N/A", "NONE", "NULL"}
ACTIVO_FINANCIERO_RE = re.compile(br"<activoFinanciero\b[^>]*>.*?</activoFinanciero>", re.DOTALL | re.IGNORECASE)
ACCEPTED_SET_MODES = {"ACCEPTED_SET", "ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON"}
EXACT_LIKE_MODES = {"EXACT", "EXACT_OR_BUSINESS_ASSERTION"}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_upper(value: Any) -> str:
    return clean(value).upper()


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def same_tag(actual: str, expected: str) -> bool:
    return local_name(actual).lower() == expected.lower()


def direct_children(elem: ET.Element | None, name: str | None = None) -> list[ET.Element]:
    if elem is None:
        return []
    children = list(elem)
    if name is None:
        return children
    return [child for child in children if same_tag(child.tag, name)]


def direct_child(elem: ET.Element | None, name: str) -> ET.Element | None:
    for child in direct_children(elem):
        if same_tag(child.tag, name):
            return child
    return None


def find_first(elem: ET.Element | None, name: str) -> ET.Element | None:
    if elem is None:
        return None
    if same_tag(elem.tag, name):
        return elem
    for child in elem.iter():
        if same_tag(child.tag, name):
            return child
    return None


def text(elem: ET.Element | None, name: str, default: str = "") -> str:
    child = direct_child(elem, name)
    if child is None:
        return default
    return clean(child.text)


def direct_dict(elem: ET.Element | None) -> dict[str, str]:
    data: dict[str, str] = {}
    if elem is None:
        return data
    for child in direct_children(elem):
        if len(list(child)) == 0:
            data[local_name(child.tag)] = clean(child.text)
    return data


def normalize_credito_fields(data: dict[str, str]) -> dict[str, str]:
    aliases = {
        "cosechaCodigoCn": "cnCosechaCod",
        "cosechaNombreCn": "cnCosechaNombre",
        "cosechaEstadoCn": "cnCosechaEstado",
        "cosechaRegionCn": "cnCosechaRegion",
        "cosechaDepartamentoCn": "cnCosechaDepartamento",
        "cosechaMunicipioCn": "cnCosechaMunicipio",
    }
    for new_name, legacy_name in aliases.items():
        if new_name in data and legacy_name not in data:
            data[legacy_name] = data[new_name]
    return data


def split_set(value: str) -> set[str]:
    value = clean(value)
    if not value:
        return set()
    parts = re.split(r"[|;,\s]+", value)
    return {clean(part) for part in parts if clean(part)}


def abf_slot_names(row: dict[str, str] | None) -> list[str]:
    if not row:
        return []
    names = [name for name in row if re.fullmatch(r"codAbfActual\d+", name or "")]
    return sorted(names, key=lambda name: int(re.search(r"\d+", name).group(0)))


def abf_slot_values(row: dict[str, str] | None) -> list[str]:
    return [clean((row or {}).get(name)) for name in abf_slot_names(row) if clean((row or {}).get(name))]


def primary_abf_actual(row: dict[str, str] | None) -> str:
    values = abf_slot_values(row)
    if values:
        return values[0]
    return clean((row or {}).get("codAbfActual"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with path.open("r", newline="", encoding=encoding) as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except UnicodeDecodeError:
            continue
    with path.open("r", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def is_issue(row: dict[str, Any]) -> bool:
    severity = clean(row.get("severity"))
    status = clean(row.get("status")).upper()
    return severity in {"CRITICAL", "ERROR", "WARNING"} and status not in {
        "PASS",
        "INFO",
        "NOT_APPLICABLE",
    }


def inferir_tipo_cliente(estados_credito: Iterable[str]) -> str:
    estados = [clean(estado) for estado in estados_credito if clean(estado)]
    if not estados:
        return "CN"
    if "D" in estados:
        return "CE"
    if estados and all(estado == "C" for estado in estados):
        return "CR"
    return "INDETERMINADO"


def parse_decisions(value: str) -> dict[str, str]:
    decisions: dict[str, str] = {}
    for key, decision in re.findall(r"(R\d\.D\d+)\s*=\s*([A-Z]+)", clean(value)):
        decisions[key] = decision
    return decisions


def municipio_known(value: str) -> bool:
    return clean(value).upper() not in UNKNOWN_MUNICIPIO


def abf_especialista_en_patrono(abf: dict[str, str] | None, patrono_cliente: str) -> bool:
    if not abf:
        return False
    patrono = clean(patrono_cliente).upper()
    if not patrono or patrono in SENTINEL_EMPTY:
        return False
    values = {
        clean(abf.get("especialistaPatrono1")).upper(),
        clean(abf.get("especialistaPatrono2")).upper(),
        clean(abf.get("especialistaPatrono3")).upper(),
    }
    values = {value for value in values if value not in SENTINEL_EMPTY}
    return patrono in values


def normalize_activo_financiero(activo: ET.Element) -> str:
    centros = []
    for cn in direct_children(activo, "centroDeNegocio"):
        cn_fields = {
            local_name(child.tag): clean(child.text)
            for child in direct_children(cn)
            if not same_tag(child.tag, "abf")
        }
        abfs = []
        for abf in direct_children(cn, "abf"):
            abfs.append(
                {
                    local_name(child.tag): clean(child.text)
                    for child in direct_children(abf)
                }
            )
        abfs.sort(key=lambda item: item.get("asignadoCod", ""))
        centros.append({"fields": dict(sorted(cn_fields.items())), "abfs": abfs})
    centros.sort(key=lambda item: item["fields"].get("cnCod", ""))
    return json.dumps(centros, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass
class XMLFact:
    case_id: str
    expanded_route_id: str
    input_xml_path: str
    parse_ok: bool = False
    parse_error: str = ""
    has_envelope: bool = False
    has_body: bool = False
    has_solicitud: bool = False
    has_activo_crediticio: bool = False
    has_activo_financiero: bool = False
    cn_count: int = 0
    abf_count: int = 0
    raw_activo_hash: str = ""
    normalized_activo_hash: str = ""
    cliente_fields: dict[str, str] = field(default_factory=dict)
    creditos: list[dict[str, str]] = field(default_factory=list)
    cn_states: dict[str, str] = field(default_factory=dict)
    cn_regions: dict[str, str] = field(default_factory=dict)
    cn_municipios: dict[str, str] = field(default_factory=dict)
    cn_departamentos: dict[str, str] = field(default_factory=dict)
    abfs: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    invalid_domains: list[dict[str, str]] = field(default_factory=list)
    invalid_specialist_values: set[str] = field(default_factory=set)

    @property
    def abf_pairs(self) -> set[tuple[str, str]]:
        return set(self.abfs.keys())


def parse_xml_fact(
    path: Path,
    case_id: str,
    expanded_route_id: str,
    input_xml_path: str,
    raw_to_normalized_hash: dict[str, str],
    patrono_catalog: set[str],
) -> XMLFact:
    fact = XMLFact(case_id=case_id, expanded_route_id=expanded_route_id, input_xml_path=input_xml_path)
    try:
        xml_bytes = path.read_bytes()
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        fact.parse_error = str(exc)
        return fact
    except OSError as exc:
        fact.parse_error = str(exc)
        return fact

    fact.parse_ok = True
    fact.has_envelope = local_name(root.tag) == "Envelope"
    body = direct_child(root, "Body")
    fact.has_body = body is not None
    solicitud = find_first(root, "arg0") or find_first(root, "solicitud")
    fact.has_solicitud = solicitud is not None

    if solicitud is None:
        return fact

    fact.cliente_fields = direct_dict(solicitud)
    activo_crediticio = direct_child(solicitud, "activoCrediticio")
    activo_financiero = direct_child(solicitud, "activoFinanciero")
    fact.has_activo_crediticio = activo_crediticio is not None
    fact.has_activo_financiero = activo_financiero is not None

    for credito in direct_children(activo_crediticio, "credito"):
        fact.creditos.append(normalize_credito_fields(direct_dict(credito)))

    if activo_financiero is not None:
        match = ACTIVO_FINANCIERO_RE.search(xml_bytes)
        raw_xml = match.group(0) if match else ET.tostring(activo_financiero, encoding="utf-8", method="xml")
        raw_hash = hashlib.sha256(raw_xml).hexdigest()
        fact.raw_activo_hash = raw_hash
        if raw_hash not in raw_to_normalized_hash:
            normalized = normalize_activo_financiero(activo_financiero)
            raw_to_normalized_hash[raw_hash] = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        fact.normalized_activo_hash = raw_to_normalized_hash[raw_hash]

        for cn in direct_children(activo_financiero, "centroDeNegocio"):
            fact.cn_count += 1
            cn_data = direct_dict(cn)
            cn_cod = clean(cn_data.get("cnCod"))
            fact.cn_states[cn_cod] = clean(cn_data.get("cnEstado"))
            fact.cn_regions[cn_cod] = clean(cn_data.get("cnRegion"))
            fact.cn_municipios[cn_cod] = clean(cn_data.get("cnMunicipio"))
            fact.cn_departamentos[cn_cod] = clean(cn_data.get("cnDepartamento"))
            for abf in direct_children(cn, "abf"):
                fact.abf_count += 1
                abf_data = direct_dict(abf)
                abf_cod = clean(abf_data.get("asignadoCod"))
                if cn_cod and abf_cod:
                    fact.abfs[(cn_cod, abf_cod)] = abf_data
                for field in ("especialistaPatrono1", "especialistaPatrono2", "especialistaPatrono3"):
                    value = clean(abf_data.get(field)).upper()
                    if value not in SENTINEL_EMPTY and patrono_catalog and value not in patrono_catalog:
                        fact.invalid_specialist_values.add(value)

    collect_domain_issues(fact)
    return fact


def collect_domain_issues(fact: XMLFact) -> None:
    def check(location: str, data: dict[str, str], fields: Iterable[str]) -> None:
        for field in fields:
            value = clean(data.get(field))
            if not value:
                continue
            allowed = DOMAIN_ALLOWED[field]
            if value not in allowed:
                fact.invalid_domains.append(
                    {
                        "case_id": fact.case_id,
                        "expanded_route_id": fact.expanded_route_id,
                        "input_xml_path": fact.input_xml_path,
                        "status": "FAIL",
                        "severity": "ERROR",
                        "location": location,
                        "field": field,
                        "value": value,
                        "allowed": "|".join(sorted(allowed)),
                        "message": "Valor fuera del dominio permitido.",
                    }
                )

    check("solicitud", fact.cliente_fields, SOLICITUD_DOMAIN_FIELDS)
    for idx, credito in enumerate(fact.creditos, start=1):
        check(f"Credito[{idx}]", credito, CREDITO_DOMAIN_FIELDS)
    for cn_cod in fact.cn_states:
        cn_data = {
            "cnEstado": fact.cn_states.get(cn_cod, ""),
            "cnRegion": fact.cn_regions.get(cn_cod, ""),
        }
        check(f"CentroDeNegocio[{cn_cod}]", cn_data, CN_DOMAIN_FIELDS)
    for (cn_cod, abf_cod), abf in fact.abfs.items():
        check(f"CentroDeNegocio[{cn_cod}]/Abf[{abf_cod}]", abf, ABF_DOMAIN_FIELDS)


def has_desembolso_en_municipio(fact: XMLFact, municipio_objetivo: str) -> tuple[bool, str]:
    municipio = clean(municipio_objetivo)
    if not municipio_known(municipio):
        return False, ""
    for credito in fact.creditos:
        cn_cod = clean(credito.get("cnCosechaCod"))
        if clean(credito.get("cnCosechaMunicipio")) != municipio:
            continue
        if clean_upper(credito.get("cnCosechaEstado")) != "ALTA":
            continue
        if clean_upper(fact.cn_states.get(cn_cod)) == "ALTA":
            return True, cn_cod
    return False, ""


def expected_candidate_pairs(
    expected: dict[str, str] | None,
    random_candidates: list[dict[str, str]],
) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for row in random_candidates:
        if clean(row.get("candidate_valid_flag")) in {"", "Si", "SI", "S"}:
            cn = clean(row.get("codCnActual")) or clean(row.get("candidate_cod_cn_actual"))
            row_abfs = abf_slot_values(row)
            if not row_abfs:
                legacy_abf = clean(row.get("candidate_cod_abf_actual"))
                row_abfs = [legacy_abf] if legacy_abf else []
            for abf in row_abfs:
                if cn and abf:
                    pairs.add((cn, abf))
    if pairs:
        return pairs
    if expected:
        cn = clean(expected.get("codCnActual"))
        abfs = abf_slot_values(expected)
        legacy_abf = clean(expected.get("codAbfActual"))
        if not abfs and legacy_abf:
            abfs = [legacy_abf]
        if cn and abfs:
            for abf in abfs:
                pairs.add((cn, abf))
        else:
            abf = primary_abf_actual(expected)
            if cn and abf:
                pairs.add((cn, abf))
            cn_set = split_set(clean(expected.get("accepted_cod_cn_set")))
            abf_set = split_set(clean(expected.get("accepted_cod_abf_set")))
            if len(cn_set) == 1:
                for accepted_abf in abf_set:
                    pairs.add((next(iter(cn_set)), accepted_abf))
    return pairs


class QAValidator:
    def __init__(self, root: Path, limit: int | None = None, verbose: bool = False) -> None:
        self.root = root.resolve()
        self.limit = limit
        self.verbose = verbose
        self.output_dir = self.root / PATHS["outputs"]
        self.reports: dict[str, list[dict[str, Any]]] = {name: [] for name in REPORT_FILES}
        self.manifest_rows: list[dict[str, str]] = []
        self.expected_rows: list[dict[str, str]] = []
        self.route_rows: list[dict[str, str]] = []
        self.random_case_rows: list[dict[str, str]] = []
        self.random_candidate_rows: list[dict[str, str]] = []
        self.expected_by_case: dict[str, dict[str, str]] = {}
        self.route_by_id: dict[str, dict[str, str]] = {}
        self.random_case_by_case: dict[str, dict[str, str]] = {}
        self.random_candidates_by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.patrono_catalog: set[str] = set()
        self.actual_xml_files: set[str] = set()
        self.flat_xml_files: set[str] = set()
        self.route_folders: set[str] = set()
        self.raw_to_normalized_hash: dict[str, str] = {}
        self.raw_hash_groups: dict[str, dict[str, Any]] = {}
        self.normalized_hash_groups: dict[str, dict[str, Any]] = {}
        self.total_xml_found = 0

    def log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    def load_data(self) -> None:
        self.manifest_rows = read_csv_rows(self.root / PATHS["manifest"])
        self.expected_rows = read_csv_rows(self.root / PATHS["expected"])
        self.route_rows = read_csv_rows(self.root / PATHS["route_catalog"])
        self.random_case_rows = read_csv_rows(self.root / PATHS["random_case_id"])
        self.random_candidate_rows = read_csv_rows(self.root / PATHS["random_candidates"])

        self.expected_by_case = {}
        for row in self.expected_rows:
            case_id = clean(row.get("case_id"))
            if case_id and case_id not in self.expected_by_case:
                self.expected_by_case[case_id] = row

        self.route_by_id = {}
        for row in self.route_rows:
            route_id = clean(row.get("expanded_route_id"))
            if route_id:
                self.route_by_id[route_id] = row

        self.random_case_by_case = {}
        for row in self.random_case_rows:
            case_id = clean(row.get("case_id"))
            if case_id:
                self.random_case_by_case[case_id] = row

        self.random_candidates_by_case = defaultdict(list)
        for row in self.random_candidate_rows:
            case_id = clean(row.get("case_id"))
            if case_id:
                self.random_candidates_by_case[case_id].append(row)

        patrono_rows = read_csv_rows(self.root / PATHS["patrono_catalog"])
        self.patrono_catalog = {
            clean(row.get("patronoNombre")).upper()
            for row in patrono_rows
            if clean(row.get("patronoNombre"))
        }

        flat_dir = self.root / "02_inputs_xml_flat"
        if flat_dir.exists():
            flat_xml_files: set[str] = set()
            for path in flat_dir.iterdir():
                if path.is_file() and path.name.lower().endswith(".xml"):
                    flat_xml_files.add(f"02_inputs_xml_flat/{path.name}")
            self.flat_xml_files = flat_xml_files
            self.actual_xml_files = set(flat_xml_files)
        self.total_xml_found = len(self.flat_xml_files)

    def add(self, report: str, row: dict[str, Any]) -> None:
        self.reports[report].append(row)

    def validate_repo_structure(self) -> None:
        for folder in REQUIRED_DIRS:
            exists = (self.root / folder).is_dir()
            self.add(
                "repo_structure",
                {
                    "check": f"required_dir:{folder}",
                    "status": "PASS" if exists else "FAIL",
                    "severity": "INFO" if exists else "CRITICAL",
                    "expected": "exists",
                    "found": "exists" if exists else "missing",
                    "message": "Directorio requerido presente." if exists else "Directorio requerido faltante.",
                },
            )

        required_files = ["manifest", "expected", "route_catalog", "patrono_catalog"]
        for key in required_files:
            rel = PATHS[key]
            exists = (self.root / rel).is_file()
            self.add(
                "repo_structure",
                {
                    "check": f"required_file:{rel.as_posix()}",
                    "status": "PASS" if exists else "FAIL",
                    "severity": "INFO" if exists else "CRITICAL",
                    "expected": "exists",
                    "found": "exists" if exists else "missing",
                    "message": "Archivo requerido presente." if exists else "Archivo requerido faltante.",
                },
            )

        route_xml_dir = self.root / "02_inputs_xml"
        self.add(
            "repo_structure",
            {
                "check": "route_xml_folder_absent",
                "status": "PASS" if not route_xml_dir.exists() else "FAIL",
                "severity": "INFO" if not route_xml_dir.exists() else "CRITICAL",
                "expected": "absent",
                "found": "exists" if route_xml_dir.exists() else "absent",
                "message": "Solo debe existir la carpeta plana de XMLs.",
            },
        )

        expected_routes = set(self.route_by_id) or {clean(r.get("expanded_route_id")) for r in self.manifest_rows}
        expected_routes.discard("")

        expected_xml_total = len(expected_routes) * EXPECTED_CASES_PER_ROUTE
        self.add(
            "repo_structure",
            {
                "check": "xml_total_count",
                "status": "PASS" if self.total_xml_found == expected_xml_total else "FAIL",
                "severity": "INFO" if self.total_xml_found == expected_xml_total else "CRITICAL",
                "expected": expected_xml_total,
                "found": self.total_xml_found,
                "message": "Conteo total de XMLs.",
            },
        )
        self.add(
            "repo_structure",
            {
                "check": "flat_xml_total_count",
                "status": "PASS" if len(self.flat_xml_files) == expected_xml_total else "FAIL",
                "severity": "INFO" if len(self.flat_xml_files) == expected_xml_total else "CRITICAL",
                "expected": expected_xml_total,
                "found": len(self.flat_xml_files),
                "message": "Conteo total de XMLs en carpeta plana.",
            },
        )

        counts_by_route = Counter(Path(path).stem.rsplit("__", 1)[0] for path in self.flat_xml_files)
        bad_count_routes = [
            (route, counts_by_route.get(route, 0))
            for route in sorted(expected_routes)
            if counts_by_route.get(route, 0) != EXPECTED_CASES_PER_ROUTE
        ]
        if not bad_count_routes:
            self.add(
                "repo_structure",
                {
                    "check": "xml_count_per_route",
                    "status": "PASS",
                    "severity": "INFO",
                    "expected": EXPECTED_CASES_PER_ROUTE,
                    "found": EXPECTED_CASES_PER_ROUTE,
                    "message": "Todas las rutas tienen el conteo esperado de XMLs.",
                },
            )
        for route, count in bad_count_routes[:1000]:
            self.add(
                "repo_structure",
                {
                    "check": "case_count_not_expected",
                    "status": "FAIL",
                    "severity": "CRITICAL",
                    "expected": EXPECTED_CASES_PER_ROUTE,
                    "found": count,
                    "message": route,
                },
            )

        max_path = ""
        max_len = 0
        for rel in self.actual_xml_files:
            abs_path = str(self.root / Path(rel))
            if len(abs_path) > max_len:
                max_len = len(abs_path)
                max_path = rel
        self.add(
            "repo_structure",
            {
                "check": "max_path_length",
                "status": "PASS" if max_len <= 259 else "FAIL",
                "severity": "INFO" if max_len <= 259 else "WARNING",
                "expected": "<=259",
                "found": max_len,
                "message": max_path,
            },
        )

    def validate_manifest(self) -> None:
        manifest_path = self.root / PATHS["manifest"]
        if not manifest_path.exists():
            self.add(
                "manifest_integrity",
                {
                    "check": "manifest_exists",
                    "status": "FAIL",
                    "severity": "CRITICAL",
                    "message": "Manifest principal faltante.",
                },
            )
            return

        required_columns = {
            "case_id",
            "expanded_route_id",
            "case_number",
            "global_case_number",
            "expected_mode",
            "input_xml_path",
            "input_xml_flat_path",
            "expected_output_path",
        }
        columns = set(self.manifest_rows[0].keys()) if self.manifest_rows else set()
        missing_columns = sorted(required_columns - columns)
        self.add(
            "manifest_integrity",
            {
                "check": "required_columns",
                "status": "PASS" if not missing_columns else "FAIL",
                "severity": "INFO" if not missing_columns else "CRITICAL",
                "message": "OK" if not missing_columns else "Columnas faltantes: " + "|".join(missing_columns),
            },
        )

        case_counter = Counter(clean(row.get("case_id")) for row in self.manifest_rows)
        duplicates = [case_id for case_id, count in case_counter.items() if case_id and count > 1]
        if duplicates:
            for case_id in duplicates[:500]:
                self.add(
                    "manifest_integrity",
                    {
                        "check": "duplicate_case_id",
                        "status": "FAIL",
                        "severity": "CRITICAL",
                        "case_id": case_id,
                        "message": "case_id duplicado en manifest.",
                    },
                )
        else:
            self.add(
                "manifest_integrity",
                {
                    "check": "duplicate_case_id",
                    "status": "PASS",
                    "severity": "INFO",
                    "message": "No hay case_id duplicados.",
                },
            )

        route_counts = Counter(clean(row.get("expanded_route_id")) for row in self.manifest_rows)
        bad_routes = [(route, count) for route, count in route_counts.items() if route and count != EXPECTED_CASES_PER_ROUTE]
        if not bad_routes:
            self.add(
                "manifest_integrity",
                {
                    "check": "manifest_cases_per_route",
                    "status": "PASS",
                    "severity": "INFO",
                    "message": f"Todas las rutas del manifest tienen {EXPECTED_CASES_PER_ROUTE} casos.",
                },
            )
        for route, count in sorted(bad_routes)[:1000]:
            self.add(
                "manifest_integrity",
                {
                    "check": "manifest_cases_per_route",
                    "status": "FAIL",
                    "severity": "CRITICAL",
                    "expanded_route_id": route,
                    "message": f"Conteo en manifest: {count}",
                },
            )

        manifest_paths = set()
        manifest_flat_paths = set()
        expected_file_exists_cache: dict[str, bool] = {}
        for row in self.manifest_rows:
            case_id = clean(row.get("case_id"))
            route = clean(row.get("expanded_route_id"))
            input_path = clean(row.get("input_xml_path"))
            flat_path = clean(row.get("input_xml_flat_path"))
            expected_path = clean(row.get("expected_output_path"))
            if input_path:
                normalized_input_path = Path(input_path).as_posix()
                manifest_paths.add(normalized_input_path)
                if normalized_input_path not in self.actual_xml_files:
                    self.add(
                        "manifest_integrity",
                        {
                            "check": "missing_xml",
                            "status": "FAIL",
                            "severity": "CRITICAL",
                            "case_id": case_id,
                            "expanded_route_id": route,
                            "input_xml_path": input_path,
                            "message": "XML referenciado por manifest no existe.",
                        },
                    )
            if flat_path:
                normalized_flat_path = Path(flat_path).as_posix()
                manifest_flat_paths.add(normalized_flat_path)
                if normalized_flat_path not in self.flat_xml_files:
                    self.add(
                        "manifest_integrity",
                        {
                            "check": "missing_flat_xml",
                            "status": "FAIL",
                            "severity": "CRITICAL",
                            "case_id": case_id,
                            "expanded_route_id": route,
                            "input_xml_path": flat_path,
                            "message": "XML plano referenciado por manifest no existe.",
                        },
                    )
            if route and self.route_by_id and route not in self.route_by_id:
                self.add(
                    "manifest_integrity",
                    {
                        "check": "route_missing_from_catalog",
                        "status": "FAIL",
                        "severity": "ERROR",
                        "case_id": case_id,
                        "expanded_route_id": route,
                        "input_xml_path": input_path,
                        "message": "Ruta del manifest no aparece en catalogo de rutas.",
                    },
                )
            if expected_path and expected_path not in expected_file_exists_cache:
                expected_file_exists_cache[expected_path] = (self.root / expected_path).is_file()
            if expected_path and not expected_file_exists_cache[expected_path]:
                self.add(
                    "manifest_integrity",
                    {
                        "check": "missing_expected_file",
                        "status": "FAIL",
                        "severity": "CRITICAL",
                        "case_id": case_id,
                        "expanded_route_id": route,
                        "input_xml_path": input_path,
                        "message": "Archivo expected_output_path no existe.",
                    },
                )

        extra_xmls = sorted(self.actual_xml_files - manifest_paths)
        for rel in extra_xmls[:1000]:
            self.add(
                "manifest_integrity",
                {
                    "check": "extra_xml",
                    "status": "FAIL",
                    "severity": "WARNING",
                    "input_xml_path": rel,
                    "message": "XML existe en carpeta pero no esta referenciado por manifest.",
                },
            )
        extra_flat_xmls = sorted(self.flat_xml_files - manifest_flat_paths)
        for rel in extra_flat_xmls[:1000]:
            self.add(
                "manifest_integrity",
                {
                    "check": "extra_flat_xml",
                    "status": "FAIL",
                    "severity": "WARNING",
                    "input_xml_path": rel,
                    "message": "XML existe en carpeta plana pero no esta referenciado por manifest.",
                },
            )

        if not any(is_issue(row) for row in self.reports["manifest_integrity"]):
            self.add(
                "manifest_integrity",
                {
                    "check": "manifest_integrity",
                    "status": "PASS",
                    "severity": "INFO",
                    "message": "Manifest integro contra rutas, XMLs y expected output.",
                },
            )

    def scan_xmls(self, selected: set[str]) -> None:
        rows = self.manifest_rows[: self.limit] if self.limit else self.manifest_rows
        total = len(rows)
        for idx, row in enumerate(rows, start=1):
            if self.verbose and (idx == 1 or idx % 1000 == 0 or idx == total):
                self.log(f"Procesando XML {idx}/{total}")
            case_id = clean(row.get("case_id"))
            route = clean(row.get("expanded_route_id"))
            input_path = clean(row.get("input_xml_path"))
            abs_path = self.root / input_path
            expected = self.expected_by_case.get(case_id)
            route_meta = self.route_by_id.get(route, {})
            random_case = self.random_case_by_case.get(case_id)
            candidates = self.random_candidates_by_case.get(case_id, [])

            if Path(input_path).as_posix() not in self.actual_xml_files:
                fact = XMLFact(case_id=case_id, expanded_route_id=route, input_xml_path=input_path)
                fact.parse_error = "missing file"
            else:
                fact = parse_xml_fact(
                    abs_path,
                    case_id,
                    route,
                    input_path,
                    self.raw_to_normalized_hash,
                    self.patrono_catalog,
                )

            if "xml_wellformed" in selected:
                self.add_xml_report(fact, expected)

            if fact.parse_ok:
                if "sales_force_static" in selected:
                    self.collect_sales_force_hash(fact)
                if "domains" in selected:
                    for issue in fact.invalid_domains:
                        self.add("domains", issue)
                if "tipo_cliente" in selected:
                    self.add_tipo_cliente_report(fact, expected)
                if "patrono" in selected:
                    self.add_patrono_report(fact, expected, route_meta, candidates)
                if "rule2" in selected:
                    self.add_rule2_report(fact, route_meta)
                if "random" in selected:
                    self.add_random_report(fact, expected, random_case, candidates)
                if "expected_outputs" in selected:
                    self.add_expected_output_report(fact, expected, route_meta, candidates)
            else:
                if "domains" in selected:
                    self.add_parse_blocked("domains", fact)
                if "tipo_cliente" in selected:
                    self.add_parse_blocked("tipo_cliente", fact)
                if "patrono" in selected:
                    self.add_parse_blocked("patrono", fact)
                if "rule2" in selected and "R2-" in route:
                    self.add_parse_blocked("rule2", fact)
                if "random" in selected and (random_case or (expected and clean(expected.get("is_random_selection")) == "Si")):
                    self.add_parse_blocked("random", fact)
                if "expected_outputs" in selected:
                    self.add_expected_output_report(fact, expected, route_meta, candidates)

        if "domains" in selected and not self.reports["domains"]:
            self.add(
                "domains",
                {
                    "status": "PASS",
                    "severity": "INFO",
                    "message": "No se encontraron valores fuera de dominio.",
                },
            )
        if "sales_force_static" in selected:
            self.finalize_sales_force_report()
        if "random" in selected and not self.reports["random"]:
            self.add(
                "random",
                {
                    "status": "PASS",
                    "severity": "INFO",
                    "message": "No hay casos aleatorios aplicables en el alcance ejecutado.",
                },
            )

    def add_parse_blocked(self, report: str, fact: XMLFact) -> None:
        row = {
            "case_id": fact.case_id,
            "expanded_route_id": fact.expanded_route_id,
            "input_xml_path": fact.input_xml_path,
            "status": "FAIL",
            "severity": "CRITICAL",
            "message": "Validacion bloqueada porque el XML no se pudo parsear.",
        }
        self.add(report, row)

    def add_xml_report(self, fact: XMLFact, expected: dict[str, str] | None) -> None:
        status = "PASS"
        severity = "INFO"
        messages = []
        if not fact.parse_ok:
            status = "FAIL"
            severity = "CRITICAL"
            messages.append("XML no parseable o faltante.")
        else:
            if not fact.has_envelope or not fact.has_body:
                status = "FAIL"
                severity = "ERROR"
                messages.append("Estructura SOAP incompleta.")
            if not fact.has_solicitud:
                status = "FAIL"
                severity = "CRITICAL"
                messages.append("Nodo solicitud faltante.")
            if not fact.has_activo_financiero:
                status = "FAIL"
                severity = "CRITICAL"
                messages.append("ActivoFinanciero faltante.")
            expected_tipo = clean(expected.get("tipo_cliente_expected")) if expected else ""
            if expected_tipo in {"CE", "CR"} and not fact.has_activo_crediticio:
                status = "FAIL"
                severity = "CRITICAL"
                messages.append("ActivoCrediticio faltante para cliente con historial esperado.")
        self.add(
            "xml_wellformed",
            {
                "case_id": fact.case_id,
                "expanded_route_id": fact.expanded_route_id,
                "input_xml_path": fact.input_xml_path,
                "status": status,
                "severity": severity,
                "parse_error": fact.parse_error,
                "has_envelope": "Si" if fact.has_envelope else "No",
                "has_body": "Si" if fact.has_body else "No",
                "has_solicitud": "Si" if fact.has_solicitud else "No",
                "has_activo_crediticio": "Si" if fact.has_activo_crediticio else "No",
                "has_activo_financiero": "Si" if fact.has_activo_financiero else "No",
                "cn_count": fact.cn_count,
                "abf_count": fact.abf_count,
                "message": " ".join(messages) if messages else "XML bien formado con estructura minima requerida.",
            },
        )

    def collect_sales_force_hash(self, fact: XMLFact) -> None:
        if not fact.has_activo_financiero:
            return
        raw_group = self.raw_hash_groups.setdefault(
            fact.raw_activo_hash,
            {
                "count": 0,
                "sample_case_id": fact.case_id,
                "sample_input_xml_path": fact.input_xml_path,
                "cn_count": fact.cn_count,
                "abf_count": fact.abf_count,
            },
        )
        raw_group["count"] += 1
        norm_group = self.normalized_hash_groups.setdefault(
            fact.normalized_activo_hash,
            {
                "count": 0,
                "sample_case_id": fact.case_id,
                "sample_input_xml_path": fact.input_xml_path,
                "cn_count": fact.cn_count,
                "abf_count": fact.abf_count,
            },
        )
        norm_group["count"] += 1

    def finalize_sales_force_report(self) -> None:
        if not self.normalized_hash_groups:
            self.add(
                "sales_force_static",
                {
                    "hash_type": "normalized",
                    "status": "FAIL",
                    "severity": "CRITICAL",
                    "message": "No se pudo calcular hash de ActivoFinanciero.",
                },
            )
            return

        normalized_ok = len(self.normalized_hash_groups) == 1
        raw_ok = len(self.raw_hash_groups) == 1
        for hash_value, group in sorted(self.normalized_hash_groups.items()):
            self.add(
                "sales_force_static",
                {
                    "hash_type": "normalized",
                    "activo_financiero_hash": hash_value,
                    "status": "PASS" if normalized_ok else "FAIL",
                    "severity": "INFO" if normalized_ok else "CRITICAL",
                    "case_count": group["count"],
                    "sample_case_id": group["sample_case_id"],
                    "sample_input_xml_path": group["sample_input_xml_path"],
                    "cn_count": group["cn_count"],
                    "abf_count": group["abf_count"],
                    "message": "Hash normalizado unico." if normalized_ok else "ActivoFinanciero normalizado difiere entre XMLs.",
                },
            )
        for hash_value, group in sorted(self.raw_hash_groups.items()):
            self.add(
                "sales_force_static",
                {
                    "hash_type": "raw",
                    "activo_financiero_hash": hash_value,
                    "status": "PASS" if raw_ok else "FAIL",
                    "severity": "INFO" if raw_ok else "WARNING",
                    "case_count": group["count"],
                    "sample_case_id": group["sample_case_id"],
                    "sample_input_xml_path": group["sample_input_xml_path"],
                    "cn_count": group["cn_count"],
                    "abf_count": group["abf_count"],
                    "message": "Hash raw unico." if raw_ok else "Hash raw difiere; revisar si el orden importa para Blaze.",
                },
            )

    def add_tipo_cliente_report(self, fact: XMLFact, expected: dict[str, str] | None) -> None:
        estados = [clean(credito.get("creditoEstado")) for credito in fact.creditos if clean(credito.get("creditoEstado"))]
        tipos = sorted({clean(credito.get("creditoTipoCliente")) for credito in fact.creditos if clean(credito.get("creditoTipoCliente"))})
        inferred = inferir_tipo_cliente(estados)
        expected_tipo = clean(expected.get("tipo_cliente_expected")) if expected else ""
        status = "PASS"
        severity = "INFO"
        messages = []

        if inferred == "INDETERMINADO":
            status = "FAIL"
            severity = "CRITICAL"
            messages.append("Estados de credito no permiten inferir tipo cliente.")
        if expected_tipo and inferred != expected_tipo:
            status = "FAIL"
            severity = "CRITICAL"
            messages.append(f"Tipo esperado {expected_tipo} no coincide con inferido {inferred}.")
        if tipos and any(tipo != inferred for tipo in tipos):
            status = "FAIL"
            severity = "CRITICAL"
            messages.append("creditoTipoCliente en Credito no es coherente con estados.")
        if inferred == "CE" and "D" not in estados:
            status = "FAIL"
            severity = "CRITICAL"
            messages.append("CE sin credito en estado D.")
        if inferred == "CR" and (not estados or "D" in estados or not all(estado == "C" for estado in estados)):
            status = "FAIL"
            severity = "CRITICAL"
            messages.append("CR requiere historial solo en estado C.")
        if inferred == "CN" and estados:
            status = "FAIL"
            severity = "CRITICAL"
            messages.append("CN no debe tener historial crediticio.")

        self.add(
            "tipo_cliente",
            {
                "case_id": fact.case_id,
                "expanded_route_id": fact.expanded_route_id,
                "input_xml_path": fact.input_xml_path,
                "status": status,
                "severity": severity,
                "inferred_tipo_cliente": inferred,
                "expected_tipo_cliente": expected_tipo,
                "credito_tipo_cliente_values": "|".join(tipos),
                "credito_estado_values": "|".join(estados),
                "credito_count": len(fact.creditos),
                "message": " ".join(messages) if messages else "Tipo cliente coherente.",
            },
        )

    def add_patrono_report(
        self,
        fact: XMLFact,
        expected: dict[str, str] | None,
        route_meta: dict[str, str],
        random_candidates: list[dict[str, str]],
    ) -> None:
        patrono = ""
        if expected:
            patrono = clean(expected.get("cliente_patrono"))
        if not patrono:
            for credito in fact.creditos:
                patrono = clean(credito.get("creditoPatrono")) or clean(credito.get("creditoPatronoNombre"))
                if patrono:
                    break

        route_text = " ".join(
            [
                clean(route_meta.get("final_output_class_id")),
                clean(route_meta.get("candidate_scope")),
                clean(route_meta.get("subroute_path")),
            ]
        )
        decisions = parse_decisions(clean(route_meta.get("subroute_path")))
        route_requires_patrono = "PATRONO" in route_text.upper() or "patrono" in route_text.lower()
        patrono_decision_no = any(decisions.get(key) == "NO" for key in ("R2.D03", "R2.D06", "R2.D07", "R2.D08"))

        candidates = expected_candidate_pairs(expected, random_candidates)
        checked = 0
        with_patrono = 0
        missing_patrono = 0
        for pair in candidates:
            checked += 1
            abf = fact.abfs.get(pair)
            if abf_especialista_en_patrono(abf, patrono):
                with_patrono += 1
            else:
                missing_patrono += 1

        status = "PASS"
        severity = "INFO"
        messages = []
        patrono_key = patrono.upper()
        patrono_in_catalog = (not patrono_key) or (not self.patrono_catalog) or patrono_key in self.patrono_catalog
        if not patrono_in_catalog:
            status = "FAIL"
            severity = "ERROR"
            messages.append("Patrono del cliente no existe en catalogo.")
        if fact.invalid_specialist_values:
            status = "FAIL"
            severity = "ERROR"
            messages.append("especialistaPatrono contiene valores fuera de catalogo.")
        if route_requires_patrono and checked and missing_patrono:
            status = "FAIL"
            severity = "ERROR"
            messages.append("Ruta requiere especialista de patrono pero algun candidato esperado no lo cumple.")
        if patrono_decision_no and with_patrono:
            status = "FAIL"
            severity = "ERROR"
            messages.append("Ruta esperaba respuesta No a patrono pero hay candidato esperado especialista.")

        self.add(
            "patrono",
            {
                "case_id": fact.case_id,
                "expanded_route_id": fact.expanded_route_id,
                "input_xml_path": fact.input_xml_path,
                "status": status,
                "severity": severity,
                "patrono_cliente": patrono,
                "patrono_in_catalog": "Si" if patrono_in_catalog else "No",
                "route_requires_patrono": "Si" if route_requires_patrono else "No",
                "patrono_decision_no": "Si" if patrono_decision_no else "No",
                "candidates_checked": checked,
                "candidates_with_patrono": with_patrono,
                "candidates_missing_patrono": missing_patrono,
                "invalid_specialist_values": "|".join(sorted(fact.invalid_specialist_values)),
                "message": " ".join(messages) if messages else "Validacion de patrono coherente.",
            },
        )

    def add_rule2_report(self, fact: XMLFact, route_meta: dict[str, str]) -> None:
        subroute_path = clean(route_meta.get("subroute_path"))
        if "R2." not in subroute_path and "R2-" not in fact.expanded_route_id:
            return
        decisions = parse_decisions(subroute_path)
        vivienda = clean(fact.cliente_fields.get("clienteMunicipioVivienda"))
        trabajo = clean(fact.cliente_fields.get("clienteMunicipioTrabajo"))
        has_viv, target_viv = has_desembolso_en_municipio(fact, vivienda)
        has_trab, target_trab = has_desembolso_en_municipio(fact, trabajo)
        status = "PASS"
        severity = "INFO"
        messages = []

        def fail(message: str) -> None:
            nonlocal status, severity
            status = "FAIL"
            severity = "ERROR"
            messages.append(message)

        if decisions.get("R2.D01") == "SI" and not municipio_known(vivienda):
            fail("D01=SI requiere municipio de vivienda conocido.")
        if decisions.get("R2.D01") == "NO" and municipio_known(vivienda):
            fail("D01=NO requiere convencion explicita de municipio vivienda desconocido.")
        if decisions.get("R2.D02") == "SI" and not has_viv:
            fail("D02=SI requiere desembolso historico en CN abierto de municipio vivienda.")
        if decisions.get("R2.D02") == "NO" and has_viv:
            fail("D02=NO no debe tener desembolso historico valido en municipio vivienda.")
        if decisions.get("R2.D04") == "SI" and not municipio_known(trabajo):
            fail("D04=SI requiere municipio de trabajo conocido.")
        if decisions.get("R2.D04") == "NO" and municipio_known(trabajo):
            fail("D04=NO requiere convencion explicita de municipio trabajo desconocido.")
        if decisions.get("R2.D05") == "SI" and not has_trab:
            fail("D05=SI requiere desembolso historico en CN abierto de municipio trabajo.")
        if decisions.get("R2.D05") == "NO" and has_trab:
            fail("D05=NO no debe tener desembolso historico valido en municipio trabajo.")

        self.add(
            "rule2",
            {
                "case_id": fact.case_id,
                "expanded_route_id": fact.expanded_route_id,
                "input_xml_path": fact.input_xml_path,
                "status": status,
                "severity": severity,
                "r2_decisions": ";".join(f"{key}={value}" for key, value in sorted(decisions.items())),
                "clienteMunicipioVivienda": vivienda,
                "clienteMunicipioTrabajo": trabajo,
                "has_hist_vivienda": "Si" if has_viv else "No",
                "has_hist_trabajo": "Si" if has_trab else "No",
                "target_cn_vivienda": target_viv,
                "target_cn_trabajo": target_trab,
                "message": " ".join(messages) if messages else "Regla 2 coherente para validaciones implementadas.",
            },
        )

    def add_random_report(
        self,
        fact: XMLFact,
        expected: dict[str, str] | None,
        random_case: dict[str, str] | None,
        candidates: list[dict[str, str]],
    ) -> None:
        is_random = bool(random_case) or (expected is not None and clean(expected.get("is_random_selection")) == "Si")
        if not is_random:
            return
        valid_candidates = [
            row
            for row in candidates
            if clean(row.get("candidate_valid_flag")) in {"", "Si", "SI", "S"}
        ]
        candidate_pairs = expected_candidate_pairs(expected, valid_candidates)
        missing_pairs = sorted(pair for pair in candidate_pairs if pair not in fact.abf_pairs)

        accepted_cn = split_set(clean((random_case or {}).get("accepted_cod_cn_set")))
        accepted_abf = split_set(clean((random_case or {}).get("accepted_cod_abf_set")))
        if random_case:
            accepted_cn = accepted_cn or ({clean(random_case.get("codCnActual"))} if clean(random_case.get("codCnActual")) else set())
            accepted_abf = accepted_abf or set(abf_slot_values(random_case))
        if expected:
            accepted_cn = accepted_cn or split_set(clean(expected.get("accepted_cod_cn_set")))
            accepted_abf = accepted_abf or split_set(clean(expected.get("accepted_cod_abf_set")))
            accepted_cn = accepted_cn or ({clean(expected.get("codCnActual"))} if clean(expected.get("codCnActual")) else set())
            accepted_abf = accepted_abf or set(abf_slot_values(expected))
        candidate_cn = {cn for cn, _abf in candidate_pairs}
        candidate_abf = {abf for _cn, abf in candidate_pairs}
        accepted_cn_match = accepted_cn == candidate_cn if accepted_cn else False
        accepted_abf_match = accepted_abf == candidate_abf if accepted_abf else False
        expected_mode = clean(expected.get("expected_mode")) if expected else ""

        status = "PASS"
        severity = "INFO"
        messages = []
        if len(candidate_pairs) < 2:
            status = "FAIL"
            severity = "CRITICAL"
            messages.append("Caso aleatorio sin al menos dos candidatos validos.")
        if missing_pairs:
            status = "FAIL"
            severity = "CRITICAL"
            messages.append("Candidatos aleatorios no existen en ActivoFinanciero.")
        if expected_mode not in ACCEPTED_SET_MODES:
            status = "FAIL"
            severity = "ERROR" if severity != "CRITICAL" else severity
            messages.append("Expected output de caso aleatorio no usa ACCEPTED_SET.")
        elif expected_mode != "ACCEPTED_SET":
            status = "FAIL"
            severity = "ERROR" if severity != "CRITICAL" else severity
            messages.append("Expected output de caso aleatorio usa modo no canonico; el goal pide ACCEPTED_SET.")
        if not accepted_cn_match or not accepted_abf_match:
            status = "FAIL"
            severity = "ERROR" if severity != "CRITICAL" else severity
            messages.append("Columnas codAbfActualN no coinciden con random_candidates.")

        self.add(
            "random",
            {
                "case_id": fact.case_id,
                "expanded_route_id": fact.expanded_route_id,
                "input_xml_path": fact.input_xml_path,
                "status": status,
                "severity": severity,
                "candidate_count": len(candidate_pairs),
                "missing_candidate_count": len(missing_pairs),
                "expected_mode": expected_mode,
                "accepted_cn_match": "Si" if accepted_cn_match else "No",
                "accepted_abf_match": "Si" if accepted_abf_match else "No",
                "message": " ".join(messages) if messages else "Caso aleatorio coherente con candidatos en columnas codAbfActualN.",
            },
        )

    def add_expected_output_report(
        self,
        fact: XMLFact,
        expected: dict[str, str] | None,
        route_meta: dict[str, str],
        random_candidates: list[dict[str, str]],
    ) -> None:
        if expected is None:
            self.add(
                "expected_outputs",
                {
                    "case_id": fact.case_id,
                    "expanded_route_id": fact.expanded_route_id,
                    "input_xml_path": fact.input_xml_path,
                    "status": "FAIL",
                    "severity": "CRITICAL",
                    "message": "case_id del manifest no tiene expected output.",
                },
            )
            return

        mode = clean(expected.get("expected_mode"))
        cn = clean(expected.get("codCnActual"))
        abf_values = abf_slot_values(expected)
        abf = primary_abf_actual(expected)
        control_tree = clean(expected.get("expected_control_tree"))
        is_bt = fact.expanded_route_id.endswith("__CONTROL_BT") or control_tree == "BT"
        status = "PASS"
        severity = "INFO"
        messages = []

        if is_bt:
            if control_tree != "BT":
                status = "FAIL"
                severity = "CRITICAL"
                messages.append("Control BT sin expected_control_tree=BT.")
            bancas = {clean_upper(credito.get("creditoBanca")) for credito in fact.creditos if clean(credito.get("creditoBanca"))}
            if "BANCA_PERSONAS" in bancas:
                status = "FAIL"
                severity = "ERROR" if severity != "CRITICAL" else severity
                messages.append("Control BT no debe pertenecer a banca_personas.")
        elif mode in EXACT_LIKE_MODES:
            if not cn or not abf:
                status = "FAIL"
                severity = "CRITICAL"
                messages.append("EXACT requiere codCnActual y codAbfActual1.")
            elif len(abf_values) > 1:
                status = "FAIL"
                severity = "ERROR"
                messages.append("Ruta deterministica debe usar solo codAbfActual1.")
            elif fact.parse_ok and abf not in SENTINEL_EMPTY and (cn, abf) not in fact.abf_pairs:
                status = "FAIL"
                severity = "ERROR"
                messages.append("codCnActual/codAbfActual1 no existe como par en ActivoFinanciero.")
            elif fact.parse_ok and abf in SENTINEL_EMPTY and cn not in fact.cn_states:
                status = "FAIL"
                severity = "ERROR"
                messages.append("codCnActual no existe en ActivoFinanciero.")
            if mode != "EXACT":
                status = "FAIL"
                severity = "ERROR" if severity != "CRITICAL" else severity
                messages.append("Modo exacto no canonico; el goal pide EXACT para rutas deterministicas.")
        elif mode in ACCEPTED_SET_MODES:
            pairs = expected_candidate_pairs(expected, random_candidates)
            cn_set = {pair[0] for pair in pairs if pair[0]}
            abf_set = {pair[1] for pair in pairs if pair[1]}
            if not cn_set or not abf_set:
                status = "FAIL"
                severity = "CRITICAL"
                messages.append("ACCEPTED_SET requiere codCnActual y al menos un codAbfActualN.")
            if mode != "ACCEPTED_SET":
                status = "FAIL"
                severity = "ERROR" if severity != "CRITICAL" else severity
                messages.append("Modo no canonico para seleccion aleatoria; el goal pide ACCEPTED_SET.")
            missing_pairs = [pair for pair in pairs if fact.parse_ok and pair not in fact.abf_pairs]
            if missing_pairs:
                status = "FAIL"
                severity = "ERROR" if severity != "CRITICAL" else severity
                messages.append("Algun candidato accepted_set no existe en ActivoFinanciero.")
        elif mode == "HANDOFF_CONTROL":
            if control_tree != "BT":
                status = "FAIL"
                severity = "ERROR"
                messages.append("HANDOFF_CONTROL requiere convencion de arbol de control.")
        elif mode == "BOLSON":
            if clean(expected.get("bolson")) not in {"PENDIENTES", "PENDIENTE"}:
                status = "FAIL"
                severity = "ERROR"
                messages.append("Modo BOLSON requiere bolson esperado.")
        else:
            status = "FAIL"
            severity = "ERROR"
            messages.append("expected_mode no reconocido.")

        self.add(
            "expected_outputs",
            {
                "case_id": fact.case_id,
                "expanded_route_id": fact.expanded_route_id,
                "input_xml_path": fact.input_xml_path,
                "status": status,
                "severity": severity,
                "expected_mode": mode,
                "codCnActual": cn,
                "codAbfActual1": clean(expected.get("codAbfActual1")) or abf,
                "codAbfActual2": clean(expected.get("codAbfActual2")),
                "codAbfActual3": clean(expected.get("codAbfActual3")),
                "codAbfActual4": clean(expected.get("codAbfActual4")),
                "expected_control_tree": control_tree,
                "message": " ".join(messages) if messages else "Expected output coherente para validaciones implementadas.",
            },
        )

    def validate_expected_completeness_without_xml(self) -> None:
        manifest_cases = {clean(row.get("case_id")) for row in self.manifest_rows if clean(row.get("case_id"))}
        expected_cases = {clean(row.get("case_id")) for row in self.expected_rows if clean(row.get("case_id"))}
        for case_id in sorted(manifest_cases - expected_cases)[:1000]:
            manifest_row = next((row for row in self.manifest_rows if clean(row.get("case_id")) == case_id), {})
            self.add(
                "expected_outputs",
                {
                    "case_id": case_id,
                    "expanded_route_id": clean(manifest_row.get("expanded_route_id")),
                    "input_xml_path": clean(manifest_row.get("input_xml_path")),
                    "status": "FAIL",
                    "severity": "CRITICAL",
                    "message": "case_id del manifest no existe en expected_outputs.csv.",
                },
            )
        for case_id in sorted(expected_cases - manifest_cases)[:1000]:
            expected_row = self.expected_by_case.get(case_id, {})
            self.add(
                "expected_outputs",
                {
                    "case_id": case_id,
                    "expanded_route_id": clean(expected_row.get("expanded_route_id")),
                    "status": "FAIL",
                    "severity": "ERROR",
                    "message": "expected_outputs.csv contiene case_id fuera del manifest.",
                },
            )
        for field, label in [("codCliente", "codigo de cliente"), ("dpiCliente", "DPI")]:
            values = [clean(row.get(field)) for row in self.expected_rows if clean(row.get(field))]
            counts = Counter(values)
            duplicates = [value for value, count in counts.items() if count > 1]
            if not duplicates:
                self.add(
                    "expected_outputs",
                    {
                        "check": f"unique_{field}",
                        "status": "PASS",
                        "severity": "INFO",
                        "message": f"No hay duplicados en {label}.",
                    },
                )
            for value in duplicates[:1000]:
                first = next((row for row in self.expected_rows if clean(row.get(field)) == value), {})
                self.add(
                    "expected_outputs",
                    {
                        "check": f"duplicate_{field}",
                        "case_id": clean(first.get("case_id")),
                        "expanded_route_id": clean(first.get("expanded_route_id")),
                        "status": "FAIL",
                        "severity": "CRITICAL",
                        "message": f"Duplicado en {label}: {value}.",
                    },
                )

    def write_reports(self, selected: set[str]) -> None:
        for name in REPORT_FILES:
            if name not in selected:
                continue
            rows = self.reports[name]
            write_csv_rows(self.output_dir / REPORT_FILES[name], rows, REPORT_FIELDS[name])

    def summary(self, selected: set[str]) -> dict[str, Any]:
        route_count = len(self.route_by_id) or len({clean(row.get("expanded_route_id")) for row in self.manifest_rows})
        total_expected = route_count * EXPECTED_CASES_PER_ROUTE
        all_rows = [row for name in selected for row in self.reports.get(name, [])]
        critical = sum(1 for row in all_rows if is_issue(row) and clean(row.get("severity")) == "CRITICAL")
        errors = sum(1 for row in all_rows if is_issue(row) and clean(row.get("severity")) == "ERROR")
        warnings = sum(1 for row in all_rows if is_issue(row) and clean(row.get("severity")) == "WARNING")
        status = "PASS"
        if critical:
            status = "FAIL"
        elif errors or warnings:
            status = "PARTIAL"
        return {
            "total_routes": route_count,
            "expected_cases_per_route": EXPECTED_CASES_PER_ROUTE,
            "total_xml_expected": total_expected,
            "total_xml_found": self.total_xml_found,
            "total_flat_xml_found": len(self.flat_xml_files),
            "total_errors": errors,
            "critical_errors": critical,
            "warnings": warnings,
            "status": status,
            "reports": {
                name: {
                    "file": f"04_validation/outputs/{REPORT_FILES[name]}",
                    "rows": len(self.reports.get(name, [])),
                    "issues": sum(1 for row in self.reports.get(name, []) if is_issue(row)),
                }
                for name in sorted(selected)
            },
            "limit": self.limit,
        }

    def run(self, selected: set[str] | None = None) -> dict[str, Any]:
        if selected is None:
            selected = set(REPORT_FILES)
        else:
            selected = set(selected)

        self.load_data()
        if "repo_structure" in selected:
            self.validate_repo_structure()
        if "manifest_integrity" in selected:
            self.validate_manifest()
        scan_selected = selected & SCAN_REPORTS
        if scan_selected:
            if "expected_outputs" in scan_selected:
                self.validate_expected_completeness_without_xml()
            self.scan_xmls(scan_selected)
        self.write_reports(selected)
        summary = self.summary(selected)
        if selected == set(REPORT_FILES):
            write_json(self.output_dir / "qa_validation_summary.json", summary)
        return summary


def parse_common_args(report_name: str | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Raiz del proyecto QA.")
    parser.add_argument("--limit", type=int, default=None, help="Limitar cantidad de casos del manifest para muestra.")
    parser.add_argument("--verbose", action="store_true", help="Mostrar progreso.")
    if report_name is None:
        parser.add_argument(
            "--only",
            choices=sorted(REPORT_FILES),
            action="append",
            help="Ejecutar solo un reporte. Puede repetirse.",
        )
    return parser.parse_args()


def run_cli(report_name: str | None = None) -> int:
    args = parse_common_args(report_name)
    selected = {report_name} if report_name else (set(args.only) if args.only else None)
    validator = QAValidator(Path(args.root), limit=args.limit, verbose=args.verbose)
    summary = validator.run(selected=selected)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


def main_all() -> int:
    return run_cli(None)


def main_single(report_name: str) -> int:
    return run_cli(report_name)


if __name__ == "__main__":
    sys.exit(main_all())
