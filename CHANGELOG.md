# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-20

### Added
- Initial release.
- Parse OIC `.iar` archives (ZIP format) and extract the orchestration flow from `project.xml`.
- Generate **PlantUML** (`.puml`) sequence diagrams with full skinparam styling.
- Generate **Mermaid Markdown** (`.md`) sequence diagrams with autonumber.
- Generate **PNG** via local PlantUML CLI or PlantUML web-server fallback.
- CLI entry point `oic-sequence-gen` (and `python -m oic_sequence_gen`).
- Support for all OIC flow constructs: `for`, `while`, `router`, `try/catchAll`, `throw`, `stageFile`, `invoke`, `transformer`, `assignment`, `wait`, `activityStreamLogger`.
- Dynamic participant discovery: participants are derived from `appinstances/*.xml` (`applicationTypeRef`) rather than hardcoded connection names; one participant per unique connection.
- Dynamic route conditions: labels are read from `ExpressionName` / `TextExpression` in each route's `expr.properties` file.
- Zero runtime dependencies (Python stdlib only).

[Unreleased]: https://github.com/YOUR_USER/oic-sequence-gen/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR_USER/oic-sequence-gen/releases/tag/v0.1.0
