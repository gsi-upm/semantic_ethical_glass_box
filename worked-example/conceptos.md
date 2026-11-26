# Glosario mínimo

## RDF y Turtle

- **Tripleta**: `sujeto – predicado – objeto`. Ejemplo: `ex:msg_demo_1 schema:text "Good morning"@en`.
- **Grafo**: conjunto de tripletas. No tiene orden. Dos ficheros con la misma URI se fusionan en un nodo.
- **URI**: identificador del recurso. `ex:maria_demo` = `http://example.org#maria_demo`.
- **Nodo en blanco** (`[]`): nodo sin URI. Evítalo: no se puede volver a referenciar y el validador da `SEM_BLANK_NODES`.
- **Literal**: valor con tipo o idioma. `"0.3"^^xsd:float`, `"Maria"@es`.
- **`a`**: atajo de `rdf:type` ("es un/una").
- **`;`** mismo sujeto, otro predicado. **`,`** mismo sujeto y predicado, otro objeto. **`.`** fin de las frases de ese sujeto.

## Prefijos (las ontologías del tutorial)

| Prefijo | Namespace | Para qué |
|---|---|---|
| `prov:` | `http://www.w3.org/ns/prov#` | Procedencia: `prov:Activity`, `prov:Agent`, `prov:used`, `prov:wasGeneratedBy`, `prov:startedAtTime` |
| `segb:` | `http://www.gsi.upm.es/ontologies/segb/ns#` | Actividades registradas y sus relaciones (ver `ontology/segb.ttl`) |
| `mls:` | `http://www.w3.org/ns/mls#` | ML Schema: `mls:Run`, `mls:Model`, `mls:Algorithm`, `mls:Dataset` |
| `oro:` | `http://kb.openrobots.org#` | OpenRobots: `oro:Robot`, `oro:ListeningEvent`, `oro:DecisionMakingAction`, `oro:SpeechAction` (comprobado el 24/11/2026 en `share/ontologies/oro.ttl` de `alvarocarrera/openrobots-ontology`, con `oro:Human`) |
| `schema:` | `http://schema.org/` | Mensajes, noticias, personas |
| `foaf:` | `http://xmlns.com/foaf/0.1/` | Nombres de personas |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` | Tipos de datos (`xsd:dateTime`) |

## SEGB en 4 ideas

1. Todo lo registrado es un `segb:LoggedActivity`, que es un `prov:Activity`.
2. `segb:wasPerformedBy` dice **qué agente** lo hizo.
3. `segb:triggeredByActivity` dice **qué lo causó**; `segb:usedMLModel` dice **qué modelo** usó; `segb:producedActivityResult` / `segb:producedEntityResult` dicen **qué produjo**.
4. Las fechas van en `prov:startedAtTime` y `prov:endedAtTime`. Un `xsd:dateTime` sin zona es ambiguo al comparar sistemas.

## Roles

- `logger`: publica (`POST /ttl`).
- `auditor`: consulta (`GET /query`, `GET /history`).
- `admin`: opera (`/system/logs`, `/logs/insert`).
