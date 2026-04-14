# RXO Document Normalizer

This repository implements an AI-driven Excel schema standardization platform for RXO, as specified in ./docs/software_spec.md and ./docs/implementation_plan.md.

## Public Release Notes

- Copy `local.settings.template.json` to `local.settings.json` for local development.
- Never commit `local.settings.json`, `.env*`, or generated runtime artifacts.
- Report vulnerabilities via [SECURITY.md](SECURITY.md).
- See contribution process in [CONTRIBUTING.md](CONTRIBUTING.md).
- Repository license: [LICENSE](LICENSE).
- Community expectations: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Project Structure

- docs/: Specifications and implementation plans
- examples/: Sample input/output workbooks
- schema/: Output templates and schema definitions
- src/function_app/: Main application code
  - models/: Data contracts and enums
  - services/: Core logic modules
  - templates/: Canonical schema and output templates
  - prompts/: LLM prompt assets

## Tooling Baseline

- Python packaging and tool config: [pyproject.toml](pyproject.toml)
- Repository ignore rules: [.gitignore](.gitignore)

## Artifact Storage Modes

- Default: local artifact storage under per-run output folders
- Optional blob mirror mode:
  - `ARTIFACT_STORAGE_MODE=blob`
  - `ARTIFACT_BLOB_CONTAINER=<container-name>` (default `artifacts`)
  - Uses `AzureWebJobsStorage` connection string
  - Writes local artifacts and mirrors them to blob with a manifest

## Getting Started

1. Review ./docs/software_spec.md and ./docs/implementation_plan.md
2. Set up a Python virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Run tests: `python -m unittest tests/test_artifact_store.py tests/test_sandbox_executor.py tests/test_script_policy.py tests/test_pipeline_runner.py tests/test_planning_service.py tests/test_template_loader.py tests/test_normalization_service.py tests/test_validation_service.py tests/test_output_writer.py tests/test_sheet_classifier.py tests/test_workbook_profiler.py`

## Local Service Restart

- One-command restart (opens separate terminals for Azurite, Functions, and Streamlit):
  - `./scripts/restart-local.ps1`
- Detailed startup and troubleshooting guide:
  - [.copilot/startup_procedure.md](.copilot/startup_procedure.md)

## Preliminary Localhost Smoke Run

- Command: `python -m src.function_app.local_smoke_runner --input "examples/inputs/Input 8.xlsx" --output-root "artifacts/local_smoke"`
- Artifacts produced per run:
  - workbook profile JSON
  - canonical CSV
  - canonical XLSX
  - deterministic validation report JSON

## Local Real Core Pipeline Run

- Command: `python -m src.function_app.local_pipeline_runner --input "examples/inputs/Input 8.xlsx" --output-root "artifacts/local_pipeline" --run-mode execute_with_validation --planner-mode mock`
- This executes the full core flow:
  - planner response generation
  - script policy enforcement
  - sandbox transform execution
  - canonical CSV/XLSX writing from sandbox-produced records
  - validation report + execution artifacts
- Planner mode options:
  - `mock` (default): built-in planner script for local deterministic execution
  - `live`: calls Foundry endpoint using `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_AGENT_NAME`, `FOUNDRY_API_KEY`

## Streamlit Companion App

- UI/UX plan: [docs/streamlit_uiux_plan.md](docs/streamlit_uiux_plan.md)
- Launch command: `streamlit run streamlit_app.py`
- Capabilities:
  - Browse prior runs discovered from local artifact roots
  - Launch new runs from `examples/inputs/*.xlsx`
  - Visualize canonical output table, planner payload/script, validation issues, and sandbox execution logs

## Blob Trigger Function App Entry

- Main Function App entrypoint: [function_app.py](function_app.py)
- Function name: `ProcessWorkbookBlob`
- Trigger: blob trigger on `%INPUT_CONTAINER%/{name}`
- Run mode via env var `RUN_MODE`:
  - `draft`
  - `execute_with_validation` (default)
- Planner mode via env var `PLANNER_MODE`:
  - `mock` (default)
  - `live`
- Outputs:
  - `%OUTPUT_CONTAINER%/{name}.canonical.csv`
  - `%OUTPUT_CONTAINER%/{name}.validation.json`
  - `%OUTPUT_CONTAINER%/{name}.planner.json`
- Local settings template: [local.settings.template.json](local.settings.template.json)
- Local artifact persistence (for blob-trigger runs):
  - `FUNCTION_PERSIST_ARTIFACTS=true`
  - `FUNCTION_LOCAL_ARTIFACT_ROOT=artifacts/function_runs`
  - Per input blob, artifacts are cached under `artifacts/function_runs/<blob-stem>/pipeline_<runid>/`
  - Includes: `planner_response.json` (with `python_script`), `sandbox_execution_report.json`, `validation_report.json`, canonical outputs, and execution summary

To run locally with Azure Functions Core Tools:
- Copy `local.settings.template.json` to `local.settings.json`
- Ensure Azurite or an Azure Storage account is configured in `AzureWebJobsStorage`
- Start with: `func start`

## Infrastructure (Bicep)

- Main template: `infra/main.bicep`
- Environment parameter files:
  - `infra/main.dev.bicepparam`
  - `infra/main.test.bicepparam`
  - `infra/main.prod.bicepparam`
- Modules included:
  - storage, monitoring, key vault, function plan, function app, RBAC roles, optional container apps execution worker

Deploy examples:
- Dev: `az deployment group create --resource-group <rg-name> --parameters infra/main.dev.bicepparam`
- Test: `az deployment group create --resource-group <rg-name> --parameters infra/main.test.bicepparam`
- Prod: `az deployment group create --resource-group <rg-name> --parameters infra/main.prod.bicepparam`

### Minimal infra runbook (dev)

1) Baseline dev deployment (Function App + core resources)
- `az deployment group create --resource-group <rg-name> --parameters infra/main.dev.bicepparam`

2) Enable optional container worker (Container Apps environment + job)
- `az deployment group create --resource-group <rg-name> --parameters infra/main.dev.bicepparam --parameters enableContainerWorker=true`

3) Grant worker identity data-plane access (Storage + Key Vault)
- `az deployment group create --resource-group <rg-name> --parameters infra/main.dev.bicepparam --parameters enableContainerWorker=true assignContainerWorkerRoles=true`

4) Also grant worker Foundry access (if your worker needs direct Foundry calls)
- `az deployment group create --resource-group <rg-name> --parameters infra/main.dev.bicepparam --parameters enableContainerWorker=true assignContainerWorkerRoles=true assignContainerWorkerFoundryRoles=true assignFoundryRoles=true foundryAccountName=<foundry-account-name> foundryProjectName=<foundry-project-name>`

5) Inspect useful deployment outputs
- `functionAppName`
- `containerWorkerJobResourceId`
- `containerWorkerManagedEnvironmentId`
- `containerWorkerPrincipalId`

New Foundry runtime configuration is parameterized in Bicep via:
- `foundryProjectEndpoint`
- `foundryAgentName`
- `foundryAgentVersion`
- `foundryAssistantId` (kept empty for strict `agent_reference` mode)

## Implemented Slices

- Phase 1 foundational contracts (`src/function_app/models/contracts.py`, `src/function_app/models/enums.py`)
- Canonical schema contract and deterministic loader (`src/function_app/templates/canonical_schema.freight_bid_v1.json`, `src/function_app/services/template_loader.py`)
- Phase 2 deterministic workbook profiling and sheet classification (`src/function_app/services/workbook_profiler.py`, `src/function_app/services/sheet_classifier.py`)
- Phase 3 deterministic canonical output writing for CSV/XLSX (`src/function_app/services/output_writer.py`)
- Phase 4 deterministic validation service for schema shape, required fields, type checks, enum enforcement, null-rate threshold warnings, and cross-field consistency checks (`src/function_app/services/validation_rules.py`, `src/function_app/services/validation_service.py`)
- Phase 5 deterministic normalization helpers and lineage-aware validation output (`src/function_app/services/normalization_service.py`, `src/function_app/services/validation_service.py`)
- Preliminary deterministic localhost smoke runner (`src/function_app/local_smoke_runner.py`)
- Blob-trigger Function App entrypoint (`function_app.py`)
- Phase 6 Foundry planning scaffolding (prompt assets + client seam + planning service) (`src/function_app/prompts/`, `src/function_app/services/foundry_agent_client.py`, `src/function_app/services/planning_service.py`)
- Phase 7 mode-aware pipeline orchestration with planner artifact persistence (`src/function_app/services/pipeline_runner.py`, `function_app.py`)
- Phase 8 script policy guardrails for planner-generated code (`src/function_app/services/script_policy.py`)
- Phase 9 sandbox execution scaffolding with structured execution reports (`src/function_app/services/sandbox_executor.py`)
- Phase 10 artifact store seam + execution result artifact alignment (`src/function_app/services/artifact_store.py`, `execution_result.json` in pipeline outputs)
- Phase 11 packaging/tooling baseline (`pyproject.toml`, `.gitignore`)
- Phase 12 blob-backed artifact store seam and local-to-blob mirroring (`src/function_app/services/artifact_store.py`)
- Early unit tests covering classifier behavior and workbook profiling on sample workbook (`tests/`)

## Implementation Status

See ./.copilot/TODO.md for current progress and next steps.

## Operating Principles

- All architecture and implementation must align with the software spec and implementation plan.
- All infrastructure is provisioned via Bicep.
- Deterministic, testable, and auditable transformation is required.
- See ./.copilot/copilot_instructions.md for agent operating rules.
