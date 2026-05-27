# QA BT

Este paquete valida el arbol de Banca Trabajadores extraido desde `00_catalogos/Motor_BT.drawio.xml`.

La regla operativa de esta variante es mantener todos los XMLs de entrada en `02_inputs_xml_flat`.
No se debe crear `02_inputs_xml` ni subcarpetas por regla/ruta.

Scripts principales:
- `05_scripts/extract_bt_routes_from_drawio.py`: extrae nodos, aristas y rutas expandidas del draw.io.
- `05_scripts/generate_bt_qa_inputs.py`: genera manifest, expected outputs y XMLs planos.
- `05_scripts/run_all_validations.py`: valida estructura, manifest, XMLs y banca de credito.
