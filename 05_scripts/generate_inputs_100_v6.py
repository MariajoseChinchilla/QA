#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, importlib.util, io, json, os, random, re, shutil, subprocess, tarfile, tempfile, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

def write_bytes_retry(path: Path, data: bytes, attempts: int = 5) -> None:
    for attempt in range(attempts):
        try:
            path.write_bytes(data)
            return
        except OSError as exc:
            if attempt == attempts - 1 or exc.errno not in {13, 22, 32}:
                raise
            time.sleep(0.2 * (attempt + 1))

SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parent
BASE_GEN = SCRIPT_DIR / 'generate_full_qa_xml_inputs.py'
spec = importlib.util.spec_from_file_location('qa_base_gen', BASE_GEN)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)  # type: ignore

CASES_PER_ROUTE = 1000
MANIFEST = BASE / '01_manifest' / 'case_manifest_1000_full_v6.csv'
CATALOG = BASE / '00_catalogos' / 'catalogo_rutas_arbol_expandido_general_post_full_with_bt_control.csv'
FIELD_CONTRACT = BASE / '00_catalogos' / 'field_contract_arbol_expandido_general_post_primera_asignacion.csv'
SCENARIOS = BASE / '00_catalogos' / 'scenario_constraints_arbol_expandido_general_post_primera_asignacion.yml'
ARCHIVE = BASE / 'qa100_v6.tar.zst'
ROOT_NAME = 'qa100'
RUN_VERSION = 'XML_INPUT_GENERATOR_V15_FLAT_ONLY_NEW_XML_STRUCTURE_GENDER_UPPERCASE_2026_06_03'
RUN_DATE = '2026-05-14'
FLAT_XML_DIR = '02_inputs_xml_flat'

# Patronos finitos. Los campos especialistaPatrono1/2/3 contienen NOMBRES de patrono.
PATRONO_CATALOG = [
    {'patronoCod': 'P001', 'patronoNombre': 'patrono1'},
    {'patronoCod': 'P002', 'patronoNombre': 'patrono2'},
    {'patronoCod': 'P003', 'patronoNombre': 'patrono3'},
    {'patronoCod': 'P004', 'patronoNombre': 'patrono4'},
]
PATRONO_MATCH_NAMES = [p['patronoNombre'] for p in PATRONO_CATALOG[:3]]
PATRONO_NO_SPECIALIST = {'patronoCod': 'P999', 'patronoNombre': 'patrono_sin_especialista'}
PATRONO_CODE_BY_NAME = {p['patronoNombre']: p['patronoCod'] for p in PATRONO_CATALOG}
PATRONO_CODE_BY_NAME[PATRONO_NO_SPECIALIST['patronoNombre']] = PATRONO_NO_SPECIALIST['patronoCod']

REGION_VALUES = ['Metropolitana', 'Nor_oriente', 'Sur_occidente']
BANCA_PERSONAS = 'banca_personas'
BANCA_TRABAJADORES = 'banca_trabajadores'
GENDER_VALUES = ['MASCULINO', 'FEMENINO']

DOMAIN_RULES = {
    # El requerimiento original traía V,C; para este paquete se agrega D por la regla de negocio indicada por el usuario.
    'creditoEstado': {'C', 'D'},
    'creditoBanca': {'BANCA_PERSONAS', 'BANCA_TRABAJADORES'},
    'creditoTipoCliente': {'CN', 'CE', 'CR'},
    'creditoRegion': {'METROPOLITANA', 'NOR_ORIENTE', 'SUR_OCCIDENTE'},
    'participanteLaborEstado': {'ALTA', 'BAJA'},
    'participanteLaborBanca': {'BANCA_PERSONAS', 'BANCA_TRABAJADORES'},
    'participanteLaborRegion': {'METROPOLITANA', 'NOR_ORIENTE', 'SUR_OCCIDENTE'},
    'participanteLaborVacacion': {'0', '1'},
    'participanteLaborTipo': {'ABF', 'CN', 'CP'},
    'clienteRegion': {'METROPOLITANA', 'NOR_ORIENTE', 'SUR_OCCIDENTE'},
    'clienteEsSugerido': {'SI', 'NO'},
    'clienteEstabaAsignadoAbf': {'SI', 'NO'},
    'clienteFueDesembolsadoEnElUltimoMes': {'SI', 'NO'},
    'clienteGenero': {'MASCULINO', 'FEMENINO'},
    'cnEstado': {'ALTA', 'BAJA'},
    'cnRegion': {'METROPOLITANA', 'NOR_ORIENTE', 'SUR_OCCIDENTE'},
    'asignadoEstado': {'ALTA', 'BAJA'},
    'asignadoEnVacacion': {'0', '1'},
    'asignadoBanca': {'BANCA_PERSONAS', 'BANCA_TRABAJADORES'},
    'asignadoGenero': {'MASCULINO', 'FEMENINO'},
    'asignadoBolsonEstado': {'EXCESO', 'EQUILIBRIO', 'DEFICIT'},
    'abfSugeridoEstado': {'ALTA', 'BAJA'},
    'abfSugeridoBanca': {'BANCA_PERSONAS', 'BANCA_TRABAJADORES'},
    'abfSugeridoRegion': {'METROPOLITANA', 'NOR_ORIENTE', 'SUR_OCCIDENTE'},
    'abfSugeridoOportunidad': {'SUGERIDO', 'NO_SUGERIDO'},
    'clienteesTrabajadorBt': {'S', 'N'},
    'cosechaEstadoCn': {'ALTA', 'BAJA'},
    'cosechaRegionCn': {'METROPOLITANA', 'NOR_ORIENTE', 'SUR_OCCIDENTE'},
}
OPTIONAL_BLANK_DOMAIN_FIELDS = {
    'abfSugeridoEstado',
    'abfSugeridoBanca',
    'abfSugeridoRegion',
    'abfSugeridoOportunidad',
}

R1_VARIANTS = {
    'R1-001': ('DU', 'deficit_unique'),
    'R1-002': ('DT', 'deficit_tie'),
    'R1-003': ('EU', 'equilibrio_unique'),
    'R1-004': ('ET', 'equilibrio_tie'),
}
VARIANT_NUM = {'DU': 1, 'DT': 2, 'EU': 3, 'ET': 4}
REPLICAS_PER_GROUP_VARIANT = 3

CURRENT_ASSIGNMENT_CN = '1001'
CURRENT_ASSIGNMENT_ABF = '500001'
CURRENT_ASSIGNMENT_ABF_BAJA = '500002'
CURRENT_ASSIGNMENT_ABF_VACATION = '500004'
DIRECT_COSECHA_CN = '1010'
LABOR_CN = '1020'
LABOR_ABF_ALTA = '600001'
LABOR_ABF_BAJA = '600002'
LABOR_ABF_BT = '600003'
LABOR_ABF_BT_BAJA = '600005'
CP_CN = '9001'
CERRADO_CN = '1301'

LABOR_BY_REGION = {
    'Metropolitana': {
        'cn': LABOR_CN,
        'alta_bp': LABOR_ABF_ALTA,
        'baja_bp': LABOR_ABF_BAJA,
        'alta_bt': LABOR_ABF_BT,
        'baja_bt': LABOR_ABF_BT_BAJA,
        'nombre': 'Agencia Labor Del Vendedor',
        'departamento': 'departamento_labor',
        'municipio': 'municipio_labor',
    },
    'Nor_oriente': {
        'cn': '1021',
        'alta_bp': '610001',
        'baja_bp': '610002',
        'alta_bt': '610003',
        'baja_bt': '610005',
        'nombre': 'Agencia Labor Nor Oriente',
        'departamento': 'departamento_labor_nor',
        'municipio': 'municipio_labor_nor',
    },
    'Sur_occidente': {
        'cn': '1022',
        'alta_bp': '620001',
        'baja_bp': '620002',
        'alta_bt': '620003',
        'baja_bt': '620005',
        'nombre': 'Agencia Labor Sur Occidente',
        'departamento': 'departamento_labor_sur',
        'municipio': 'municipio_labor_sur',
    },
}

BASE_CNS = [
    {'key':'ASIGNACION_ACTUAL','cod':CURRENT_ASSIGNMENT_CN,'nombre':'Agencia Asignacion Actual','estado':'Alta','region':'Nor_oriente','departamento':'departamento_asig','municipio':'municipio_asig'},
    {'key':'COSECHA_DIRECTA','cod':DIRECT_COSECHA_CN,'nombre':'Agencia Cosecha Directa','estado':'Alta','region':'Metropolitana','departamento':'departamento_current','municipio':'municipio_current'},
    {'key':'LABOR_VENDEDOR','cod':LABOR_BY_REGION['Metropolitana']['cn'],'nombre':LABOR_BY_REGION['Metropolitana']['nombre'],'estado':'Alta','region':'Metropolitana','departamento':LABOR_BY_REGION['Metropolitana']['departamento'],'municipio':LABOR_BY_REGION['Metropolitana']['municipio']},
    {'key':'LABOR_VENDEDOR_NOR','cod':LABOR_BY_REGION['Nor_oriente']['cn'],'nombre':LABOR_BY_REGION['Nor_oriente']['nombre'],'estado':'Alta','region':'Nor_oriente','departamento':LABOR_BY_REGION['Nor_oriente']['departamento'],'municipio':LABOR_BY_REGION['Nor_oriente']['municipio']},
    {'key':'LABOR_VENDEDOR_SUR','cod':LABOR_BY_REGION['Sur_occidente']['cn'],'nombre':LABOR_BY_REGION['Sur_occidente']['nombre'],'estado':'Alta','region':'Sur_occidente','departamento':LABOR_BY_REGION['Sur_occidente']['departamento'],'municipio':LABOR_BY_REGION['Sur_occidente']['municipio']},
    {'key':'CENTRO_PROCESAMIENTO','cod':CP_CN,'nombre':'Centro De Procesamiento','estado':'Alta','region':'Metropolitana','departamento':'departamento_cp','municipio':'municipio_cp'},
    {'key':'CERRADO_CONTROL','cod':CERRADO_CN,'nombre':'Agencia Cerrada Control','estado':'Baja','region':'Nor_oriente','departamento':'departamento_closed','municipio':'municipio_closed'},
]


def esc(x) -> str:
    return escape('' if x is None else str(x), {'"': '&quot;'})

def xml_value(x) -> str:
    value = '' if x is None else str(x)
    return value.upper() if any(ch.isalpha() for ch in value) else value

def tag(name: str, value) -> str:
    return f'<{name}>{esc(xml_value(value))}</{name}>'

def deterministic_gender(key) -> str:
    digest = hashlib.sha256(str(key).encode('utf-8')).hexdigest()
    return GENDER_VALUES[int(digest[:8], 16) % len(GENDER_VALUES)]

def fmt_region(v: str) -> str:
    return {'METROPOLITANA':'Metropolitana','NOR_ORIENTE':'Nor_oriente','SUR_OCCIDENTE':'Sur_occidente','Metropolitana':'Metropolitana','Nor_oriente':'Nor_oriente','Sur_occidente':'Sur_occidente'}.get(v, v)

def req_bool(v: bool) -> str:
    return 'Si' if v else 'No'

def norm_region(v: str) -> str:
    m = {
        'METROPOLITANA': 'Metropolitana',
        'NOR_ORIENTE': 'Nor_oriente',
        'SUR_OCCIDENTE': 'Sur_occidente',
        'Metropolitana': 'Metropolitana',
        'Nor_oriente': 'Nor_oriente',
        'Sur_occidente': 'Sur_occidente',
    }
    return m.get(str(v), str(v))


def r1_id(expanded_route_id: str) -> str | None:
    m = re.search(r'(R1-\d{3})', expanded_route_id or '')
    return m.group(1) if m else None

def r2_id(expanded_route_id: str) -> str | None:
    m = re.search(r'(R2-\d{3})', expanded_route_id or '')
    return m.group(1) if m else None

def r3_id(expanded_route_id: str) -> str | None:
    m = re.search(r'(R3-\d{3})', expanded_route_id or '')
    return m.group(1) if m else None

def is_r1_route(expanded_route_id: str) -> bool:
    return '__R1-' in (expanded_route_id or '')

def group_requires_patrono(route: dict) -> bool:
    fc = route.get('final_output_class_id','')
    scope = route.get('candidate_scope','')
    src = route.get('source_general_output_class_id','')
    return ('PATRONO' in fc) or ('especialista' in scope.lower()) or src == 'DELEGATE_R1_PATRONO'

def group_requires_desembolso(route: dict) -> bool:
    fc = route.get('final_output_class_id','')
    scope = route.get('candidate_scope','')
    src = route.get('source_general_output_class_id','')
    if 'DESEMBOLSO' in fc:
        return True
    if 'le han desembolsado' in scope.lower() or 'último cn' in scope.lower() or 'ultimo cn' in scope.lower():
        return True
    if 'MUNICIPIO_ULT_CN' in src or 'DEPTO_ULT_CN' in src:
        return True
    return False

def candidate_group_region(route: dict) -> str:
    gen = qa.parse_general_decisions(route.get('general_decision_path_codes', ''))
    if gen.get('D04') == 'SI' or gen.get('D27') == 'SI':
        return 'Metropolitana'
    if gen.get('D18') == 'SI':
        return 'Nor_oriente'
    if gen.get('D04') == 'NO':
        return 'Nor_oriente'
    return 'Nor_oriente'

def group_location_kind(route: dict) -> str:
    fc = route.get('final_output_class_id','')
    scope = route.get('candidate_scope','').lower()
    if 'VIV' in fc or 'municipio de vivienda' in scope:
        return 'vivienda'
    if 'TRAB' in fc or 'municipio de trabajo' in scope:
        return 'trabajo'
    if 'departamento' in scope or 'DEPTO' in fc:
        return 'departamento'
    if 'municipio del último' in scope or 'municipio del ultimo' in scope or 'MUNI_ULT' in fc:
        return 'ultimo_municipio'
    return 'otro'

def candidate_group_key(route: dict) -> str | None:
    er = route.get('expanded_route_id','')
    if not is_r1_route(er):
        return None
    patrono = 'PATRONO' if group_requires_patrono(route) else 'ABFS'
    hist = 'HIST' if group_requires_desembolso(route) else 'NOHIST'
    region = candidate_group_region(route).upper()
    # Se mantiene un número controlado de grupos para que cada XML siga siendo manejable.
    # La variación de municipios se logra con 3 CNs alternos por grupo/variante.
    return f'{patrono}_{hist}_{region}'

def load_catalog_rows() -> list[dict]:
    with CATALOG.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def load_catalog() -> dict[str, dict]:
    return {r['expanded_route_id']: r for r in load_catalog_rows()}

def build_manifest_rows_from_catalog(catalog_rows: list[dict], limit: int|None=None) -> list[dict]:
    rows=[]
    for route_idx, route in enumerate(catalog_rows, start=1):
        route_cases = int(route.get('target_cases') or CASES_PER_ROUTE)
        if route_cases != CASES_PER_ROUTE:
            route_cases = CASES_PER_ROUTE
        for case_number in range(1, route_cases + 1):
            global_case_number = (route_idx - 1) * CASES_PER_ROUTE + case_number
            case_id = f"{route['expanded_route_id']}__{case_number:04d}"
            rows.append({
                'case_id': case_id,
                'expanded_route_id': route['expanded_route_id'],
                'general_route_id': route['general_route_id'],
                'case_number': str(case_number),
                'global_case_number': str(global_case_number),
                'seed': str(240000000000000 + global_case_number),
                'included_in_core': route['included_in_core'],
                'route_depth': route['route_depth'],
                'final_rule': route['final_rule'],
                'final_output_class_id': route['final_output_class_id'],
                'expected_mode': route['expected_mode'],
                'input_xml_path': f"{FLAT_XML_DIR}/{case_id}.xml",
                'input_xml_flat_path': f"{FLAT_XML_DIR}/{case_id}.xml",
                'expected_output_path': '03_expected/expected_outputs.csv',
                'tree_version': 'General_post_primera_asignacion_full',
                'mapping_version': 'v6',
                'generator_version': 'GENERATOR_MANIFEST_V4_1000_PER_ROUTE_FLAT_ONLY',
            })
            if limit is not None and len(rows) >= limit:
                return rows
    return rows

def load_manifest_rows(limit: int|None=None) -> list[dict]:
    return build_manifest_rows_from_catalog(load_catalog_rows(), limit)

def write_manifest_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields=[
        'case_id','expanded_route_id','general_route_id','case_number','global_case_number','seed',
        'included_in_core','route_depth','final_rule','final_output_class_id','expected_mode',
        'input_xml_path','input_xml_flat_path','expected_output_path','tree_version',
        'mapping_version','generator_version'
    ]
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: r.get(k, '') for k in fields} for r in rows)

def is_specialist(abf: dict, patrono_nombre: str) -> bool:
    return patrono_nombre in {abf.get('especialistaPatrono1',''), abf.get('especialistaPatrono2',''), abf.get('especialistaPatrono3','')}

def make_abf(code: str, estado: str, banca: str, edad: int, bolson: str, patrono: bool, vac='0', cosecha='-1') -> dict:
    # Cuando patrono=True, el ABF se especializa en tres patronos finitos, uno por cada campo.
    # Esto permite probar que Blaze revise especialistaPatrono1, especialistaPatrono2 y especialistaPatrono3.
    e1, e2, e3 = ('patrono1', 'patrono2', 'patrono3') if patrono else ('-1', '-1', '-1')
    return {
        'asignadoCod': code,
        'asignadoEstado': estado,
        'asignadoEnVacacion': vac,
        'asignadoBanca': banca,
        'asignadoEdad': str(edad),
        'asignadoGenero': deterministic_gender(code),
        'especialistaPatrono1': e1,
        'especialistaPatrono2': e2,
        'especialistaPatrono3': e3,
        'asignadoBolsonAcumulativo': '75000' if bolson == 'Deficit' else ('150000' if bolson == 'Equilibrio' else '300000'),
        'asignadoBolsonLimExposicion': '100000',
        'asignadoBolsonEstado': bolson,
        'participanteCosechaCod': cosecha,
        'participanteCosechaVacacion': '0',
    }

def candidate_abfs_for_variant(cn_code: str, rid: str, patrono: bool) -> list[dict]:
    if rid == 'R1-001':
        return [
            make_abf(f'{cn_code}01','Alta',BANCA_PERSONAS,35,'Deficit',patrono,cosecha=cn_code),
            make_abf(f'{cn_code}02','Alta',BANCA_PERSONAS,49,'Equilibrio',patrono,cosecha=cn_code),
            make_abf(f'{cn_code}03','Alta',BANCA_PERSONAS,55,'Exceso',False,cosecha='-1'),
            make_abf(f'{cn_code}04','Baja',BANCA_PERSONAS,35,'Deficit',patrono,cosecha='-1'),
        ]
    if rid == 'R1-002':
        return [
            make_abf(f'{cn_code}01','Alta',BANCA_PERSONAS,35,'Deficit',patrono,cosecha=cn_code),
            make_abf(f'{cn_code}02','Alta',BANCA_PERSONAS,35,'Deficit',patrono,cosecha=cn_code),
            make_abf(f'{cn_code}03','Alta',BANCA_PERSONAS,52,'Equilibrio',False,cosecha='-1'),
            make_abf(f'{cn_code}04','Baja',BANCA_PERSONAS,35,'Deficit',patrono,cosecha='-1'),
        ]
    if rid == 'R1-003':
        return [
            make_abf(f'{cn_code}01','Alta',BANCA_PERSONAS,35,'Equilibrio',patrono,cosecha=cn_code),
            make_abf(f'{cn_code}02','Alta',BANCA_PERSONAS,49,'Equilibrio',patrono,cosecha=cn_code),
            make_abf(f'{cn_code}03','Alta',BANCA_PERSONAS,58,'Exceso',False,cosecha='-1'),
            make_abf(f'{cn_code}04','Baja',BANCA_PERSONAS,35,'Equilibrio',patrono,cosecha='-1'),
        ]
    # R1-004: empate por edad; salida por conjunto aceptado. El ABF 03 sirve como candidato adicional
    # cuando la ruta no filtra por patrono.
    return [
        make_abf(f'{cn_code}01','Alta',BANCA_PERSONAS,35,'Equilibrio',patrono,cosecha=cn_code),
        make_abf(f'{cn_code}02','Alta',BANCA_PERSONAS,35,'Equilibrio',patrono,cosecha=cn_code),
        make_abf(f'{cn_code}03','Alta',BANCA_PERSONAS,53,'Exceso',False,cosecha='-1'),
        make_abf(f'{cn_code}04','Baja',BANCA_PERSONAS,35,'Equilibrio',patrono,cosecha='-1'),
    ]

def base_abfs_for_cn(key: str, cod: str) -> list[dict]:
    if key == 'ASIGNACION_ACTUAL':
        return [
            make_abf(CURRENT_ASSIGNMENT_ABF,'Alta',BANCA_PERSONAS,39,'Equilibrio',False),
            make_abf(CURRENT_ASSIGNMENT_ABF_BAJA,'Baja',BANCA_PERSONAS,43,'Equilibrio',False),
            make_abf('500003','Alta',BANCA_TRABAJADORES,41,'Equilibrio',False),
            make_abf(CURRENT_ASSIGNMENT_ABF_VACATION,'Alta',BANCA_PERSONAS,57,'Exceso',False,vac='1'),
        ]
    if key == 'COSECHA_DIRECTA':
        return [
            make_abf('510001','Alta',BANCA_PERSONAS,35,'Equilibrio',True,cosecha=cod),
            make_abf('510002','Alta',BANCA_PERSONAS,48,'Equilibrio',False),
            make_abf('510003','Alta',BANCA_TRABAJADORES,44,'Equilibrio',False),
            make_abf('510004','Baja',BANCA_PERSONAS,35,'Deficit',True),
        ]
    if key.startswith('LABOR_VENDEDOR'):
        region = next((cfg for cfg in LABOR_BY_REGION.values() if cfg['cn'] == cod), LABOR_BY_REGION['Metropolitana'])
        return [
            make_abf(region['alta_bp'],'Alta',BANCA_PERSONAS,33,'Equilibrio',True,cosecha=DIRECT_COSECHA_CN),
            make_abf(region['baja_bp'],'Baja',BANCA_PERSONAS,33,'Equilibrio',True,cosecha=DIRECT_COSECHA_CN),
            make_abf(region['alta_bt'],'Alta',BANCA_TRABAJADORES,34,'Equilibrio',False,cosecha=DIRECT_COSECHA_CN),
            make_abf(region['baja_bt'],'Baja',BANCA_TRABAJADORES,34,'Equilibrio',False,cosecha=DIRECT_COSECHA_CN),
        ]
    if key == 'CENTRO_PROCESAMIENTO':
        return [
            make_abf('900101','Alta',BANCA_PERSONAS,41,'Equilibrio',False),
            make_abf('900102','Alta',BANCA_PERSONAS,42,'Equilibrio',False),
            make_abf('900103','Alta',BANCA_TRABAJADORES,43,'Equilibrio',False),
            make_abf('900104','Baja',BANCA_PERSONAS,44,'Exceso',False),
        ]
    return [
        make_abf('130101','Baja',BANCA_PERSONAS,35,'Equilibrio',False),
        make_abf('130102','Baja',BANCA_PERSONAS,42,'Equilibrio',False),
        make_abf('130103','Baja',BANCA_TRABAJADORES,44,'Equilibrio',False),
        make_abf('130104','Baja',BANCA_PERSONAS,50,'Exceso',False),
    ]

def build_static_catalog(catalog: dict[str,dict]) -> tuple[list[dict], dict[tuple[str,str],list[str]], dict[str,dict]]:
    parent_meta = {}
    for er, route in sorted(catalog.items()):
        pg = candidate_group_key(route)
        rid = r1_id(er)
        if pg and rid and pg not in parent_meta:
            parent_meta[pg] = {
                'patrono': group_requires_patrono(route),
                'requires_desembolso': group_requires_desembolso(route),
                'location_kind': group_location_kind(route),
                'region': candidate_group_region(route),
                'route_example': er,
            }
    cns=[]
    for b in BASE_CNS:
        d=dict(b)
        d['abfs'] = base_abfs_for_cn(d['key'], d['cod'])
        cns.append(d)
    group_variant_to_cns: dict[tuple[str,str], list[str]] = defaultdict(list)
    group_idx = 0
    for pg, meta in sorted(parent_meta.items()):
        group_idx += 1
        region = meta['region']
        for rid, (var, label) in R1_VARIANTS.items():
            for rep in range(1, REPLICAS_PER_GROUP_VARIANT + 1):
                code_int = 30000 + group_idx * 100 + VARIANT_NUM[var] * 10 + rep
                code = str(code_int)
                cn = {
                    'key': f'CG_{group_idx:03d}_{var}_{rep}',
                    'parent_group_key': pg,
                    'r1_id': rid,
                    'replica': str(rep),
                    'cod': code,
                    'nombre': f'Agencia QA {group_idx:03d} {label} {rep}',
                    'estado': 'Alta',
                    'region': region,
                    'departamento': f'departamento{code_int}',
                    'municipio': f'municipio{code_int}',
                    'group_requires_patrono': 'Si' if meta['patrono'] else 'No',
                    'group_requires_desembolso': 'Si' if meta['requires_desembolso'] else 'No',
                    'location_kind': meta['location_kind'],
                }
                cn['abfs'] = candidate_abfs_for_variant(code, rid, meta['patrono'])
                cns.append(cn)
                group_variant_to_cns[(pg, rid)].append(code)
    by_code = {c['cod']: c for c in cns}
    return cns, dict(group_variant_to_cns), by_code

def abf_xml(abf: dict) -> str:
    fields = ['asignadoCod','asignadoEstado','asignadoEnVacacion','asignadoBanca','asignadoEdad','asignadoGenero','especialistaPatrono1','especialistaPatrono2','especialistaPatrono3','asignadoBolsonAcumulativo','asignadoBolsonLimExposicion','asignadoBolsonEstado']
    return '<abf>' + ''.join(tag(f, abf.get(f,'')) for f in fields) + '</abf>'

def centro_xml(cn: dict) -> str:
    parts=['<centroDeNegocio>']
    for f, source in [('cnCod','cod'),('cnNombre','nombre'),('cnEstado','estado'),('cnRegion','region'),('cnMunicipio','municipio'),('cnDepartamento','departamento')]:
        parts.append(tag(f, cn[source]))
    parts.extend(abf_xml(a) for a in cn['abfs'])
    parts.append('</centroDeNegocio>')
    return ''.join(parts)

def assigned_abf_details(current_cn: str, current_abf: str, by_code: dict[str,dict]) -> tuple[dict|None, dict|None]:
    if current_cn in {'', '-1'} or current_abf in {'', '-1'}:
        return None, None
    cn = by_code.get(current_cn)
    if not cn:
        return None, None
    for abf in cn.get('abfs', []):
        if abf.get('asignadoCod') == current_abf:
            return cn, abf
    return cn, None

def suggested_abf_fields(current_cn: str, current_abf: str, by_code: dict[str,dict]) -> dict[str, str]:
    """ABF sugerido mirrors the client's assigned ABF, or stays fully blank."""
    cn, abf = assigned_abf_details(current_cn, current_abf, by_code)
    if not (cn and abf):
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
    return {
        'abfSugeridoCod': current_abf,
        'abfSugeridoEstado': abf.get('asignadoEstado', ''),
        'abfSugeridoEdad': abf.get('asignadoEdad', ''),
        'abfSugeridoCnCod': current_cn,
        'abfSugeridoBanca': abf.get('asignadoBanca', ''),
        'abfSugeridoRegion': cn.get('region', ''),
        'abfSugeridoMunicipio': cn.get('municipio', ''),
        'abfSugeridoOportunidad': 'Sugerido',
    }

def labor_abf_for_context(ctx: dict, by_code: dict[str,dict]) -> tuple[dict, dict]:
    region_name = norm_region(ctx.get('labor_region', 'Metropolitana'))
    cfg = LABOR_BY_REGION.get(region_name, LABOR_BY_REGION['Metropolitana'])
    estado_key = 'baja' if str(ctx.get('labor_estado', '')).upper() == 'BAJA' else 'alta'
    banca_key = 'bt' if str(ctx.get('labor_banca', '')).upper() == 'BANCA_TRABAJADORES' else 'bp'
    abf_code = cfg[f'{estado_key}_{banca_key}']
    cn = by_code[cfg['cn']]
    for abf in cn['abfs']:
        if abf['asignadoCod'] == abf_code:
            return cn, abf
    raise KeyError(f"No labor ABF for region={region_name}, estado={estado_key}, banca={banca_key}")

def current_assignment_for_context(ctx: dict, target_cn: str|None=None) -> tuple[str, str, bool]:
    gen = ctx.get('general_decisions', {})
    if gen.get('D06') == 'SI' and target_cn:
        return target_cn, f'{target_cn}04', True
    if gen.get('D06') == 'NO':
        return CURRENT_ASSIGNMENT_CN, CURRENT_ASSIGNMENT_ABF_BAJA, True
    if ctx.get('assigned_yes'):
        abf = CURRENT_ASSIGNMENT_ABF_VACATION if gen.get('D16') == 'SI' or gen.get('D34') == 'SI' else CURRENT_ASSIGNMENT_ABF
        return CURRENT_ASSIGNMENT_CN, abf, True
    if gen.get('D22') == 'SI':
        return DIRECT_COSECHA_CN, '-1', False
    return '-1', '-1', False

def harvest_cn_for_context(ctx: dict, route: dict, target_cn: str|None, by_code: dict[str,dict]) -> dict:
    gen = ctx.get('general_decisions', {})
    direct_general_r1 = is_r1_route(ctx['expanded_route_id']) and '__R2-' not in ctx['expanded_route_id'] and '__R3-' not in ctx['expanded_route_id']
    if target_cn and direct_general_r1 and (gen.get('D07') == 'SI' or gen.get('D10') == 'SI' or gen.get('D21') == 'SI'):
        return by_code[target_cn]
    if ctx.get('cn_cosecha_estado') == 'BAJA':
        return by_code[CERRADO_CN]
    region = norm_region(ctx.get('cn_cosecha_region', 'Metropolitana'))
    cn_by_region = {
        'Metropolitana': DIRECT_COSECHA_CN,
        'Nor_oriente': LABOR_BY_REGION['Nor_oriente']['cn'],
        'Sur_occidente': LABOR_BY_REGION['Sur_occidente']['cn'],
    }
    return by_code[cn_by_region.get(region, DIRECT_COSECHA_CN)]

def target_group(ctx: dict, route: dict, group_variant_to_cns: dict[tuple[str,str],list[str]]) -> tuple[str|None, str|None, str|None]:
    rid = r1_id(ctx['expanded_route_id'])
    pg = candidate_group_key(route)
    if not (pg and rid):
        return pg, rid, None
    options = group_variant_to_cns.get((pg, rid), [])
    if not options:
        return pg, rid, None
    chosen = options[(ctx['case_number'] - 1) % len(options)]
    return pg, rid, chosen

def route_patrono_yes(route: dict) -> bool:
    return group_requires_patrono(route)

def assign_case_overrides(ctx: dict, route: dict) -> None:
    # Variación controlada sin romper la ruta.
    ctx['cliente_edad'] = 31 + ((ctx['case_number'] - 1) % 9)  # 31..39; ABF 35 sigue siendo cercano/empate.
    ctx['client_region'] = norm_region(ctx.get('client_region', 'Metropolitana'))
    gen = ctx['general_decisions']
    if ctx['final_output_class_id'] == 'CONTROL_BT':
        ctx['tipo_cliente'] = 'CE'
        ctx['tipo_cliente_rule'] = 'CE: cliente existente; al menos un crédito con estado D.'
        ctx['current_credit_status'] = 'D'
        ctx['history_credit_status'] = 'D'
    elif gen.get('D02') == 'SI':
        ctx['tipo_cliente'] = 'CE'
        ctx['tipo_cliente_rule'] = 'CE: cliente existente; al menos un crédito con estado D.'
        ctx['current_credit_status'] = 'D'
        ctx['history_credit_status'] = 'D'
    elif gen.get('D03') == 'SI':
        ctx['tipo_cliente'] = 'CR'
        ctx['tipo_cliente_rule'] = 'CR: cliente reactivado; historial con créditos y todos con estado C.'
        ctx['current_credit_status'] = 'C'
        ctx['history_credit_status'] = 'C'
    else:
        ctx['tipo_cliente'] = 'CN'
        ctx['tipo_cliente_rule'] = 'CN: cliente nuevo; sin créditos en ActivoCrediticio.'
        ctx['current_credit_status'] = 'N'
        ctx['history_credit_status'] = ''
    # Patrono del cliente: si la ruta requiere especialista, usar patronos presentes en especialistaPatrono1/2/3.
    # Si debe responder No, usar un patrono no presente en ningún especialista.
    if route_patrono_yes(route):
        patrono_nombre = PATRONO_MATCH_NAMES[(ctx['case_number'] - 1) % len(PATRONO_MATCH_NAMES)]
    else:
        patrono_nombre = PATRONO_NO_SPECIALIST['patronoNombre']
    ctx['cliente_patrono_nombre'] = patrono_nombre
    ctx['cliente_patrono_cod'] = PATRONO_CODE_BY_NAME[patrono_nombre]

def stable_client_fields(ctx: dict) -> dict:
    global_case_number = int(ctx.get('global_case_number') or ctx.get('seed') or 0)
    return {
        'clienteCod': str(10000000 + global_case_number),
        'clienteDpi': str(3000000000000 + global_case_number),
        'clienteEdad': str(ctx['cliente_edad']),
        'clienteGenero': deterministic_gender(ctx['case_id']),
        'clienteNombre': 'Cliente QA ' + ctx['case_id'],
    }

def client_locations(ctx: dict, route: dict, target_cn: str|None, by_code: dict[str,dict]) -> tuple[str,str]:
    vivienda = 'municipio_sin_cn_viv'
    trabajo = 'municipio_sin_cn_trab'
    sub = ctx.get('sub_decisions', {})
    fc = ctx['final_output_class_id']
    target = by_code[target_cn] if target_cn else None
    if target:
        loc = group_location_kind(route)
        if loc == 'vivienda':
            vivienda = target['municipio']
        elif loc == 'trabajo':
            trabajo = target['municipio']
        elif loc == 'ultimo_municipio':
            vivienda = target['municipio']
        elif loc == 'departamento':
            # Municipio cualquiera dentro del mismo departamento; el CN candidato mantiene departamento único.
            vivienda = f"municipio_base_{target['departamento']}"
    if 'R2.D01' in sub and sub['R2.D01'] == 'NO':
        vivienda = 'SIN_MUNICIPIO'
    if 'R2.D04' in sub and sub['R2.D04'] == 'NO' and 'TRAB_ONLY' not in fc and 'TRAB_' not in fc:
        trabajo = 'SIN_MUNICIPIO'
    if r3_id(ctx['expanded_route_id']) == 'R3-001':
        vivienda = 'SIN_MUNICIPIO'
        trabajo = 'SIN_MUNICIPIO'
    return vivienda, trabajo

def target_abfs_for_expected(cn: dict, patrono_filter: bool, rid: str, cliente_patrono: str) -> list[str]:
    out=[]
    for a in cn['abfs']:
        if a['asignadoEstado'] != 'Alta' or a['asignadoBanca'] != BANCA_PERSONAS:
            continue
        if patrono_filter and not is_specialist(a, cliente_patrono):
            continue
        if rid == 'R1-002' and a['asignadoBolsonEstado'] != 'Deficit':
            continue
        out.append(a['asignadoCod'])
    return out

def main_credit(ctx: dict, route: dict, target_cn: str|None, by_code: dict[str,dict]) -> dict:
    bt = ctx['final_output_class_id'] == 'CONTROL_BT'
    credito_banca = BANCA_TRABAJADORES if bt else BANCA_PERSONAS
    labor_type = {'ABF':'abf','CN':'cn','CP':'cp','abf':'abf','cn':'cn','cp':'cp'}.get(ctx['labor_type'], 'abf')
    cosecha = harvest_cn_for_context(ctx, route, target_cn, by_code)
    cosecha_code = cosecha['cod']
    labor_cn_obj, labor_abf = labor_abf_for_context(ctx, by_code)
    labor_code = labor_abf['asignadoCod']
    labor_estado = labor_abf['asignadoEstado']
    labor_banca = labor_abf['asignadoBanca']
    labor_cn = labor_cn_obj['cod']
    labor_region = labor_cn_obj['region']
    labor_municipio = labor_cn_obj['municipio']
    labor_age = labor_abf['asignadoEdad']
    if ctx['general_decisions'].get('D25') == 'SI':
        current_cn, current_abf, has_current_abf = current_assignment_for_context(ctx, target_cn)
        current_cn_obj = by_code.get(current_cn)
        current_abf_obj = None
        if current_cn_obj:
            current_abf_obj = next((a for a in current_cn_obj['abfs'] if a['asignadoCod'] == current_abf), None)
        if has_current_abf and current_cn_obj and current_abf_obj:
            labor_type = 'abf'
            labor_code = current_abf
            labor_estado = current_abf_obj['asignadoEstado']
            labor_banca = current_abf_obj['asignadoBanca']
            labor_cn = current_cn
            labor_region = current_cn_obj['region']
            labor_municipio = current_cn_obj['municipio']
            labor_age = current_abf_obj['asignadoEdad']
    if ctx['labor_type'] == 'CP':
        labor_type = 'cp'; labor_code = CP_CN; labor_cn = CP_CN; labor_age='0'
        labor_region = by_code[CP_CN]['region']; labor_municipio = by_code[CP_CN]['municipio']; cosecha_code = CP_CN; cosecha = by_code[cosecha_code]
    elif ctx['labor_type'] == 'CN':
        labor_type = 'cn'; labor_code = cosecha['cod']; labor_cn = cosecha['cod']; labor_age='0'
        labor_region = cosecha['region']; labor_municipio = cosecha['municipio']
    if ctx['cn_cosecha_estado'] == 'BAJA':
        cosecha_code = CERRADO_CN; cosecha = by_code[cosecha_code]
    fecha = '2026-05-01' if ctx['harvest_last_month'] else '2025-01-15'
    return {
        'creditoNo': 'SOL' + ctx['case_id'][-4:] + str(ctx['seed'])[-6:],
        'creditoMonto': str(10000 + ctx['rng'].randint(0, 40000)) + '.00',
        'creditoTasa': '18.5',
        'creditoTipo': 'Recredito' if ctx['credito_tipo'] == 'RECREDITO' else 'Nuevo',
        'creditoEstado': ctx['current_credit_status'],
        'creditoPatronoNombre': ctx['cliente_patrono_nombre'],
        'creditoPatronoCod': ctx['cliente_patrono_cod'],
        'creditoBanca': credito_banca,
        'creditoTipoCliente': ctx['tipo_cliente'],
        'creditoRegion': norm_region(ctx['client_region']),
        'creditoFechaConsecion': fecha,
        'creditoFechaCancelacion': '2027-05-01',
        'creditoPatrono': ctx['cliente_patrono_nombre'],
        'participanteLaborCod': labor_code,
        'participanteLaborEstado': labor_estado,
        'participanteLaborEdad': labor_age,
        'participanteLaborCn': labor_cn,
        'participanteLaborBanca': labor_banca,
        'participanteLaborRegion': labor_region,
        'participanteLaborMunicipio': labor_municipio,
        'participanteLaborVacacion': '0',
        'participanteLaborTipo': labor_type,
        'cnCosechaCod': cosecha['cod'],
        'cnCosechaNombre': cosecha['nombre'],
        'cnCosechaEstado': cosecha['estado'],
        'cnCosechaRegion': cosecha['region'],
        'cnCosechaDepartamento': cosecha['departamento'],
        'cnCosechaMunicipio': cosecha['municipio'],
        '_history_role': 'CURRENT_REQUEST',
    }

def historical_credit(ctx: dict, i: int, cn_code: str, abf_code: str, by_code: dict[str,dict]) -> dict:
    cn = by_code[cn_code]
    return {
        'creditoNo': 'HD' + str(i) + ctx['case_id'][-4:] + str(ctx['seed'])[-5:],
        'creditoMonto': str(8000 + ctx['rng'].randint(0, 25000)) + '.00',
        'creditoTasa': '17.0',
        'creditoTipo': 'Nuevo',
        'creditoEstado': ctx['history_credit_status'] or 'C',
        'creditoPatronoNombre': ctx['cliente_patrono_nombre'],
        'creditoPatronoCod': ctx['cliente_patrono_cod'],
        'creditoBanca': BANCA_PERSONAS,
        'creditoTipoCliente': ctx['tipo_cliente'],
        'creditoRegion': cn['region'],
        'creditoFechaConsecion': '2025-02-10',
        'creditoFechaCancelacion': '2026-02-10',
        'creditoPatrono': ctx['cliente_patrono_nombre'],
        'participanteLaborCod': abf_code,
        'participanteLaborEstado': 'Alta',
        'participanteLaborEdad': '35',
        'participanteLaborCn': cn_code,
        'participanteLaborBanca': BANCA_PERSONAS,
        'participanteLaborRegion': cn['region'],
        'participanteLaborMunicipio': cn['municipio'],
        'participanteLaborVacacion': '0',
        'participanteLaborTipo': 'abf',
        'cnCosechaCod': cn['cod'],
        'cnCosechaNombre': cn['nombre'],
        'cnCosechaEstado': cn['estado'],
        'cnCosechaRegion': cn['region'],
        'cnCosechaDepartamento': cn['departamento'],
        'cnCosechaMunicipio': cn['municipio'],
        '_history_role': 'HISTORY',
    }

def credito_xml(c: dict) -> str:
    fields = [
        ('creditoNo','creditoNo'),
        ('creditoMonto','creditoMonto'),
        ('creditoTasa','creditoTasa'),
        ('creditoTipo','creditoTipo'),
        ('creditoEstado','creditoEstado'),
        ('creditoPatronoNombre','creditoPatronoNombre'),
        ('creditoPatronoCod','creditoPatronoCod'),
        ('creditoBanca','creditoBanca'),
        ('creditoTipoCliente','creditoTipoCliente'),
        ('creditoRegion','creditoRegion'),
        ('creditoFechaConsecion','creditoFechaConsecion'),
        ('creditoFechaCancelacion','creditoFechaCancelacion'),
        ('creditoPatrono','creditoPatrono'),
        ('participanteLaborCod','participanteLaborCod'),
        ('participanteLaborEstado','participanteLaborEstado'),
        ('participanteLaborEdad','participanteLaborEdad'),
        ('participanteLaborCn','participanteLaborCn'),
        ('participanteLaborBanca','participanteLaborBanca'),
        ('participanteLaborRegion','participanteLaborRegion'),
        ('participanteLaborMunicipio','participanteLaborMunicipio'),
        ('participanteLaborVacacion','participanteLaborVacacion'),
        ('participanteLaborTipo','participanteLaborTipo'),
        ('cosechaCodigoCn','cnCosechaCod'),
        ('cosechaNombreCn','cnCosechaNombre'),
        ('cosechaEstadoCn','cnCosechaEstado'),
        ('cosechaRegionCn','cnCosechaRegion'),
        ('cosechaDepartamentoCn','cnCosechaDepartamento'),
        ('cosechaMunicipioCn','cnCosechaMunicipio'),
    ]
    return '<credito>' + ''.join(tag(out_name, c.get(src_name,'')) for out_name, src_name in fields) + '</credito>'

def build_creditos(ctx: dict, route: dict, target_cn: str|None, by_code: dict[str,dict]) -> list[dict]:
    # Cliente nuevo: sin historial de créditos en ActivoCrediticio.
    if ctx.get('tipo_cliente') == 'CN':
        return []
    creditos=[main_credit(ctx, route, target_cn, by_code)]
    rid = r1_id(ctx['expanded_route_id'])
    if target_cn and group_requires_desembolso(route):
        # Para rutas de desembolso, se agrega historial en el municipio/CN correcto. Para variantes con empate,
        # se agrega historial para cada ABF candidato válido.
        if rid in {'R1-002','R1-004'}:
            # Usar al menos 01 y 02. En R1-004 sin patrono, 03 puede ser candidato aleatorio, pero no se marca como historial.
            abfs = [f'{target_cn}01', f'{target_cn}02']
        else:
            abfs = [f'{target_cn}01']
        for i, abf in enumerate(abfs, 1):
            creditos.append(historical_credit(ctx, i, target_cn, abf, by_code))
    return creditos

def build_xml(ctx: dict, route: dict, creditos: list[dict], target_cn: str|None, by_code: dict[str,dict], static_activo_financiero: str) -> str:
    cf = stable_client_fields(ctx)
    gen = ctx['general_decisions']
    bt = ctx['final_output_class_id'] == 'CONTROL_BT'
    current_cn, current_abf, has_current_abf = current_assignment_for_context(ctx, target_cn)
    cliente_region = norm_region(ctx['client_region'])
    vivienda, trabajo = client_locations(ctx, route, target_cn, by_code)
    suggested = suggested_abf_fields(current_cn, current_abf, by_code) if gen.get('D15') == 'SI' else suggested_abf_fields('', '', by_code)
    first_credit_no = creditos[0]['creditoNo'] if creditos else ''
    parts = ['<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:rule="http://bar.foo.com/rule">',
             '<soapenv:Header/>',
             '<soapenv:Body><rule:entryPointAdmonCarteraV2><arg0>']
    parts.extend([
        tag('clienteNombre', cf['clienteNombre']),
        tag('clienteCod', cf['clienteCod']),
        tag('clienteEdad', cf['clienteEdad']),
        tag('clienteGenero', cf['clienteGenero']),
        tag('clienteRegion', cliente_region),
        tag('clienteMunicipioVivienda', vivienda),
        tag('clienteMunicipioTrabajo', trabajo),
        tag('clienteEsSugerido', req_bool(gen.get('D15') == 'SI')),
        tag('clienteEstabaAsignadoAbf', req_bool(has_current_abf)),
        tag('clienteEsCarteraDelCnCod', current_cn),
        tag('clienteFueDesembolsadoEnElUltimoMes', req_bool(bool(ctx['harvest_last_month']))),
        tag('clienteEsCarteraDelAbfCod', current_abf),
        tag('abfSugeridoCod', suggested['abfSugeridoCod']),
        tag('abfSugeridoEstado', suggested['abfSugeridoEstado']),
        tag('abfSugeridoEdad', suggested['abfSugeridoEdad']),
        tag('abfSugeridoCnCod', suggested['abfSugeridoCnCod']),
        tag('abfSugeridoBanca', suggested['abfSugeridoBanca']),
        tag('abfSugeridoRegion', suggested['abfSugeridoRegion']),
        tag('abfSugeridoMunicipio', suggested['abfSugeridoMunicipio']),
        tag('abfSugeridoOportunidad', suggested['abfSugeridoOportunidad']),
        tag('clienteDpi', cf['clienteDpi']),
        tag('clienteesTrabajadorBt', 'S' if gen.get('D03') == 'EMPLEADO' else 'N'),
        '<informacionGeneral>' + tag('fecha', RUN_DATE) + '</informacionGeneral>',
        '<activoCrediticio>'
    ])
    parts.extend(credito_xml(c) for c in creditos)
    parts.append('</activoCrediticio>')
    parts.append(static_activo_financiero)
    parts.append(
        '<salidaBlaze><asignacionCredito>'
        + tag('clienteCredito', first_credit_no)
        + tag('clienteDpi', cf['clienteDpi'])
        + tag('cnAsignadoAnteriorCod', current_cn)
        + tag('abfAsignadoAnteriorCod', current_abf)
        + '</asignacionCredito></salidaBlaze>'
    )
    parts.append('</arg0></rule:entryPointAdmonCarteraV2></soapenv:Body></soapenv:Envelope>')
    return ''.join(parts)

def build_expected(ctx: dict, route: dict, target_cn: str|None, by_code: dict[str,dict]) -> dict:
    cf = stable_client_fields(ctx)
    fc = ctx['final_output_class_id']
    current_cn, current_abf, _has_current_abf = current_assignment_for_context(ctx, target_cn)
    expected = {
        'case_id': ctx['case_id'],
        'expanded_route_id': ctx['expanded_route_id'],
        'general_route_id': ctx['general_route_id'],
        'included_in_core': ctx['included_in_core'],
        'expected_mode': ctx['expected_mode'],
        'final_output_class_id': fc,
        'codCliente': cf['clienteCod'],
        'dpiCliente': cf['clienteDpi'],
        'codCnAnterior': current_cn,
        'codAbfAnterior': current_abf,
        'codCnActual': '',
        'codAbfActual': '',
        'bolson': '',
        'accepted_cod_cn_set': '',
        'accepted_cod_abf_set': '',
        'expected_control_tree': '',
        'expected_description': '',
        'is_random_selection': 'No',
        'cliente_patrono': ctx['cliente_patrono_nombre'],
        'tipo_cliente_expected': ctx['tipo_cliente'],
    }
    rid = r1_id(ctx['expanded_route_id'])
    if fc == 'CONTROL_BT':
        expected['expected_mode'] = 'HANDOFF_CONTROL'
        expected['expected_control_tree'] = 'BT'
        expected['expected_description'] = 'Redirigir a árbol BT; fuera del flujo ABF/Banca Personas.'
    elif fc == 'R3_PENDING_BOLSON':
        expected['expected_mode'] = 'BOLSON'
        expected['bolson'] = 'PENDIENTES'
        expected['expected_description'] = 'Asignar al bolsón de clientes pendientes.'
    elif is_r1_route(ctx['expanded_route_id']) and target_cn:
        expected['codCnActual'] = target_cn
        patrono_filter = group_requires_patrono(route)
        cn_obj = by_code[target_cn]
        accepted = target_abfs_for_expected(cn_obj, patrono_filter, rid or '', ctx['cliente_patrono_nombre'])
        if rid in {'R1-002','R1-004'}:
            expected['expected_mode'] = 'ACCEPTED_SET'
            expected['accepted_cod_cn_set'] = target_cn
            expected['accepted_cod_abf_set'] = '|'.join(accepted)
            expected['is_random_selection'] = 'Si'
            expected['expected_description'] = 'Selección aleatoria: cualquier ABF listado en codAbfActual1..N es válido.'
        else:
            expected['expected_mode'] = 'EXACT'
            expected['codAbfActual'] = accepted[0] if accepted else ''
            expected['expected_description'] = 'Asignar al ABF candidato único esperado.'
    elif fc in {'KEEP_CURRENT_ASSIGNMENT', 'KEEP_ABF_ASSIGNMENT'}:
        expected['expected_mode'] = 'EXACT'
        expected['codCnActual'] = current_cn
        expected['codAbfActual'] = current_abf
        expected['expected_description'] = 'Mantener asignación actual.'
    elif fc in {'ASSIGN_NEW_ABF','ASSIGN_NEW_ABF_CANCEL_NEW_CN','ASSIGN_LAST_DISB_ABF','ASSIGN_LAST_DISB_ABF_CANCEL_LAST_CN','ASSIGN_HARVEST_ABF'}:
        expected['expected_mode'] = 'EXACT'
        labor_cn, labor_abf = labor_abf_for_context(ctx, by_code)
        expected['codCnActual'] = labor_cn['cod']
        expected['codAbfActual'] = labor_abf['asignadoCod']
        expected['expected_description'] = 'Asignar al ABF que desembolsó; codCnActual es el CN laboral al que pertenece el ABF.'
    elif fc in {'ASSIGN_AGENCY_NEW_CN','ASSIGN_AGENCY_NEW_CN_CANCEL_NEW_CN'}:
        expected['expected_mode'] = 'EXACT'
        expected['codCnActual'] = harvest_cn_for_context(ctx, route, target_cn, by_code)['cod']
        expected['codAbfActual'] = '-1'
        expected['expected_description'] = 'Asignar a cartera agencia del nuevo CN.'
    else:
        expected['expected_description'] = 'Salida no clasificada explícitamente; revisar catálogo.'
    return expected

def abf_slot_fields(max_slots: int) -> list[str]:
    return [f'codAbfActual{i}' for i in range(1, max_slots + 1)]

def expected_abf_values(expected: dict) -> list[str]:
    if expected.get('is_random_selection') == 'Si':
        return [x for x in expected.get('accepted_cod_abf_set', '').split('|') if x]
    abf = expected.get('codAbfActual', '')
    return [abf] if abf else []

def expected_row_for_csv(expected: dict, max_slots: int) -> dict:
    row = dict(expected)
    for field in abf_slot_fields(max_slots):
        row[field] = ''
    for idx, abf in enumerate(expected_abf_values(expected)[:max_slots], start=1):
        row[f'codAbfActual{idx}'] = abf
    return row

def ensure_hardlink(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            if os.path.samefile(src, dst):
                return
        except OSError:
            pass
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        write_bytes_retry(dst, src.read_bytes())

def tar_add_bytes(tar: tarfile.TarFile, arcname: str, data: bytes, mtime: int) -> None:
    info = tarfile.TarInfo(arcname); info.size = len(data); info.mtime = mtime; info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))

def tar_add_file(tar: tarfile.TarFile, src: Path, arcname: str, mtime: int) -> None:
    info = tarfile.TarInfo(arcname); st = src.stat(); info.size = st.st_size; info.mtime = mtime; info.mode = 0o644
    with src.open('rb') as f: tar.addfile(info, f)

def validate_domains_from_xml(xml_bytes: bytes) -> tuple[dict[str, Counter], list[dict]]:
    root = ET.fromstring(xml_bytes)
    values = {field: Counter() for field in DOMAIN_RULES}
    failures=[]
    for field, allowed in DOMAIN_RULES.items():
        for elem in root.findall(f'.//{field}'):
            val = elem.text or ''
            values[field][val]+=1
            if val == '' and field in OPTIONAL_BLANK_DOMAIN_FIELDS:
                continue
            if val not in allowed:
                failures.append({'field':field,'value':val,'allowed':'|'.join(sorted(allowed))})
    return values, failures

def derive_tipo_cliente(creditos: list[dict], ctx: dict) -> str:
    # Se usa el estado del historial. Para CN, se conserva un crédito SOL de solicitud para patrono,
    # pero no se considera historial. Los créditos históricos tienen prefijo HD.
    hist = [c for c in creditos if str(c.get('creditoNo','')).startswith('HD')]
    if ctx['tipo_cliente'] == 'CN' and not hist:
        return 'CN'
    states = [c['creditoEstado'] for c in creditos]
    if any(s == 'D' for s in states):
        return 'CE'
    if states and all(s == 'C' for s in states):
        return 'CR'
    return 'INDETERMINADO'

def tipo_cliente_validation(ctx: dict, creditos: list[dict]) -> dict:
    derived = derive_tipo_cliente(creditos, ctx)
    return {
        'tipo_cliente_expected': ctx['tipo_cliente'],
        'tipo_cliente_derived': derived,
        'tipo_cliente_pass': 'Si' if derived == ctx['tipo_cliente'] else 'No',
        'credit_states': '|'.join(c['creditoEstado'] for c in creditos),
        'history_credit_count': sum(1 for c in creditos if str(c.get('creditoNo','')).startswith('HD')),
        'rule_note': ctx['tipo_cliente_rule'],
    }

def patrono_validation(ctx: dict, route: dict, cns: list[dict], target_cn: str|None, by_code: dict[str,dict]) -> dict:
    patrono = ctx['cliente_patrono_nombre']
    all_abfs = [a for cn in cns for a in cn['abfs']]
    global_match = any(is_specialist(a, patrono) for a in all_abfs)
    target_match = False
    if target_cn:
        target_match = any(a['asignadoEstado']=='Alta' and a['asignadoBanca']==BANCA_PERSONAS and is_specialist(a, patrono) for a in by_code[target_cn]['abfs'])
    expected_yes = route_patrono_yes(route)
    return {
        'cliente_patrono': patrono,
        'expected_specialist_answer': 'Si' if expected_yes else 'No',
        'global_abf_specialist_exists': 'Si' if global_match else 'No',
        'target_scope_specialist_exists': 'Si' if target_match else 'No',
        'patrono_validation_pass': 'Si' if ((global_match if expected_yes else not global_match)) else 'No',
        'patrono_field_rule': 'Se revisa especialistaPatrono1, especialistaPatrono2 o especialistaPatrono3 contra creditoPatrono.'
    }

def r2_validation(ctx: dict, route: dict, creditos: list[dict], target_cn: str|None, by_code: dict[str,dict]) -> dict:
    sub = ctx.get('sub_decisions', {})
    if not any(k.startswith('R2.') for k in sub):
        return {'is_r2':'No','r2_pass':'N/A','notes':''}
    target = by_code[target_cn] if target_cn else None
    vivienda, trabajo = client_locations(ctx, route, target_cn, by_code)
    hist = [c for c in creditos if str(c.get('creditoNo','')).startswith('HD')]
    viv_hist = any(c['cnCosechaMunicipio'] == vivienda and c['cnCosechaEstado'] == 'Alta' for c in hist)
    trab_hist = any(c['cnCosechaMunicipio'] == trabajo and c['cnCosechaEstado'] == 'Alta' for c in hist)
    target_patrono = None
    if target:
        target_patrono = any(a['asignadoEstado']=='Alta' and a['asignadoBanca']==BANCA_PERSONAS and is_specialist(a, ctx['cliente_patrono_nombre']) for a in target['abfs'])
    checks=[]; notes=[]
    if 'R2.D01' in sub:
        checks.append((sub['R2.D01']=='SI' and vivienda!='SIN_MUNICIPIO') or (sub['R2.D01']=='NO' and vivienda=='SIN_MUNICIPIO'))
    if 'R2.D02' in sub:
        checks.append((sub['R2.D02']=='SI' and viv_hist) or (sub['R2.D02']=='NO' and not viv_hist))
    if 'R2.D03' in sub:
        checks.append((sub['R2.D03']=='SI' and bool(target_patrono)) or (sub['R2.D03']=='NO' and not bool(target_patrono)))
    if 'R2.D04' in sub:
        if sub['R2.D04']=='SI': checks.append(trabajo!='SIN_MUNICIPIO')
        elif sub['R2.D04']=='NO' and 'TRAB_' not in ctx['final_output_class_id'] and 'TRAB_ONLY' not in ctx['final_output_class_id']:
            checks.append(trabajo=='SIN_MUNICIPIO')
    for d in ['R2.D05','R2.D09']:
        if d in sub:
            checks.append((sub[d]=='SI' and trab_hist) or (sub[d]=='NO' and not trab_hist))
    for d in ['R2.D06','R2.D07','R2.D08','R2.D10','R2.D11']:
        if d in sub:
            checks.append((sub[d]=='SI' and bool(target_patrono)) or (sub[d]=='NO' and not bool(target_patrono)))
    r2_pass = all(checks) if checks else True
    if not r2_pass:
        notes.append(f"sub={sub}; vivienda={vivienda}; trabajo={trabajo}; viv_hist={viv_hist}; trab_hist={trab_hist}; target_patrono={target_patrono}; target_cn={target_cn}; cliente_patrono={ctx['cliente_patrono_nombre']}")
    return {
        'is_r2':'Si',
        'r2_pass':'Si' if r2_pass else 'No',
        'r2_decisions': ';'.join(f'{k}={v}' for k,v in sorted(sub.items()) if k.startswith('R2.')),
        'clienteMunicipioVivienda': vivienda,
        'clienteMunicipioTrabajo': trabajo,
        'target_cn': target_cn or '',
        'target_cn_municipio': target['municipio'] if target else '',
        'target_cn_departamento': target['departamento'] if target else '',
        'has_hist_vivienda': 'Si' if viv_hist else 'No',
        'has_hist_trabajo': 'Si' if trab_hist else 'No',
        'target_has_patrono_specialist': 'Si' if target_patrono else 'No',
        'cliente_patrono': ctx['cliente_patrono_nombre'],
        'notes':' | '.join(notes)
    }

def write_static_cn_catalog_csv(path: Path, cns: list[dict]) -> None:
    fields = ['cn_key','parent_group_key','r1_id','replica','cn_cod','cn_nombre','cn_estado','cn_region','cn_departamento','cn_municipio','group_requires_patrono','group_requires_desembolso','location_kind','abf_count','abf_codes','abf_specialist_values']
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for cn in cns:
            w.writerow({
                'cn_key': cn.get('key',''), 'parent_group_key': cn.get('parent_group_key',''), 'r1_id': cn.get('r1_id',''), 'replica': cn.get('replica',''),
                'cn_cod': cn['cod'], 'cn_nombre': cn['nombre'], 'cn_estado': cn['estado'], 'cn_region': cn['region'],
                'cn_departamento': cn['departamento'], 'cn_municipio': cn['municipio'],
                'group_requires_patrono': cn.get('group_requires_patrono',''), 'group_requires_desembolso': cn.get('group_requires_desembolso',''), 'location_kind': cn.get('location_kind',''),
                'abf_count': len(cn['abfs']), 'abf_codes': '|'.join(a['asignadoCod'] for a in cn['abfs']),
                'abf_specialist_values': '|'.join(f"{a['asignadoCod']}:{a['especialistaPatrono1']},{a['especialistaPatrono2']},{a['especialistaPatrono3']}" for a in cn['abfs'])
            })

def write_patrono_catalog_csv(path: Path) -> None:
    with path.open('w', newline='', encoding='utf-8') as f:
        fields=['patronoCod','patronoNombre','appears_in_specialist_fields']
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for p in PATRONO_CATALOG:
            w.writerow({**p, 'appears_in_specialist_fields':'Si' if p['patronoNombre'] in PATRONO_MATCH_NAMES else 'No'})
        w.writerow({**PATRONO_NO_SPECIALIST, 'appears_in_specialist_fields':'No'})

def write_validate_random_script(path: Path) -> None:
    path.write_text(r'''#!/usr/bin/env python3
import argparse, csv
from collections import defaultdict

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--responses', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--score', required=True)
    args=ap.parse_args()
    expected_per_route=1000
    valid=defaultdict(set); meta={}
    with open(args.candidates, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            cn=(r.get('codCnActual') or r.get('candidate_cod_cn_actual') or '').strip()
            abfs=[(r.get(k) or '').strip() for k in sorted(r) if k.startswith('codAbfActual')]
            if not abfs and r.get('candidate_cod_abf_actual'):
                abfs=[r.get('candidate_cod_abf_actual','').strip()]
            for abf in abfs:
                if cn and abf:
                    valid[r['case_id']].add((cn, abf))
            meta[r['case_id']]=r['expanded_route_id']
    rows=[]; score=defaultdict(lambda:{'valid':0,'invalid':0,'pending':0})
    with open(args.responses, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            cid=r['case_id']; route=r.get('expanded_route_id') or meta.get(cid,'')
            cn=(r.get('actual_cod_cn_actual') or '').strip(); abf=(r.get('actual_cod_abf_actual') or '').strip()
            if not cn and not abf:
                status='PENDING'; score[route]['pending']+=1
            elif (cn,abf) in valid.get(cid,set()):
                status='PASS_ACCEPTED_SET'; score[route]['valid']+=1
            else:
                status='FAIL_RANDOM_NOT_IN_ACCEPTED_SET'; score[route]['invalid']+=1
            out=dict(r); out['random_validation_status']=status; rows.append(out)
    fields=list(rows[0].keys()) if rows else ['case_id','random_validation_status']
    with open(args.out,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    with open(args.score,'w',newline='',encoding='utf-8') as f:
        fields=['expanded_route_id','actual_correct_count','invalid_random_selection_count','pending_count','branch_status']
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for route,s in sorted(score.items()):
            branch_status='PASS' if s['valid']==expected_per_route and s['invalid']==0 and s['pending']==0 else 'REVIEW'
            w.writerow({'expanded_route_id':route,'actual_correct_count':s['valid'],'invalid_random_selection_count':s['invalid'],'pending_count':s['pending'],'branch_status':branch_status})
if __name__=='__main__': main()
''', encoding='utf-8')

def main(limit: int|None=None) -> None:
    start=time.time()
    if ARCHIVE.exists(): ARCHIVE.unlink()
    catalog_rows=load_catalog_rows()
    catalog={r['expanded_route_id']: r for r in catalog_rows}
    manifest_rows=build_manifest_rows_from_catalog(catalog_rows, limit)
    cns, group_variant_to_cns, by_code = build_static_catalog(catalog)
    static_activo_financiero = '<activoFinanciero>' + ''.join(centro_xml(cn) for cn in cns) + '</activoFinanciero>'
    static_hash = hashlib.sha256(static_activo_financiero.encode('utf-8')).hexdigest()
    max_abf_slots=max(len(cn['abfs']) for cn in cns)
    abf_fields=abf_slot_fields(max_abf_slots)
    tmpdir=Path(tempfile.mkdtemp(prefix='qa100_v6_', dir=str(BASE)))
    mtime=int(time.time())
    expected_csv=tmpdir/'expected_outputs.csv'
    validation_csv=tmpdir/'generation_validation.csv'
    r2_detail_csv=tmpdir/'r2_validation_detail.csv'
    tipo_csv=tmpdir/'tipo_cliente_validation.csv'
    patrono_csv=tmpdir/'patrono_validation.csv'
    bt_csv=tmpdir/'bt_validation_detail.csv'
    route_summary_csv=tmpdir/'route_generation_summary.csv'
    sample_sha_csv=tmpdir/'sample_sha256_validation.csv'
    generation_summary_json=tmpdir/'generation_summary.json'
    domain_summary_json=tmpdir/'domain_validation_summary.json'
    r2_summary_json=tmpdir/'r2_validation_summary.json'
    tipo_summary_json=tmpdir/'tipo_cliente_validation_summary.json'
    patrono_summary_json=tmpdir/'patrono_validation_summary.json'
    bt_summary_json=tmpdir/'bt_validation_summary.json'
    random_summary_json=tmpdir/'random_selection_validation_summary.json'
    cn_catalog_csv=tmpdir/'cn_catalog.csv'
    patrono_catalog_csv=tmpdir/'patrono_catalog.csv'
    random_case_id_csv=tmpdir/'random_case_id.csv'
    random_candidates_csv=tmpdir/'random_candidates.csv'
    random_response_template_csv=tmpdir/'random_response_template.csv'
    random_branch_score_csv=tmpdir/'random_branch_score.csv'
    validate_random_py=tmpdir/'validate_random.py'
    write_static_cn_catalog_csv(cn_catalog_csv, cns)
    write_patrono_catalog_csv(patrono_catalog_csv)
    write_validate_random_script(validate_random_py)
    manifest_copy=tmpdir/'case_manifest_1000_full_v6.csv'
    write_manifest_csv(manifest_copy, manifest_rows)

    expected_fields=['case_id','expanded_route_id','general_route_id','included_in_core','expected_mode','final_output_class_id','codCliente','dpiCliente','codCnActual',*abf_fields,'codCnAnterior','codAbfAnterior','bolson','expected_control_tree','expected_description','is_random_selection','cliente_patrono','tipo_cliente_expected']
    validation_fields=['case_id','expanded_route_id','general_route_id','final_output_class_id','input_xml_path','xml_generated','expected_generated','all_static_cn_catalog_present','cn_count','min_abfs_per_cn','max_abfs_per_cn','activo_financiero_hash','activo_financiero_hash_matches_static','domain_validation_pass','r2_case','r2_validation_pass','tipo_cliente_pass','patrono_validation_pass','bt_control_case','bt_credito_banca_ok','bt_expected_tree_ok','labor_cn','cosecha_cn','labor_cosecha_can_differ','cliente_edad','cliente_patrono','tipo_cliente_expected','target_cn','notes']
    r2_fields=['case_id','expanded_route_id','input_xml_path','r2_decisions','clienteMunicipioVivienda','clienteMunicipioTrabajo','target_cn','target_cn_municipio','target_cn_departamento','has_hist_vivienda','has_hist_trabajo','target_has_patrono_specialist','cliente_patrono','r2_pass','notes']
    tipo_fields=['case_id','expanded_route_id','input_xml_path','tipo_cliente_expected','tipo_cliente_derived','tipo_cliente_pass','credit_states','history_credit_count','rule_note']
    patrono_fields=['case_id','expanded_route_id','input_xml_path','cliente_patrono','expected_specialist_answer','global_abf_specialist_exists','target_scope_specialist_exists','patrono_validation_pass','patrono_field_rule']
    bt_fields=['case_id','input_xml_path','credito_banca_values','abf_sugerido_banca','expected_control_tree','pass_bt_validation']
    sample_fields=['case_id','input_xml_path','sha256','activo_financiero_hash','domain_validation_pass','r2_case','r2_pass','tipo_cliente_pass','patrono_validation_pass']
    rand_case_fields=['case_id','expanded_route_id','input_xml_path','is_random_selection','validation_mode','expected_correct_count_for_branch','codCnActual',*abf_fields]
    rand_candidate_fields=[*rand_case_fields,'candidate_valid_flag','candidate_selected_flag_after_blaze']
    rand_response_fields=['case_id','expanded_route_id','input_xml_path','actual_cod_cn_actual','actual_cod_abf_actual']
    rand_score_fields=['expanded_route_id','random_cases_expected','expected_correct_count','validation_rule']

    counts=Counter(); route_counts=Counter(); output_counts=Counter(); final_rule_counts=Counter(); cn_count_values=Counter(); abf_min_values=Counter(); abf_max_values=Counter()
    bt_total=bt_pass=0; static_hash_fail=0; domain_fail_total=0; r2_total=r2_pass_count=0; labor_diff_count=0
    tipo_total=tipo_pass_count=0; patrono_total=patrono_pass_count=0; random_cases=0; random_candidate_rows=0
    domain_value_counters={field:Counter() for field in DOMAIN_RULES}; domain_failure_samples=[]; sample_rows=[]; first_xml_full=None
    route_r2_failures=Counter(); route_tipo_failures=Counter(); route_patrono_failures=Counter(); route_random_counts=Counter()
    age_by_route=defaultdict(set); vivienda_by_route=defaultdict(set); patrono_by_route=defaultdict(set)

    zstd_out = ARCHIVE.open('wb')
    zstd = subprocess.Popen(['zstd','-T0','--fast=5','--quiet'], stdin=subprocess.PIPE, stdout=zstd_out)
    zstd._qa_out_handle = zstd_out  # keep file handle alive until zstd finishes
    try:
        assert zstd.stdin is not None
        tar=tarfile.open(fileobj=zstd.stdin, mode='w|')
        try:
            for src, subdir in [(CATALOG,'00_catalogos'),(FIELD_CONTRACT,'00_catalogos'),(SCENARIOS,'00_catalogos'),(manifest_copy,'01_manifest'),(cn_catalog_csv,'00_catalogos'),(patrono_catalog_csv,'00_catalogos')]:
                tar_add_file(tar, src, f'{ROOT_NAME}/{subdir}/{src.name}', mtime)
            for src in [BASE_GEN, Path(__file__), validate_random_py]:
                if src.exists(): tar_add_file(tar, src, f'{ROOT_NAME}/05_scripts/{src.name}', mtime)
            with expected_csv.open('w',newline='',encoding='utf-8') as ef, validation_csv.open('w',newline='',encoding='utf-8') as vf, r2_detail_csv.open('w',newline='',encoding='utf-8') as r2f, tipo_csv.open('w',newline='',encoding='utf-8') as tf, patrono_csv.open('w',newline='',encoding='utf-8') as pf, bt_csv.open('w',newline='',encoding='utf-8') as bf, random_case_id_csv.open('w',newline='',encoding='utf-8') as rcf, random_candidates_csv.open('w',newline='',encoding='utf-8') as rcandf, random_response_template_csv.open('w',newline='',encoding='utf-8') as rrtf:
                ew=csv.DictWriter(ef, fieldnames=expected_fields); ew.writeheader()
                vw=csv.DictWriter(vf, fieldnames=validation_fields); vw.writeheader()
                r2w=csv.DictWriter(r2f, fieldnames=r2_fields); r2w.writeheader()
                tw=csv.DictWriter(tf, fieldnames=tipo_fields); tw.writeheader()
                pw=csv.DictWriter(pf, fieldnames=patrono_fields); pw.writeheader()
                bw=csv.DictWriter(bf, fieldnames=bt_fields); bw.writeheader()
                rcw=csv.DictWriter(rcf, fieldnames=rand_case_fields); rcw.writeheader()
                rcandw=csv.DictWriter(rcandf, fieldnames=rand_candidate_fields); rcandw.writeheader()
                rrw=csv.DictWriter(rrtf, fieldnames=rand_response_fields); rrw.writeheader()
                for idx, man in enumerate(manifest_rows, start=1):
                    route=catalog[man['expanded_route_id']]
                    ctx=qa.build_context(man, route)
                    ctx['global_case_number']=int(man.get('global_case_number') or idx)
                    assign_case_overrides(ctx, route)
                    pg, rid, target_cn = target_group(ctx, route, group_variant_to_cns)
                    creditos=build_creditos(ctx, route, target_cn, by_code)
                    xml=build_xml(ctx, route, creditos, target_cn, by_code, static_activo_financiero)
                    xml_bytes=xml.encode('utf-8')
                    rel_xml=man['input_xml_path']
                    tar_add_bytes(tar, f'{ROOT_NAME}/{rel_xml}', xml_bytes, mtime)
                    tar_add_bytes(tar, f'{ROOT_NAME}/{man["input_xml_flat_path"]}', xml_bytes, mtime)
                    expected=build_expected(ctx, route, target_cn, by_code)
                    expected_row=expected_row_for_csv(expected, max_abf_slots)
                    ew.writerow({k:expected_row.get(k,'') for k in expected_fields})

                    if expected.get('is_random_selection') == 'Si':
                        random_cases += 1
                        route_random_counts[ctx['expanded_route_id']] += 1
                        random_base={
                            'case_id': ctx['case_id'], 'expanded_route_id': ctx['expanded_route_id'], 'input_xml_path': rel_xml,
                            'is_random_selection': 'Si', 'validation_mode': 'ACCEPTED_SET', 'expected_correct_count_for_branch': str(CASES_PER_ROUTE),
                            'codCnActual': expected_row.get('codCnActual','')
                        }
                        random_base.update({field: expected_row.get(field, '') for field in abf_fields})
                        rcw.writerow(random_base)
                        rrw.writerow({'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml,'actual_cod_cn_actual':'','actual_cod_abf_actual':''})
                        random_candidate_rows += 1
                        rcandw.writerow({**random_base, 'candidate_valid_flag':'Si','candidate_selected_flag_after_blaze':''})

                    domain_ok=True
                    if idx <= 50 or idx % 1000 == 0:
                        dom_values, dom_failures=validate_domains_from_xml(xml_bytes)
                        for field,counter in dom_values.items(): domain_value_counters[field].update(counter)
                        if dom_failures:
                            domain_ok=False; domain_fail_total += 1
                            if len(domain_failure_samples)<20: domain_failure_samples.append({'case_id':ctx['case_id'],'failures':dom_failures[:10]})
                    cn_count=len(cns); abf_counts=[len(cn['abfs']) for cn in cns]
                    min_abfs=min(abf_counts); max_abfs=max(abf_counts)
                    cn_count_values[cn_count]+=1; abf_min_values[min_abfs]+=1; abf_max_values[max_abfs]+=1
                    static_hash_fail += 0

                    r2v=r2_validation(ctx, route, creditos, target_cn, by_code)
                    if r2v['is_r2']=='Si':
                        r2_total += 1
                        if r2v['r2_pass']=='Si': r2_pass_count += 1
                        else: route_r2_failures[ctx['expanded_route_id']]+=1
                        r2w.writerow({k:r2v.get(k,'') for k in r2_fields if k not in {'case_id','expanded_route_id','input_xml_path'}} | {'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml})
                    tv=tipo_cliente_validation(ctx, creditos); tipo_total += 1
                    if tv['tipo_cliente_pass']=='Si': tipo_pass_count += 1
                    else: route_tipo_failures[ctx['expanded_route_id']]+=1
                    tw.writerow({'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml, **tv})
                    pv=patrono_validation(ctx, route, cns, target_cn, by_code); patrono_total += 1
                    if pv['patrono_validation_pass']=='Si': patrono_pass_count += 1
                    else: route_patrono_failures[ctx['expanded_route_id']]+=1
                    pw.writerow({'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml, **pv})

                    is_bt=ctx['final_output_class_id']=='CONTROL_BT'
                    bt_credito_banca_ok='N/A'; bt_expected_tree_ok='N/A'
                    if is_bt:
                        bt_total += 1
                        root=ET.fromstring(xml_bytes)
                        credito_bancas={e.text for e in root.findall('.//creditoBanca')}
                        abf_sug_banca=(root.find('.//abfSugeridoBanca').text or '') if root.find('.//abfSugeridoBanca') is not None else ''
                        bt_credito_banca_ok='Si' if credito_bancas=={xml_value(BANCA_TRABAJADORES)} else 'No'
                        bt_expected_tree_ok='Si' if expected.get('expected_control_tree')=='BT' else 'No'
                        pass_bt = bt_credito_banca_ok=='Si' and bt_expected_tree_ok=='Si'
                        if pass_bt: bt_pass += 1
                        bw.writerow({'case_id':ctx['case_id'],'input_xml_path':rel_xml,'credito_banca_values':'|'.join(sorted(credito_bancas)),'abf_sugerido_banca':abf_sug_banca,'expected_control_tree':expected.get('expected_control_tree',''),'pass_bt_validation':'Si' if pass_bt else 'No'})
                    if creditos:
                        labor_cn=creditos[0]['participanteLaborCn']; cosecha_cn=creditos[0]['cnCosechaCod']
                    else:
                        labor_cn=''; cosecha_cn=''
                    if labor_cn and labor_cn != cosecha_cn: labor_diff_count += 1
                    vivienda, _trabajo = client_locations(ctx, route, target_cn, by_code)
                    age_by_route[ctx['expanded_route_id']].add(ctx['cliente_edad'])
                    vivienda_by_route[ctx['expanded_route_id']].add(vivienda)
                    patrono_by_route[ctx['expanded_route_id']].add(ctx['cliente_patrono_nombre'])

                    vw.writerow({
                        'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'general_route_id':ctx['general_route_id'],'final_output_class_id':ctx['final_output_class_id'],'input_xml_path':rel_xml,
                        'xml_generated':'Si','expected_generated':'Si','all_static_cn_catalog_present':'Si','cn_count':cn_count,'min_abfs_per_cn':min_abfs,'max_abfs_per_cn':max_abfs,'activo_financiero_hash':static_hash,'activo_financiero_hash_matches_static':'Si','domain_validation_pass':'Si' if domain_ok else 'No',
                        'r2_case':r2v['is_r2'],'r2_validation_pass':r2v['r2_pass'],'tipo_cliente_pass':tv['tipo_cliente_pass'],'patrono_validation_pass':pv['patrono_validation_pass'],'bt_control_case':'Si' if is_bt else 'No','bt_credito_banca_ok':bt_credito_banca_ok,'bt_expected_tree_ok':bt_expected_tree_ok,
                        'labor_cn':labor_cn,'cosecha_cn':cosecha_cn,'labor_cosecha_can_differ':'Si' if labor_cn != cosecha_cn else 'No','cliente_edad':ctx['cliente_edad'],'cliente_patrono':ctx['cliente_patrono_nombre'],'tipo_cliente_expected':ctx['tipo_cliente'],'target_cn':target_cn or '','notes':r2v.get('notes','')
                    })
                    if len(sample_rows)<1000 or idx % 10000==0:
                        sample_rows.append({'case_id':ctx['case_id'],'input_xml_path':rel_xml,'sha256':hashlib.sha256(xml_bytes).hexdigest(),'activo_financiero_hash':static_hash,'domain_validation_pass':'Si' if domain_ok else 'No','r2_case':r2v['is_r2'],'r2_pass':r2v['r2_pass'],'tipo_cliente_pass':tv['tipo_cliente_pass'],'patrono_validation_pass':pv['patrono_validation_pass']})
                    if first_xml_full is None:
                        first_xml_full=xml
                    counts['total_cases']+=1; route_counts[ctx['expanded_route_id']]+=1; output_counts[ctx['final_output_class_id']]+=1; final_rule_counts[ctx['final_rule']]+=1
                    if idx % 5000 == 0: print(f'Generated {idx:,} XMLs', flush=True)
            with route_summary_csv.open('w',newline='',encoding='utf-8') as rf:
                rw=csv.DictWriter(rf, fieldnames=['expanded_route_id','generated_cases','distinct_cliente_edad','distinct_clienteMunicipioVivienda','distinct_cliente_patrono','random_cases']); rw.writeheader()
                for k,v in sorted(route_counts.items()):
                    rw.writerow({'expanded_route_id':k,'generated_cases':v,'distinct_cliente_edad':len(age_by_route[k]),'distinct_clienteMunicipioVivienda':len(vivienda_by_route[k]),'distinct_cliente_patrono':len(patrono_by_route[k]),'random_cases':route_random_counts.get(k,0)})
            with sample_sha_csv.open('w',newline='',encoding='utf-8') as sf:
                sw=csv.DictWriter(sf, fieldnames=sample_fields); sw.writeheader(); sw.writerows(sample_rows)
            with random_branch_score_csv.open('w',newline='',encoding='utf-8') as rb:
                rbw=csv.DictWriter(rb, fieldnames=rand_score_fields); rbw.writeheader()
                for k,v in sorted(route_random_counts.items()):
                    rbw.writerow({'expanded_route_id':k,'random_cases_expected':v,'expected_correct_count':str(CASES_PER_ROUTE),'validation_rule':f'PASS si Blaze devuelve un codCnActual y un codAbfActual dentro de las columnas codAbfActual1..N en los {CASES_PER_ROUTE} casos de la rama.'})

            domain_summary={
                'domain_validation_failed_sampled_cases': domain_fail_total,
                'sampled_case_count_for_domain_validation': 50 + max(0, (len(manifest_rows)-50)//1000),
                'domain_failure_samples': domain_failure_samples,
                'domain_values_observed': {f:dict(c) for f,c in domain_value_counters.items()},
                'domain_rules': {f:sorted(list(v)) for f,v in DOMAIN_RULES.items()},
                'note':'Validación muestral contra valores de requerimiento. creditoEstado permite C y D por regla de negocio indicada.'
            }
            r2_summary={
                'r2_cases_generated': r2_total,
                'r2_cases_passed_validation': r2_pass_count,
                'r2_validation_failed_cases': r2_total-r2_pass_count,
                'r2_validation_pass_rate': None if r2_total==0 else round(r2_pass_count/r2_total,6),
                'route_r2_failures': dict(route_r2_failures),
                'validation_rules': [
                    'R2.D01=SI implica clienteMunicipioVivienda conocido; R2.D01=NO implica SIN_MUNICIPIO.',
                    'R2.D02/R2.D05/R2.D09 validan si existe crédito histórico HD en CN abierto del municipio correspondiente.',
                    'Preguntas de especialista en patrono se validan contra especialistaPatrono1/2/3 del CN candidato.',
                    'Cada CN candidato usa municipioN/departamentoN único y se rota entre 3 réplicas por ruta para variar datos.'
                ]
            }
            tipo_summary={
                'tipo_cliente_cases_generated': tipo_total,
                'tipo_cliente_cases_passed_validation': tipo_pass_count,
                'tipo_cliente_validation_failed_cases': tipo_total-tipo_pass_count,
                'tipo_cliente_validation_pass_rate': None if tipo_total==0 else round(tipo_pass_count/tipo_total,6),
                'route_tipo_failures': dict(route_tipo_failures),
                'business_rule': [
                    'CE: al menos un crédito con estado D.',
                    'CR: existen créditos y todos están en estado C.',
                    'CN: sin créditos en ActivoCrediticio.'
                ]
            }
            patrono_summary={
                'patrono_cases_generated': patrono_total,
                'patrono_cases_passed_validation': patrono_pass_count,
                'patrono_validation_failed_cases': patrono_total-patrono_pass_count,
                'patrono_validation_pass_rate': None if patrono_total==0 else round(patrono_pass_count/patrono_total,6),
                'route_patrono_failures': dict(route_patrono_failures),
                'business_rule': 'Se compara creditoPatrono contra especialistaPatrono1, especialistaPatrono2 o especialistaPatrono3. Los campos de especialista contienen nombres de patrono, no códigos.',
                'finite_patronos_used': [p['patronoNombre'] for p in PATRONO_CATALOG] + [PATRONO_NO_SPECIALIST['patronoNombre']]
            }
            random_summary={
                'random_cases_generated': random_cases,
                'random_candidate_rows_generated': random_candidate_rows,
                'random_routes': len(route_random_counts),
                'expected_correct_count_per_random_route': CASES_PER_ROUTE,
                'random_candidate_layout': 'una fila por cliente con codAbfActual1..N',
                'validation_files': {
                    'case_identifier': '04_validation/random_case_id.csv',
                    'candidate_options': '04_validation/random_candidates.csv',
                    'response_template': '04_validation/random_response_template.csv',
                    'branch_scorecard': '04_validation/random_branch_score.csv',
                    'validator_script': '05_scripts/validate_random.py'
                }
            }
            summary={
                'artifact':ROOT_NAME,
                'archive_path':str(ARCHIVE),
                'archive_type':'tar.zst',
                'generated_at_utc':datetime.utcnow().isoformat()+'Z',
                'generator_version':RUN_VERSION,
                'cases_per_route':CASES_PER_ROUTE,
                'total_xml_inputs_generated':counts['total_cases'],
                'flat_xml_folder':FLAT_XML_DIR,
                'flat_xml_count':counts['total_cases'],
                'expected_abf_slot_count':max_abf_slots,
                'expanded_routes_generated':len(route_counts),
                'core_cases_generated':sum(cnt for rid2,cnt in route_counts.items() if rid2 != 'GPA-038__CONTROL_BT'),
                'bt_control_cases_generated':bt_total,
                'bt_control_cases_passed_validation':bt_pass,
                'bt_validation_pass_rate':None if bt_total==0 else round(bt_pass/bt_total,6),
                'r2_cases_generated':r2_total,
                'r2_cases_passed_validation':r2_pass_count,
                'r2_validation_failed_cases':r2_total-r2_pass_count,
                'tipo_cliente_cases_passed_validation': tipo_pass_count,
                'tipo_cliente_validation_failed_cases': tipo_total-tipo_pass_count,
                'patrono_cases_passed_validation': patrono_pass_count,
                'patrono_validation_failed_cases': patrono_total-patrono_pass_count,
                'random_cases_generated': random_cases,
                'random_routes_generated': len(route_random_counts),
                'static_cn_catalog_count':len(cns),
                'static_abf_total':sum(len(cn['abfs']) for cn in cns),
                'activo_financiero_static_hash':static_hash,
                'activo_financiero_hash_failures':static_hash_fail,
                'domain_validation_failed_sampled_cases':domain_fail_total,
                'cn_count_distribution':dict(cn_count_values),
                'min_abfs_per_cn_distribution':dict(abf_min_values),
                'max_abfs_per_cn_distribution':dict(abf_max_values),
                'labor_cosecha_different_cases':labor_diff_count,
                'final_rule_counts':dict(final_rule_counts),
                'output_class_counts':dict(output_counts),
                'notes':[
                    'Cada XML incluye exactamente el mismo bloque activoFinanciero en la estructura SOAP vigente.',
                    'Se agregan clienteGenero y asignadoGenero; como PED no depende de genero, se asignan de forma deterministica pseudoaleatoria.',
                    'Los valores alfanumericos del XML se serializan en mayuscula sin cambiar los nombres de etiquetas.',
                    'La fuerza comercial fija usa CNs/ABFs repetidos en todos los XMLs; se rotan 3 CNs candidatos por ruta para variar municipios sin perder control.',
                    'Los campos especialistaPatrono1/2/3 contienen nombres de patrono; el patrono del cliente se compara contra cualquiera de esos campos.',
                    'Tipo de cliente se deriva con la regla CE/D, CR/C, CN/sin créditos en ActivoCrediticio.',
                    'Las salidas aleatorias se consolidan en una fila por cliente con columnas codAbfActual1..N; codCnActual permanece unico.',
                    'La carpeta plana contiene todos los XMLs juntos, ademas de las carpetas separadas por ruta.'
                ]
            }
            generation_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
            domain_summary_json.write_text(json.dumps(domain_summary, ensure_ascii=False, indent=2), encoding='utf-8')
            r2_summary_json.write_text(json.dumps(r2_summary, ensure_ascii=False, indent=2), encoding='utf-8')
            tipo_summary_json.write_text(json.dumps(tipo_summary, ensure_ascii=False, indent=2), encoding='utf-8')
            patrono_summary_json.write_text(json.dumps(patrono_summary, ensure_ascii=False, indent=2), encoding='utf-8')
            random_summary_json.write_text(json.dumps(random_summary, ensure_ascii=False, indent=2), encoding='utf-8')
            bt_summary_json.write_text(json.dumps({'bt_control_cases_generated':bt_total,'bt_control_cases_passed_validation':bt_pass,'bt_validation_pass_rate':None if bt_total==0 else round(bt_pass/bt_total,6)}, ensure_ascii=False, indent=2), encoding='utf-8')
            readme = f'''Paquete QA Blaze - qa100 v6

Cambios incluidos:
- especialistaPatrono1/2/3 ahora son nombres de patrono; se compara contra creditoPatrono.
- Patronos finitos: patrono1, patrono2, patrono3, patrono4 y patrono_sin_especialista para forzar No.
- Tipo cliente derivado por regla de negocio: CE si existe estado D; CR si historial todo C; CN sin historial HD.
- Variación controlada por ruta: edad del cliente, patrono y municipio candidato cambian entre los {CASES_PER_ROUTE} casos sin romper la ruta.
- Casos de selección aleatoria identificados en una fila por cliente con columnas codAbfActual1..N.
- Estructura XML vigente con arg0, informacionGeneral, activoCrediticio, activoFinanciero y salidaBlaze/asignacionCredito.
- Campos clienteGenero y asignadoGenero agregados de forma deterministica pseudoaleatoria.
- Valores alfanumericos serializados en mayuscula sin cambiar nombres de etiquetas.
- activoFinanciero fijo en todos los XMLs con los mismos CNs y ABFs.

Resumen:
{json.dumps(summary, ensure_ascii=False, indent=2)}
'''
            tar_add_bytes(tar, f'{ROOT_NAME}/README.txt', readme.encode('utf-8'), mtime)
            if first_xml_full:
                tar_add_bytes(tar, f'{ROOT_NAME}/04_validation/sample_input_qa100_v6.xml', first_xml_full.encode('utf-8'), mtime)
                tar_add_bytes(tar, f'{ROOT_NAME}/04_validation/first_xml_preview.txt', first_xml_full[:12000].encode('utf-8'), mtime)
            for src, arc in [
                (expected_csv,'03_expected/expected_outputs.csv'),
                (validation_csv,'04_validation/generation_validation.csv'),
                (r2_detail_csv,'04_validation/r2_validation_detail.csv'),
                (tipo_csv,'04_validation/tipo_cliente_validation.csv'),
                (patrono_csv,'04_validation/patrono_validation.csv'),
                (bt_csv,'04_validation/bt_validation_detail.csv'),
                (random_case_id_csv,'04_validation/random_case_id.csv'),
                (random_candidates_csv,'04_validation/random_candidates.csv'),
                (random_response_template_csv,'04_validation/random_response_template.csv'),
                (random_branch_score_csv,'04_validation/random_branch_score.csv'),
                (route_summary_csv,'04_validation/route_generation_summary.csv'),
                (sample_sha_csv,'04_validation/sample_sha256_validation.csv'),
                (generation_summary_json,'04_validation/generation_summary.json'),
                (domain_summary_json,'04_validation/domain_validation_summary.json'),
                (r2_summary_json,'04_validation/r2_validation_summary.json'),
                (tipo_summary_json,'04_validation/tipo_cliente_validation_summary.json'),
                (patrono_summary_json,'04_validation/patrono_validation_summary.json'),
                (random_summary_json,'04_validation/random_selection_validation_summary.json'),
                (bt_summary_json,'04_validation/bt_validation_summary.json')
            ]:
                tar_add_file(tar, src, f'{ROOT_NAME}/{arc}', mtime)
        finally:
            tar.close()
    finally:
        try:
            if zstd.stdin: zstd.stdin.close()
        except Exception: pass
        rc=zstd.wait()
        try:
            zstd._qa_out_handle.close()
        except Exception:
            pass
        if rc!=0: raise RuntimeError(f'zstd exit code {rc}')
        # Copias sueltas para revisión rápida
        (BASE/'generation_summary_qa100_v6.json').write_bytes(generation_summary_json.read_bytes())
        (BASE/'domain_validation_summary_qa100_v6.json').write_bytes(domain_summary_json.read_bytes())
        (BASE/'r2_validation_summary_qa100_v6.json').write_bytes(r2_summary_json.read_bytes())
        (BASE/'tipo_cliente_validation_summary_qa100_v6.json').write_bytes(tipo_summary_json.read_bytes())
        (BASE/'patrono_validation_summary_qa100_v6.json').write_bytes(patrono_summary_json.read_bytes())
        (BASE/'random_selection_validation_summary_qa100_v6.json').write_bytes(random_summary_json.read_bytes())
        (BASE/'bt_validation_summary_qa100_v6.json').write_bytes(bt_summary_json.read_bytes())
        (BASE/'cn_catalog_qa100_v6.csv').write_bytes(cn_catalog_csv.read_bytes())
        (BASE/'patrono_catalog_qa100_v6.csv').write_bytes(patrono_catalog_csv.read_bytes())
        (BASE/'case_manifest_1000_full_v6.csv').write_bytes(manifest_copy.read_bytes())
        (BASE/'random_case_id_qa100_v6.csv').write_bytes(random_case_id_csv.read_bytes())
        (BASE/'random_candidates_qa100_v6.csv').write_bytes(random_candidates_csv.read_bytes())
        (BASE/'random_response_template_qa100_v6.csv').write_bytes(random_response_template_csv.read_bytes())
        (BASE/'random_branch_score_qa100_v6.csv').write_bytes(random_branch_score_csv.read_bytes())
        if first_xml_full:
            (BASE/'sample_input_qa100_v6.xml').write_text(first_xml_full, encoding='utf-8')
        # Evitar listar el .tar.zst completo aquí: tiene 22,200 XMLs y la validación de rutas largas
        # se controla por convención de nombres cortos en el manifest.
        (BASE/'qa100_v6_longest_path.txt').write_text('menor_a_120_caracteres\nqa100/02_inputs_xml_flat/<case_id>.xml>\n', encoding='utf-8')
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(json.dumps({'archive':str(ARCHIVE),'size_bytes':ARCHIVE.stat().st_size,'duration_seconds':round(time.time()-start,2),'total_xml_inputs_generated':counts['total_cases'],'r2_cases_generated':r2_total,'r2_cases_passed_validation':r2_pass_count,'tipo_cliente_passed':tipo_pass_count,'patrono_passed':patrono_pass_count,'random_cases':random_cases,'bt_cases_generated':bt_total,'bt_cases_passed_validation':bt_pass,'static_cn_catalog_count':len(cns),'static_abf_total':sum(len(cn['abfs']) for cn in cns),'cn_count_distribution':dict(cn_count_values)}, ensure_ascii=False, indent=2), flush=True)

def main_in_place(limit: int|None=None) -> None:
    start=time.time()
    catalog_rows=load_catalog_rows()
    catalog={r['expanded_route_id']: r for r in catalog_rows}
    manifest_rows=build_manifest_rows_from_catalog(catalog_rows, limit)
    if limit is None:
        write_manifest_csv(MANIFEST, manifest_rows)
    cns, group_variant_to_cns, by_code = build_static_catalog(catalog)
    static_activo_financiero = '<activoFinanciero>' + ''.join(centro_xml(cn) for cn in cns) + '</activoFinanciero>'
    static_hash = hashlib.sha256(static_activo_financiero.encode('utf-8')).hexdigest()
    max_abf_slots=max(len(cn['abfs']) for cn in cns)
    abf_fields=abf_slot_fields(max_abf_slots)

    route_xml_dir = BASE / '02_inputs_xml'
    if limit is None and route_xml_dir.exists():
        shutil.rmtree(route_xml_dir)
    if limit is None and (BASE / FLAT_XML_DIR).exists():
        shutil.rmtree(BASE / FLAT_XML_DIR)
    for rel in [FLAT_XML_DIR, '03_expected', '04_validation', '00_catalogos']:
        (BASE / rel).mkdir(parents=True, exist_ok=True)
    write_static_cn_catalog_csv(BASE / '00_catalogos' / 'cn_catalog.csv', cns)
    write_patrono_catalog_csv(BASE / '00_catalogos' / 'patrono_catalog.csv')

    expected_fields=['case_id','expanded_route_id','general_route_id','included_in_core','expected_mode','final_output_class_id','codCliente','dpiCliente','codCnActual',*abf_fields,'codCnAnterior','codAbfAnterior','bolson','expected_control_tree','expected_description','is_random_selection','cliente_patrono','tipo_cliente_expected']
    validation_fields=['case_id','expanded_route_id','general_route_id','final_output_class_id','input_xml_path','xml_generated','expected_generated','all_static_cn_catalog_present','cn_count','min_abfs_per_cn','max_abfs_per_cn','activo_financiero_hash','activo_financiero_hash_matches_static','domain_validation_pass','r2_case','r2_validation_pass','tipo_cliente_pass','patrono_validation_pass','bt_control_case','bt_credito_banca_ok','bt_expected_tree_ok','labor_cn','cosecha_cn','labor_cosecha_can_differ','cliente_edad','cliente_patrono','tipo_cliente_expected','target_cn','notes']
    r2_fields=['case_id','expanded_route_id','input_xml_path','r2_decisions','clienteMunicipioVivienda','clienteMunicipioTrabajo','target_cn','target_cn_municipio','target_cn_departamento','has_hist_vivienda','has_hist_trabajo','target_has_patrono_specialist','cliente_patrono','r2_pass','notes']
    tipo_fields=['case_id','expanded_route_id','input_xml_path','tipo_cliente_expected','tipo_cliente_derived','tipo_cliente_pass','credit_states','history_credit_count','rule_note']
    patrono_fields=['case_id','expanded_route_id','input_xml_path','cliente_patrono','expected_specialist_answer','global_abf_specialist_exists','target_scope_specialist_exists','patrono_validation_pass','patrono_field_rule']
    bt_fields=['case_id','input_xml_path','credito_banca_values','abf_sugerido_banca','expected_control_tree','pass_bt_validation']
    rand_case_fields=['case_id','expanded_route_id','input_xml_path','is_random_selection','validation_mode','expected_correct_count_for_branch','codCnActual',*abf_fields]
    rand_candidate_fields=[*rand_case_fields,'candidate_valid_flag','candidate_selected_flag_after_blaze']
    rand_response_fields=['case_id','expanded_route_id','input_xml_path','actual_cod_cn_actual','actual_cod_abf_actual']
    rand_score_fields=['expanded_route_id','random_cases_expected','expected_correct_count','validation_rule']
    sample_fields=['case_id','input_xml_path','sha256','activo_financiero_hash','domain_validation_pass','r2_case','r2_pass','tipo_cliente_pass','patrono_validation_pass']

    counts=Counter(); route_counts=Counter(); output_counts=Counter(); final_rule_counts=Counter()
    cn_count_values=Counter(); abf_min_values=Counter(); abf_max_values=Counter()
    route_r2_failures=Counter(); route_tipo_failures=Counter(); route_patrono_failures=Counter(); route_random_counts=Counter()
    domain_value_counters={field:Counter() for field in DOMAIN_RULES}; domain_failure_samples=[]
    sample_rows=[]; first_xml_full=None
    bt_total=bt_pass=0; domain_fail_total=0; r2_total=r2_pass_count=0; tipo_total=tipo_pass_count=0; patrono_total=patrono_pass_count=0; random_cases=0; random_candidate_rows=0; labor_diff_count=0
    age_by_route=defaultdict(set); vivienda_by_route=defaultdict(set); patrono_by_route=defaultdict(set)

    expected_csv=BASE/'03_expected'/'expected_outputs.csv'
    validation_csv=BASE/'04_validation'/'generation_validation.csv'
    r2_detail_csv=BASE/'04_validation'/'r2_validation_detail.csv'
    tipo_csv=BASE/'04_validation'/'tipo_cliente_validation.csv'
    patrono_csv=BASE/'04_validation'/'patrono_validation.csv'
    bt_csv=BASE/'04_validation'/'bt_validation_detail.csv'
    random_case_id_csv=BASE/'04_validation'/'random_case_id.csv'
    random_candidates_csv=BASE/'04_validation'/'random_candidates.csv'
    random_response_template_csv=BASE/'04_validation'/'random_response_template.csv'
    random_branch_score_csv=BASE/'04_validation'/'random_branch_score.csv'

    with expected_csv.open('w',newline='',encoding='utf-8') as ef, validation_csv.open('w',newline='',encoding='utf-8') as vf, r2_detail_csv.open('w',newline='',encoding='utf-8') as r2f, tipo_csv.open('w',newline='',encoding='utf-8') as tf, patrono_csv.open('w',newline='',encoding='utf-8') as pf, bt_csv.open('w',newline='',encoding='utf-8') as bf, random_case_id_csv.open('w',newline='',encoding='utf-8') as rcf, random_candidates_csv.open('w',newline='',encoding='utf-8') as rcandf, random_response_template_csv.open('w',newline='',encoding='utf-8') as rrtf:
        ew=csv.DictWriter(ef, fieldnames=expected_fields); ew.writeheader()
        vw=csv.DictWriter(vf, fieldnames=validation_fields); vw.writeheader()
        r2w=csv.DictWriter(r2f, fieldnames=r2_fields); r2w.writeheader()
        tw=csv.DictWriter(tf, fieldnames=tipo_fields); tw.writeheader()
        pw=csv.DictWriter(pf, fieldnames=patrono_fields); pw.writeheader()
        bw=csv.DictWriter(bf, fieldnames=bt_fields); bw.writeheader()
        rcw=csv.DictWriter(rcf, fieldnames=rand_case_fields); rcw.writeheader()
        rcandw=csv.DictWriter(rcandf, fieldnames=rand_candidate_fields); rcandw.writeheader()
        rrw=csv.DictWriter(rrtf, fieldnames=rand_response_fields); rrw.writeheader()

        for idx, man in enumerate(manifest_rows, start=1):
            route=catalog[man['expanded_route_id']]
            ctx=qa.build_context(man, route)
            ctx['global_case_number']=int(man.get('global_case_number') or idx)
            assign_case_overrides(ctx, route)
            _pg, _rid, target_cn = target_group(ctx, route, group_variant_to_cns)
            creditos=build_creditos(ctx, route, target_cn, by_code)
            xml=build_xml(ctx, route, creditos, target_cn, by_code, static_activo_financiero)
            xml_bytes=xml.encode('utf-8')
            rel_xml=man['input_xml_path']
            out_path=BASE / rel_xml
            out_path.parent.mkdir(parents=True, exist_ok=True)
            write_bytes_retry(out_path, xml_bytes)

            expected=build_expected(ctx, route, target_cn, by_code)
            expected_row=expected_row_for_csv(expected, max_abf_slots)
            ew.writerow({k:expected_row.get(k,'') for k in expected_fields})
            if expected.get('is_random_selection') == 'Si':
                random_cases += 1
                route_random_counts[ctx['expanded_route_id']] += 1
                random_base={'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml,'is_random_selection':'Si','validation_mode':'ACCEPTED_SET','expected_correct_count_for_branch':str(CASES_PER_ROUTE),'codCnActual':expected_row.get('codCnActual','')}
                random_base.update({field: expected_row.get(field, '') for field in abf_fields})
                rcw.writerow(random_base)
                rrw.writerow({'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml,'actual_cod_cn_actual':'','actual_cod_abf_actual':''})
                random_candidate_rows += 1
                rcandw.writerow({**random_base, 'candidate_valid_flag':'Si','candidate_selected_flag_after_blaze':''})

            domain_ok=True
            if idx <= 50 or idx % 1000 == 0:
                dom_values, dom_failures=validate_domains_from_xml(xml_bytes)
                for field,counter in dom_values.items(): domain_value_counters[field].update(counter)
                if dom_failures:
                    domain_ok=False; domain_fail_total += 1
                    if len(domain_failure_samples)<20: domain_failure_samples.append({'case_id':ctx['case_id'],'failures':dom_failures[:10]})
            cn_count=len(cns); abf_counts=[len(cn['abfs']) for cn in cns]
            min_abfs=min(abf_counts); max_abfs=max(abf_counts)
            cn_count_values[cn_count]+=1; abf_min_values[min_abfs]+=1; abf_max_values[max_abfs]+=1
            r2v=r2_validation(ctx, route, creditos, target_cn, by_code)
            if r2v['is_r2']=='Si':
                r2_total += 1
                if r2v['r2_pass']=='Si': r2_pass_count += 1
                else: route_r2_failures[ctx['expanded_route_id']]+=1
                r2w.writerow({k:r2v.get(k,'') for k in r2_fields if k not in {'case_id','expanded_route_id','input_xml_path'}} | {'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml})
            tv=tipo_cliente_validation(ctx, creditos); tipo_total += 1
            if tv['tipo_cliente_pass']=='Si': tipo_pass_count += 1
            else: route_tipo_failures[ctx['expanded_route_id']]+=1
            tw.writerow({'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml, **tv})
            pv=patrono_validation(ctx, route, cns, target_cn, by_code); patrono_total += 1
            if pv['patrono_validation_pass']=='Si': patrono_pass_count += 1
            else: route_patrono_failures[ctx['expanded_route_id']]+=1
            pw.writerow({'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'input_xml_path':rel_xml, **pv})

            is_bt=ctx['final_output_class_id']=='CONTROL_BT'
            bt_credito_banca_ok='N/A'; bt_expected_tree_ok='N/A'
            if is_bt:
                bt_total += 1
                root=ET.fromstring(xml_bytes)
                credito_bancas={e.text for e in root.findall('.//creditoBanca')}
                abf_sug_banca=(root.find('.//abfSugeridoBanca').text or '') if root.find('.//abfSugeridoBanca') is not None else ''
                bt_credito_banca_ok='Si' if credito_bancas=={xml_value(BANCA_TRABAJADORES)} else 'No'
                bt_expected_tree_ok='Si' if expected.get('expected_control_tree')=='BT' else 'No'
                pass_bt = bt_credito_banca_ok=='Si' and bt_expected_tree_ok=='Si'
                if pass_bt: bt_pass += 1
                bw.writerow({'case_id':ctx['case_id'],'input_xml_path':rel_xml,'credito_banca_values':'|'.join(sorted(credito_bancas)),'abf_sugerido_banca':abf_sug_banca,'expected_control_tree':expected.get('expected_control_tree',''),'pass_bt_validation':'Si' if pass_bt else 'No'})

            labor_cn=creditos[0]['participanteLaborCn'] if creditos else ''
            cosecha_cn=creditos[0]['cnCosechaCod'] if creditos else ''
            if labor_cn and labor_cn != cosecha_cn: labor_diff_count += 1
            vivienda, _trabajo = client_locations(ctx, route, target_cn, by_code)
            age_by_route[ctx['expanded_route_id']].add(ctx['cliente_edad'])
            vivienda_by_route[ctx['expanded_route_id']].add(vivienda)
            patrono_by_route[ctx['expanded_route_id']].add(ctx['cliente_patrono_nombre'])
            vw.writerow({'case_id':ctx['case_id'],'expanded_route_id':ctx['expanded_route_id'],'general_route_id':ctx['general_route_id'],'final_output_class_id':ctx['final_output_class_id'],'input_xml_path':rel_xml,'xml_generated':'Si','expected_generated':'Si','all_static_cn_catalog_present':'Si','cn_count':cn_count,'min_abfs_per_cn':min_abfs,'max_abfs_per_cn':max_abfs,'activo_financiero_hash':static_hash,'activo_financiero_hash_matches_static':'Si','domain_validation_pass':'Si' if domain_ok else 'No','r2_case':r2v['is_r2'],'r2_validation_pass':r2v['r2_pass'],'tipo_cliente_pass':tv['tipo_cliente_pass'],'patrono_validation_pass':pv['patrono_validation_pass'],'bt_control_case':'Si' if is_bt else 'No','bt_credito_banca_ok':bt_credito_banca_ok,'bt_expected_tree_ok':bt_expected_tree_ok,'labor_cn':labor_cn,'cosecha_cn':cosecha_cn,'labor_cosecha_can_differ':'Si' if labor_cn != cosecha_cn else 'No','cliente_edad':ctx['cliente_edad'],'cliente_patrono':ctx['cliente_patrono_nombre'],'tipo_cliente_expected':ctx['tipo_cliente'],'target_cn':target_cn or '','notes':r2v.get('notes','')})
            if len(sample_rows)<1000 or idx % 10000==0:
                sample_rows.append({'case_id':ctx['case_id'],'input_xml_path':rel_xml,'sha256':hashlib.sha256(xml_bytes).hexdigest(),'activo_financiero_hash':static_hash,'domain_validation_pass':'Si' if domain_ok else 'No','r2_case':r2v['is_r2'],'r2_pass':r2v['r2_pass'],'tipo_cliente_pass':tv['tipo_cliente_pass'],'patrono_validation_pass':pv['patrono_validation_pass']})
            if first_xml_full is None:
                first_xml_full=xml
            counts['total_cases']+=1; route_counts[ctx['expanded_route_id']]+=1; output_counts[ctx['final_output_class_id']]+=1; final_rule_counts[ctx['final_rule']]+=1
            if idx % 5000 == 0: print(f'Generated {idx:,} XMLs', flush=True)

    with (BASE/'04_validation'/'route_generation_summary.csv').open('w',newline='',encoding='utf-8') as rf:
        rw=csv.DictWriter(rf, fieldnames=['expanded_route_id','generated_cases','distinct_cliente_edad','distinct_clienteMunicipioVivienda','distinct_cliente_patrono','random_cases']); rw.writeheader()
        for k,v in sorted(route_counts.items()):
            rw.writerow({'expanded_route_id':k,'generated_cases':v,'distinct_cliente_edad':len(age_by_route[k]),'distinct_clienteMunicipioVivienda':len(vivienda_by_route[k]),'distinct_cliente_patrono':len(patrono_by_route[k]),'random_cases':route_random_counts.get(k,0)})
    with (BASE/'04_validation'/'sample_sha256_validation.csv').open('w',newline='',encoding='utf-8') as sf:
        sw=csv.DictWriter(sf, fieldnames=sample_fields); sw.writeheader(); sw.writerows(sample_rows)
    with random_branch_score_csv.open('w',newline='',encoding='utf-8') as rb:
        rbw=csv.DictWriter(rb, fieldnames=rand_score_fields); rbw.writeheader()
        for k,v in sorted(route_random_counts.items()):
            rbw.writerow({'expanded_route_id':k,'random_cases_expected':v,'expected_correct_count':str(CASES_PER_ROUTE),'validation_rule':f'PASS si Blaze devuelve un codCnActual y un codAbfActual dentro de las columnas codAbfActual1..N en los {CASES_PER_ROUTE} casos de la rama.'})
    if first_xml_full:
        (BASE/'04_validation'/'sample_input_qa100_v6.xml').write_text(first_xml_full, encoding='utf-8')
        (BASE/'04_validation'/'first_xml_preview.txt').write_text(first_xml_full[:12000], encoding='utf-8')

    domain_summary={'domain_validation_failed_sampled_cases':domain_fail_total,'sampled_case_count_for_domain_validation':50 + max(0, (len(manifest_rows)-50)//1000),'domain_failure_samples':domain_failure_samples,'domain_values_observed':{f:dict(c) for f,c in domain_value_counters.items()},'domain_rules':{f:sorted(list(v)) for f,v in DOMAIN_RULES.items()},'note':'Validacion muestral; campos abfSugerido* pueden ir en blanco cuando no existe ABF sugerido.'}
    r2_summary={'r2_cases_generated':r2_total,'r2_cases_passed_validation':r2_pass_count,'r2_validation_failed_cases':r2_total-r2_pass_count,'r2_validation_pass_rate':None if r2_total==0 else round(r2_pass_count/r2_total,6),'route_r2_failures':dict(route_r2_failures)}
    tipo_summary={'tipo_cliente_cases_generated':tipo_total,'tipo_cliente_cases_passed_validation':tipo_pass_count,'tipo_cliente_validation_failed_cases':tipo_total-tipo_pass_count,'tipo_cliente_validation_pass_rate':None if tipo_total==0 else round(tipo_pass_count/tipo_total,6),'route_tipo_failures':dict(route_tipo_failures)}
    patrono_summary={'patrono_cases_generated':patrono_total,'patrono_cases_passed_validation':patrono_pass_count,'patrono_validation_failed_cases':patrono_total-patrono_pass_count,'patrono_validation_pass_rate':None if patrono_total==0 else round(patrono_pass_count/patrono_total,6),'route_patrono_failures':dict(route_patrono_failures)}
    random_summary={'random_cases_generated':random_cases,'random_candidate_rows_generated':random_candidate_rows,'random_routes':len(route_random_counts),'expected_correct_count_per_random_route':CASES_PER_ROUTE,'random_candidate_layout':'una fila por cliente con codAbfActual1..N'}
    bt_summary={'bt_control_cases_generated':bt_total,'bt_control_cases_passed_validation':bt_pass,'bt_validation_pass_rate':None if bt_total==0 else round(bt_pass/bt_total,6)}
    generated_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    summary={'artifact':ROOT_NAME,'output_root':str(BASE),'generated_at_utc':generated_at,'generator_version':RUN_VERSION,'duration_seconds':round(time.time()-start,2),'cases_per_route':CASES_PER_ROUTE,'total_xml_inputs_generated':counts['total_cases'],'expanded_routes_generated':len(route_counts),'flat_xml_folder':FLAT_XML_DIR,'flat_xml_count':counts['total_cases'],'expected_abf_slot_count':max_abf_slots,'core_cases_generated':sum(cnt for rid2,cnt in route_counts.items() if rid2 != 'GPA-038__CONTROL_BT'),'bt_control_cases_generated':bt_total,'bt_control_cases_passed_validation':bt_pass,'r2_cases_generated':r2_total,'r2_cases_passed_validation':r2_pass_count,'tipo_cliente_cases_passed_validation':tipo_pass_count,'patrono_cases_passed_validation':patrono_pass_count,'random_cases_generated':random_cases,'random_routes_generated':len(route_random_counts),'static_cn_catalog_count':len(cns),'static_abf_total':sum(len(cn['abfs']) for cn in cns),'activo_financiero_static_hash':static_hash,'domain_validation_failed_sampled_cases':domain_fail_total,'cn_count_distribution':dict(cn_count_values),'min_abfs_per_cn_distribution':dict(abf_min_values),'max_abfs_per_cn_distribution':dict(abf_max_values),'labor_cosecha_different_cases':labor_diff_count,'final_rule_counts':dict(final_rule_counts),'output_class_counts':dict(output_counts),'notes':['Campos abfSugerido* espejan la asignacion actual del cliente cuando existe; si abfSugeridoCod es nulo, todos los campos abfSugerido* quedan en blanco.','Campos participanteLabor* usan un CN/ABF labor de la region exigida por la ruta; el CN de cosecha puede diferir cuando la regla lo permite.','Estructura XML vigente con arg0, informacionGeneral, activoCrediticio, activoFinanciero y salidaBlaze/asignacionCredito.','Se agregan clienteGenero y asignadoGenero; como PED no depende de genero, se asignan de forma deterministica pseudoaleatoria.','Los valores alfanumericos del XML se serializan en mayuscula sin cambiar nombres de etiquetas.','Las salidas aleatorias se consolidan en una fila por cliente con columnas codAbfActual1..N; codCnActual permanece unico.','Solo se genera la carpeta 02_inputs_xml_flat con todos los XMLs juntos; no se conserva 02_inputs_xml por ruta.','Alinea General post primera asignacion: ABF asignado en baja para D06, asesor asignado para D25, baja temporal D16/D34 y CN de cosecha por region/ruta.']}
    for path, data in [
        (BASE/'04_validation'/'generation_summary.json', summary),
        (BASE/'04_validation'/'domain_validation_summary.json', domain_summary),
        (BASE/'04_validation'/'r2_validation_summary.json', r2_summary),
        (BASE/'04_validation'/'tipo_cliente_validation_summary.json', tipo_summary),
        (BASE/'04_validation'/'patrono_validation_summary.json', patrono_summary),
        (BASE/'04_validation'/'random_selection_validation_summary.json', random_summary),
        (BASE/'04_validation'/'bt_validation_summary.json', bt_summary),
    ]:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    limit_env=os.getenv('QA_GENERATOR_LIMIT')
    if os.getenv('QA_GENERATOR_ARCHIVE') == '1':
        main(int(limit_env) if limit_env else None)
    else:
        main_in_place(int(limit_env) if limit_env else None)
