# Worked example de SEGB: modelado, logs y auditoría

Laboratorio para aprender a:

1. leer la ontología SEGB y entender el modelo semántico,
2. generar logs de un agente paso a paso,
3. volcarlos en el grafo (`POST /ttl`),
4. consultarlos y auditar un caso completo (worked example).

Todo es **sintético** (`example.org`, nombres inventados). Ningún script borra datos.

## Reglas

- **No** ejecutes `POST /ttl/delete_all`: borra el grafo entero.
- `publica_escenario.py` solo envía con `--enviar`. Sin esa opción, valida los ficheros y no publica nada.
- Envía el escenario **una vez**. Si lo reenvías, quedan entradas duplicadas en la auditoría (ver `ejercicios.md`, M4).
- Usa tu propio SEGB local, no un servidor compartido.
- No pegues tokens ni el contenido de `.env` en ningún sitio.

## Requisitos

- Stack local levantado (`docs/getting-started/quickstart.md`). Comprobación:
  ```bash
  curl -s localhost:5000/healthz/ready
  ```
  Debe devolver `true` en `ready`.
- `python3` (la librería estándar basta: `publica_escenario.py` no instala nada).

## Autenticación y roles

Compruébalo con `curl -s localhost:5000/auth/mode`. Sin autenticación (`SECRET_KEY` vacío) toda petición tiene
todos los roles: solo sirve para una instalación local aislada. Con autenticación, guarda un token en la variable
`SEGB_TOKEN` y no lo pegues ni lo imprimas.

| Acción | Ruta | Roles |
|---|---|---|
| Validar Turtle | `POST /ttl/validate` | `admin` |
| Publicar | `POST /ttl` | `logger` o `admin` |
| Consultar y auditar | `GET /query`, `GET /history`, `GET /log` | `auditor` o `admin` |

Como `publica_escenario.py` valida antes de enviar, con un token `logger` hay que añadir `--sin-validar`.

Para generar un token en un stack local arrancado con Docker (más detalles en
`docs/operations/authentication-and-jwt.md`):

```bash
docker exec -w /app/src segb-server /app/.venv/bin/python -m tools.generate_jwt \
  --username demo_user --role admin --expires-in 3600 --json
```

## Archivos

| Archivo | Qué es | ¿Escribe en el grafo? |
|---|---|---|
| `README.md` | Esta guía | No |
| `ejercicios.md` | Módulos M1–M9 en orden | Solo M4, con el script |
| `soluciones.md` | Soluciones de M4, M5, M7 y M8. Míralas solo después de intentarlo | No |
| `conceptos.md` | Glosario: RDF, Turtle, prefijos, PROV, SEGB, ML Schema, OpenRobots | No |
| `ttl/escenario/*.ttl` | Escenario María–ARI en 4 ficheros, en orden | No (son datos) |
| `publica_escenario.py` | Valida y envía los ficheros de `ttl/escenario/` (`--carpeta` para otra subcarpeta de `ttl/`) | Solo con `--enviar` |
| `consultas.sparql` | Consultas de lectura para `/query` | No |

## Fuentes

- `ontology/segb.ttl` y `ontology/example.ttl` (en el repo).
- Tutorial original, que ya no está en el árbol actual: `git show 0.3.0:docs/SEGB_tutorial.rst` (tag `0.3.0`). Es el escenario del que parte este worked example, con más pasos (modelos, emociones, noticias).
- `https://www.gsi.upm.es/ontologies/` y `https://www.gsi.upm.es/ontologies/segb/examples/doc/index-en.html` (online).
- `https://github.com/alvarocarrera/openrobots-ontology` (vocabulario `oro:`).
