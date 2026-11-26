# Ejercicios: modelado, logs y auditoría en SEGB

Cada módulo tiene: **qué hacer**, **qué debe salir** y **qué explicar con tus palabras**.
Haz los módulos en orden. Regla: si tu salida no coincide con la esperada, anótalo. Es un dato útil, no un fallo tuyo.

Empieza desde la carpeta de este worked example, la que contiene `ejercicios.md` (los comandos usan rutas relativas a ella).


---

## Antes de empezar

### La idea
SEGB es una "caja negra" para robots: guarda qué ocurrió para poder revisarlo después. En este ejemplo
inventado, una persona le pide noticias a un robot (ARI), el robot decide y responde.

### Lo que necesitas saber
La información se guarda en un **grafo** hecho de **tripletas**: sujeto, propiedad y objeto. Se escribe en
ficheros Turtle (`.ttl`):

```turtle
ex:aviso_1 a schema:Message ;
    schema:sender ex:robot_ejemplo ;
    prov:wasGeneratedBy ex:habla_ejemplo .
```

- Se lee: "`aviso_1` es un mensaje; lo envió `robot_ejemplo`; lo generó `habla_ejemplo`".
- `a` significa "es un". El `;` repite el sujeto y el `.` cierra el bloque.
- Cada cosa tiene una dirección única (**URI**). `ex:` abrevia `http://example.org#`, así que
  `ex:aviso_1` es `<http://example.org#aviso_1>`.
- Una **actividad** es algo que ocurrió (escuchar, decidir, hablar).
- **SPARQL** es el lenguaje para preguntar al grafo. Las palabras con `?` son huecos que se rellenan solos.

### Prepara el entorno
1. Arranca SEGB desde la raíz del repo: `docker compose -f docker-compose.yaml up -d`.
2. Comprueba que está listo: `curl -s localhost:5000/healthz/ready` debe dar `"ready":true`.
3. Vuelve a la carpeta de este worked example (`cd worked-example`). En `ttl/escenario/` están los cuatro
   ficheros, de `01_personas.ttl` a `04_respuesta.ttl`.

Si SEGB tiene la autenticación activada, mira "Autenticación y roles" en `README.md`.

### Cómo lanzar una consulta
1. Guarda **una sola** consulta en un fichero `consulta.rq`. Delante puede llevar una línea de comentario como
   mucho: con dos, SEGB 1.3.1 la rechaza.
2. Envíala:

```bash
curl -sG localhost:5000/query --data-urlencode query@consulta.rq
# Con autenticación, añade: -H "Authorization: Bearer $SEGB_TOKEN"
```

La respuesta llega en Turtle. Cada fila es un bloque `ns:Result`, y cada `?hueco` aparece como `ns:hueco`:

```turtle
[] a ns:Result ;
    ns:n 0 .
```

Aquí hay una fila y `?n` vale 0.

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

## M4. Enviar el escenario
**Objetivo:** comprobar los ficheros, publicarlos una sola vez y ver qué rastro deja el envío. Hazlo después de
M1 a M3.

> **Atención:** el paso 4 se hace **una sola vez**. No uses `POST /ttl/delete_all`: borra todo el grafo.

1. **Mira cómo está el grafo antes.** Cuenta las tripletas del escenario y apunta el número:

```sparql
SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o . FILTER(STRSTARTS(STR(?s), "http://example.org#")) }
```

Si no es 0, el escenario (u otros datos con ese prefijo) ya está: pregunta antes de enviar.

2. **Ensaya.** Esto valida cada fichero y no publica nada (con autenticación, la validación pide un token
   `admin`; si solo tienes `logger`, añade `--sin-validar` aquí y en el paso 4):

```bash
python3 publica_escenario.py
```

3. **Lee el resultado.** Un `error` impide enviar. Un `warning` avisa, pero deja enviar. Apunta las
   tripletas, errores y avisos de cada fichero.
4. **Publica:**

```bash
python3 publica_escenario.py --enviar
```

   Apunta el `log_id` de cada fichero: identifica ese envío.
5. **Comprueba el cambio.** Repite la consulta del paso 1.
6. **Mira la auditoría**, el registro de quién cambió el grafo (rol `auditor` o `admin`):

```bash
curl -s localhost:5000/history
curl -s "localhost:5000/log?log_id=PON_AQUI_UN_LOG_ID"
# Con autenticación, añade a cada orden: -H "Authorization: Bearer $SEGB_TOKEN"
```

**Preguntas**
- ¿Por qué un fichero puede ser válido y tener un aviso?
- ¿En qué se diferencian la auditoría (`/history`) y los datos que consultas con `/query`?
- **Sin ejecutarlo:** si enviaras dos veces, ¿qué cambiaría en el grafo y qué en la auditoría?
- ¿Por qué el escenario se envía en cuatro pasos y no en uno?
- **Sin ejecutarlo:** ¿qué pasaría si el fichero 04 se enviara antes que el 03?

**Tu respuesta:**

Mira `soluciones.md` solo después de intentarlo.

---

## M5. Comprobar la fusión por URI
**Objetivo:** ver que dos ficheros que usan la misma URI describen **la misma cosa**.

1. Abre `03_decision.ttl` y `04_respuesta.ttl`. Apunta qué dice cada uno **con `ex:decision_demo_1` como sujeto**.
2. **Predice** cuántas filas devolverá la consulta. Cuenta una por cada propiedad y valor: si una línea tiene
   dos valores separados por coma, son dos.
3. Ejecuta (es la consulta **C5** de `consultas.sparql`):

```sparql
SELECT ?p ?o WHERE { <http://example.org#decision_demo_1> ?p ?o }
```

4. Marca cada fila con el fichero del que viene (03 o 04).

**Preguntas**
- ¿Coincide con tu predicción? Si hay filas de más, ¿de dónde pueden haber salido?
- ¿Qué sabrías de la decisión si solo se hubiera enviado el 03?
- ¿Qué pasaría si en el 04 `ex:` abreviara otra dirección?
- Explica con tus palabras qué es la **fusión por URI**. Pista: un grafo es un conjunto de tripletas.

**Tu respuesta:**

Mira `soluciones.md` solo después de intentarlo.

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

## M7. Consultas
**Objetivo:** hacer preguntas al grafo y escribir tu propia consulta.

### 1. Las consultas del escenario
Ejecuta, una a una, las consultas **C1 a C4** de `consultas.sparql`. Para cada una, escribe en una frase qué
pregunta responde.

### 2. ¿Qué hizo el robot?

```sparql
SELECT ?actividad ?inicio ?fin WHERE {
  ?actividad <http://www.gsi.upm.es/ontologies/segb/ns#wasPerformedBy> <http://example.org#ari_demo> .
  OPTIONAL { ?actividad <http://www.w3.org/ns/prov#startedAtTime> ?inicio }
  OPTIONAL { ?actividad <http://www.w3.org/ns/prov#endedAtTime> ?fin }
}
```

Se lee: "busca las actividades que hizo `ari_demo` y, si las tienen, su inicio y su fin". Predice cuántas
saldrán antes de ejecutarla.

### 3. ¿Qué se dijo?

```sparql
SELECT ?mensaje ?quien ?texto ?actividad WHERE {
  ?mensaje <http://schema.org/text> ?texto ;
           <http://schema.org/sender> ?quien ;
           <http://www.w3.org/ns/prov#wasGeneratedBy> ?actividad .
  FILTER(STRSTARTS(STR(?mensaje), "http://example.org#"))
}
```

Identifica qué dijo la persona y qué dijo el robot.

### 4. Ahora tú
a. Amplía la consulta de «¿Qué hizo el robot?» para ver también quién disparó cada actividad
   (`<http://www.gsi.upm.es/ontologies/segb/ns#triggeredByActivity>`). No pierdas ninguna fila.

b. Escribe una consulta que devuelva las actividades que usaron un modelo
   (`<http://www.gsi.upm.es/ontologies/segb/ns#usedMLModel>`) y cuál usaron.

**Preguntas**
- La consulta de «¿Qué hizo el robot?» identifica al robot con `<http://example.org#ari_demo>`. ¿Por qué no con su nombre?
- ¿Para qué sirve `OPTIONAL`?
- ¿Para qué sirve el `FILTER` de la consulta de «¿Qué se dijo?»?
- ¿Puedes fiarte del orden de las filas?

**Tu respuesta:**

Mira `soluciones.md` solo después de intentarlo.

---

## M8. Auditar una respuesta
**Objetivo:** averiguar de dónde salió una respuesta del robot siguiendo los enlaces registrados.

**La situación.** ARI contestó: *"Here is some news. Stop being so sensitive."* Esa respuesta es
`ex:msg_demo_2`. Te piden explicar cómo se llegó hasta ella.

### Cómo buscar
Elige una de las dos formas (lo básico está al principio del documento):
- **Leyendo** los ficheros de `ttl/escenario/`. Un mismo nodo puede aparecer en más de un fichero.
- **Consultando** (después de M4). Pon entre `<...>` la dirección completa de lo que quieres mirar:

```sparql
SELECT ?p ?o WHERE { <http://example.org#msg_demo_2> ?p ?o }
```

**Seguir un enlace** es tomar el objeto (`?o`) de una fila y volver a consultar poniéndolo como sujeto.

### Paso a paso
Rellena una fila antes de pasar a la siguiente: la respuesta de cada salto es el punto de partida del próximo.

| Salto | Parte de | Pregunta | Propiedad | Lo que encuentras |
|---|---|---|---|---|
| 1 | `ex:msg_demo_2` | ¿Qué actividad generó el mensaje? | `prov:wasGeneratedBy` | |
| 2 | respuesta 1 | ¿Qué la disparó? | `segb:triggeredByActivity` | |
| 3 | respuesta 2 | ¿Qué modelo usó? | `segb:usedMLModel` | |
| 4 | respuesta 2 | ¿Qué la disparó? | `segb:triggeredByActivity` | |
| 5 | respuesta 4 | ¿Qué mensaje generó esa actividad y quién lo envió? | `prov:wasGeneratedBy`, `schema:sender` | |

**Pista para el salto 5.** Aquí la flecha va al revés: la actividad no apunta al mensaje, es el mensaje el que
apunta a la actividad. Busca quién tiene tu respuesta 4 como **objeto**. Con una consulta:

```sparql
SELECT ?s ?p WHERE { ?s ?p <DIRECCION_DE_TU_RESPUESTA_4> }
```

Pueden salir varias filas: quédate con la que use `prov:wasGeneratedBy` y consulta después quién lo envió.

### Une la cadena
1. Escribe en una frase el recorrido, desde la respuesta de ARI hasta el mensaje original.
2. Compón tú la consulta de auditoría con lo que has visto en **C2**, **C3** y **C4** de `consultas.sparql`, más
   `prov:wasGeneratedBy` de la tabla. Usar la misma variable (por ejemplo, `?actividad`) en dos líneas las une.
   Empieza llegando desde el mensaje del robot hasta el modelo y después alárgala hasta el mensaje de la persona.
3. En tu consulta, ¿cómo indicas que el mensaje es del robot? ¿Por qué con su URI y no con su nombre?

### Piensa como auditor
- Si la consulta unida no devuelve filas, ¿cómo averiguas qué enlace falta?
- El grafo no dice si el mensaje es ético: dice **de dónde salió**. ¿Dice **por qué** ARI respondió así? Separa lo que está registrado de lo que estás suponiendo.
- ¿Qué más habría que registrar para auditar esa respuesta?
- Del modelo `llm_demo_1` solo se sabe que es un modelo. ¿Qué más sabrías si estuviera descrito con
  `mls:Run` (una ejecución), `mls:Implementation` (el software) y `mls:Dataset` (los datos)?

El escenario es sintético: compruebas la trazabilidad, no si el robot se portó bien. El escenario original, con más
pasos, está en el tutorial del tag `0.3.0`: `git show 0.3.0:docs/SEGB_tutorial.rst`, sección «Retrieving the
global graph».

**Tu respuesta:**

Mira `soluciones.md` solo después de intentarlo.

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
