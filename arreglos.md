## [2026-05-14 13:58] Arreglo: Preparacion de validadores automaticos

### Error detectado
- El repositorio no tenia el conjunto completo de validadores solicitados por el goal.

### Causa probable
- La suite contenia archivos de generacion y validaciones parciales, pero no un runner integral con reportes consolidados.

### Cambio aplicado
- Se preparara un modulo comun de validacion y scripts wrapper en `05_scripts/`.

### Archivos modificados
- Pendiente de aplicar.

### Validacion posterior
- Pendiente de ejecutar muestra y corrida completa.

### Estado
- PENDIENTE

## [2026-05-14 14:48] Arreglo: Implementacion de runner integral de validacion

### Error detectado
- Faltaban los validadores solicitados por el goal y no existia generacion consolidada de reportes en `04_validation/outputs/`.

### Causa probable
- La suite tenia generadores y validaciones parciales, pero no una capa automatica comun para ejecutar el QA completo.

### Cambio aplicado
- Se creo `05_scripts/qa_validation_lib.py` con validaciones de estructura, manifest, XML, dominios, fuerza comercial estatica, tipo cliente, patrono, Regla 2, aleatoriedad y expected outputs.
- Se agregaron wrappers con los nombres requeridos por el goal.
- Se actualizo `05_scripts/validate_random.py` para integrarse al runner comun.

### Archivos modificados
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
- `avances.md`
- `arreglos.md`

### Validacion posterior
- `python -m py_compile` ejecuto sin errores.
- `python .\05_scripts\run_all_validations.py --limit 100` finalizo PASS.
- `python .\05_scripts\run_all_validations.py` finalizo PARTIAL y genero reportes.

### Estado
- CORREGIDO

## [2026-05-15 16:30] Arreglo: QA1000, carpeta plana y salidas aleatorias anchas

### Error detectado
- El paquete seguia generando 100 casos por ruta y no existia una carpeta unica con todos los XMLs juntos.
- Los casos de seleccion aleatoria estaban representados como una fila por opcion posible en `random_candidates.csv`, lo que multiplicaba registros por cliente.
- `expected_outputs.csv` usaba una sola columna `codAbfActual`, insuficiente para expresar todas las opciones validas de un caso aleatorio.
- La generacion previa podia reutilizar codigos de cliente/DPI derivados del seed; se requeria garantizar un unico registro por cliente.

### Causa probable
- El generador dependia del manifest historico de 100 casos por ruta y de la convencion antigua `accepted_cod_abf_set` / `random_candidates` por candidato.

### Cambio aplicado
- `generate_inputs_100_v6.py` ahora construye un manifest reproducible de 1000 casos por ruta (`222,000` casos en total).
- Se agrego `02_inputs_xml_flat/` con todos los XMLs juntos; los archivos se crean como enlaces duros hacia `02_inputs_xml/` para no duplicar almacenamiento.
- `expected_outputs.csv`, `random_case_id.csv` y `random_candidates.csv` usan `codAbfActual1..codAbfActual4`; `codCnActual` permanece como columna unica.
- Los casos aleatorios quedan en una sola fila por cliente, con todas las opciones ABF en columnas.
- Los casos deterministicos usan solo `codAbfActual1`.
- `codCliente` y `dpiCliente` se derivan de `global_case_number`, garantizando unicidad en los 222,000 clientes.
- Se actualizo `qa_validation_lib.py` para validar 1000 casos por ruta, carpeta plana, columnas anchas y unicidad de cliente/DPI.
- El generador historico `generate_full_qa_xml_inputs.py` quedo alineado con el formato ancho de expected y carpeta plana.

### Archivos modificados
- `05_scripts/generate_inputs_100_v6.py`
- `05_scripts/generate_full_qa_xml_inputs.py`
- `05_scripts/qa_validation_lib.py`
- `01_manifest/case_manifest_1000_full_v6.csv`
- `02_inputs_xml/`
- `02_inputs_xml_flat/`
- `03_expected/expected_outputs.csv`
- `04_validation/`

### Validacion posterior
- `python -m py_compile .\05_scripts\generate_inputs_100_v6.py .\05_scripts\generate_full_qa_xml_inputs.py .\05_scripts\qa_validation_lib.py`
- `python .\05_scripts\generate_inputs_100_v6.py`: 222,000 XMLs generados, 222 rutas, 1000 casos por ruta.
- `python .\05_scripts\validate_repo_structure.py`: PASS, 222,000 XMLs por ruta y 222,000 XMLs en carpeta plana.
- `python .\05_scripts\validate_manifest.py`: PASS.
- `python .\05_scripts\run_all_validations.py --limit 10000`: PASS, 0 issues.
- Control completo de CSV: 222,000 expected, 0 duplicados en `codCliente`, 0 duplicados en `dpiCliente`, 98,000 casos aleatorios y 98,000 filas en `random_candidates.csv`.
- Verificacion de pares esperados: 345,000 pares CN/ABF revisados contra catalogo, 0 errores.
- Muestra transversal: 666 XMLs (casos 1, 500 y 1000 de cada ruta), 0 errores de parseo o mismatch cliente/DPI.
- Focal `GPA-012__DIRECT`: 1000 XMLs revisados, 0 errores de region entre cliente y labor.

### Estado
- CORREGIDO

## [2026-05-15 12:12] Arreglo: Alineacion de General post primera asignacion contra arbol completo

### Error detectado
- Al revisar el arbol completo compartido, varios XMLs no forzaban correctamente algunas decisiones de `General_post_primera_asignacion`.
- En D06, las rutas partian de un cliente con ABF asignado en baja, pero los XMLs podian dejar `clienteEsCarteraDelAbfCod=-1`.
- En D25, la cosecha debia venir del asesor asignado, pero `participanteLabor*` podia apuntar a otro ABF de labor.
- En D16/D34, la baja temporal del ABF original no se reflejaba con un ABF asignado en vacaciones.
- En D18/D27, el CN de cosecha no siempre respetaba la region exigida por la rama.

### Causa probable
- El generador usaba defaults fijos para asignacion previa, CN de cosecha y participante labor.
- Las rutas R1 candidatas estaban agrupadas sin separar siempre por la region que necesitaba la rama General.

### Cambio aplicado
- Se agrego resolucion contextual de asignacion actual/anterior del cliente:
  - ABF activo normal.
  - ABF asignado en baja para D06.
  - ABF asignado con vacaciones para D16/D34.
  - cartera agencia cuando aplica.
- D25 ahora coloca `participanteLabor*` igual al asesor asignado del cliente.
- El CN de cosecha se resuelve por region/ruta y por target cuando la rama delega a R1 con el CN de la ruta.
- Los grupos candidatos R1 se separan por region para que las ramas que exigen misma region no reutilicen CNs de otra region.
- Se actualizaron los outputs esperados para que `codCnAnterior`, `codAbfAnterior`, `codCnActual` y `codAbfActual` coincidan con la nueva asignacion contextual.
- Se regeneraron XMLs, catalogos y reportes.

### Archivos modificados
- `05_scripts/generate_inputs_100_v6.py`
- `00_catalogos/cn_catalog.csv`
- `02_inputs_xml/`
- `03_expected/expected_outputs.csv`
- `04_validation/generation_summary.json`
- `04_validation/outputs/qa_validation_summary.json`

### Validacion posterior
- `python -m py_compile .\05_scripts\generate_inputs_100_v6.py .\05_scripts\generate_full_qa_xml_inputs.py`
- `python .\05_scripts\generate_inputs_100_v6.py`
- Validacion focal: D06, D25, D16/D34, D18/D27 y ABF labor, 14,100 XMLs revisados, 0 errores.
- Validacion focal de `abfSugerido*`: 836 XMLs revisados, 0 errores.
- `python .\05_scripts\run_all_validations.py --verbose` finalizo `PARTIAL` solo por modos no canonicos ya documentados; 0 errores criticos.

### Estado
- CORREGIDO

## [2026-05-14 14:48] Arreglo: Optimizacion de corrida completa

### Error detectado
- La primera muestra era demasiado lenta para una corrida completa de 22,200 XMLs.

### Causa probable
- Se resolvian rutas con `Path.resolve()` y se serializaba `ActivoFinanciero` desde ElementTree para cada XML.

### Cambio aplicado
- Se reemplazaron verificaciones repetidas de archivos por sets de rutas ya inventariadas.
- Se calculo el hash raw de `ActivoFinanciero` desde bytes del XML y se dejo el hash normalizado solo para hashes raw nuevos.
- Se agrego validacion de `cnRegion` en dominios de CN.

### Archivos modificados
- `05_scripts/qa_validation_lib.py`

### Validacion posterior
- La corrida completa termino y genero los reportes en `04_validation/outputs/`.

### Estado
- CORREGIDO

## [2026-05-14 14:48] Arreglo: Mensajes de modos expected no canonicos

### Error detectado
- El reporte marcaba `ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON`, `EXACT_OR_BUSINESS_ASSERTION` y `BOLSON` como modos no reconocidos sin explicar la convencion.

### Causa probable
- El goal define modos canonicos (`EXACT`, `ACCEPTED_SET`, `BT`), pero los archivos existentes incluyen convenciones intermedias.

### Cambio aplicado
- Se valido `ACCEPTED_SET_OR_DETERMINISTIC_SINGLETON` como accepted set no canonico.
- Se valido `EXACT_OR_BUSINESS_ASSERTION` como exacto no canonico.
- Se reporto `BOLSON` como convencion que requiere confirmacion de comparacion contra Blaze.
- Para `codAbfActual=-1`, se valida existencia del CN sin exigir un par CN/ABF inexistente.

### Archivos modificados
- `05_scripts/qa_validation_lib.py`

### Validacion posterior
- `expected_output_validation_report.csv` se regenero y agrupa los hallazgos por convencion no canonica.

### Estado
- CORREGIDO

## [2026-05-14 19:56] Arreglo: ABF sugerido igual a asignacion del cliente

### Error detectado
- Los campos `abfSugerido*` no estaban necesariamente alineados con el ABF de cartera/asignacion actual del cliente.
- Cuando no existia ABF sugerido, algunos campos seguian trayendo informacion de sugerido.

### Causa probable
- El generador usaba valores fijos o derivados de contexto de ruta para `abfSugerido*`, en lugar de leer la asignacion actual del cliente.

### Cambio aplicado
- `abfSugerido*` ahora se construye desde `clienteEsCarteraDelCnCod` y `clienteEsCarteraDelAbfCod`.
- Si el ABF de cartera del cliente es nulo (`-1` o vacio), todos los campos `abfSugerido*` se generan vacios.
- Si existe ABF de cartera, `abfSugeridoCod`, estado, edad, CN, banca, region, municipio y oportunidad espejan ese ABF/CN.
- El generador `qa100_v6` ahora puede regenerar directamente esta carpeta del repo sin depender de `/mnt/data` ni de `zstd`.
- Se regeneraron los 22,200 XMLs y reportes de apoyo.

### Archivos modificados
- `05_scripts/generate_inputs_100_v6.py`
- `05_scripts/generate_full_qa_xml_inputs.py`
- `02_inputs_xml/`
- `04_validation/bt_validation_detail.csv`
- `04_validation/bt_validation_summary.json`
- `04_validation/domain_validation_summary.json`
- `04_validation/first_xml_preview.txt`
- `04_validation/generation_summary.json`
- `04_validation/patrono_validation_summary.json`
- `04_validation/r2_validation_summary.json`
- `04_validation/random_selection_validation_summary.json`
- `04_validation/sample_input_qa100_v6.xml`
- `04_validation/sample_sha256_validation.csv`
- `04_validation/tipo_cliente_validation_summary.json`
- `04_validation/outputs/qa_validation_summary.json`

### Validacion posterior
- `python -m py_compile .\05_scripts\generate_inputs_100_v6.py .\05_scripts\generate_full_qa_xml_inputs.py`
- `python .\05_scripts\generate_inputs_100_v6.py`
- Verificacion especifica de `abfSugerido*`: 22,200 revisados, 21,900 sin sugerido, 300 con sugerido, 0 errores.
- `python .\05_scripts\run_all_validations.py --verbose` finalizo `PARTIAL` solo por los mismos modos no canonicos de expected output ya documentados.

### Estado
- CORREGIDO

## [2026-05-15 10:30] Arreglo: ABF labor alineado a condiciones de region

### Error detectado
- En `GPA-012__DIRECT`, y potencialmente en otras rutas con condiciones sobre labor, `participanteLabor*` podia quedar con ABF de una region distinta a la del cliente.
- Ejemplo observado: cliente de `Nor_oriente` con ABF labor de `Metropolitana`, aunque la regla exige que la persona que desembolsa el credito sea de la misma region.

### Causa probable
- `build_context()` definia la region de labor segun la ruta, pero el generador `qa100_v6` poblaba los campos de labor con un CN/ABF fijo de `Metropolitana`.
- Los expected para asignacion por ultimo desembolso/labor tambien usaban ese CN/ABF fijo.

### Cambio aplicado
- Se agregaron CNs de labor por region y sus ABFs asociados:
  - `1020` / `60000x` para `Metropolitana`.
  - `1021` / `61000x` para `Nor_oriente`.
  - `1022` / `62000x` para `Sur_occidente`.
- `participanteLabor*` ahora se resuelve desde `ctx['labor_region']`, `ctx['labor_estado']` y `ctx['labor_banca']`.
- Los expected de rutas que asignan por ABF labor usan el mismo CN/ABF labor resuelto.
- El generador completo historico tambien define CNs de labor por region y guarda `labor_cn_code` / municipio de labor para mantener consistencia.
- Se agrego reintento corto al escribir XMLs para evitar fallos transitorios de Windows mientras otros procesos observan la carpeta.

### Archivos modificados
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
- Verificacion focal de rutas con decisiones `D11/D12/D13/D14/D31/D32/D36/D37`: 1,600 XMLs revisados, 0 errores.
- Muestra de `GPA-012__DIRECT`: cliente `Nor_oriente`, `participanteLaborCn=1021`, `participanteLaborCod=610001`, `participanteLaborRegion=Nor_oriente`; `cnCosechaRegion=Metropolitana` permitido por regla.
- `python .\05_scripts\run_all_validations.py --verbose` finalizo `PARTIAL` solo por los modos no canonicos de expected output ya documentados; 0 errores criticos.

### Estado
- CORREGIDO

## [2026-06-04 17:20] Arreglo: creditoEstado D reemplazado por V

### Error detectado
- Los XMLs de clientes existentes `CE` estaban usando `creditoEstado=D`.
- El nuevo criterio pide reemplazar ese estado por `V` en todos los XMLs.

### Causa probable
- El generador principal todavia trataba `D` como estado valido para identificar clientes existentes.
- El validador tambien aceptaba `D` dentro del dominio de `creditoEstado`.

### Cambio aplicado
- `creditoEstado` ahora permite solo `C` y `V` en el generador principal.
- La derivacion de tipo cliente ahora usa `CE` cuando existe al menos un credito con estado `V`.
- Los casos `CONTROL_BT` y las rutas con cliente existente ahora generan credito actual e historico con estado `V`.
- El validador rechaza `D` y valida `CE` contra estado `V`.
- Se regeneraron los 222,000 XMLs en `02_inputs_xml_flat/`.

### Archivos modificados
- `05_scripts/generate_inputs_100_v6.py`
- `05_scripts/qa_validation_lib.py`
- `02_inputs_xml_flat/`
- `03_expected/expected_outputs.csv`
- `04_validation/`
- `README.txt`

### Validacion posterior
- `python -m py_compile .\05_scripts\generate_inputs_100_v6.py .\05_scripts\qa_validation_lib.py`
- `python .\05_scripts\generate_inputs_100_v6.py`
- `tipo_cliente_validation_summary.json`: 222,000/222,000 casos pasan.
- `domain_validation_summary.json`: `creditoEstado` observado y permitido solo con `C` y `V`.
- `python .\05_scripts\run_all_validations.py --limit 10000`: PASS, 0 issues.

### Estado
- CORREGIDO
