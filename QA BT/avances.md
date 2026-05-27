## [2026-05-27 12:44] Avance: Creacion QA BT plano

### Que se reviso
- Estructura del QA actual.
- Archivo `Motor_BT.drawio.xml`.
- Reglas de no separar entradas por ruta/regla.

### Hallazgos
- El draw.io contiene 5 paginas: Primera asignacion, General_post_primera_asignacion, Regla no. 1, Regla no. 2 y Regla no. 3.
- La expansion del arbol BT genera 82 rutas finales.

### Resultado
- PASS

### Archivos involucrados
- `00_catalogos/Motor_BT.drawio.xml`
- `00_catalogos/catalogo_rutas_arbol_bt_expandido.csv`
- `01_manifest/case_manifest_100_bt.csv`
- `02_inputs_xml_flat/*.xml`
- `03_expected/expected_outputs.csv`
- `05_scripts/*.py`

### Proximo paso sugerido
- Revisar con negocio si las rutas de control PED deben conservarse dentro del paquete BT o excluirse del set final de ejecucion.
