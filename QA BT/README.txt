Paquete QA Blaze - Banca Trabajadores

Contenido principal:
- 00_catalogos/: draw.io fuente, catalogo de rutas BT expandido, nodos/aristas del arbol y catalogos auxiliares.
- 01_manifest/case_manifest_100_bt.csv: manifest reproducible con 8,200 casos.
- 02_inputs_xml_flat/: todos los XMLs juntos en una sola carpeta.
- 03_expected/expected_outputs.csv: salidas esperadas por case_id.
- 04_validation/: reportes y resumenes de generacion/validacion.
- 05_scripts/: scripts reproducibles.
- docs/: notas de trabajo.

Resumen de la version actual:
- Fuente del arbol: 00_catalogos/Motor_BT.drawio.xml.
- Extractor: extract_bt_routes_from_drawio.py.
- Generador: XML_INPUT_GENERATOR_BT_FLAT_V3_GENDER_STRUCTURE_2026_06_03.
- Rutas expandidas: 82.
- Casos por ruta: 100.
- XMLs totales: 8,200.
- XMLs en carpeta plana: 8,200.
- Tipos esperados: CE=1,400, CR=4,800, CN=2,000.

Nota de estructura:
- Esta variante BT no crea 02_inputs_xml ni subcarpetas por regla/ruta.
- La unica carpeta de entradas es 02_inputs_xml_flat.
- Los XMLs usan la estructura del ejemplo con arg0, informacionGeneral, activoCrediticio, activoFinanciero, salidaBlaze y asignacionCredito.
- Se agregaron clienteGenero y asignadoGenero en el orden del ejemplo.
- Los valores textuales se escriben en mayuscula; los nombres de etiquetas se mantienen sin cambios.

Restricciones BT aplicadas:
- Cliente existente => tipo CE y al menos un credito en estado D.
- Cliente reactivado => tipo CR y sin credito en estado D.
- Cliente nuevo/no reactivado => tipo CN y sin credito en estado D.
- Todas las regiones de CN, cosecha y participante labor son Metropolitana.
- Cada municipio conocido del cliente tiene al menos un CN en ActivoFinanciero.

Validacion ejecutada:
- Extraccion del draw.io: PASS.
- Generacion de manifest/expected/XMLs: PASS.
- Estructura plana: PASS.
- Manifest vs expected vs XMLs: PASS.
- XML well-formed: PASS.
- Validacion de banca de credito BT/PED: PASS.
- Validacion de fidelidad de ruta BT: PASS.
