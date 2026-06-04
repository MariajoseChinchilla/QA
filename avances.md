## [2026-05-14 13:58] Avance: Inicio de validacion integral QA ABF

### Que se reviso
- Se leyo `docs/prompt_codex_validacion_qa_abf.md`.
- Se inventario la estructura principal del repositorio.
- Se confirmo la existencia de `00_catalogos/`, `01_manifest/`, `02_inputs_xml/`, `03_expected/`, `04_validation/` y `05_scripts/`.

### Hallazgos
- Existen 222 carpetas de rutas en `02_inputs_xml/`.
- Existen 22,200 XMLs bajo `02_inputs_xml/`.
- Ya existian scripts de generacion y un `validate_random.py` parcial.

### Resultado
- PARCIAL

### Archivos involucrados
- `docs/prompt_codex_validacion_qa_abf.md`
- `01_manifest/case_manifest_100_full_v6.csv`
- `03_expected/expected_outputs.csv`
- `05_scripts/validate_random.py`

### Proximo paso sugerido
- Crear validadores automaticos y generar reportes en `04_validation/outputs/`.

## [2026-05-14 14:48] Avance: Validadores automaticos creados

### Que se reviso
- Scripts existentes en `05_scripts/`.
- Cabeceras de manifest, expected outputs, rutas, patronos y archivos random.
- Estructura de una muestra XML con SOAP, `solicitud`, `ActivoCrediticio` y `ActivoFinanciero`.

### Hallazgos
- Existia un `validate_random.py` orientado a respuestas reales de Blaze, pero no un runner integral.
- Los XMLs contienen una fotografia completa de fuerza comercial con 53 CNs y 212 ABFs.

### Resultado
- PASS

### Archivos involucrados
- `05_scripts/qa_validation_lib.py`
- `05_scripts/run_all_validations.py`
- `05_scripts/validate_repo_structure.py`
- `05_scripts/validate_xml_wellformed.py`
- `05_scripts/validate_manifest.py`
- `05_scripts/validate_domains.py`
- `05_scripts/validate_sales_force_static.py`
- `05_scripts/validate_tipo_cliente.py`
- `05_scripts/validate_patrono.py`
- `05_scripts/validate_rule2.py`
- `05_scripts/validate_random.py`
- `05_scripts/validate_expected_outputs.py`

### Proximo paso sugerido
- Ejecutar muestra inicial y despues validacion completa.

## [2026-05-14 14:48] Avance: Ejecucion de muestras

### Que se reviso
- Muestra de 100 XMLs con todos los validadores.
- Muestra de 1,000 XMLs para cubrir ramas aleatorias.

### Hallazgos
- Las muestras confirmaron estructura, dominios, tipo cliente, patrono, Regla 2 y fuerza comercial sin errores.
- Se detecto que ramas aleatorias usan `ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON`, aunque el goal pide `ACCEPTED_SET`.

### Resultado
- PARCIAL

### Archivos involucrados
- `04_validation/outputs/random_validation_report.csv`
- `04_validation/outputs/expected_output_validation_report.csv`

### Proximo paso sugerido
- Ejecutar validacion completa y confirmar alcance de modos no canonicos.

## [2026-05-14 14:48] Avance: Validacion completa ejecutada

### Que se reviso
- 22,200 XMLs en 222 rutas.
- Manifest, expected outputs, estructura SOAP, dominios, fuerza comercial estatica, tipo cliente, patrono, Regla 2, aleatoriedad y salidas esperadas.

### Hallazgos
- `repo_structure`, `manifest_integrity`, `xml_wellformed`, `domains`, `sales_force_static`, `tipo_cliente`, `patrono` y `rule2` quedaron sin issues.
- `sales_force_static` confirmo hash raw y normalizado unico para los 22,200 XMLs.
- `expected_outputs` reporto 12,300 issues por modos de expected no canonicos frente al goal.
- `random` reporto 9,800 issues porque los casos aleatorios usan `ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON` en expected, no `ACCEPTED_SET`.
- No hubo errores criticos.

### Resultado
- PARCIAL

### Archivos involucrados
- `04_validation/outputs/repo_structure_report.csv`
- `04_validation/outputs/xml_wellformed_report.csv`
- `04_validation/outputs/manifest_integrity_report.csv`
- `04_validation/outputs/domain_validation_report.csv`
- `04_validation/outputs/sales_force_static_report.csv`
- `04_validation/outputs/tipo_cliente_validation_report.csv`
- `04_validation/outputs/patrono_validation_report.csv`
- `04_validation/outputs/rule2_validation_report.csv`
- `04_validation/outputs/random_validation_report.csv`
- `04_validation/outputs/expected_output_validation_report.csv`
- `04_validation/outputs/qa_validation_summary.json`

### Proximo paso sugerido
- Confirmar si se deben normalizar los modos `ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON`, `EXACT_OR_BUSINESS_ASSERTION` y `BOLSON` en `expected_outputs.csv`.

## [2026-05-14 19:56] Avance: Regeneracion por regla de ABF sugerido

### Que se reviso
- Requerimiento nuevo: todo campo `abfSugerido*` debe espejar la asignacion actual del cliente cuando existe.
- Scripts generadores de XML en `05_scripts/`.
- XMLs generados bajo `02_inputs_xml/`.

### Hallazgos
- El generador anterior poblaba `abfSugerido*` con valores derivados de ruta/cliente aunque el cliente no tuviera ABF asignado.
- En la nueva corrida, 21,900 XMLs quedaron con `abfSugeridoCod` vacio y todos los campos `abfSugerido*` vacios.
- En 300 XMLs el sugerido existe y espeja `clienteEsCarteraDelCnCod=1001` / `clienteEsCarteraDelAbfCod=500001`.

### Resultado
- PASS

### Archivos involucrados
- `05_scripts/generate_inputs_100_v6.py`
- `05_scripts/generate_full_qa_xml_inputs.py`
- `02_inputs_xml/`
- `04_validation/generation_summary.json`
- `04_validation/outputs/qa_validation_summary.json`

### Proximo paso sugerido
- Mantener pendiente la decision de negocio sobre los modos no canonicos de `expected_outputs.csv`.

## [2026-05-15 10:30] Avance: Correccion de ABF labor por region

### Que se reviso
- Observacion puntual en `GPA-012__DIRECT`: el cliente era de `Nor_oriente`, pero `participanteLabor*` quedaba con fuerza comercial de `Metropolitana`.
- Rutas donde las decisiones del arbol exigen condiciones sobre ABF labor: banca, estado y/o misma region que el cliente.
- Scripts generadores y XMLs bajo `02_inputs_xml/`.

### Hallazgos
- El contexto calculaba correctamente la region esperada de labor, pero `generate_inputs_100_v6.py` siempre usaba el CN/ABF labor fijo `1020` / `60000x`, de region `Metropolitana`.
- El CN de cosecha puede variar por regla, pero `participanteLabor*` debe cumplir las condiciones de labor cuando la regla lo exige.
- Se agregaron CN/ABF labor por region para `Metropolitana`, `Nor_oriente` y `Sur_occidente`.

### Resultado
- PASS focal en 16 rutas y 1,600 XMLs revisados: 0 errores de banca, estado o region en `participanteLabor*`.
- En `GPA-012__DIRECT`, `participanteLaborRegion` ahora queda `Nor_oriente` con CN labor `1021` y ABF labor `610001`; `cnCosechaRegion` puede permanecer `Metropolitana`.
- Se regeneraron los 22,200 XMLs.

### Archivos involucrados
- `05_scripts/generate_inputs_100_v6.py`
- `05_scripts/generate_full_qa_xml_inputs.py`
- `00_catalogos/cn_catalog.csv`
- `02_inputs_xml/`
- `03_expected/expected_outputs.csv`
- `04_validation/generation_summary.json`
- `04_validation/outputs/qa_validation_summary.json`

### Validacion posterior
- `python -m py_compile .\05_scripts\generate_inputs_100_v6.py .\05_scripts\generate_full_qa_xml_inputs.py`
- `python .\05_scripts\generate_inputs_100_v6.py`
- Verificacion focal de rutas con condiciones de ABF labor: 1,600 XMLs, 0 errores.
- `python .\05_scripts\run_all_validations.py --verbose` termino `PARTIAL` por los mismos modos no canonicos de `expected_outputs.csv`; 0 errores criticos.

### Proximo paso sugerido
- Confirmar la convencion final de los modos `ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON`, `EXACT_OR_BUSINESS_ASSERTION` y `BOLSON`.

## [2026-05-15 12:12] Avance: Revision contra arbol completo General post primera asignacion

### Que se reviso
- `motor_asignacion.drawio (1).xml`, pagina `General_post_primera_asignacion`.
- Diccionarios de soporte en `Requerimiento bases de datos Admon Cartera 2.docx`, `Mapeo de Campos de Salida.xlsx` y `Ejemplo tabla estructurada.csv`.
- Catalogo expandido de rutas, generador `qa100_v6`, XMLs y expected outputs.

### Hallazgos
- Se detectaron inconsistencias entre el arbol y los XMLs generados en varias senales de General post primera asignacion:
  - D06: cuando el cliente no esta asignado a un ABF de alta, la ruta requiere un ABF asignado en baja; algunos XMLs lo dejaban sin ABF asignado.
  - D25: cuando la cosecha la hizo el asesor asignado, `participanteLabor*` no siempre era el mismo ABF/CN asignado al cliente.
  - D16/D34: la baja temporal del ABF original no estaba representada con un ABF asignado en vacaciones.
  - D18/D27: el CN de cosecha podia quedar en una region fija en vez de la region exigida por la rama.

### Resultado
- PASS focal sobre las decisiones corregidas: 14,100 XMLs revisados, 0 errores.
- Validacion focal de `abfSugerido*`: 836 XMLs relevantes/muestra, 300 con sugerido, 536 sin sugerido, 0 errores.
- Se regeneraron los 22,200 XMLs y `03_expected/expected_outputs.csv`.

### Archivos involucrados
- `05_scripts/generate_inputs_100_v6.py`
- `00_catalogos/cn_catalog.csv`
- `02_inputs_xml/`
- `03_expected/expected_outputs.csv`
- `04_validation/generation_summary.json`
- `04_validation/outputs/qa_validation_summary.json`

### Validacion posterior
- `python -m py_compile .\05_scripts\generate_inputs_100_v6.py .\05_scripts\generate_full_qa_xml_inputs.py`
- `python .\05_scripts\generate_inputs_100_v6.py`
- Validacion focal de D06, D25, D16/D34, D18/D27 y ABF labor: 14,100 XMLs, 0 errores.
- `python .\05_scripts\run_all_validations.py --verbose` termino `PARTIAL` por los mismos modos no canonicos de expected/random; 0 errores criticos.

### Proximo paso sugerido
- Mantener pendiente solo la decision de negocio sobre normalizar los modos no canonicos de expected/random.

## [2026-05-15 16:30] Avance: Regeneracion QA1000 y carpeta plana

### Que se hizo
- Se aumento la generacion a 1000 casos por ruta para General post primera asignacion.
- Se creo `02_inputs_xml_flat/` con todos los XMLs juntos, manteniendo `02_inputs_xml/` separado por regla/ruta.
- Se reemplazo la salida aleatoria por columnas `codAbfActual1..codAbfActual4`, donde 4 es el maximo de ABFs por CN en el catalogo simulado.
- Se dejo `codCnActual` como una sola columna.
- Se garantizo unicidad de `codCliente` y `dpiCliente` con `global_case_number`.

### Resultado
- Total generado: 222,000 XMLs.
- Rutas: 222.
- Casos por ruta: 1000.
- Carpeta plana: 222,000 XMLs.
- Expected outputs: 222,000 filas.
- Casos aleatorios: 98,000 filas, una por cliente.
- `random_candidates.csv`: 98,000 filas, una por cliente, ya no una por opcion.

### Validacion posterior
- Compilacion de scripts: PASS.
- Estructura del repo: PASS.
- Manifest: PASS.
- Validacion muestral integral `--limit 10000`: PASS, 0 issues.
- Unicidad completa: 0 duplicados en `codCliente` y 0 duplicados en `dpiCliente`.
- Pares esperados CN/ABF contra catalogo: 345,000 revisados, 0 errores.
- Muestra transversal por todas las rutas: 666 XMLs, 0 errores.
- `GPA-012__DIRECT`: 1000/1000 casos con `participanteLaborRegion` igual a `clienteRegion`.

### Archivos involucrados
- `05_scripts/generate_inputs_100_v6.py`
- `05_scripts/generate_full_qa_xml_inputs.py`
- `05_scripts/qa_validation_lib.py`
- `01_manifest/case_manifest_1000_full_v6.csv`
- `02_inputs_xml/`
- `02_inputs_xml_flat/`
- `03_expected/expected_outputs.csv`
- `04_validation/`

### Nota operativa
- Se activo compresion NTFS para las carpetas generadas y se usaron enlaces duros en la carpeta plana para evitar duplicar el peso de los XMLs.

## [2026-06-04 17:20] Avance: creditoEstado actualizado de D a V

### Que se hizo
- Se ajusto el generador principal para que `creditoEstado` use `V` en los clientes existentes `CE`.
- Se elimino `D` del dominio permitido de `creditoEstado` en el generador y en el validador.
- Se cambio la inferencia de tipo cliente: `CE` se deriva por presencia de estado `V`; `CR` se mantiene con historial solo en `C`.
- Se regeneraron los 222,000 XMLs en la unica carpeta `02_inputs_xml_flat/`.
- Se actualizaron expected outputs y reportes de validacion.

### Resultado
- Carpeta plana: 222,000 XMLs.
- Carpeta separada `02_inputs_xml/`: no existe.
- `tipo_cliente_validation_summary.json`: 222,000 casos generados, 222,000 pasan.
- `domain_validation_summary.json`: `creditoEstado` permitido/observado con `C` y `V`; sin `D`.

### Validacion posterior
- Compilacion de scripts: PASS.
- Regeneracion completa: PASS.
- `python .\05_scripts\run_all_validations.py --limit 10000`: PASS, 0 issues.
