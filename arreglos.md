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
