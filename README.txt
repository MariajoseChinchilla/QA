Paquete QA Blaze - General post primera asignacion

Contenido principal:
- 00_catalogos/: catalogos de rutas, contrato de campos y catalogos auxiliares.
- 01_manifest/case_manifest_1000_full_v6.csv: manifest reproducible con 222,000 casos.
- 02_inputs_xml_flat/: todos los XMLs juntos en una sola carpeta.
- 03_expected/expected_outputs.csv: salidas esperadas por case_id.
- 04_validation/: reportes y resumenes de generacion/validacion.
- 05_scripts/: scripts reproducibles.

Resumen de la version actual:
- Generador: XML_INPUT_GENERATOR_V15_FLAT_ONLY_NEW_XML_STRUCTURE_GENDER_UPPERCASE_2026_06_03.
- Rutas: 222.
- Casos por ruta: 1000.
- XMLs totales: 222,000.
- XMLs en carpeta plana: 222,000.
- Carpeta separada por ruta `02_inputs_xml/`: no existe.
- CNs simulados: 103.
- ABFs simulados: 412.
- Maximo de ABFs por CN: 4.

Convencion de salidas esperadas:
- `codCnActual` permanece como una unica columna.
- Las opciones de ABF esperado se expresan en `codAbfActual1`, `codAbfActual2`, `codAbfActual3` y `codAbfActual4`.
- En rutas deterministicas, la asignacion esperada va en `codAbfActual1`.
- En rutas aleatorias, todas las opciones validas van una por columna en una sola fila por cliente.
- `random_candidates.csv` tambien queda en una sola fila por cliente; ya no hay una fila por opcion.

Reglas de datos incorporadas:
- `abfSugerido*` espeja la asignacion actual del cliente cuando existe; si no existe ABF sugerido, todos los campos de sugerido quedan vacios.
- `participanteLabor*` representa la persona que desembolso el credito y cumple las condiciones de banca, estado y region exigidas por la ruta.
- El CN de cosecha puede diferir del CN labor cuando la regla lo permite.
- `codCliente` y `dpiCliente` son unicos en todo el paquete.
- Los XMLs usan la estructura SOAP vigente con `arg0`, `informacionGeneral`, `activoCrediticio`, `activoFinanciero` y `salidaBlaze/asignacionCredito`.
- Se agregaron `clienteGenero` y `asignadoGenero`; PED no depende del genero, por lo que se asignan de forma deterministica pseudoaleatoria.
- Todos los valores alfanumericos del XML se serializan en mayuscula sin cambiar los nombres de etiquetas.
- Todo XML tiene al menos un `credito` y al menos un credito historico `HD`; ya no se generan clientes `CN` sin historial.

Validaciones ejecutadas:
- Compilacion de scripts: PASS.
- Estructura del repo: PASS.
- Manifest: PASS.
- Validacion integral muestral `--limit 10000`: PASS, 0 issues.
- Conteo completo de expected/manifest/carpeta plana: PASS.
- Conteo completo de XMLs sin `<credito>`: PASS, 0.
- Conteo completo de XMLs sin credito historico `HD`: PASS, 0.
- Conteo completo de `creditoTipoCliente=CN`: PASS, 0.
- Unicidad completa de `codCliente` y `dpiCliente`: PASS.
- Pares esperados CN/ABF contra catalogo: PASS.
- Muestra transversal de todas las rutas: PASS.
- `GPA-012__DIRECT`: 1000/1000 casos con `participanteLaborRegion` igual a `clienteRegion`.
- BT: 1000/1000 casos pasan validacion de control.
