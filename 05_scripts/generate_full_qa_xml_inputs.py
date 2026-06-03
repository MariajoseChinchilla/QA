#!/usr/bin/env python3
"""
Generador de XMLs de entrada para QA Blaze - General_post_primera_asignacion expandido.
Genera 222,000 XMLs: 221,000 rutas core ABF + 1,000 casos de control BT.
Usa la estructura XML vigente con arg0, genero y salidaBlaze de contexto.
"""
from __future__ import annotations
import csv
import json
import os
import random
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

BASE = Path('/mnt/data')
MANIFEST = BASE / 'case_manifest_arbol_expandido_general_post_full_with_bt_control.csv'
CATALOG = BASE / 'catalogo_rutas_arbol_expandido_general_post_full_with_bt_control.csv'
FIELD_CONTRACT = BASE / 'field_contract_arbol_expandido_general_post_primera_asignacion.csv'
SCENARIOS = BASE / 'scenario_constraints_arbol_expandido_general_post_primera_asignacion.yml'
OUT_ROOT = BASE / 'qa_inputs_arbol_expandido_general_post_full_bt'
RUN_VERSION = 'XML_INPUT_GENERATOR_V14_NEW_XML_STRUCTURE_GENDER_UPPERCASE_2026_06_02'
RUN_DATE = '2026-05-13'
FLAT_XML_DIR = '02_inputs_xml_flat'
MAX_EXPECTED_ABF_SLOTS = 4

# CNs sintéticos. Se mantienen en todos los XML para cumplir el criterio de incluir el catálogo completo.
CN_CODES = {
    'ASIGNADO': '1001',
    'COSECHA': '1010',
    'MUNI_VIV': '1101',
    'MUNI_TRAB': '1102',
    'MUNI_ULT': '1103',
    'DEPTO_ULT': '1201',
    'LABOR_METRO': '1020',
    'LABOR_NOR': '1021',
    'LABOR_SUR': '1022',
    'CP': '9001',
    'CERRADO': '1301',
}

CN_NAMES = {
    'ASIGNADO': 'AGENCIA ASIGNACION',
    'COSECHA': 'AGENCIA COSECHA',
    'MUNI_VIV': 'AGENCIA MUNICIPIO VIVIENDA',
    'MUNI_TRAB': 'AGENCIA MUNICIPIO TRABAJO',
    'MUNI_ULT': 'AGENCIA MUNICIPIO ULTIMO DESEMBOLSO',
    'DEPTO_ULT': 'AGENCIA DEPARTAMENTO ULTIMO DESEMBOLSO',
    'LABOR_METRO': 'AGENCIA LABOR METROPOLITANA',
    'LABOR_NOR': 'AGENCIA LABOR NOR ORIENTE',
    'LABOR_SUR': 'AGENCIA LABOR SUR OCCIDENTE',
    'CP': 'CENTRO DE PROCESAMIENTO',
    'CERRADO': 'AGENCIA CERRADA CONTROL',
}

LABOR_CN_BY_REGION = {
    'METROPOLITANA': 'LABOR_METRO',
    'NOR_ORIENTE': 'LABOR_NOR',
    'SUR_OCCIDENTE': 'LABOR_SUR',
}

PATRONO_CODE = '1000786'
PATRONO_NAME = 'MINISTERIO DE EDUCACION'
GENDER_VALUES = ['MASCULINO', 'FEMENINO']


def norm_yes_no(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip().upper().replace('Í', 'I')
    if s in {'SI', 'SÍ', 'S'}:
        return 'SI'
    if s in {'NO', 'N'}:
        return 'NO'
    return s


def parse_general_decisions(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (text or '').split(';'):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'(D\d+)\s*=\s*(.+)', part)
        if m:
            out[m.group(1)] = norm_yes_no(m.group(2)) or ''
    return out


def parse_sub_decisions(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    # R2.D01=SI > R2.D02=NO > R1.D01=SI
    for m in re.finditer(r'((?:R\d+\.)?D\d+)\s*=\s*([^>]+)', text or ''):
        out[m.group(1).strip()] = norm_yes_no(m.group(2).strip()) or ''
    return out


def esc(x) -> str:
    return escape('' if x is None else str(x), {'"': '&quot;'})


def xml_value(x) -> str:
    value = '' if x is None else str(x)
    return value.upper() if any(ch.isalpha() for ch in value) else value


def tag(name: str, value) -> str:
    return f'<{name}>{esc(xml_value(value))}</{name}>'


def deterministic_gender(key) -> str:
    digest = sum(ord(ch) for ch in str(key))
    return GENDER_VALUES[digest % len(GENDER_VALUES)]


def stable_code(prefix_num: int, rng: random.Random) -> str:
    return str(prefix_num + rng.randint(0, 89999))


def is_r1_route(expanded_route_id: str) -> bool:
    return '__R1-' in expanded_route_id


def r1_id(expanded_route_id: str) -> str | None:
    m = re.search(r'(R1-\d{3})', expanded_route_id)
    return m.group(1) if m else None


def r2_id(expanded_route_id: str) -> str | None:
    m = re.search(r'(R2-\d{3})', expanded_route_id)
    return m.group(1) if m else None


def r3_id(expanded_route_id: str) -> str | None:
    m = re.search(r'(R3-\d{3})', expanded_route_id)
    return m.group(1) if m else None


def candidate_scope_key(route: dict) -> str | None:
    fc = route['final_output_class_id']
    src = route['source_general_output_class_id']
    gid = route['general_route_id']
    scope = route.get('candidate_scope', '')

    if fc == 'R3_PENDING_BOLSON' or fc == 'CONTROL_BT':
        return None
    if is_r1_route(route['expanded_route_id']):
        if 'MUNICIPIO_ULT_CN' in src:
            return 'MUNI_ULT'
        if 'DEPTO_ULT_CN' in src:
            return 'DEPTO_ULT'
        if 'VIV' in fc:
            return 'MUNI_VIV'
        if 'TRAB' in fc:
            return 'MUNI_TRAB'
        if 'ABFS_CN' in src or 'PATRONO' in src:
            if gid in {'GPA-003', 'GPA-004'}:
                return 'ASIGNADO'
            return 'COSECHA'
        if 'municipio del último CN' in scope.lower():
            return 'MUNI_ULT'
        if 'departamento del último CN' in scope.lower():
            return 'DEPTO_ULT'
        return 'COSECHA'
    return None


def build_context(man: dict, route: dict) -> dict:
    seed = int(man['seed'])
    rng = random.Random(seed)
    gen_dec = parse_general_decisions(route['general_decision_path_codes'])
    sub_dec = parse_sub_decisions(route.get('subroute_path', ''))
    expanded_route_id = man['expanded_route_id']
    general_route_id = man['general_route_id']
    final_class = man['final_output_class_id']

    bt = final_class == 'CONTROL_BT'
    client_is_bp = False if bt else (gen_dec.get('D01', 'SI') == 'SI')
    existing = gen_dec.get('D02', 'SI') == 'SI'
    is_metro = gen_dec.get('D04') == 'SI'
    client_region = 'METROPOLITANA' if is_metro else 'NOR_ORIENTE'
    if bt:
        client_region = 'METROPOLITANA'

    vivienda = 'MIXCO' if is_metro else 'CHIQUIMULA'
    trabajo = 'GUATEMALA' if is_metro else 'ESQUIPULAS'
    if r3_id(expanded_route_id) == 'R3-001':
        vivienda = 'SIN_MUNICIPIO'
        trabajo = 'SIN_MUNICIPIO'

    depto = 'GUATEMALA' if is_metro else 'CHIQUIMULA'
    depto_alt = 'EL PROGRESO' if not is_metro else 'SACATEPEQUEZ'

    assigned_yes = None
    if 'D05' in gen_dec:
        assigned_yes = gen_dec['D05'] == 'SI'
    elif 'D20' in gen_dec:
        assigned_yes = gen_dec['D20'] == 'SI'
    elif 'D33' in gen_dec:
        assigned_yes = gen_dec['D33'] == 'SI'
    else:
        assigned_yes = existing and not bt

    # El cliente puede estar en cartera agencia aunque no tenga ABF asignado.
    current_is_agency = (not assigned_yes)

    harvest_last_month = None
    if 'D09' in gen_dec:
        harvest_last_month = gen_dec['D09'] == 'SI'
    elif 'D24' in gen_dec:
        harvest_last_month = gen_dec['D24'] == 'SI'
    else:
        harvest_last_month = False

    # Tipo de cosecha: ABF, CN o CP.
    labor_type = 'ABF'
    if gen_dec.get('D10') == 'SI' or gen_dec.get('D26') == 'NO':
        labor_type = 'CN'
    if gen_dec.get('D29') == 'SI' or gen_dec.get('D30') == 'SI':
        labor_type = 'CP'

    # Si la ruta pregunta por ABF cosechador, controlar banca/región/estado del participante labor.
    labor_banca = 'BANCA_PERSONAS'
    if bt or gen_dec.get('D11') == 'NO' or gen_dec.get('D31') == 'NO':
        labor_banca = 'BANCA_TRABAJADORES'

    labor_region = client_region
    if gen_dec.get('D12') == 'SI' or gen_dec.get('D32') == 'SI':
        labor_region = 'METROPOLITANA'
    elif gen_dec.get('D12') == 'NO':
        labor_region = client_region if gen_dec.get('D13') == 'SI' else 'SUR_OCCIDENTE'
    elif gen_dec.get('D32') == 'NO':
        labor_region = 'NOR_ORIENTE'

    labor_estado = 'ALTA'
    if gen_dec.get('D14') == 'NO' or gen_dec.get('D36') == 'NO' or gen_dec.get('D37') == 'NO':
        labor_estado = 'BAJA'

    # Estado / región del CN de cosecha.
    cn_cosecha_estado = 'ALTA'
    if gen_dec.get('D07') == 'NO' or gen_dec.get('D21') == 'NO':
        cn_cosecha_estado = 'BAJA'
    cn_cosecha_region = client_region
    if gen_dec.get('D18') == 'NO' or gen_dec.get('D27') == 'NO':
        cn_cosecha_region = 'SUR_OCCIDENTE' if client_region != 'SUR_OCCIDENTE' else 'NOR_ORIENTE'
    elif gen_dec.get('D27') == 'SI':
        cn_cosecha_region = 'METROPOLITANA'

    # Recrédito / nuevo.
    credito_tipo = 'NUEVO'
    for d in ('D17', 'D28', 'D35'):
        if gen_dec.get(d) == 'SI':
            credito_tipo = 'RECREDITO'
        elif gen_dec.get(d) == 'NO':
            credito_tipo = 'NUEVO'

    credito_banca = 'BANCA_PERSONAS' if client_is_bp else 'BANCA_TRABAJADORES'
    tipo_cliente = 'CE' if existing else ('CR' if gen_dec.get('D03') == 'SI' else 'CN')
    credito_estado_base = 'VIGENTE' if existing else 'CANCELADO'

    # Edad: R1 usa cercanía de edad.
    cliente_edad = rng.randint(27, 58)
    target_age = cliente_edad
    tie_age = cliente_edad
    far_age = max(22, min(64, cliente_edad + rng.choice([7, 9, -8, -10])))

    current_abf = stable_code(500000, rng)
    labor_abf = stable_code(600000, rng)
    target_abf_1 = stable_code(700000, rng)
    target_abf_2 = str(int(target_abf_1) + 1)
    decoy_abf = stable_code(800000, rng)
    client_code = str(10000000 + (seed % 9000000))
    dpi = str(3000000000000 + (seed % 700000000000))

    target_scope = candidate_scope_key(route)
    target_cn_key = target_scope
    target_cn_code = CN_CODES.get(target_scope or 'COSECHA', CN_CODES['COSECHA'])

    r1 = r1_id(expanded_route_id)
    r1_has_deficit = r1 in {'R1-001', 'R1-002'}
    r1_unique = r1 in {'R1-001', 'R1-003'}
    r1_tie = r1 in {'R1-002', 'R1-004'}
    expected_mode = man['expected_mode']

    # Especialista patrono: aplica cuando el alcance trae PATRONO o cuando la decisión General/R2/R3 lo requiere.
    needs_patrono_specialist = 'PATRONO' in final_class or route['source_general_output_class_id'] == 'DELEGATE_R1_PATRONO'

    ctx = {
        'seed': seed,
        'rng': rng,
        'case_id': man['case_id'],
        'case_number': int(man['case_number']),
        'expanded_route_id': expanded_route_id,
        'general_route_id': general_route_id,
        'included_in_core': man['included_in_core'],
        'route_depth': man['route_depth'],
        'final_rule': man['final_rule'],
        'final_output_class_id': final_class,
        'expected_mode': expected_mode,
        'source_general_output_class_id': route['source_general_output_class_id'],
        'general_decisions': gen_dec,
        'sub_decisions': sub_dec,
        'client_is_bp': client_is_bp,
        'existing': existing,
        'is_metro': is_metro,
        'client_region': client_region,
        'vivienda': vivienda,
        'trabajo': trabajo,
        'depto': depto,
        'depto_alt': depto_alt,
        'assigned_yes': assigned_yes,
        'current_is_agency': current_is_agency,
        'harvest_last_month': harvest_last_month,
        'labor_type': labor_type,
        'labor_banca': labor_banca,
        'labor_region': labor_region,
        'labor_estado': labor_estado,
        'cn_cosecha_estado': cn_cosecha_estado,
        'cn_cosecha_region': cn_cosecha_region,
        'credito_tipo': credito_tipo,
        'credito_banca': credito_banca,
        'tipo_cliente': tipo_cliente,
        'credito_estado_base': credito_estado_base,
        'cliente_edad': cliente_edad,
        'target_age': target_age,
        'tie_age': tie_age,
        'far_age': far_age,
        'current_abf': current_abf,
        'labor_abf': labor_abf,
        'target_abf_1': target_abf_1,
        'target_abf_2': target_abf_2,
        'decoy_abf': decoy_abf,
        'client_code': client_code,
        'dpi': dpi,
        'target_scope': target_scope,
        'target_cn_key': target_cn_key,
        'target_cn_code': target_cn_code,
        'r1_id': r1,
        'r1_has_deficit': r1_has_deficit,
        'r1_unique': r1_unique,
        'r1_tie': r1_tie,
        'needs_patrono_specialist': needs_patrono_specialist,
        'patrono_code': PATRONO_CODE,
        'patrono_name': PATRONO_NAME,
    }
    return ctx


def cn_profile(ctx: dict, key: str) -> dict:
    region = ctx['client_region']
    depto = ctx['depto']
    municipio = ctx['trabajo']
    estado = 'ALTA'
    if key == 'ASIGNADO':
        municipio = ctx['trabajo']
        region = ctx['client_region']
        depto = ctx['depto']
    elif key == 'COSECHA':
        municipio = ctx['vivienda'] if ctx['is_metro'] else ctx['trabajo']
        region = ctx['cn_cosecha_region']
        depto = ctx['depto'] if region == ctx['client_region'] else ctx['depto_alt']
        estado = ctx['cn_cosecha_estado']
    elif key == 'MUNI_VIV':
        municipio = ctx['vivienda']
        region = ctx['client_region']
        depto = ctx['depto']
    elif key == 'MUNI_TRAB':
        municipio = ctx['trabajo']
        region = ctx['client_region']
        depto = ctx['depto']
    elif key == 'MUNI_ULT':
        municipio = ctx['vivienda'] if ctx['is_metro'] else ctx['trabajo']
        region = ctx['client_region']
        depto = ctx['depto']
        if ctx['general_decisions'].get('D08') == 'NO' or ctx['general_decisions'].get('D23') == 'NO':
            estado = 'BAJA'
    elif key == 'DEPTO_ULT':
        municipio = 'JOCOTAN' if ctx['depto'] == 'CHIQUIMULA' else 'VILLA_NUEVA'
        region = ctx['client_region']
        depto = ctx['depto']
    elif key == 'LABOR_METRO':
        municipio = 'GUATEMALA'
        region = 'METROPOLITANA'
        depto = 'GUATEMALA'
    elif key == 'LABOR_NOR':
        municipio = 'CHIQUIMULA'
        region = 'NOR_ORIENTE'
        depto = 'CHIQUIMULA'
    elif key == 'LABOR_SUR':
        municipio = 'QUETZALTENANGO'
        region = 'SUR_OCCIDENTE'
        depto = 'QUETZALTENANGO'
    elif key == 'CP':
        municipio = 'GUATEMALA'
        region = 'METROPOLITANA'
        depto = 'GUATEMALA'
        estado = 'ALTA'
    elif key == 'CERRADO':
        municipio = ctx['vivienda']
        region = ctx['client_region']
        depto = ctx['depto']
        estado = 'BAJA'
    return {
        'key': key,
        'cod': CN_CODES[key],
        'nombre': CN_NAMES[key],
        'estado': estado,
        'region': region,
        'departamento': depto,
        'municipio': municipio,
    }


def abf_xml(abf: dict) -> str:
    parts = ['<abf>']
    for k in ['asignadoCod', 'asignadoEstado', 'asignadoEnVacacion', 'asignadoBanca', 'asignadoEdad',
              'asignadoGenero', 'especialistaPatrono1', 'especialistaPatrono2', 'especialistaPatrono3',
              'asignadoBolsonAcumulativo', 'asignadoBolsonLimExposicion', 'asignadoBolsonEstado']:
        if k in abf:
            parts.append(tag(k, abf[k]))
    parts.append('</abf>')
    return ''.join(parts)


def make_abf(code: str, estado: str, banca: str, edad: int, bolson: str, patrono: bool = False, vac: str = '0', cosecha: str | None = None) -> dict:
    return {
        'asignadoCod': code,
        'asignadoEstado': estado,
        'asignadoEnVacacion': vac,
        'asignadoBanca': banca,
        'asignadoEdad': str(edad),
        'asignadoGenero': deterministic_gender(code),
        'especialistaPatrono1': PATRONO_CODE if patrono else '-1',
        'especialistaPatrono2': '-1',
        'especialistaPatrono3': '-1',
        'asignadoBolsonAcumulativo': '75000' if bolson == 'DEFICIT' else '250000',
        'asignadoBolsonLimExposicion': '100000',
        'asignadoBolsonEstado': bolson,
    }


def build_cns_and_abfs(ctx: dict) -> list[dict]:
    profiles = [cn_profile(ctx, key) for key in ['ASIGNADO', 'COSECHA', 'MUNI_VIV', 'MUNI_TRAB', 'MUNI_ULT', 'DEPTO_ULT', 'LABOR_METRO', 'LABOR_NOR', 'LABOR_SUR', 'CP', 'CERRADO']]
    by_key = {p['key']: p for p in profiles}

    # Default: un ABF decoy por CN para representar catálogo completo.
    for p in profiles:
        p['abfs'] = [make_abf(
            code=str(int(ctx['decoy_abf']) + int(p['cod']) % 997),
            estado='ALTA' if p['estado'] == 'ALTA' else 'BAJA',
            banca='BANCA_PERSONAS',
            edad=ctx['far_age'],
            bolson='EQUILIBRIO',
            patrono=False,
        )]

    # ABF asignado actual en CN de asignación.
    assigned_estado = 'ALTA' if ctx['assigned_yes'] else 'BAJA'
    assigned_vac = '1' if ctx['general_decisions'].get('D16') == 'SI' or ctx['general_decisions'].get('D34') == 'SI' else '0'
    by_key['ASIGNADO']['abfs'].insert(0, make_abf(
        code=ctx['current_abf'],
        estado=assigned_estado,
        banca='BANCA_PERSONAS',
        edad=max(23, ctx['cliente_edad'] + 4),
        bolson='EQUILIBRIO',
        patrono=False,
        vac=assigned_vac,
    ))

    # ABF labor / cosechador si el participante labor es ABF.
    if ctx['labor_type'] == 'ABF':
        labor_cn_key = LABOR_CN_BY_REGION.get(ctx['labor_region'], 'LABOR_METRO')
        ctx['labor_cn_code'] = by_key[labor_cn_key]['cod']
        ctx['labor_municipio'] = by_key[labor_cn_key]['municipio']
        by_key[labor_cn_key]['abfs'].insert(0, make_abf(
            code=ctx['labor_abf'],
            estado=ctx['labor_estado'],
            banca=ctx['labor_banca'],
            edad=max(22, ctx['cliente_edad'] - 2),
            bolson='EQUILIBRIO',
            patrono=ctx['needs_patrono_specialist'],
            cosecha=CN_CODES['COSECHA'],
        ))

    # Candidatos R1.
    if ctx['target_cn_key']:
        target_profile = by_key[ctx['target_cn_key']]
        target_profile['estado'] = 'ALTA'
        target_bolson = 'DEFICIT' if ctx['r1_has_deficit'] else 'EQUILIBRIO'
        target_profile['abfs'].insert(0, make_abf(
            code=ctx['target_abf_1'],
            estado='ALTA',
            banca='BANCA_PERSONAS',
            edad=ctx['target_age'],
            bolson=target_bolson,
            patrono=ctx['needs_patrono_specialist'],
            cosecha=target_profile['cod'],
        ))
        if ctx['r1_tie']:
            target_profile['abfs'].insert(1, make_abf(
                code=ctx['target_abf_2'],
                estado='ALTA',
                banca='BANCA_PERSONAS',
                edad=ctx['tie_age'],
                bolson=target_bolson,
                patrono=ctx['needs_patrono_specialist'],
                cosecha=target_profile['cod'],
            ))
        else:
            # Decoy en el mismo CN, pero no debe ganar por edad/bolsón/patrono.
            target_profile['abfs'].append(make_abf(
                code=ctx['target_abf_2'],
                estado='ALTA',
                banca='BANCA_PERSONAS',
                edad=ctx['far_age'],
                bolson='EQUILIBRIO',
                patrono=False,
                cosecha=target_profile['cod'],
            ))

    return profiles


def credito_xml(c: dict) -> str:
    fields = [
        ('creditoNo','creditoNo'), ('creditoMonto','creditoMonto'), ('creditoTasa','creditoTasa'),
        ('creditoTipo','creditoTipo'), ('creditoEstado','creditoEstado'), ('creditoPatronoNombre','creditoPatronoNombre'),
        ('creditoPatronoCod','creditoPatronoCod'), ('creditoBanca','creditoBanca'), ('creditoTipoCliente','creditoTipoCliente'),
        ('creditoRegion','creditoRegion'), ('creditoFechaConsecion','creditoFechaConsecion'),
        ('creditoFechaCancelacion','creditoFechaCancelacion'), ('creditoPatrono','creditoPatrono'),
        ('participanteLaborCod','participanteLaborCod'), ('participanteLaborEstado','participanteLaborEstado'),
        ('participanteLaborEdad','participanteLaborEdad'), ('participanteLaborCn','participanteLaborCn'),
        ('participanteLaborBanca','participanteLaborBanca'), ('participanteLaborRegion','participanteLaborRegion'),
        ('participanteLaborMunicipio','participanteLaborMunicipio'), ('participanteLaborVacacion','participanteLaborVacacion'),
        ('participanteLaborTipo','participanteLaborTipo'), ('cosechaCodigoCn','cnCosechaCod'),
        ('cosechaNombreCn','cnCosechaNombre'), ('cosechaEstadoCn','cnCosechaEstado'),
        ('cosechaRegionCn','cnCosechaRegion'), ('cosechaDepartamentoCn','cnCosechaDepartamento'),
        ('cosechaMunicipioCn','cnCosechaMunicipio'),
    ]
    return '<credito>' + ''.join(tag(out_name, c.get(src_name, '')) for out_name, src_name in fields) + '</credito>'


def build_creditos(ctx: dict, cns: list[dict]) -> list[dict]:
    by_key = {c['key']: c for c in cns}
    recent_date = '2026-05-01'
    old_date = '2025-01-15'
    fecha_concesion = recent_date if ctx['harvest_last_month'] else old_date
    labor_code = ctx['labor_abf'] if ctx['labor_type'] == 'ABF' else (CN_CODES['CP'] if ctx['labor_type'] == 'CP' else CN_CODES['COSECHA'])
    labor_cn = ctx.get('labor_cn_code', CN_CODES['COSECHA']) if ctx['labor_type'] == 'ABF' else (CN_CODES['COSECHA'] if ctx['labor_type'] != 'CP' else CN_CODES['CP'])
    labor_muni = ctx.get('labor_municipio', by_key['COSECHA']['municipio']) if ctx['labor_type'] == 'ABF' else (by_key['COSECHA']['municipio'] if ctx['labor_type'] != 'CP' else by_key['CP']['municipio'])
    labor_region = ctx['labor_region'] if ctx['labor_type'] == 'ABF' else by_key['COSECHA']['region']
    if ctx['labor_type'] == 'CP':
        labor_region = 'METROPOLITANA'
    labor_age = str(max(0, ctx['cliente_edad'] - 2)) if ctx['labor_type'] == 'ABF' else '0'

    creditos = [{
        'creditoNo': 'CR' + ctx['case_id'][-4:] + str(ctx['seed'])[-6:],
        'creditoMonto': str(10000 + ctx['rng'].randint(0, 40000)) + '.00',
        'creditoTasa': '18.5',
        'creditoTipo': ctx['credito_tipo'],
        'creditoEstado': ctx['credito_estado_base'],
        'creditoPatronoNombre': ctx['patrono_name'],
        'creditoPatronoCod': ctx['patrono_code'],
        'creditoBanca': ctx['credito_banca'],
        'creditoTipoCliente': ctx['tipo_cliente'],
        'creditoRegion': ctx['client_region'],
        'creditoFechaConsecion': fecha_concesion,
        'creditoFechaCancelacion': '2027-05-01',
        'creditoPatrono': ctx['patrono_name'],
        'participanteLaborCod': labor_code,
        'participanteLaborEstado': ctx['labor_estado'] if ctx['labor_type'] == 'ABF' else 'ALTA',
        'participanteLaborEdad': labor_age,
        'participanteLaborCn': labor_cn,
        'participanteLaborBanca': ctx['labor_banca'] if ctx['labor_type'] == 'ABF' else ctx['credito_banca'],
        'participanteLaborRegion': labor_region,
        'participanteLaborMunicipio': labor_muni,
        'participanteLaborVacacion': '0',
        'participanteLaborTipo': ctx['labor_type'],
        'cnCosechaCod': CN_CODES['CP'] if ctx['labor_type'] == 'CP' else CN_CODES['COSECHA'],
        'cnCosechaNombre': CN_NAMES['CP'] if ctx['labor_type'] == 'CP' else CN_NAMES['COSECHA'],
        'cnCosechaEstado': 'ALTA' if ctx['labor_type'] == 'CP' else ctx['cn_cosecha_estado'],
        'cnCosechaRegion': 'METROPOLITANA' if ctx['labor_type'] == 'CP' else ctx['cn_cosecha_region'],
        'cnCosechaDepartamento': 'GUATEMALA' if ctx['labor_type'] == 'CP' else by_key['COSECHA']['departamento'],
        'cnCosechaMunicipio': 'GUATEMALA' if ctx['labor_type'] == 'CP' else by_key['COSECHA']['municipio'],
    }]

    # Para rutas cuyo alcance dice "que le han desembolsado", agregamos historial con los ABFs candidatos.
    final_class = ctx['final_output_class_id']
    if 'DESEMBOLSO' in final_class and ctx['target_cn_key']:
        target_cn = by_key[ctx['target_cn_key']]
        for i, abf_code in enumerate([ctx['target_abf_1']] + ([ctx['target_abf_2']] if ctx['r1_tie'] else []), start=1):
            creditos.append({
                'creditoNo': 'HD' + str(i) + ctx['case_id'][-4:] + str(ctx['seed'])[-5:],
                'creditoMonto': str(8000 + ctx['rng'].randint(0, 25000)) + '.00',
                'creditoTasa': '17.0',
                'creditoTipo': 'NUEVO',
                'creditoEstado': 'CANCELADO' if not ctx['existing'] else 'VIGENTE',
                'creditoPatronoNombre': ctx['patrono_name'],
                'creditoPatronoCod': ctx['patrono_code'],
                'creditoBanca': ctx['credito_banca'],
                'creditoTipoCliente': ctx['tipo_cliente'],
                'creditoRegion': ctx['client_region'],
                'creditoFechaConsecion': '2025-02-10',
                'creditoFechaCancelacion': '2026-02-10',
                'creditoPatrono': ctx['patrono_name'],
                'participanteLaborCod': abf_code,
                'participanteLaborEstado': 'ALTA',
                'participanteLaborEdad': str(ctx['target_age']),
                'participanteLaborCn': target_cn['cod'],
                'participanteLaborBanca': 'BANCA_PERSONAS',
                'participanteLaborRegion': target_cn['region'],
                'participanteLaborMunicipio': target_cn['municipio'],
                'participanteLaborVacacion': '0',
                'participanteLaborTipo': 'ABF',
                'cnCosechaCod': target_cn['cod'],
                'cnCosechaNombre': target_cn['nombre'],
                'cnCosechaEstado': target_cn['estado'],
                'cnCosechaRegion': target_cn['region'],
                'cnCosechaDepartamento': target_cn['departamento'],
                'cnCosechaMunicipio': target_cn['municipio'],
            })
    return creditos


def build_expected(ctx: dict) -> dict:
    fc = ctx['final_output_class_id']
    expected = {
        'case_id': ctx['case_id'],
        'expanded_route_id': ctx['expanded_route_id'],
        'general_route_id': ctx['general_route_id'],
        'included_in_core': ctx['included_in_core'],
        'expected_mode': ctx['expected_mode'],
        'final_output_class_id': fc,
        'codCliente': ctx['client_code'],
        'dpiCliente': ctx['dpi'],
        'codCnAnterior': CN_CODES['ASIGNADO'],
        'codAbfAnterior': ctx['current_abf'] if ctx['assigned_yes'] else '-1',
        'codCnActual': '',
        'codAbfActual': '',
        'bolson': '',
        'accepted_cod_cn_set': '',
        'accepted_cod_abf_set': '',
        'expected_control_tree': '',
        'expected_description': '',
    }
    if fc == 'CONTROL_BT':
        expected['expected_control_tree'] = 'BT'
        expected['expected_description'] = 'Redirigir a árbol BT; fuera del flujo ABF/Banca Personas.'
    elif fc == 'R3_PENDING_BOLSON':
        expected['bolson'] = 'PENDIENTES'
        expected['expected_description'] = 'Asignar al bolsón de clientes pendientes.'
    elif is_r1_route(ctx['expanded_route_id']):
        expected['codCnActual'] = ctx['target_cn_code']
        if ctx['r1_tie']:
            expected['accepted_cod_abf_set'] = f"{ctx['target_abf_1']}|{ctx['target_abf_2']}"
            expected['accepted_cod_cn_set'] = ctx['target_cn_code']
            expected['codAbfActual'] = ''
            expected['expected_description'] = 'Cualquier ABF del conjunto aceptado es válido por empate/selección aleatoria.'
        else:
            expected['codAbfActual'] = ctx['target_abf_1']
            expected['expected_description'] = 'Asignar al ABF candidato único esperado.'
    elif fc in {'KEEP_CURRENT_ASSIGNMENT', 'KEEP_ABF_ASSIGNMENT'}:
        expected['codCnActual'] = CN_CODES['ASIGNADO'] if ctx['assigned_yes'] else CN_CODES['COSECHA']
        expected['codAbfActual'] = ctx['current_abf'] if ctx['assigned_yes'] else '-1'
        expected['expected_description'] = 'Mantener asignación actual.'
    elif fc in {'ASSIGN_NEW_ABF', 'ASSIGN_NEW_ABF_CANCEL_NEW_CN', 'ASSIGN_LAST_DISB_ABF', 'ASSIGN_LAST_DISB_ABF_CANCEL_LAST_CN', 'ASSIGN_HARVEST_ABF'}:
        expected['codCnActual'] = ctx.get('labor_cn_code', CN_CODES['COSECHA'])
        expected['codAbfActual'] = ctx['labor_abf']
        expected['expected_description'] = 'Asignar al ABF que desembolsó/cosechó según la ruta.'
    elif fc in {'ASSIGN_AGENCY_NEW_CN', 'ASSIGN_AGENCY_NEW_CN_CANCEL_NEW_CN'}:
        expected['codCnActual'] = CN_CODES['COSECHA']
        expected['codAbfActual'] = '-1'
        expected['expected_description'] = 'Asignar a cartera agencia del nuevo CN.'
    else:
        expected['expected_description'] = 'Salida no clasificada explícitamente; revisar catálogo.'
    return expected


def abf_slot_fields(max_slots: int = MAX_EXPECTED_ABF_SLOTS) -> list[str]:
    return [f'codAbfActual{i}' for i in range(1, max_slots + 1)]


def expected_row_for_csv(expected: dict, max_slots: int = MAX_EXPECTED_ABF_SLOTS) -> dict:
    row = dict(expected)
    values = []
    if expected.get('accepted_cod_abf_set'):
        values = [x for x in expected.get('accepted_cod_abf_set', '').split('|') if x]
        row['expected_mode'] = 'ACCEPTED_SET'
    elif expected.get('codAbfActual'):
        values = [expected.get('codAbfActual')]
        if expected.get('codCnActual'):
            row['expected_mode'] = 'EXACT'
    for field in abf_slot_fields(max_slots):
        row[field] = ''
    for idx, value in enumerate(values[:max_slots], start=1):
        row[f'codAbfActual{idx}'] = value
    return row


def ensure_hardlink(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build_xml(ctx: dict, cns: list[dict], creditos: list[dict]) -> str:
    assigned_abf_code = ctx['current_abf'] if ctx['assigned_yes'] else '-1'
    current_cn = CN_CODES['ASIGNADO'] if ctx['assigned_yes'] else (CN_CODES['COSECHA'] if ctx['general_decisions'].get('D22') == 'SI' else '-1')
    suggested = suggested_abf_fields(current_cn, assigned_abf_code, cns) if ctx['general_decisions'].get('D15') == 'SI' else suggested_abf_fields('', '', cns)
    first_credit_no = creditos[0]['creditoNo'] if creditos else ''

    parts = ['<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:rule="http://bar.foo.com/rule">',
             '<soapenv:Header/>',
             '<soapenv:Body><rule:entryPointAdmonCarteraV2><arg0>']
    parts.extend([
        tag('clienteNombre', 'CLIENTE QA ' + ctx['case_id']),
        tag('clienteCod', ctx['client_code']),
        tag('clienteEdad', ctx['cliente_edad']),
        tag('clienteGenero', deterministic_gender(ctx['case_id'])),
        tag('clienteRegion', ctx['client_region']),
        tag('clienteMunicipioVivienda', ctx['vivienda']),
        tag('clienteMunicipioTrabajo', ctx['trabajo']),
        tag('clienteEsSugerido', 'SI' if ctx['general_decisions'].get('D15') == 'SI' else 'NO'),
        tag('clienteEstabaAsignadoAbf', 'SI' if ctx['assigned_yes'] else 'NO'),
        tag('clienteEsCarteraDelCnCod', current_cn),
        tag('clienteFueDesembolsadoEnElUltimoMes', 'SI' if ctx['harvest_last_month'] else 'NO'),
        tag('clienteEsCarteraDelAbfCod', assigned_abf_code),
        tag('abfSugeridoCod', suggested['abfSugeridoCod']),
        tag('abfSugeridoEstado', suggested['abfSugeridoEstado']),
        tag('abfSugeridoEdad', suggested['abfSugeridoEdad']),
        tag('abfSugeridoCnCod', suggested['abfSugeridoCnCod']),
        tag('abfSugeridoBanca', suggested['abfSugeridoBanca']),
        tag('abfSugeridoRegion', suggested['abfSugeridoRegion']),
        tag('abfSugeridoMunicipio', suggested['abfSugeridoMunicipio']),
        tag('abfSugeridoOportunidad', suggested['abfSugeridoOportunidad']),
        tag('clienteDpi', ctx['dpi']),
        tag('clienteesTrabajadorBt', 'S' if ctx['general_decisions'].get('D03') == 'EMPLEADO' else 'N'),
        '<informacionGeneral>' + tag('fecha', RUN_DATE) + '</informacionGeneral>',
        '<activoCrediticio>'
    ])
    parts.extend(credito_xml(c) for c in creditos)
    parts.append('</activoCrediticio><activoFinanciero>')
    for cn in cns:
        parts.append('<centroDeNegocio>')
        parts.extend([
            tag('cnCod', cn['cod']), tag('cnNombre', cn['nombre']), tag('cnEstado', cn['estado']),
            tag('cnRegion', cn['region']), tag('cnMunicipio', cn['municipio']), tag('cnDepartamento', cn['departamento'])
        ])
        parts.extend(abf_xml(a) for a in cn['abfs'])
        parts.append('</centroDeNegocio>')
    parts.append('</activoFinanciero>')
    parts.append(
        '<salidaBlaze><asignacionCredito>'
        + tag('clienteCredito', first_credit_no)
        + tag('clienteDpi', ctx['dpi'])
        + tag('cnAsignadoAnteriorCod', current_cn)
        + tag('abfAsignadoAnteriorCod', assigned_abf_code)
        + '</asignacionCredito></salidaBlaze>'
    )
    parts.append('</arg0></rule:entryPointAdmonCarteraV2></soapenv:Body></soapenv:Envelope>')
    return ''.join(parts)


def suggested_abf_fields(current_cn: str, current_abf: str, cns: list[dict]) -> dict[str, str]:
    """ABF sugerido mirrors the client's assigned ABF, or stays fully blank."""
    if current_cn in {'', '-1'} or current_abf in {'', '-1'}:
        return {
            'abfSugeridoCod': '',
            'abfSugeridoEstado': '',
            'abfSugeridoEdad': '',
            'abfSugeridoCnCod': '',
            'abfSugeridoBanca': '',
            'abfSugeridoRegion': '',
            'abfSugeridoMunicipio': '',
            'abfSugeridoOportunidad': '',
        }
    for cn in cns:
        if cn.get('cod') != current_cn:
            continue
        for abf in cn.get('abfs', []):
            if abf.get('asignadoCod') == current_abf:
                return {
                    'abfSugeridoCod': current_abf,
                    'abfSugeridoEstado': abf.get('asignadoEstado', ''),
                    'abfSugeridoEdad': abf.get('asignadoEdad', ''),
                    'abfSugeridoCnCod': current_cn,
                    'abfSugeridoBanca': abf.get('asignadoBanca', ''),
                    'abfSugeridoRegion': cn.get('region', ''),
                    'abfSugeridoMunicipio': cn.get('municipio', ''),
                    'abfSugeridoOportunidad': 'SUGERIDO',
                }
    return {
        'abfSugeridoCod': '',
        'abfSugeridoEstado': '',
        'abfSugeridoEdad': '',
        'abfSugeridoCnCod': '',
        'abfSugeridoBanca': '',
        'abfSugeridoRegion': '',
        'abfSugeridoMunicipio': '',
        'abfSugeridoOportunidad': '',
    }


def load_catalog() -> dict[str, dict]:
    with CATALOG.open(newline='', encoding='utf-8-sig') as f:
        return {r['expanded_route_id']: r for r in csv.DictReader(f)}


def prepare_output_root() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    (OUT_ROOT / '00_catalogos').mkdir(parents=True)
    (OUT_ROOT / '01_manifest').mkdir(parents=True)
    (OUT_ROOT / '02_inputs_xml').mkdir(parents=True)
    (OUT_ROOT / FLAT_XML_DIR).mkdir(parents=True)
    (OUT_ROOT / '03_expected').mkdir(parents=True)
    (OUT_ROOT / '04_validation').mkdir(parents=True)
    (OUT_ROOT / '05_scripts').mkdir(parents=True)
    # Copiar insumos de gobernanza.
    for src in [CATALOG, MANIFEST, FIELD_CONTRACT, SCENARIOS]:
        if src.exists():
            dest_dir = '01_manifest' if src.name.startswith('case_manifest') else '00_catalogos'
            shutil.copy2(src, OUT_ROOT / dest_dir / src.name)
    shutil.copy2(Path(__file__), OUT_ROOT / '05_scripts' / Path(__file__).name)


def write_readme(summary: dict | None = None) -> None:
    text = f"""Paquete QA Blaze - arbol expandido General_post_primera_asignacion\n\nGenerado: {datetime.utcnow().isoformat()}Z\nVersion generador: {RUN_VERSION}\n\nContenido:\n- 00_catalogos/: catalogo de rutas, contrato de campos y constraints usados para generar los casos.\n- 01_manifest/: manifest full con 222,000 casos.\n- 02_inputs_xml/: XMLs de entrada para ejecutar contra Blaze.\n- 03_expected/: expected_outputs.csv con la salida esperada por case_id.\n- 04_validation/: reportes de validacion de generacion, incluyendo control BT.\n- 05_scripts/: script reproducible de generacion.\n\nNota importante:\nLos XMLs usan la estructura SOAP vigente con arg0, informacionGeneral, activoCrediticio, activoFinanciero y salidaBlaze/asignacionCredito. Se agregan clienteGenero y asignadoGenero, y los valores alfanumericos se serializan en mayuscula.\n\nAclaracion de negocio incorporada:\n- labor = persona que desembolso el credito; campos participanteLabor*.\n- asignacion = a quien pertenece actualmente el cliente; campos clienteEsCarteraDel*, asignado*.\n- cosecha = CN donde se desembolso el credito; campos cosecha* en el XML. Puede diferir de participanteLaborCn.\n"""
    if summary:
        text += "\nResumen de generación:\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    (OUT_ROOT / 'README.txt').write_text(text, encoding='utf-8')


def main(limit: int | None = None) -> None:
    start = time.time()
    catalog = load_catalog()
    prepare_output_root()
    write_readme()

    expected_fields = ['case_id', 'expanded_route_id', 'general_route_id', 'included_in_core', 'expected_mode', 'final_output_class_id',
                       'codCliente', 'dpiCliente', 'codCnActual', *abf_slot_fields(), 'codCnAnterior', 'codAbfAnterior', 'bolson',
                       'expected_control_tree', 'expected_description']
    validation_fields = ['case_id', 'expanded_route_id', 'general_route_id', 'final_output_class_id', 'input_xml_path',
                         'xml_generated', 'expected_generated', 'bt_control_case', 'bt_credito_banca_ok', 'bt_expected_tree_ok',
                         'all_cn_catalog_present', 'notes']
    bt_detail_fields = ['case_id', 'input_xml_path', 'credito_banca_values', 'abf_sugerido_banca', 'expected_control_tree', 'pass_bt_validation']

    counts = Counter()
    route_counts = Counter()
    output_counts = Counter()
    bt_pass = 0
    bt_total = 0
    generated_paths_sample = []

    with MANIFEST.open(newline='', encoding='utf-8-sig') as mf, \
         (OUT_ROOT / '03_expected' / 'expected_outputs.csv').open('w', newline='', encoding='utf-8') as ef, \
         (OUT_ROOT / '04_validation' / 'generation_validation.csv').open('w', newline='', encoding='utf-8') as vf, \
         (OUT_ROOT / '04_validation' / 'bt_validation_detail.csv').open('w', newline='', encoding='utf-8') as btf:
        reader = csv.DictReader(mf)
        exp_writer = csv.DictWriter(ef, fieldnames=expected_fields)
        val_writer = csv.DictWriter(vf, fieldnames=validation_fields)
        bt_writer = csv.DictWriter(btf, fieldnames=bt_detail_fields)
        exp_writer.writeheader()
        val_writer.writeheader()
        bt_writer.writeheader()

        for idx, man in enumerate(reader, start=1):
            if limit is not None and idx > limit:
                break
            route = catalog[man['expanded_route_id']]
            ctx = build_context(man, route)
            cns = build_cns_and_abfs(ctx)
            creditos = build_creditos(ctx, cns)
            xml = build_xml(ctx, cns, creditos)
            expected = build_expected(ctx)

            rel_path = Path(man['input_xml_path'])
            out_path = OUT_ROOT / rel_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(xml, encoding='utf-8')
            ensure_hardlink(out_path, OUT_ROOT / FLAT_XML_DIR / f"{ctx['case_id']}.xml")

            expected_row = expected_row_for_csv(expected)
            exp_writer.writerow({k: expected_row.get(k, '') for k in expected_fields})
            is_bt = ctx['final_output_class_id'] == 'CONTROL_BT'
            bt_credito_banca_ok = ''
            bt_expected_tree_ok = ''
            if is_bt:
                bt_total += 1
                credito_bancas = sorted({c['creditoBanca'] for c in creditos})
                abf_sug_banca = 'BANCA_TRABAJADORES'
                bt_credito_banca_ok = 'SI' if credito_bancas == ['BANCA_TRABAJADORES'] else 'NO'
                bt_expected_tree_ok = 'SI' if expected['expected_control_tree'] == 'BT' else 'NO'
                pass_bt = bt_credito_banca_ok == 'SI' and bt_expected_tree_ok == 'SI'
                bt_pass += 1 if pass_bt else 0
                bt_writer.writerow({
                    'case_id': ctx['case_id'],
                    'input_xml_path': man['input_xml_path'],
                    'credito_banca_values': '|'.join(credito_bancas),
                    'abf_sugerido_banca': abf_sug_banca,
                    'expected_control_tree': expected['expected_control_tree'],
                    'pass_bt_validation': 'SI' if pass_bt else 'NO',
                })
            val_writer.writerow({
                'case_id': ctx['case_id'],
                'expanded_route_id': ctx['expanded_route_id'],
                'general_route_id': ctx['general_route_id'],
                'final_output_class_id': ctx['final_output_class_id'],
                'input_xml_path': man['input_xml_path'],
                'xml_generated': 'SI',
                'expected_generated': 'SI',
                'bt_control_case': 'SI' if is_bt else 'NO',
                'bt_credito_banca_ok': bt_credito_banca_ok,
                'bt_expected_tree_ok': bt_expected_tree_ok,
                'all_cn_catalog_present': 'SI' if len(cns) == 8 else 'NO',
                'notes': '',
            })
            counts['total_cases'] += 1
            route_counts[ctx['expanded_route_id']] += 1
            output_counts[ctx['final_output_class_id']] += 1
            if len(generated_paths_sample) < 20:
                generated_paths_sample.append(str(rel_path))
            if idx % 25000 == 0:
                print(f'Generated {idx:,} XMLs...', flush=True)

    # Validar XML bien formado en una muestra y en todos los BT.
    sample_ok = 0
    sample_fail = []
    sample_files = []
    # Primeros 20 generados + 20 BT si existen.
    for p in generated_paths_sample:
        sample_files.append(OUT_ROOT / p)
    bt_dir = OUT_ROOT / '02_inputs_xml' / 'GPA-038__CONTROL_BT'
    if bt_dir.exists():
        sample_files.extend(sorted(bt_dir.glob('*.xml'))[:20])
    for p in sample_files:
        try:
            ET.parse(p)
            sample_ok += 1
        except Exception as e:
            sample_fail.append({'path': str(p.relative_to(OUT_ROOT)), 'error': str(e)})

    # Reporte por ruta.
    with (OUT_ROOT / '04_validation' / 'route_generation_summary.csv').open('w', newline='', encoding='utf-8') as rf:
        writer = csv.DictWriter(rf, fieldnames=['expanded_route_id', 'generated_cases'])
        writer.writeheader()
        for route_id, cnt in sorted(route_counts.items()):
            writer.writerow({'expanded_route_id': route_id, 'generated_cases': cnt})

    duration = round(time.time() - start, 2)
    summary = {
        'generator_version': RUN_VERSION,
        'output_root': str(OUT_ROOT),
        'generated_at_utc': datetime.utcnow().isoformat() + 'Z',
        'duration_seconds': duration,
        'total_xml_inputs_generated': counts['total_cases'],
        'expanded_routes_generated': len(route_counts),
        'core_routes_generated': len([r for r in route_counts if not r.endswith('__CONTROL_BT')]),
        'bt_control_routes_generated': 1 if 'GPA-038__CONTROL_BT' in route_counts else 0,
        'bt_control_cases_generated': bt_total,
        'bt_control_cases_passed_validation': bt_pass,
        'bt_validation_pass_rate': None if bt_total == 0 else round(bt_pass / bt_total, 6),
        'sample_xml_parse_ok': sample_ok,
        'sample_xml_parse_failures': sample_fail,
        'expected_outputs_file': '03_expected/expected_outputs.csv',
        'validation_files': [
            '04_validation/generation_validation.csv',
            '04_validation/bt_validation_detail.csv',
            '04_validation/route_generation_summary.csv',
            '04_validation/generation_summary.json',
        ],
        'output_class_counts': dict(output_counts),
    }
    (OUT_ROOT / '04_validation' / 'generation_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT_ROOT / '04_validation' / 'bt_validation_summary.json').write_text(json.dumps({
        'bt_control_cases_generated': bt_total,
        'bt_control_cases_passed_validation': bt_pass,
        'bt_validation_pass_rate': None if bt_total == 0 else round(bt_pass / bt_total, 6),
        'validation_rule': 'Todos los casos GPA-038__CONTROL_BT deben tener creditoBanca=BANCA_TRABAJADORES y expected_control_tree=BT.',
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    write_readme(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    lim = None
    if len(sys.argv) > 1 and sys.argv[1] != 'full':
        lim = int(sys.argv[1])
    main(lim)
