# Ejercicios: modelado, logs y auditoría en SEGB

Cada módulo tiene: **qué hacer**, **qué debe salir** y **qué explicar con tus palabras**.
Regla: si tu salida no coincide con la esperada, anótalo. Es un dato útil, no un fallo tuyo.

Empieza desde la carpeta de este worked example, la que contiene `ejercicios.md` (los comandos usan rutas relativas a ella).

---

## M1. Leer Turtle

Lee `ttl/escenario/01_personas.ttl` y responde sin ejecutar nada:

1. ¿Cuántos sujetos distintos hay?
2. ¿Qué tipos tiene `ex:maria_demo`? ¿Por qué tiene varios?
3. ¿Qué significa `a`?

Después lee `conceptos.md` (sección RDF y Turtle) y comprueba cada respuesta.

**Explica:** qué es una tripleta y dónde está el sujeto, el predicado y el objeto en la línea `foaf:name "Maria Demo"@es`.

---

## M2. Leer la ontología

Abre `ontology/segb.ttl` (en la raíz del repositorio; en la ontología el prefijo vacío `:` es `segb:`) y localiza:

- `:LoggedActivity` (¿de qué clase es subclase?),
- `:wasPerformedBy` (¿cuál es su `rdfs:domain` y su `rdfs:range`?),
- `:triggeredByActivity` (¿es subpropiedad de cuál?),
- `:producedActivityResult` y `:producedEntityResult`.

Rellena esta tabla con lo que encuentres:

| Propiedad | Dominio (`domain`) | Rango (`range`) | Superpropiedad |
|---|---|---|---|
| `segb:wasPerformedBy` | | | |
| `segb:triggeredByActivity` | | | |
| `segb:producedEntityResult` | | | |

**Explica:** ¿por qué `segb:triggeredBy` es más general que `segb:triggeredByActivity`? ¿Qué pasa si usas `triggeredBy` en lugar de la hija?

Ahora abre `ontology/example.ttl`: contiene ejemplos de uso de estas propiedades. Busca uno de cada una y anota si encaja con tu tabla.

---

## M3. Modelar un escenario propio (sin insertar)

Ya tienes el escenario en `ttl/escenario/`. Ahora, en un fichero nuevo `ttl/mi_escenario.ttl` (no lo envíes todavía):

1. Crea un agente (`prov:SoftwareAgent`) y una persona (`prov:Person`) inventadas.
2. Crea una actividad `segb:LoggedActivity` con `segb:wasPerformedBy` y `prov:startedAtTime`.
3. Crea un mensaje (`schema:Message`) con `schema:text` y `prov:wasGeneratedBy` apuntando a la actividad.

Valida el Turtle con el backend, que no escribe nada (`POST /ttl/validate`). Con el stack local levantado:

```bash
python3 -c 'import json,sys; print(json.dumps({"ttl_content": open(sys.argv[1]).read()}))' ttl/mi_escenario.ttl \
  | curl -s -X POST localhost:5000/ttl/validate -H 'Content-Type: application/json' -d @-
```

Si la autenticación está activada, añade `-H "Authorization: Bearer $SEGB_TOKEN"` con un token de rol `admin` (esta ruta lo exige). La respuesta trae `valid`, `triple_count` e `issues`. `HTTP 200` solo indica que el backend respondió: lo que cuenta es `valid`.

**Explica:** qué parte del modelo es "quién", "qué", "cuándo" y "por qué".

---

## M4. Enviar el escenario (escribe en el grafo)

Solo tras M1–M3. Primero, lista lo que se enviaría (sin enviar):

```bash
python3 publica_escenario.py
```

Si la autenticación está activada, antes exporta un token de rol `logger` o `admin` en `SEGB_TOKEN` (ver `README.md`).

Salida esperada: los cuatro ficheros, en orden (`01_personas.ttl`, `02_escucha.ttl`, `03_decision.ttl`, `04_respuesta.ttl`), sin ningún `HTTP`.

Ahora envía de verdad (una sola vez):

```bash
python3 publica_escenario.py --enviar
```

Salida esperada: un `HTTP 201` (o `200`) por fichero.

**Advertencia:** cada envío deja una entrada en `/history`. Si reenvías, quedan duplicados en la auditoría. Para verlo: `curl -s localhost:5000/history`.

**Explica:** ¿por qué el escenario se envía en 4 pasos y no en uno? ¿Qué pasa si el paso 4 se envía antes que el 3?

---

## M5. Comprobar que el grafo se fusionó

1. Ejecuta `consultas.sparql` consulta **C1** en `/query`. Debe aparecer `decision_demo_1`.
2. Ejecuta **C2**. Debe aparecer `speech_demo_1 → decision_demo_1`.
3. Ejecuta **C6**, que lista todo lo que se sabe de `decision_demo_1`. Debe devolver 8 filas. Pregunta: ¿tiene `prov:endedAtTime`? Aparece en el paso 4, no en el 3. ¿Por qué lo ves completo?

**Explica:** qué significa "fusión por URI" con tus palabras. Pista: un grafo es un conjunto de tripletas.

---

## M6. Generar logs paso a paso (de un escenario nuevo)

Este módulo es el que hay que dominar para escribir logs propios:

1. Decide la lista de pasos (p. ej. escuchar → decidir → hablar).
2. Para cada paso, un fichero `.ttl` con una actividad (`segb:LoggedActivity`), su agente y su causa.
3. Usa la misma URI para el mismo recurso en todos los ficheros.
4. Añade `prov:endedAtTime` al cerrar la actividad, en un fichero posterior.

Valida cada fichero como en M3. Después, **revisa tú** lo que el validador no comprueba:

- que el prefijo `ex:` sea el mismo namespace en todos los ficheros (si cambia, los enlaces entre ficheros se rompen y el validador lo da por bueno),
- que `prov:endedAtTime` no sea anterior a `prov:startedAtTime`,
- que `segb:usedMLModel` apunte a un modelo (`mls:Model`) y no a otra cosa,
- que uses `prov:wasGeneratedBy` para entidades (mensajes) y `segb:triggeredByActivity` entre actividades.

El validador revisa cada fichero por separado: un aviso `SEM_SUBJECT_WITHOUT_TYPE` en un fichero que completa un recurso definido en otro es esperable.

**Explica:** ¿por qué puedes escribir el fin de una actividad en otro fichero? ¿Qué riesgo hay si cambias la URI de un agente entre dos ficheros?

---

## M7. Consultas de lectura

Pega en `/query` las consultas de `consultas.sparql`, una a una (C1 a C7). Para cada una, escribe en una frase qué pregunta responde.

**Ojo al copiar:** `/query` rechaza una consulta con dos o más líneas de comentario delante del `SELECT` (o del `PREFIX`). Copia cada consulta desde su línea `# C…` (una sola línea de comentario) o sin comentarios.

**Pregunta de control:** ¿por qué C5 usa `schema:sender <http://example.org#ari_demo>` y no un nombre? (Pista: en RDF se identifica por URI.)

---

## M8. Worked example: auditoría de un mensaje

Caso: `msg_demo_2` dice "Here is some news. Stop being so sensitive." ¿Qué causó ese mensaje?

Sigue la cadena **sin mirar la respuesta**:

1. ¿Qué actividad lo generó? (`prov:wasGeneratedBy`)
2. ¿Qué disparó esa actividad? (`segb:triggeredByActivity`)
3. ¿Qué modelo usó la decisión? (`segb:usedMLModel`)
4. ¿Qué hizo el robot antes de decidir? (`prov:wasGeneratedBy` del mensaje de María)

Ejecuta **C5** (llega hasta el modelo) y **C7** (llega además hasta el mensaje de María) y compara.

**Explica:** el grafo no dice si el mensaje es ético; dice **de dónde salió**. ¿Qué datos le faltan al auditor para decidir si el modelo es responsable? (Pista: `llm_demo_1` no tiene descripción en el escenario: ¿qué sabrías de él si estuviera descrito con `mls:Run`, `mls:Implementation` y `mls:Dataset`?)

**Nota:** el escenario es sintético. Lo que compruebas es la trazabilidad (de dónde sale el mensaje), no si el robot se portó bien. Para ver el escenario original con más pasos (modelos, emociones, noticias), lee el tutorial del tag `0.3.0`: `git show 0.3.0:docs/SEGB_tutorial.rst`, sección «Retrieving the global graph».

---

## M9. Fuentes externas (lectura)

Lee, en este orden, y anota en `conceptos.md` lo que no entiendas:

1. `https://www.gsi.upm.es/ontologies/` (índice de ontologías del GSI).
2. `https://www.gsi.upm.es/ontologies/segb/examples/doc/index-en.html` (documentación Widoco de los ejemplos).
3. `https://github.com/alvarocarrera/openrobots-ontology` (de dónde sale `oro:`).

**Explica:** qué prefijo viene de qué ontología, y qué ontología define `segb:`.

---

## Cierre

En tu cuaderno de trabajo, añade una entrada con:

- qué módulos hiciste y qué salió (lo verificado),
- qué suposiciones quedan sin verificar,
- qué no entiendes todavía (para preguntar a Álvaro).
