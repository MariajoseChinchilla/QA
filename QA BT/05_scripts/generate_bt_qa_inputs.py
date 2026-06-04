#!/usr/bin/env python3
"""Generate flat XML inputs for the BT QA decision tree."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import random
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parent
CATALOG = BASE / "00_catalogos" / "catalogo_rutas_arbol_bt_expandido.csv"
MANIFEST = BASE / "01_manifest" / "case_manifest_100_bt.csv"
EXPECTED = BASE / "03_expected" / "expected_outputs.csv"
FLAT_DIR = BASE / "02_inputs_xml_flat"
VALIDATION_DIR = BASE / "04_validation"
CASES_PER_ROUTE = int(os.getenv("QA_BT_CASES_PER_ROUTE", "100"))
RUN_VERSION = "XML_INPUT_GENERATOR_BT_FLAT_V3_GENDER_STRUCTURE_2026_06_03"
TREE_VERSION = "MOTOR_BT_DRAWIO_EXPANDED_V1"
MAPPING_VERSION = "BT_FLAT_V1"

BANCA_BT = "banca_trabajadores"
BANCA_BP = "banca_personas"
REGION = "Metropolitana"

MAX_ABF_SLOTS = 4


def esc(value: object) -> str:
    return escape("" if value is None else str(value), {'"': "&quot;"})


def xml_value(value: object) -> str:
    value_str = "" if value is None else str(value)
    if not any(char.isalpha() for char in value_str):
        return value_str
    no_marks = "".join(
        char for char in unicodedata.normalize("NFKD", value_str) if not unicodedata.combining(char)
    )
    return no_marks.upper()


def tag(name: str, value: object) -> str:
    return f"<{name}>{esc(xml_value(value))}</{name}>"


def unlink_retry(path: Path, attempts: int = 8) -> None:
    for attempt in range(attempts):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.25 * (attempt + 1))


def write_text_retry(path: Path, text: str, attempts: int = 8) -> None:
    for attempt in range(attempts):
        try:
            path.write_text(text, encoding="utf-8")
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.25 * (attempt + 1))


def load_catalog() -> list[dict[str, str]]:
    if not CATALOG.exists():
        spec = importlib.util.spec_from_file_location(
            "extract_bt_routes_from_drawio", SCRIPT_DIR / "extract_bt_routes_from_drawio.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        module.main()
    with CATALOG.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def r1_id(expanded_route_id: str) -> str | None:
    match = re.search(r"(R1-\d{3})", expanded_route_id)
    return match.group(1) if match else None


def is_random_route(route: dict[str, str]) -> bool:
    return "RANDOM" in route["final_output_class_id"] or "ACCEPTED_SET" in route["expected_mode"]


def abf(code: str, estado: str, banca: str, edad: int, bolson: str, patronos: bool = False) -> dict[str, object]:
    return {
        "cod": code,
        "estado": estado,
        "vacacion": "0",
        "banca": banca,
        "edad": edad,
        "patronos": ["patrono1", "patrono2", "patrono3"] if patronos else ["-1", "-1", "-1"],
        "bolson": bolson,
    }


def cn(
    code: str,
    name: str,
    municipio: str,
    departamento: str,
    abfs: list[dict[str, object]],
    estado: str = "Alta",
) -> dict[str, object]:
    return {
        "cod": code,
        "nombre": name,
        "estado": estado,
        "region": REGION,
        "municipio": municipio,
        "departamento": departamento,
        "abfs": abfs,
    }


def build_static_catalog() -> list[dict[str, object]]:
    return [
        cn(
            "1001",
            "Agencia Asignacion Actual BT",
            "municipio_asignacion_bt",
            "departamento_asignacion_bt",
            [
                abf("500001", "Alta", BANCA_BT, 38, "Equilibrio", True),
                abf("500002", "Baja", BANCA_BT, 41, "Equilibrio", True),
                abf("500003", "Alta", BANCA_BP, 39, "Equilibrio"),
                abf("500004", "Alta", BANCA_BT, 55, "Exceso"),
            ],
        ),
        cn(
            "7001",
            "Agencia Ultimo Desembolso BT",
            "municipio_ultimo_desembolso_bt",
            "departamento_ultimo_desembolso_bt",
            [
                abf("700101", "Alta", BANCA_BT, 34, "Equilibrio", True),
                abf("700102", "Alta", BANCA_BP, 34, "Equilibrio"),
                abf("700103", "Baja", BANCA_BT, 34, "Equilibrio", True),
            ],
        ),
        cn(
            "2001",
            "Agencia Municipio Vivienda BT",
            "municipio_vivienda_bt",
            "departamento_vivienda_bt",
            [
                abf("200101", "Alta", BANCA_BT, 35, "Equilibrio", True),
                abf("200102", "Alta", BANCA_BT, 42, "Deficit", True),
            ],
        ),
        cn(
            "2002",
            "Agencia Municipio Trabajo BT",
            "municipio_trabajo_bt",
            "departamento_trabajo_bt",
            [
                abf("200201", "Alta", BANCA_BT, 35, "Equilibrio", True),
                abf("200202", "Alta", BANCA_BT, 42, "Deficit", True),
            ],
        ),
        cn(
            "2003",
            "Agencia Historial Alterno BT",
            "municipio_historial_otro_bt",
            "departamento_historial_otro_bt",
            [
                abf("200301", "Alta", BANCA_BT, 36, "Equilibrio", True),
                abf("200302", "Alta", BANCA_BP, 37, "Equilibrio"),
            ],
        ),
        cn(
            "3101",
            "Grupo R1 Deficit Cercania Unica BT",
            "municipio_r1_deficit_unico_bt",
            "departamento_r1_deficit_unico_bt",
            [
                abf("310101", "Alta", BANCA_BT, 35, "Deficit", True),
                abf("310102", "Alta", BANCA_BT, 49, "Deficit", True),
                abf("310103", "Alta", BANCA_BT, 57, "Equilibrio"),
            ],
        ),
        cn(
            "3102",
            "Grupo R1 Deficit Empate BT",
            "municipio_r1_deficit_empate_bt",
            "departamento_r1_deficit_empate_bt",
            [
                abf("310201", "Alta", BANCA_BT, 35, "Deficit", True),
                abf("310202", "Alta", BANCA_BT, 35, "Deficit", True),
                abf("310203", "Alta", BANCA_BT, 51, "Equilibrio"),
            ],
        ),
        cn(
            "3103",
            "Grupo R1 Cercania Unica BT",
            "municipio_r1_cercania_unica_bt",
            "departamento_r1_cercania_unica_bt",
            [
                abf("310301", "Alta", BANCA_BT, 35, "Equilibrio", True),
                abf("310302", "Alta", BANCA_BT, 48, "Equilibrio", True),
                abf("310303", "Alta", BANCA_BT, 59, "Exceso"),
            ],
        ),
        cn(
            "3104",
            "Grupo R1 Empate General BT",
            "municipio_r1_empate_general_bt",
            "departamento_r1_empate_general_bt",
            [
                abf("310401", "Alta", BANCA_BT, 35, "Equilibrio", True),
                abf("310402", "Alta", BANCA_BT, 35, "Equilibrio", True),
                abf("310403", "Alta", BANCA_BT, 54, "Exceso"),
            ],
        ),
        cn(
            "9001",
            "Bolson Pendientes BT",
            "municipio_pendientes_bt",
            "departamento_pendientes_bt",
            [abf("900101", "Alta", BANCA_BT, 44, "Equilibrio")],
        ),
    ]


R1_TARGETS = {
    "R1-001": ("3101", ["310101"], "EXACT"),
    "R1-002": ("3102", ["310201", "310202"], "ACCEPTED_SET"),
    "R1-003": ("3103", ["310301"], "EXACT"),
    "R1-004": ("3104", ["310401", "310402"], "ACCEPTED_SET"),
}


def by_code(cns: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for item in cns:
        out[str(item["cod"])] = item
        for item_abf in item["abfs"]:  # type: ignore[index]
            out[str(item_abf["cod"])] = {"cn": item, "abf": item_abf}
    return out


def centro_xml(item: dict[str, object], ctx: dict[str, object] | None = None) -> str:
    chunks = [
        "<centroDeNegocio>",
        tag("cnCod", item["cod"]),
        tag("cnNombre", item["nombre"]),
        tag("cnEstado", item["estado"]),
        tag("cnRegion", item["region"]),
        tag("cnMunicipio", item["municipio"]),
        tag("cnDepartamento", item["departamento"]),
    ]
    for item_abf in item["abfs"]:  # type: ignore[index]
        patronos = item_abf["patronos"]  # type: ignore[index]
        asignado_genero = item_abf.get("genero", "MASCULINO")
        if ctx and str(item["cod"]) == str(ctx.get("targetCnForGender", "")):
            asignado_genero = ctx.get("targetAbfGenero", asignado_genero)
        chunks.extend(
            [
                "<abf>",
                tag("asignadoCod", item_abf["cod"]),
                tag("asignadoEstado", item_abf["estado"]),
                tag("asignadoEnVacacion", item_abf["vacacion"]),
                tag("asignadoBanca", item_abf["banca"]),
                tag("asignadoEdad", item_abf["edad"]),
                tag("asignadoGenero", asignado_genero),
                tag("especialistaPatrono1", patronos[0]),
                tag("especialistaPatrono2", patronos[1]),
                tag("especialistaPatrono3", patronos[2]),
                tag("asignadoBolsonAcumulativo", "75000" if item_abf["bolson"] == "Deficit" else "150000"),
                tag("asignadoBolsonLimExposicion", "100000"),
                tag("asignadoBolsonEstado", item_abf["bolson"]),
                "</abf>",
            ]
        )
    chunks.append("</centroDeNegocio>")
    return "".join(chunks)


def credito_xml(credito: dict[str, object]) -> str:
    fields = [
        "creditoNo",
        "creditoMonto",
        "creditoTasa",
        "creditoTipo",
        "creditoEstado",
        "creditoPatronoNombre",
        "creditoPatronoCod",
        "creditoBanca",
        "creditoTipoCliente",
        "creditoRegion",
        "creditoFechaConsecion",
        "creditoFechaCancelacion",
        "creditoPatrono",
        "participanteLaborCod",
        "participanteLaborEstado",
        "participanteLaborEdad",
        "participanteLaborCn",
        "participanteLaborBanca",
        "participanteLaborRegion",
        "participanteLaborMunicipio",
        "participanteLaborVacacion",
        "participanteLaborTipo",
        "cosechaCodigoCn",
        "cosechaNombreCn",
        "cosechaEstadoCn",
        "cosechaRegionCn",
        "cosechaDepartamentoCn",
        "cosechaMunicipioCn",
    ]
    return "<credito>" + "".join(tag(field, credito.get(field, "")) for field in fields) + "</credito>"


def base_credit(
    case_id: str,
    seq: int,
    banca: str,
    target_cn: dict[str, object],
    labor_abf: str,
    tipo_cliente: str,
    estado: str = "C",
    labor_banca: str | None = None,
    labor_estado: str = "Alta",
) -> dict[str, object]:
    labor_banca = labor_banca or banca
    return {
        "creditoNo": f"BT{seq:02d}{case_id[-4:]}",
        "creditoMonto": "25000.00",
        "creditoTasa": "17.5",
        "creditoTipo": "Nuevo",
        "creditoEstado": estado,
        "creditoPatronoNombre": "patrono1",
        "creditoPatronoCod": "P001",
        "creditoBanca": banca,
        "creditoTipoCliente": tipo_cliente,
        "creditoRegion": REGION,
        "creditoFechaConsecion": "2026-04-15",
        "creditoFechaCancelacion": "2028-04-15",
        "creditoPatrono": "patrono1",
        "participanteLaborCod": labor_abf,
        "participanteLaborEstado": labor_estado,
        "participanteLaborEdad": "35",
        "participanteLaborCn": target_cn["cod"],
        "participanteLaborBanca": labor_banca,
        "participanteLaborRegion": target_cn["region"],
        "participanteLaborMunicipio": target_cn["municipio"],
        "participanteLaborVacacion": "0",
        "participanteLaborTipo": "abf",
        "cosechaCodigoCn": target_cn["cod"],
        "cosechaNombreCn": target_cn["nombre"],
        "cosechaEstadoCn": target_cn["estado"],
        "cosechaRegionCn": target_cn["region"],
        "cosechaDepartamentoCn": target_cn["departamento"],
        "cosechaMunicipioCn": target_cn["municipio"],
    }


def has_decision(text: str, question_fragment: str, answer: str) -> bool:
    return f"{question_fragment} = {answer}" in text


def force_tipo_cliente(text: str, expected_tree: str) -> str:
    if expected_tree == "PED":
        return "CN"
    if has_decision(text, "Es cliente existente?", "Sí"):
        return "CE"
    if has_decision(text, "reactivado?", "Sí"):
        return "CR"
    return "CN"


def normalize_for_rules(value: str) -> str:
    no_marks = "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )
    return no_marks.lower()


def scenario(route: dict[str, str], case_number: int, global_number: int, cns_by_code: dict[str, dict[str, object]]) -> dict[str, object]:
    expanded_id = route["expanded_route_id"]
    class_id = route["final_output_class_id"]
    text = " > ".join([route.get("base_decision_path_text", ""), route.get("subroute_path", "")])
    route_r1 = r1_id(expanded_id)
    seed = int(hashlib.sha256(f"{expanded_id}:{case_number}".encode("utf-8")).hexdigest()[:12], 16)
    rng = random.Random(seed)

    target_cn_code = "1001"
    expected_abfs = ["500001"]
    mode = route["expected_mode"]
    expected_desc = route["final_expected_output"]
    bolson = ""
    expected_tree = "BT"

    if route_r1:
        target_cn_code, expected_abfs, r1_mode = R1_TARGETS[route_r1]
        if mode == "EXACT" and r1_mode == "ACCEPTED_SET":
            mode = "ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON"
    elif "DIRECT_PED" in class_id:
        expected_tree = "PED"
        expected_abfs = [""]
        target_cn_code = ""
    elif "PENDING_BOLSON" in class_id:
        target_cn_code = "9001"
        expected_abfs = [""]
        bolson = "PENDIENTES"
    elif "MORA_BOLSONES" in class_id:
        target_cn_code = "1001"
        expected_abfs = ["500001"]
        bolson = "LISTA_SEGUIMIENTO|CONTAGIO|CCR|BUCKET_2|EMPLEADO_BANTRAB"
    elif "ASSIGN_LAST_ABF" in class_id or "REASSIGN_DISBURSER" in class_id:
        target_cn_code = "7001"
        expected_abfs = ["700101"]

    target_cn = cns_by_code.get(target_cn_code) if target_cn_code else None
    if target_cn is None:
        target_cn = cns_by_code["1001"]

    is_bt = "¿Es cliente BT? = No" not in text
    credito_banca = BANCA_BT if is_bt else BANCA_BP
    cliente_vivienda = "municipio_base_bt"
    cliente_trabajo = "municipio_trabajo_bt"
    if route_r1:
        if "municipio de trabajo" in route.get("candidate_scope", ""):
            cliente_trabajo = str(target_cn["municipio"])
            if "¿Se conoce el municipio de vivienda? = No" in text:
                cliente_vivienda = "SIN_MUNICIPIO"
        else:
            cliente_vivienda = str(target_cn["municipio"])
            if "¿Se conoce el municipio de trabajo? = No" in text:
                cliente_trabajo = "SIN_MUNICIPIO"
    if "¿Se conoce el municipio de vivienda o trabajo? = No" in text:
        cliente_vivienda = "SIN_MUNICIPIO"
        cliente_trabajo = "SIN_MUNICIPIO"

    assigned = "Sí" if any(
        marker in text
        for marker in [
            "¿El cliente está asignado a un ABF de alta? = Sí",
            "¿El ABF y el cliente son de la misma banca?",
            "Mantener la asignación",
        ]
    ) else "No"
    if "¿El cliente está asignado a un ABF de alta? = No" in text:
        assigned = "No"

    abf_sugerido = {
        "abfSugeridoCod": "500001" if assigned == "Sí" else "",
        "abfSugeridoEstado": "Alta" if assigned == "Sí" else "",
        "abfSugeridoEdad": "38" if assigned == "Sí" else "",
        "abfSugeridoCnCod": "1001" if assigned == "Sí" else "",
        "abfSugeridoBanca": BANCA_BT if assigned == "Sí" else "",
        "abfSugeridoRegion": REGION if assigned == "Sí" else "",
        "abfSugeridoMunicipio": "municipio_asignacion_bt" if assigned == "Sí" else "",
        "abfSugeridoOportunidad": "Sugerido" if "mensual? = Sí" in text else ("No_Sugerido" if assigned == "Sí" else ""),
    }

    if "¿El ABF y el cliente son de la misma banca? = No" in text:
        abf_sugerido["abfSugeridoBanca"] = BANCA_BP

    cliente_es_sugerido = "Si" if "mensual? = Sí" in text else "No"
    if "lista de seguimiento" in text.lower() or "empleado bantrab" in text.lower():
        es_trabajador_interno = "S"
    else:
        es_trabajador_interno = "N"

    labor_abf = expected_abfs[0] if expected_abfs and expected_abfs[0] else "700101"
    if route_r1 and labor_abf:
        labor_abf = expected_abfs[0]

    creditos: list[dict[str, object]] = []
    if expected_tree == "PED":
        creditos.append(base_credit(expanded_id, 1, BANCA_BP, cns_by_code["1001"], "500003"))
    elif "sin ningún crédito activo" in text and "reactivado? = No" in text:
        credit = base_credit(expanded_id, 1, credito_banca, target_cn, labor_abf)
        credit["creditoEstado"] = "C"
        creditos.append(credit)
    else:
        creditos.append(base_credit(expanded_id, 1, credito_banca, target_cn, labor_abf))

    if "desembolsado" in route.get("candidate_scope", "") or "último periodo" in text or "último ABF" in text:
        hist_cn = target_cn if route_r1 else cns_by_code["7001"]
        hist_abf = labor_abf if route_r1 else "700101"
        history = base_credit(expanded_id, 2, credito_banca, hist_cn, hist_abf)
        history["creditoFechaConsecion"] = "2026-05-02"
        history["creditoFechaCancelacion"] = "2028-05-02"
        creditos.append(history)

    if "lista de seguimiento" in text.lower():
        mora = base_credit(expanded_id, 3, credito_banca, cns_by_code["1001"], "500001")
        mora["creditoEstado"] = "D"
        creditos.append(mora)

    return {
        "case_id": f"{expanded_id}__{case_number:04d}",
        "seed": seed,
        "codCliente": str(80000000 + global_number),
        "dpiCliente": str(4000000000000 + global_number),
        "clienteEdad": str(35 + rng.randint(0, 3)),
        "clienteGenero": cliente_genero,
        "clienteRegion": REGION,
        "clienteMunicipioVivienda": cliente_vivienda,
        "clienteMunicipioTrabajo": cliente_trabajo,
        "clienteEsSugerido": cliente_es_sugerido,
        "clienteEstabaAsignadoAbf": assigned,
        "clienteEsCarteraDelCnCod": "1001" if assigned == "Sí" else "-1",
        "clienteEsCarteraDelAbfCod": "500001" if assigned == "Sí" else "-1",
        "clienteesTrabajadorBt": es_trabajador_interno,
        **abf_sugerido,
        "creditos": creditos,
        "codCnActual": target_cn_code,
        "codAbfsActuales": expected_abfs[:MAX_ABF_SLOTS],
        "targetCnForGender": target_cn_code,
        "targetAbfGenero": target_abf_genero,
        "codCnAnterior": "1001" if assigned == "Sí" else "-1",
        "codAbfAnterior": "500001" if assigned == "Sí" else "-1",
        "bolson": bolson,
        "expected_control_tree": expected_tree,
        "expected_mode": mode,
        "expected_description": expected_desc,
        "is_random_selection": "Si" if is_random_route(route) else "No",
        "tipo_cliente_expected": "CR" if "reactivado? = Sí" in text else "CE",
    }


def scenario_v2(route: dict[str, str], case_number: int, global_number: int, cns_by_code: dict[str, dict[str, object]]) -> dict[str, object]:
    expanded_id = route["expanded_route_id"]
    class_id = route["final_output_class_id"]
    text = " > ".join([route.get("base_decision_path_text", ""), route.get("subroute_path", "")])
    norm = normalize_for_rules(text)
    route_r1 = r1_id(expanded_id)
    seed = int(hashlib.sha256(f"{expanded_id}:{case_number}".encode("utf-8")).hexdigest()[:12], 16)
    rng = random.Random(seed)

    target_cn_code = "1001"
    expected_abfs = ["500001"]
    mode = route["expected_mode"]
    expected_desc = route["final_expected_output"]
    bolson = ""
    expected_tree = "BT"

    if route_r1:
        target_cn_code, expected_abfs, r1_mode = R1_TARGETS[route_r1]
        if mode == "EXACT" and r1_mode == "ACCEPTED_SET":
            mode = "ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON"
    elif "DIRECT_PED" in class_id:
        expected_tree = "PED"
        expected_abfs = [""]
        target_cn_code = ""
    elif "PENDING_BOLSON" in class_id:
        target_cn_code = "9001"
        expected_abfs = [""]
        bolson = "PENDIENTES"
    elif "MORA_BOLSONES" in class_id:
        target_cn_code = "1001"
        expected_abfs = ["500001"]
        bolson = "LISTA_SEGUIMIENTO|CONTAGIO|CCR|BUCKET_2|EMPLEADO_BANTRAB"
    elif (
        "REASSIGN_DISBURSER" in class_id
        or "ASSIGN_LAST_ABF" in class_id
        or ("ASIGNAR_EL_CLIENTE_A_DICHO_ABF" in class_id and "ultimo abf" in norm)
    ):
        target_cn_code = "7001"
        expected_abfs = ["700101"]

    target_cn = cns_by_code.get(target_cn_code) if target_cn_code else None
    if target_cn is None:
        target_cn = cns_by_code["1001"]

    is_bt = "es cliente bt? = no" not in norm
    is_existing = "es cliente existente? = si" in norm
    is_reactivated = "reactivado? = si" in norm
    tipo_cliente = "CN" if expected_tree == "PED" else ("CE" if is_existing else ("CR" if is_reactivated else "CN"))
    credito_banca = BANCA_BT if is_bt else BANCA_BP

    cliente_vivienda = str(cns_by_code["2001"]["municipio"])
    cliente_trabajo = str(cns_by_code["2002"]["municipio"])
    scope_norm = normalize_for_rules(route.get("candidate_scope", ""))
    if route_r1:
        if "municipio de trabajo" in scope_norm:
            cliente_trabajo = str(target_cn["municipio"])
            if "se conoce el municipio de vivienda? = no" in norm:
                cliente_vivienda = "SIN_MUNICIPIO"
        elif "municipio de vivienda" in scope_norm:
            cliente_vivienda = str(target_cn["municipio"])
            if "se conoce el municipio de trabajo? = no" in norm:
                cliente_trabajo = "SIN_MUNICIPIO"
    if "se conoce el municipio de vivienda? = no" in norm and "municipio de trabajo" in scope_norm:
        cliente_vivienda = "SIN_MUNICIPIO"
    if "se conoce el municipio de vivienda o trabajo? = no" in norm:
        cliente_vivienda = "SIN_MUNICIPIO"
        cliente_trabajo = "SIN_MUNICIPIO"

    cliente_genero = "Masculino"
    target_abf_genero = "Masculino"
    if route_r1 and "sin filtro de genero" in scope_norm:
        target_abf_genero = "Femenino"

    assigned = "Sí" if "el cliente esta asignado a un abf de alta? = si" in norm else "No"
    cliente_es_sugerido = "Si" if "sugerido mensual? = si" in norm else "No"
    es_trabajador_interno = "S" if "lista de seguimiento" in norm or "empleado bantrab" in norm else "N"

    abf_sugerido = {
        "abfSugeridoCod": "500001" if assigned == "Sí" else "",
        "abfSugeridoEstado": "Alta" if assigned == "Sí" else "",
        "abfSugeridoEdad": "38" if assigned == "Sí" else "",
        "abfSugeridoCnCod": "1001" if assigned == "Sí" else "",
        "abfSugeridoBanca": BANCA_BT if assigned == "Sí" else "",
        "abfSugeridoRegion": REGION if assigned == "Sí" else "",
        "abfSugeridoMunicipio": "municipio_asignacion_bt" if assigned == "Sí" else "",
        "abfSugeridoOportunidad": "Sugerido" if cliente_es_sugerido == "Si" else ("No_Sugerido" if assigned == "Sí" else ""),
    }

    labor_abf = expected_abfs[0] if expected_abfs and expected_abfs[0] else "700101"
    creditos: list[dict[str, object]] = []
    seq = 1

    if expected_tree == "PED":
        creditos.append(base_credit(expanded_id, seq, BANCA_BP, cns_by_code["2001"], "200101", tipo_cliente, "C"))
        seq += 1
    elif is_existing:
        active_cn = cns_by_code["1001"] if assigned == "Sí" else cns_by_code["2001"]
        active_abf = "500001" if assigned == "Sí" else "200101"
        creditos.append(base_credit(expanded_id, seq, credito_banca, active_cn, active_abf, tipo_cliente, "D"))
        seq += 1
    elif is_reactivated:
        outside = base_credit(expanded_id, seq, credito_banca, cns_by_code["2003"], "200301", tipo_cliente, "C")
        outside["creditoFechaConsecion"] = "2025-11-15"
        outside["creditoFechaCancelacion"] = "2026-02-15"
        creditos.append(outside)
        seq += 1
    else:
        neutral = base_credit(expanded_id, seq, credito_banca, cns_by_code["2003"], "200301", tipo_cliente, "C")
        neutral["creditoFechaConsecion"] = "2026-01-10"
        neutral["creditoFechaCancelacion"] = "2026-04-10"
        creditos.append(neutral)
        seq += 1

    last_period_yes = "ultimo periodo" in norm and "cosecho un credito? = si" in norm
    last_abf_yes = "ultimo abf que le desembolso un credito sigue de alta? = si" in norm
    last_abf_no = "ultimo abf que le desembolso un credito sigue de alta? = no" in norm
    cliente_ultimo_mes = "Si" if last_period_yes or last_abf_yes or last_abf_no else "No"

    if last_period_yes or last_abf_yes:
        hist_abf = "700102" if "el abf y el cliente son de la misma banca? = no" in norm else "700101"
        history = base_credit(
            expanded_id,
            seq,
            credito_banca,
            cns_by_code["7001"],
            hist_abf,
            tipo_cliente,
            "C",
            labor_banca=BANCA_BP if hist_abf == "700102" else BANCA_BT,
        )
        history["creditoFechaConsecion"] = "2026-05-02"
        history["creditoFechaCancelacion"] = "2028-05-02"
        creditos.append(history)
        seq += 1
    elif last_abf_no:
        history = base_credit(
            expanded_id,
            seq,
            credito_banca,
            cns_by_code["7001"],
            "700103",
            tipo_cliente,
            "C",
            labor_banca=BANCA_BT,
            labor_estado="Baja",
        )
        history["creditoFechaConsecion"] = "2026-05-02"
        history["creditoFechaCancelacion"] = "2028-05-02"
        creditos.append(history)
        seq += 1

    needs_viv_history = "municipio de vivienda" in scope_norm and "con historial de desembolso" in scope_norm
    needs_work_history = "municipio de trabajo" in scope_norm and "con historial de desembolso" in scope_norm
    if needs_viv_history or needs_work_history:
        history = base_credit(expanded_id, seq, credito_banca, target_cn, labor_abf, tipo_cliente, "C")
        history["creditoFechaConsecion"] = "2025-12-10"
        history["creditoFechaCancelacion"] = "2026-03-10"
        creditos.append(history)
        seq += 1

    if "lista de seguimiento" in norm and not any(credito.get("creditoEstado") == "D" for credito in creditos):
        creditos.append(base_credit(expanded_id, seq, credito_banca, cns_by_code["1001"], "500001", tipo_cliente, "D"))

    return {
        "case_id": f"{expanded_id}__{case_number:04d}",
        "seed": seed,
        "codCliente": str(80000000 + global_number),
        "dpiCliente": str(4000000000000 + global_number),
        "clienteEdad": str(35 + rng.randint(0, 3)),
        "clienteGenero": cliente_genero,
        "clienteRegion": REGION,
        "clienteMunicipioVivienda": cliente_vivienda,
        "clienteMunicipioTrabajo": cliente_trabajo,
        "clienteEsSugerido": cliente_es_sugerido,
        "clienteEstabaAsignadoAbf": assigned,
        "clienteEsCarteraDelCnCod": "1001" if assigned == "Sí" else "-1",
        "clienteFueDesembolsadoEnElUltimoMes": cliente_ultimo_mes,
        "clienteEsCarteraDelAbfCod": "500001" if assigned == "Sí" else "-1",
        "clienteesTrabajadorBt": es_trabajador_interno,
        **abf_sugerido,
        "creditos": creditos,
        "codCnActual": target_cn_code,
        "codAbfsActuales": expected_abfs[:MAX_ABF_SLOTS],
        "targetCnForGender": target_cn_code,
        "targetAbfGenero": target_abf_genero,
        "codCnAnterior": "1001" if assigned == "Sí" else "-1",
        "codAbfAnterior": "500001" if assigned == "Sí" else "-1",
        "bolson": bolson,
        "expected_control_tree": expected_tree,
        "expected_mode": mode,
        "expected_description": expected_desc,
        "is_random_selection": "Si" if is_random_route(route) else "No",
        "tipo_cliente_expected": tipo_cliente,
    }


def build_xml(ctx: dict[str, object], cns: list[dict[str, object]]) -> str:
    solicitud_fields = [
        "clienteNombre",
        "clienteCod",
        "clienteEdad",
        "clienteGenero",
        "clienteRegion",
        "clienteMunicipioVivienda",
        "clienteMunicipioTrabajo",
        "clienteEsSugerido",
        "clienteEstabaAsignadoAbf",
        "clienteEsCarteraDelCnCod",
        "clienteFueDesembolsadoEnElUltimoMes",
        "clienteEsCarteraDelAbfCod",
        "abfSugeridoCod",
        "abfSugeridoEstado",
        "abfSugeridoEdad",
        "abfSugeridoCnCod",
        "abfSugeridoBanca",
        "abfSugeridoRegion",
        "abfSugeridoMunicipio",
        "abfSugeridoOportunidad",
        "clienteDpi",
        "clienteesTrabajadorBt",
    ]
    data = dict(ctx)
    data["clienteNombre"] = f"Cliente QA BT {ctx['case_id']}"
    data["clienteCod"] = ctx["codCliente"]
    data["clienteDpi"] = ctx["dpiCliente"]
    first_credit = (ctx["creditos"] or [{}])[0]  # type: ignore[index]
    activo_financiero = "<activoFinanciero>" + "".join(centro_xml(item, ctx) for item in cns) + "</activoFinanciero>"
    xml = [
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:rule="http://bar.foo.com/rule">',
        "<soapenv:Header/><soapenv:Body><rule:entryPointAdmonCarteraV2><arg0>",
        "".join(tag(field, data.get(field, "")) for field in solicitud_fields),
        "<informacionGeneral>",
        tag("fecha", "2026-06-03"),
        "</informacionGeneral>",
        "<activoCrediticio>",
        "".join(credito_xml(credito) for credito in ctx["creditos"]),  # type: ignore[arg-type]
        "</activoCrediticio>",
        activo_financiero,
        "<salidaBlaze><asignacionCredito>",
        tag("clienteCredito", first_credit.get("creditoNo", "")),
        tag("clienteDpi", data["clienteDpi"]),
        tag("cnAsignadoAnteriorCod", ctx.get("codCnAnterior", "")),
        tag("abfAsignadoAnteriorCod", ctx.get("codAbfAnterior", "")),
        "</asignacionCredito></salidaBlaze>",
        "</arg0></rule:entryPointAdmonCarteraV2></soapenv:Body></soapenv:Envelope>",
    ]
    return "".join(xml)


def write_static_catalogs(cns: list[dict[str, object]]) -> None:
    cn_fields = ["cnCod", "cnNombre", "cnEstado", "cnRegion", "cnMunicipio", "cnDepartamento", "abfCount"]
    with (BASE / "00_catalogos" / "cn_catalog.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=cn_fields)
        writer.writeheader()
        for item in cns:
            writer.writerow(
                {
                    "cnCod": item["cod"],
                    "cnNombre": item["nombre"],
                    "cnEstado": item["estado"],
                    "cnRegion": item["region"],
                    "cnMunicipio": item["municipio"],
                    "cnDepartamento": item["departamento"],
                    "abfCount": len(item["abfs"]),  # type: ignore[arg-type]
                }
            )

    with (BASE / "00_catalogos" / "patrono_catalog.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["patronoCod", "patronoNombre"])
        writer.writeheader()
        for idx in range(1, 5):
            writer.writerow({"patronoCod": f"P{idx:03d}", "patronoNombre": f"patrono{idx}"})


def main() -> int:
    start = time.time()
    catalog = load_catalog()
    cns = build_static_catalog()
    cns_by_code = by_code(cns)
    catalog_xml_fingerprint = "<activoFinanciero>" + "".join(centro_xml(item) for item in cns) + "</activoFinanciero>"
    static_hash = hashlib.sha256(catalog_xml_fingerprint.encode("utf-8")).hexdigest()

    for path in [BASE / "00_catalogos", BASE / "01_manifest", FLAT_DIR, BASE / "03_expected", VALIDATION_DIR]:
        path.mkdir(parents=True, exist_ok=True)
    for stale in FLAT_DIR.glob("*.xml"):
        unlink_retry(stale)
    write_static_catalogs(cns)

    manifest_fields = [
        "case_id",
        "expanded_route_id",
        "base_route_id",
        "source_tree",
        "case_number",
        "global_case_number",
        "seed",
        "route_depth",
        "final_rule",
        "final_output_class_id",
        "expected_mode",
        "input_xml_path",
        "input_xml_flat_path",
        "expected_output_path",
        "tree_version",
        "mapping_version",
        "generator_version",
    ]
    expected_fields = [
        "case_id",
        "expanded_route_id",
        "base_route_id",
        "source_tree",
        "expected_mode",
        "final_output_class_id",
        "codCliente",
        "dpiCliente",
        "codCnActual",
        "codAbfActual1",
        "codAbfActual2",
        "codAbfActual3",
        "codAbfActual4",
        "codCnAnterior",
        "codAbfAnterior",
        "bolson",
        "expected_control_tree",
        "expected_description",
        "is_random_selection",
        "tipo_cliente_expected",
    ]
    random_fields = [
        "case_id",
        "expanded_route_id",
        "input_xml_path",
        "expected_mode",
        "codCnActual",
        "codAbfActual1",
        "codAbfActual2",
        "codAbfActual3",
        "codAbfActual4",
    ]

    counts = Counter()
    mode_counts = Counter()
    tree_counts = Counter()
    route_counts = Counter()
    random_rows: list[dict[str, str]] = []
    first_xml = ""
    manifest_rows: list[dict[str, str]] = []
    expected_rows: list[dict[str, str]] = []

    global_number = 0
    for route in catalog:
        for case_number in range(1, CASES_PER_ROUTE + 1):
            global_number += 1
            ctx = scenario_v2(route, case_number, global_number, cns_by_code)
            case_id = str(ctx["case_id"])
            xml_name = f"{case_id}.xml"
            rel_xml = f"02_inputs_xml_flat/{xml_name}"
            xml = build_xml(ctx, cns)
            (FLAT_DIR / xml_name).write_text(xml, encoding="utf-8")
            if not first_xml:
                first_xml = xml

            expected_abfs = list(ctx["codAbfsActuales"])  # type: ignore[arg-type]
            expected_row = {
                "case_id": case_id,
                "expanded_route_id": route["expanded_route_id"],
                "base_route_id": route["base_route_id"],
                "source_tree": route["source_tree"],
                "expected_mode": str(ctx["expected_mode"]),
                "final_output_class_id": route["final_output_class_id"],
                "codCliente": str(ctx["codCliente"]),
                "dpiCliente": str(ctx["dpiCliente"]),
                "codCnActual": str(ctx["codCnActual"]),
                "codCnAnterior": str(ctx["codCnAnterior"]),
                "codAbfAnterior": str(ctx["codAbfAnterior"]),
                "bolson": str(ctx["bolson"]),
                "expected_control_tree": str(ctx["expected_control_tree"]),
                "expected_description": str(ctx["expected_description"]),
                "is_random_selection": str(ctx["is_random_selection"]),
                "tipo_cliente_expected": str(ctx["tipo_cliente_expected"]),
            }
            for idx in range(MAX_ABF_SLOTS):
                expected_row[f"codAbfActual{idx + 1}"] = expected_abfs[idx] if idx < len(expected_abfs) else ""
            expected_rows.append(expected_row)

            manifest_rows.append(
                {
                    "case_id": case_id,
                    "expanded_route_id": route["expanded_route_id"],
                    "base_route_id": route["base_route_id"],
                    "source_tree": route["source_tree"],
                    "case_number": str(case_number),
                    "global_case_number": str(global_number),
                    "seed": str(ctx["seed"]),
                    "route_depth": route["route_depth"],
                    "final_rule": route["final_rule"],
                    "final_output_class_id": route["final_output_class_id"],
                    "expected_mode": str(ctx["expected_mode"]),
                    "input_xml_path": rel_xml,
                    "input_xml_flat_path": rel_xml,
                    "expected_output_path": "03_expected/expected_outputs.csv",
                    "tree_version": TREE_VERSION,
                    "mapping_version": MAPPING_VERSION,
                    "generator_version": RUN_VERSION,
                }
            )

            if str(ctx["is_random_selection"]) == "Si":
                random_rows.append({field: expected_row.get(field, "") for field in random_fields} | {"input_xml_path": rel_xml})

            counts["total"] += 1
            route_counts[route["expanded_route_id"]] += 1
            mode_counts[str(ctx["expected_mode"])] += 1
            tree_counts[str(ctx["expected_control_tree"])] += 1

    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=manifest_fields)
        writer.writeheader()
        writer.writerows(manifest_rows)
    with EXPECTED.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=expected_fields)
        writer.writeheader()
        writer.writerows(expected_rows)

    with (VALIDATION_DIR / "random_case_id.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=random_fields)
        writer.writeheader()
        writer.writerows(random_rows)
    with (VALIDATION_DIR / "random_candidates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*random_fields, "candidate_valid_flag", "candidate_selected_flag_after_blaze"])
        writer.writeheader()
        for row in random_rows:
            writer.writerow(row | {"candidate_valid_flag": "Si", "candidate_selected_flag_after_blaze": ""})
    with (VALIDATION_DIR / "random_response_template.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["case_id", "expanded_route_id", "input_xml_path", "actual_cod_cn_actual", "actual_cod_abf_actual"],
        )
        writer.writeheader()
        for row in random_rows:
            writer.writerow(
                {
                    "case_id": row["case_id"],
                    "expanded_route_id": row["expanded_route_id"],
                    "input_xml_path": row["input_xml_path"],
                    "actual_cod_cn_actual": "",
                    "actual_cod_abf_actual": "",
                }
            )
    with (VALIDATION_DIR / "route_generation_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["expanded_route_id", "generated_cases"])
        writer.writeheader()
        for route_id, count in sorted(route_counts.items()):
            writer.writerow({"expanded_route_id": route_id, "generated_cases": count})

    if first_xml:
        (VALIDATION_DIR / "sample_input_bt.xml").write_text(first_xml, encoding="utf-8")
        (VALIDATION_DIR / "first_xml_preview.txt").write_text(first_xml[:12000], encoding="utf-8")

    summary = {
        "artifact": "QA BT",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generator_version": RUN_VERSION,
        "tree_version": TREE_VERSION,
        "cases_per_route": CASES_PER_ROUTE,
        "expanded_routes_generated": len(route_counts),
        "total_xml_inputs_generated": counts["total"],
        "flat_xml_folder": "02_inputs_xml_flat",
        "flat_xml_count": len(list(FLAT_DIR.glob("*.xml"))),
        "manifest": str(MANIFEST),
        "expected_outputs": str(EXPECTED),
        "expected_mode_counts": dict(mode_counts),
        "expected_control_tree_counts": dict(tree_counts),
        "random_cases_generated": len(random_rows),
        "static_cn_catalog_count": len(cns),
        "static_abf_total": sum(len(item["abfs"]) for item in cns),  # type: ignore[arg-type]
        "activo_financiero_static_hash": static_hash,
        "duration_seconds": round(time.time() - start, 2),
        "notes": [
            "Todos los XML de entrada se escriben únicamente en 02_inputs_xml_flat.",
            "No se crea 02_inputs_xml ni carpetas por regla/ruta.",
            "Las rutas de Regla no. 1 usan codAbfActual1..4 para representar salidas determinísticas o conjuntos aceptados.",
        ],
    }
    (VALIDATION_DIR / "generation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
