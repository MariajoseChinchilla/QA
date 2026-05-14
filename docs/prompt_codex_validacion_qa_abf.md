# Goal para Codex: Validación integral de casos QA XML para árbol ABF / BANTRAB

## Contexto general

Este repositorio contiene una suite de QA para validar el árbol de asignación de ABF a clientes de BANTRAB implementado en Blaze.

La carpeta subida corresponde a la versión `qa100_v6`, generada con 100 casos por cada ruta/rama expandida del árbol. El objetivo es validar que los XMLs de entrada estén correctamente configurados, que cada caso fuerce la ruta esperada del árbol y que las salidas esperadas sean comparables contra la respuesta real de Blaze.

El árbol probado corresponde a `General_post_primera_asignacion`, pero expandido completamente: cuando General manda a Regla 1, Regla 2 o Regla 3, esas reglas también deben considerarse dentro de la ruta completa.

Por eso hay rutas con nombres como:

```text
GPA-001__R2-001__R1-001
GPA-027__R2-012__R1-004
GPA-003__R1-002
GPA-007__DIRECT
GPA-038__CONTROL_BT
```

Cada subcarpeta de `02_inputs_xml` representa una ruta expandida. Dentro de cada subcarpeta hay 100 XMLs, normalmente nombrados como `0001.xml`, `0002.xml`, etc.

## Estructura esperada del repositorio

En la raíz del proyecto debe existir esta estructura:

```text
.
├── 00_catalogos/
├── 01_manifest/
├── 02_inputs_xml/
├── 03_expected/
├── 04_validation/
├── 05_scripts/
```

### 00_catalogos/

Contiene catálogos de soporte. Pueden incluir, según la versión:

- catálogo de rutas expandidas;
- catálogo fijo de CNs y ABFs;
- catálogo de patronos;
- contrato de campos;
- archivos auxiliares de generación.

Estos archivos sirven para validar que todos los XMLs usan la misma fuerza comercial y los mismos dominios de datos.

### 01_manifest/

Contiene el manifest principal de casos. El manifest debe permitir relacionar:

- `case_id`;
- ruta expandida;
- archivo XML de entrada;
- salida esperada;
- modo de validación;
- si el caso es determinístico o aleatorio;
- si pertenece al control BT.

El manifest es la fuente de trazabilidad entre XML, ruta esperada y expected output.

### 02_inputs_xml/

Contiene todos los XMLs de entrada que se mandarán a Blaze.

Cada XML representa un cliente. Sin embargo, cada XML debe contener también la fotografía completa de la fuerza comercial en el bloque:

```xml
<ActivoFinanciero>
  <CentroDeNegocio>
    ...
    <Abf>...</Abf>
    <Abf>...</Abf>
  </CentroDeNegocio>
</ActivoFinanciero>
```

Esta sección debe ser igual en todos los XMLs: mismos CNs, mismos ABFs por CN, mismos estados, mismas bancas, mismos patronos de especialidad, mismos bolsones y mismos atributos relevantes.

Esto es necesario porque Blaze no recibe varios archivos para resolver una asignación. Cada XML debe traer toda la información que Blaze necesita para buscar el CN o ABF aplicable.

### 03_expected/

Contiene las salidas esperadas.

El archivo principal esperado es algo como:

```text
expected_outputs.csv
```

Los campos centrales para comparar contra Blaze son:

- `codCnActual`;
- `codAbfActual`;
- `codCnAnterior`;
- `codAbfAnterior`.

Para rutas determinísticas, `codCnActual` y `codAbfActual` deben compararse de forma exacta contra la respuesta de Blaze.

Para rutas con selección aleatoria, no se debe exigir un único ABF. Se debe validar contra conjuntos aceptados:

- `accepted_cod_cn_set`;
- `accepted_cod_abf_set`.

### 04_validation/

Contiene archivos de validación y reportes, por ejemplo:

- validación de dominios;
- validación de BT;
- validación de Regla 2;
- validación de tipo de cliente;
- validación de patrono;
- identificación de casos aleatorios;
- candidatos válidos por caso aleatorio.

Los archivos de selección aleatoria pueden llamarse:

```text
random_case_id.csv
random_candidates.csv
random_response_template.csv
random_branch_score.csv
```

### 05_scripts/

Contiene scripts usados para generar o validar XMLs.

El objetivo es revisar estos scripts, mejorarlos si hace falta y agregar validadores robustos, sin romper la estructura del repositorio.

## Archivos obligatorios de trazabilidad

Crear en la raíz del proyecto, si no existen:

```text
avances.md
arreglos.md
```

### avances.md

Usar este archivo como bitácora de avances.

Cada vez que se complete un avance relevante, agregar una entrada con este formato:

```markdown
## [YYYY-MM-DD HH:MM] Avance: <título corto>

### Qué se revisó
- ...

### Hallazgos
- ...

### Resultado
- PASS / FAIL / PARCIAL

### Archivos involucrados
- ...

### Próximo paso sugerido
- ...
```

Ejemplos de avances:

- inventario de estructura del repositorio;
- conteo de XMLs;
- validación de fuerza comercial fija;
- validación de dominios;
- validación de tipo de cliente;
- validación de especialista de patrono;
- validación de Regla 2;
- validación de selección aleatoria;
- validación de salidas esperadas;
- creación de scripts nuevos;
- ejecución completa de validadores.

### arreglos.md

Usar este archivo para documentar errores encontrados y correcciones aplicadas.

Cada vez que se modifique un script, manifest, expected output o XML generado, documentar:

```markdown
## [YYYY-MM-DD HH:MM] Arreglo: <título corto>

### Error detectado
- ...

### Causa probable
- ...

### Cambio aplicado
- ...

### Archivos modificados
- ...

### Validación posterior
- ...

### Estado
- CORREGIDO / PENDIENTE / REQUIERE CONFIRMACIÓN
```

No hacer cambios silenciosos. Todo cambio debe quedar documentado en `arreglos.md`.

## Objetivo principal

Construir o mejorar un sistema de validación automática que revise si los XMLs de prueba están correctamente configurados para forzar las rutas esperadas del árbol ABF expandido.

La validación debe revisar, como mínimo:

1. Estructura del repositorio.
2. Conteo de rutas y casos.
3. Integridad del manifest.
4. Existencia de todos los XMLs esperados.
5. XMLs bien formados.
6. Estructura SOAP correcta.
7. Presencia de `solicitud`.
8. Presencia de `ActivoCrediticio`, cuando aplique.
9. Presencia de `ActivoFinanciero` en todos los XMLs.
10. Que todos los XMLs tengan la misma fuerza comercial.
11. Dominios válidos según requerimiento.
12. Tipo de cliente según estados de crédito.
13. Reglas de cliente existente, reactivado y nuevo.
14. Diferenciación correcta entre labor, asignación y cosecha.
15. Validación de especialista de patrono.
16. Validación de Regla 1.
17. Validación de Regla 2.
18. Validación de Regla 3, si hay rutas relacionadas.
19. Validación de rutas directas.
20. Validación de control BT.
21. Validación de salidas esperadas.
22. Validación de selección aleatoria mediante conjuntos aceptados.
23. Generación de reportes claros.

## Reglas de negocio importantes

### 1. Diferencia entre labor, asignación y cosecha

No confundir estos conceptos:

```text
labor = persona que desembolsó el crédito
asignación = a quién pertenece actualmente el cliente
cosecha = CN donde se desembolsó el crédito
```

Campos relacionados con la persona que vendió o desembolsó:

```text
participanteLaborCod
participanteLaborCn
participanteLaborEstado
participanteLaborBanca
participanteLaborRegion
participanteLaborMunicipio
participanteLaborTipo
```

Campos relacionados con la asignación actual o candidatos asignados:

```text
clienteEsCarteraDelCnCod
clienteEsCarteraDelAbfCod
abfSugeridoCod
asignadoCod
```

Campos relacionados con el CN donde se desembolsó el crédito:

```text
cnCosechaCod
cnCosechaNombre
cnCosechaEstado
cnCosechaRegion
cnCosechaDepartamento
cnCosechaMunicipio
```

Es válido y esperado que:

```text
participanteLaborCn != cnCosechaCod
```

porque un vendedor puede pertenecer a un CN laboral pero haber vendido en otro CN.

### 2. Fuerza comercial fija

Cada XML debe tener exactamente el mismo bloque `ActivoFinanciero`.

Validar:

- mismo número de `CentroDeNegocio`;
- mismos `cnCod`;
- mismos `cnEstado`;
- mismos `cnRegion`;
- mismos `cnMunicipio`;
- mismos `cnDepartamento`;
- mismos ABFs por CN;
- mismos `asignadoCod`;
- mismos atributos de cada ABF;
- mismo hash normalizado del bloque `ActivoFinanciero`.

Generar una validación tipo:

```text
activo_financiero_hash
```

Si el hash cambia entre XMLs, reportarlo como error crítico.

### 3. Dominios permitidos

Validar que los valores se escriban como en el requerimiento, no en mayúsculas globales.

Dominios esperados:

```text
creditoEstado: V, C, D
creditoBanca: banca_personas, banca_trabajadores
creditoTipoCliente: CN, CE, CR
creditoRegion: Metropolitana, Nor_oriente, Sur_occidente
participanteLaborEstado: Alta, Baja
participanteLaborBanca: banca_personas, banca_trabajadores
participanteLaborVacacion: 0, 1
participanteLaborTipo: abf, cn, cp
clienteEsSugerido: Si, No
clienteEstabaAsignadoAbf: Si, No
clienteFueDesembolsadoEnElUltimoMes: Si, No
esTrabajadorInterno: S, N
cnEstado: Alta, Baja
cnRegion: Metropolitana, Nor_oriente, Sur_occidente
asignadoEstado: Alta, Baja
asignadoEnVacacion: 0, 1
asignadoBanca: banca_personas, banca_trabajadores
asignadoBolsonEstado: Exceso, Equilibrio, Deficit
abfSugeridoOportunidad: Sugerido, No_Sugerido
```

No corregir valores automáticamente sin documentarlo en `arreglos.md`.

### 4. Tipo de cliente según estados de crédito

Validar esta regla:

```text
CE = cliente existente
CR = cliente reactivado
CN = cliente nuevo
```

La regla de negocio es:

```text
Si el cliente tiene al menos un crédito con creditoEstado = D:
    creditoTipoCliente debe ser CE

Si el cliente tiene historial de créditos y todos están en creditoEstado = C:
    creditoTipoCliente debe ser CR

Si el cliente no tiene historial de créditos:
    creditoTipoCliente debe ser CN
```

Validaciones concretas:

- Si un XML tiene `creditoTipoCliente = CE`, debe existir al menos un crédito con `creditoEstado = D`.
- Si un XML tiene `creditoTipoCliente = CR`, debe existir al menos un crédito y todos deben estar en `creditoEstado = C`.
- Si un XML tiene `creditoTipoCliente = CN`, no debe haber historial de créditos en `ActivoCrediticio`, salvo que el generador use una convención especial documentada. Si hay créditos históricos en un cliente `CN`, reportar como inconsistencia.
- Dentro de un mismo XML, revisar que todos los nodos `Credito` tengan un `creditoTipoCliente` coherente con la clasificación global del cliente.

### 5. Cliente existente

Cuando una ruta o regla indique que el cliente es existente, validar que el XML tenga evidencia crediticia suficiente.

Condición mínima:

```text
Existe al menos un Credito con creditoEstado = D
```

o la convención formal que el árbol use para marcar existencia. Si el caso dice ser existente, pero no tiene créditos compatibles, marcar error.

### 6. Cliente reactivado

Cuando una ruta indique cliente reactivado:

```text
Debe existir al menos un crédito.
Todos los créditos históricos deben estar en estado C.
No debe existir ningún crédito en estado D.
```

### 7. Cliente nuevo

Cuando una ruta indique cliente nuevo:

```text
No debe existir historial crediticio.
```

Si existe `ActivoCrediticio/Credito`, revisar si eso contradice la ruta. Si contradice, reportar.

### 8. Especialista de patrono

Cuando el árbol pregunte si existe algún ABF que se especialice en el patrono del cliente, la validación debe buscar en todos los ABFs candidatos si alguno tiene el patrono del cliente en cualquiera de estos campos:

```text
especialistaPatrono1
especialistaPatrono2
especialistaPatrono3
```

El patrono del cliente se toma de:

```text
creditoPatrono
```

La comparación debe ser contra el nombre del patrono, no contra código, salvo que el XML use una convención documentada. Si los campos `especialistaPatrono*` contienen códigos cuando deberían contener nombres, marcar error.

Regla:

```text
existe_especialista_patrono =
    creditoPatrono == especialistaPatrono1
    OR creditoPatrono == especialistaPatrono2
    OR creditoPatrono == especialistaPatrono3
```

Validar que:

- en ramas donde se espera respuesta `Sí`, exista al menos un ABF candidato de alta que cumpla esa condición;
- en ramas donde se espera respuesta `No`, ningún ABF candidato de alta debe cumplir esa condición;
- el patrono usado pertenezca a un catálogo finito de patronos;
- el patrono usado para forzar respuesta `No` no aparezca en ningún `especialistaPatrono1/2/3` de los ABFs candidatos.

### 9. Regla 1

Regla 1 selecciona entre un universo candidato de ABFs.

Validar, según la ruta `R1-001`, `R1-002`, `R1-003`, `R1-004`, que el universo candidato exista y que el resultado esperado sea coherente.

Validaciones mínimas:

- Todos los candidatos considerados deben tener `asignadoEstado = Alta`.
- Si la ruta filtra por banca, los candidatos válidos deben tener `asignadoBanca = banca_personas`.
- Si la ruta filtra por CN, los candidatos deben pertenecer al CN correcto.
- Si la ruta filtra por municipio o departamento, los CNs candidatos deben tener el municipio/departamento correcto.
- Si la ruta filtra por patrono, los candidatos deben tener el patrono en `especialistaPatrono1/2/3`.
- Si la ruta espera déficit de bolsón, debe haber candidato con `asignadoBolsonEstado = Deficit`.
- Si la ruta espera equilibrio, debe haber candidato con `asignadoBolsonEstado = Equilibrio`.
- Si hay empate o selección aleatoria, el caso debe estar marcado como aleatorio y sus candidatos deben estar en `random_candidates.csv`.

### 10. Regla 2

Regla 2 evalúa municipios de vivienda y trabajo, y si hubo desembolsos previos en CNs abiertos de esos municipios.

Validar:

- Si la pregunta “¿se conoce municipio de vivienda?” espera `Sí`, `clienteMunicipioVivienda` no debe estar vacío ni ser una convención de desconocido.
- Si espera `No`, debe usar una convención explícita, por ejemplo `SIN_MUNICIPIO` o valor equivalente documentado.
- Si se espera que el cliente haya tenido desembolso en CN abierto del municipio de vivienda, debe existir al menos un crédito histórico cuyo `cnCosechaMunicipio` coincida con `clienteMunicipioVivienda` y cuyo `cnCosechaEstado = Alta`.
- Además, ese CN debe existir dentro de `ActivoFinanciero` con `cnEstado = Alta`.
- Si se espera respuesta `No`, no debe existir ningún crédito histórico que cumpla esa condición.
- Repetir la misma lógica para `clienteMunicipioTrabajo`.
- No usar municipios reales que puedan causar cruces accidentales. Preferir valores sintéticos como `municipio3031`, `municipio3032`, etc., siempre que existan en el catálogo de CNs.

### 11. Regla 3

Validar las rutas `R3-*` según los campos esperados.

Regla 3 debe tener validaciones equivalentes:

- existencia o no de CN abierto;
- existencia o no de ABF candidato;
- consistencia de banca;
- consistencia de municipio/departamento;
- consistencia de patrono si aplica;
- consistencia de expected output.

### 12. Rutas directas

Para rutas `DIRECT`, validar que no se requiere una subregla posterior.

La salida esperada debe estar completa en `expected_outputs.csv`.

Validar:

```text
codCnActual
codAbfActual
codCnAnterior
codAbfAnterior
```

según corresponda.

Si una ruta directa mantiene asignación:

```text
codCnActual debe ser igual al CN actual de cartera.
codAbfActual debe ser igual al ABF actual de cartera.
```

Si una ruta directa asigna al ABF de cosecha:

```text
codAbfActual debe coincidir con participanteLaborCod o con el ABF correspondiente en la lógica de cosecha, según la ruta.
codCnActual debe coincidir con el CN correcto de cosecha/asignación.
```

### 13. Control BT

La ruta:

```text
GPA-038__CONTROL_BT
```

es control de frontera.

Validar que:

- el caso no pertenezca a `banca_personas`;
- esté marcado como control BT;
- no se compare como una asignación ABF normal;
- el expected output indique `BT` o la convención definida en el archivo de expected.

### 14. Selección aleatoria

Algunas rutas pueden tener selección aleatoria porque hay más de un candidato válido.

Estos casos deben ser fáciles de identificar.

Validar que exista un archivo:

```text
04_validation/random_case_id.csv
```

y otro:

```text
04_validation/random_candidates.csv
```

con todas las opciones válidas por caso.

Para un caso aleatorio:

- no exigir un único `codAbfActual`;
- validar que la respuesta de Blaze esté dentro de las opciones válidas;
- cada candidato válido debe tener combinación de `candidate_cod_cn_actual` y `candidate_cod_abf_actual`;
- el conjunto de candidatos debe coincidir con los ABFs realmente elegibles en el XML.

La regla de cierre por rama aleatoria debe ser:

```text
actual_correct_count = 100
invalid_random_selection_count = 0
pending_count = 0
```

Es decir: si una rama tiene 100 XMLs, al finalizar el QA contra Blaze debe haber 100 respuestas válidas. Las opciones no seleccionadas por Blaze no son errores; solo son candidatos válidos no elegidos.

### 15. Expected output

Validar `03_expected/expected_outputs.csv`.

Para rutas determinísticas:

```text
expected_mode = EXACT
codCnActual no debe estar vacío
codAbfActual no debe estar vacío
```

Para rutas aleatorias:

```text
expected_mode = ACCEPTED_SET
accepted_cod_cn_set no debe estar vacío
accepted_cod_abf_set no debe estar vacío
```

Para BT:

```text
expected_control_tree = BT
```

Validar que todo `case_id` del manifest tenga su salida esperada.

Validar que toda salida esperada tenga XML correspondiente.

## Entregables esperados

Codex debe producir o actualizar scripts de validación, preferiblemente en Python, dentro de `05_scripts/`.

Crear, si no existen:

```text
05_scripts/validate_repo_structure.py
05_scripts/validate_xml_wellformed.py
05_scripts/validate_manifest.py
05_scripts/validate_domains.py
05_scripts/validate_sales_force_static.py
05_scripts/validate_tipo_cliente.py
05_scripts/validate_patrono.py
05_scripts/validate_rule2.py
05_scripts/validate_random.py
05_scripts/validate_expected_outputs.py
05_scripts/run_all_validations.py
```

También puede consolidar todo en menos scripts si es más mantenible, pero debe conservar claridad.

## Reportes esperados

Crear una carpeta o usar `04_validation/outputs/` para reportes nuevos.

Generar como mínimo:

```text
04_validation/outputs/repo_structure_report.csv
04_validation/outputs/xml_wellformed_report.csv
04_validation/outputs/manifest_integrity_report.csv
04_validation/outputs/domain_validation_report.csv
04_validation/outputs/sales_force_static_report.csv
04_validation/outputs/tipo_cliente_validation_report.csv
04_validation/outputs/patrono_validation_report.csv
04_validation/outputs/rule2_validation_report.csv
04_validation/outputs/random_validation_report.csv
04_validation/outputs/expected_output_validation_report.csv
04_validation/outputs/qa_validation_summary.json
```

El resumen JSON debe indicar:

```json
{
  "total_routes": 222,
  "expected_cases_per_route": 100,
  "total_xml_expected": 22200,
  "total_xml_found": 0,
  "total_errors": 0,
  "critical_errors": 0,
  "warnings": 0,
  "status": "PASS|FAIL|PARTIAL"
}
```

Ajustar `total_xml_found`, errores y estado según la validación real.

## Criterios de severidad

Usar severidades:

```text
CRITICAL
ERROR
WARNING
INFO
```

### CRITICAL

Usar para errores que invalidan el QA:

- XML no parseable;
- XML faltante;
- expected output faltante;
- case_id duplicado;
- ruta sin casos;
- bloque `ActivoFinanciero` distinto entre XMLs;
- cliente tipo `CE` sin crédito `D`;
- cliente tipo `CR` con crédito `D`;
- cliente tipo `CN` con historial de créditos, salvo convención documentada;
- ruta aleatoria sin candidatos válidos;
- respuesta esperada fuera del universo candidato.

### ERROR

Usar para inconsistencias de negocio:

- dominio inválido;
- ABF esperado no existe en `ActivoFinanciero`;
- CN esperado no existe;
- especialista de patrono mal configurado;
- municipio de vivienda/trabajo no coincide con el crédito que pretende activar Regla 2;
- ruta directa sin salida esperada.

### WARNING

Usar para observaciones que no necesariamente invalidan:

- baja variabilidad en edades o montos;
- muchos casos con mismos municipios;
- campos opcionales vacíos;
- nombres de archivos largos pero menores al límite;
- campos no utilizados por validación.

## Instrucciones de implementación

1. Primero inspecciona la estructura del repo.
2. Crea `avances.md` y `arreglos.md` si no existen.
3. Registra en `avances.md` que inició la validación.
4. Revisa qué scripts ya existen en `05_scripts/`.
5. No borres scripts existentes sin documentar.
6. Implementa validadores incrementales.
7. Ejecuta validaciones sobre una muestra inicial.
8. Ejecuta validaciones sobre todos los XMLs.
9. Genera reportes.
10. Documenta cada hallazgo relevante.
11. Si haces correcciones a scripts o datos, documenta todo en `arreglos.md`.
12. Si hay errores que requieren decisión de negocio, no inventes una regla; deja el hallazgo documentado como `REQUIERE CONFIRMACIÓN`.

## Cuidado con rendimiento

Hay 22,200 XMLs. Los scripts deben ser eficientes.

Recomendaciones:

- usar `xml.etree.ElementTree` o `lxml` si está disponible;
- procesar XMLs de forma iterativa;
- no cargar todos los XMLs completos en memoria si no es necesario;
- para validar `ActivoFinanciero`, calcular hash normalizado;
- usar CSVs para reportar;
- incluir barra de progreso solo si la dependencia está disponible;
- no usar librerías externas innecesarias.

## Hash normalizado de ActivoFinanciero

Para comparar el bloque de fuerza comercial entre XMLs:

1. Extraer `ActivoFinanciero`.
2. Normalizar espacios.
3. Ordenar CNs por `cnCod` si el orden no debe importar.
4. Ordenar ABFs por `asignadoCod` dentro de cada CN si el orden no debe importar.
5. Serializar de forma estable.
6. Calcular SHA-256.
7. Confirmar que todos los XMLs tienen el mismo hash.

Si el orden sí importa para Blaze, hacer dos validaciones:

```text
hash_raw_activo_financiero
hash_normalized_activo_financiero
```

## Validación de patrono

Crear una función como:

```python
def abf_especialista_en_patrono(abf, patrono_cliente):
    return patrono_cliente in {
        abf.get("especialistaPatrono1"),
        abf.get("especialistaPatrono2"),
        abf.get("especialistaPatrono3"),
    }
```

Excluir valores vacíos o `-1`.

Validar contra ABFs candidatos, no necesariamente contra todos los ABFs globales si la ruta restringe el universo a un CN, municipio o departamento.

## Validación de tipo cliente

Crear una función como:

```python
def inferir_tipo_cliente(estados_credito):
    if not estados_credito:
        return "CN"
    if "D" in estados_credito:
        return "CE"
    if all(e == "C" for e in estados_credito):
        return "CR"
    return "INDETERMINADO"
```

Luego comparar contra los `creditoTipoCliente` presentes en el XML.

Si hay varios créditos, todos deben ser coherentes con el tipo inferido.

## Validación de Regla 2

Crear una función que revise:

```python
def existe_desembolso_en_municipio(xml, municipio_objetivo):
    # Buscar créditos históricos cuyo cnCosechaMunicipio == municipio_objetivo
    # y cuyo cnCosechaEstado == Alta.
    # Además confirmar que cnCosechaCod exista en ActivoFinanciero
    # y que ese CN esté en estado Alta.
```

Aplicar la misma lógica para municipio de vivienda y municipio de trabajo.

## Validación aleatoria

Para los casos aleatorios:

1. Leer `random_case_id.csv`.
2. Leer `random_candidates.csv`.
3. Confirmar que cada caso aleatorio tenga al menos dos candidatos válidos, salvo que esté documentado como aleatorio degenerado.
4. Confirmar que cada candidato exista en el XML.
5. Confirmar que cada candidato cumpla las restricciones de la ruta.
6. Confirmar que `expected_outputs.csv` use `ACCEPTED_SET`.

Si se agregan respuestas reales de Blaze en el futuro, validar así:

```text
actual_cod_cn_actual ∈ accepted_cod_cn_set
actual_cod_abf_actual ∈ accepted_cod_abf_set
```

## Validación de rutas

Cada carpeta de `02_inputs_xml` debe tener 100 XMLs.

Cada ruta del manifest debe existir como carpeta.

Cada carpeta debe existir en el manifest.

Reportar:

```text
missing_route_folder
extra_route_folder
missing_xml
extra_xml
case_count_not_100
```

## Validación de nombres y longitudes

Validar que ninguna ruta interna supere 259 caracteres.

Reportar la ruta más larga.

No renombrar carpetas ni XMLs sin documentarlo.

## Resultado final esperado

Al finalizar, Codex debe dejar:

1. Scripts de validación funcionales.
2. Reportes CSV/JSON en `04_validation/outputs/`.
3. `avances.md` actualizado con todos los avances.
4. `arreglos.md` actualizado con cualquier corrección.
5. Un resumen claro del estado final.

El objetivo no es únicamente “pasar pruebas”, sino determinar si los XMLs realmente están bien construidos para probar el árbol ABF completo en Blaze.

## Mensaje final esperado de Codex

Al terminar, responder con:

```text
Validación finalizada.

Estado general: PASS / FAIL / PARTIAL

Resumen:
- XMLs esperados:
- XMLs encontrados:
- Rutas esperadas:
- Rutas encontradas:
- Errores críticos:
- Errores:
- Advertencias:

Archivos generados:
- ...

Archivos modificados:
- ...

Revisar:
- avances.md
- arreglos.md
- 04_validation/outputs/qa_validation_summary.json
```
