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
