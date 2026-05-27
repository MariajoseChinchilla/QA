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

## [2026-05-27 13:38] Arreglo: Fidelidad de XMLs contra rutas BT

### Error detectado
- Rutas de cliente existente quedaban con `creditoTipoCliente=CR`.
- No se garantizaba credito en estado `D` para clientes existentes.
- Algunos municipios usados por el cliente no tenian CN en el catalogo del XML.

### Causa probable
- El generador inicial todavia tenia supuestos heredados del arbol anterior.

### Cambio aplicado
- Cliente existente ahora genera `CE` y al menos un credito `D`.
- Cliente reactivado genera `CR` sin credito `D`.
- Cliente nuevo/no reactivado genera `CN` sin credito `D`.
- Se agregaron CNs metropolitanos para municipios base de vivienda, trabajo e historial alterno.
- El validador ahora falla si no se cumplen tipo, estado, region Metropolitana o municipio con CN.

### Archivos modificados
- `05_scripts/generate_bt_qa_inputs.py`
- `05_scripts/validate_bt_flat_qa.py`
- `00_catalogos/cn_catalog.csv`
- `01_manifest/case_manifest_100_bt.csv`
- `02_inputs_xml_flat/*.xml`
- `03_expected/expected_outputs.csv`

### Validacion posterior
- `python 05_scripts/run_all_validations.py`: PASS, 0 fallos.

### Estado
- CORREGIDO
