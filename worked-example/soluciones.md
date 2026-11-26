# Soluciones

Mira cada una **solo después de intentar** el ejercicio en `ejercicios.md`.

## M4. Enviar el escenario

<details>
<summary>Ver la solución de M4</summary>

- Cada fichero se valida por separado. Un nodo puede tener su tipo declarado en otro fichero.
- `/query` consulta los hechos del escenario. La auditoría va en otro grafo y registra cada envío.
- El grafo no ganaría tripletas repetidas (todos los nodos tienen URI), pero la auditoría tendría entradas nuevas.
- Cada paso imita un momento distinto: el robot registra lo que va ocurriendo, y cada envío queda en la auditoría.
- El grafo final sería el mismo. Entre un envío y otro, la decisión estaría descrita a medias (sin tipo ni
  agente) y la auditoría reflejaría otro orden.

</details>

## M5. Comprobar la fusión por URI

<details>
<summary>Ver la solución de M5</summary>

- Salen 8 filas: 6 del 03 (dos tipos, quién la hizo, qué la disparó, modelo e inicio) y 2 del 04 (fin y
  resultado). Si hay más, alguien ha enviado otros datos con esa misma URI.
- No sabrías cuándo terminó ni qué produjo.
- Serían dos nodos distintos y la decisión quedaría partida.
- Lo que distintos ficheros dicen de una misma URI se junta en un solo nodo del grafo.

</details>

## M7. Consultas

<details>
<summary>Ver la solución de M7</summary>

El robot: tres actividades. Mensajes: dos.

a.

```sparql
SELECT ?actividad ?inicio ?fin ?disparador WHERE {
  ?actividad <http://www.gsi.upm.es/ontologies/segb/ns#wasPerformedBy> <http://example.org#ari_demo> .
  OPTIONAL { ?actividad <http://www.w3.org/ns/prov#startedAtTime> ?inicio }
  OPTIONAL { ?actividad <http://www.w3.org/ns/prov#endedAtTime> ?fin }
  OPTIONAL { ?actividad <http://www.gsi.upm.es/ontologies/segb/ns#triggeredByActivity> ?disparador }
}
```

b.

```sparql
SELECT ?actividad ?modelo WHERE { ?actividad <http://www.gsi.upm.es/ontologies/segb/ns#usedMLModel> ?modelo }
```

En tu grafo pueden salir además actividades de otros datos.

- En RDF las cosas se identifican por su URI. El nombre es un dato más y puede repetirse.
- `OPTIONAL` mantiene la fila aunque falte ese dato.
- El `FILTER` deja solo los mensajes de este ejemplo.
- No: la respuesta es Turtle y no conserva el orden (issue #59).

</details>

## M8. Auditar una respuesta

<details>
<summary>Ver la solución de M8</summary>

1. `ex:speech_demo_1`, una acción de habla (04).
2. `ex:decision_demo_1`, una decisión (el enlace está en el 04; la decisión se describe en el 03 y el 04).
3. `ex:llm_demo_1`, un modelo (03).
4. `ex:listening_demo_1`, una escucha (el enlace está en el 03; la escucha se describe en el 02).
5. `ex:msg_demo_1`, enviado por `ex:maria_demo` (02).

**Consulta de auditoría corta**, desde el mensaje del robot hasta el modelo:

```sparql
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX schema: <http://schema.org/>
SELECT ?msg ?respuesta ?decision ?modelo WHERE {
  ?msg a schema:Message ;
       schema:sender <http://example.org#ari_demo> ;
       prov:wasGeneratedBy ?respuesta .
  ?respuesta segb:triggeredByActivity ?decision .
  ?decision segb:usedMLModel ?modelo .
}
```

**Consulta de auditoría completa**, hasta el mensaje de María:

```sparql
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX schema: <http://schema.org/>
SELECT ?msgRobot ?habla ?decision ?modelo ?escucha ?msgMaria WHERE {
  ?msgRobot a schema:Message ;
            schema:sender <http://example.org#ari_demo> ;
            prov:wasGeneratedBy ?habla .
  ?habla segb:triggeredByActivity ?decision .
  ?decision segb:usedMLModel ?modelo ;
            segb:triggeredByActivity ?escucha .
  ?msgMaria prov:wasGeneratedBy ?escucha .
}
```

</details>
