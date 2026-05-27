## [2026-05-27 12:44] Arreglo: Estructura de entradas plana para BT

### Error detectado
- La estructura historica mencionaba entradas separadas en `02_inputs_xml`.

### Causa probable
- El QA base venia de una version que soportaba subcarpetas por ruta/regla.

### Cambio aplicado
- Se creo el paquete `QA BT` sin `02_inputs_xml`.
- El manifest apunta exclusivamente a `02_inputs_xml_flat`.
- El validador falla si aparece una carpeta `02_inputs_xml`.

### Archivos modificados
- `README.txt`
- `05_scripts/generate_bt_qa_inputs.py`
- `05_scripts/validate_bt_flat_qa.py`

### Validacion posterior
- `python 05_scripts/run_all_validations.py`: PASS.

### Estado
- CORREGIDO
