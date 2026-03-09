# Ontology (SEGB)

## Objective

Provide the canonical references for the SEGB ontology used by this repository and the namespace prefixes commonly
emitted in SEGB logs.

## Canonical references

- **Preferred namespace prefix:** `segb`
- **Namespace IRI:** `http://www.gsi.upm.es/ontologies/segb/ns#`
- **Ontology document (OWL, RDF/XML):** `http://www.gsi.upm.es/ontologies/segb/ns/doc/ontology.owl`
- **Version (from the ontology header):** `1.0.0`

## Namespaces used by `semantic_log_generator`

The package `semantic_log_generator` binds a default prefix set in
`packages/semantic_log_generator/src/semantic_log_generator/namespaces.py`.

Use this table as a quick reference when reading Turtle exports (for example, when you inspect the output of
`GET /events` or the UI pages that visualize the Knowledge Graph):

| Prefix | Namespace IRI |
|---|---|
| `segb` | `http://www.gsi.upm.es/ontologies/segb/ns#` |
| `prov` | `http://www.w3.org/ns/prov#` |
| `oro` | `http://kb.openrobots.org#` |
| `mls` | `http://www.w3.org/ns/mls#` |
| `onyx` | `http://www.gsi.upm.es/ontologies/onyx/ns#` |
| `emoml` | `http://www.gsi.upm.es/ontologies/onyx/vocabularies/emotionml/ns#` |
| `sosa` | `http://www.w3.org/ns/sosa/` |
| `schema` | `http://schema.org/` |
| `oa` | `http://www.w3.org/ns/oa#` |
| `foaf` | `http://xmlns.com/foaf/0.1/` |
| `rdf` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `rdfs` | `http://www.w3.org/2000/01/rdf-schema#` |
| `owl` | `http://www.w3.org/2002/07/owl#` |
| `xsd` | `http://www.w3.org/2001/XMLSchema#` |

## Optional Note For High-Assurance Deployments

If you need a pinned, offline copy of the ontology for reproducible audits:

- Decide a repository location to store it (for example `docs/assets/ontology/` or `packages/semantic_log_generator/assets/`).
- Provide the desired file format (`.owl` RDF/XML vs `.ttl` Turtle).
- Define the version pinning policy (for example, lock to `1.0.0` or track latest).
