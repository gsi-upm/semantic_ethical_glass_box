# Changelog

All notable changes to `semantic_log_generator` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.5] - 2026-03-09

### Added
- `log_message(..., sender=...)` now emits explicit message attribution with `schema:sender` and `prov:wasAttributedTo`.

## [1.0.0] - 2026-03-03

### Changed
- Promoted the package to stable `1.0.0` after ontology-compliance hardening across generated TTL.
- Shared-event confidence and robot-state properties are modeled with `schema:additionalProperty` (`schema:PropertyValue`) instead of non-existent `segb:*` properties.
- Robot agent labels now use `schema:name` (instead of `oro:hasName`) and messages use `schema:Message` + `schema:text` (instead of `oro:Message` + `oro:hasText`).
- Conversation chaining now uses `prov:wasDerivedFrom` (instead of non-existent `oro:previousMessage`/`oro:nextMessage`).
- Documentation updated to match the stable API/ontology model and `1.x` installation guidance.

## [0.1.4] - 2026-03-03

### Changed
- Removed invalid `segb:confidence` usage. Observation-to-shared-event confidence is now modeled as `schema:additionalProperty` (`schema:PropertyValue` with `schema:propertyID="shared_event_confidence"` and numeric `schema:value`).
- Removed invalid `segb:hasStateProperty` usage. Robot-state properties now link via `schema:additionalProperty`.
- Updated package and project documentation to reflect the ontology-compliant state/confidence modeling.

## [0.1.3] - 2026-03-03

### Changed
- Shared events no longer emit invalid `schema:eventType`/`schema:measurementTechnique`; modality is modeled with SOSA (`sosa:Observation` + `sosa:Procedure`).
- Shared-event confidence is now emitted as `segb:confidence` instead of non-standard `schema:confidence`.
- Robot state snapshots now link properties with `segb:hasStateProperty` and location with `prov:atLocation`.
- Shared-event metadata (`schema:about`, `schema:description`, `prov:generatedAtTime`, `schema:identifier`) is not duplicated when reusing the same `event_id`.
- Reusing the same `activity_id` with a different timestamp now raises `ValueError` to prevent inconsistent provenance.

## [0.1.2] - 2026-03-03

### Changed
- Removed `SEGB_SHARED_CONTEXT_URL` and `SEGB_SHARED_CONTEXT_TOKEN` from shared-context resolver configuration.
- Standardized resolver env inputs to `SEGB_API_URL` and `SEGB_API_TOKEN` only.
- Updated package and project documentation to match the new environment-variable contract.

## [0.1.1] - 2026-03-03

### Changed
- Updated package documentation for installation from PyPI/TestPyPI and corrected TestPyPI dependency-resolution command using `--extra-index-url`.
- Clarified usage examples so `base_namespace` is treated as application/deployment configuration, not end-user RDF/Turtle handling.
- Standardized shared-context resolver env configuration to use `SEGB_API_URL` and `SEGB_API_TOKEN`.

## [0.1.0] - 2026-02-25

### Added
- First public packaged release of `semantic_log_generator`.
- Stable API exports for `SemanticSEGBLogger`, `SEGBPublisher`, shared-context resolver types, and core datatypes.
- Packaging metadata for production distribution (authors, maintainers, license, classifiers, project URLs).

### Changed
- Declared support for Python 3.10, 3.11, and 3.12.
