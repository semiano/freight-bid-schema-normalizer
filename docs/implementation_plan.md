# Implementation Plan: AI-Driven Excel Standardization Platform
Version: 0.1

This plan translates the software spec into a build sequence that GitHub Copilot can execute with minimal ambiguity.

---

## 1. Delivery Strategy

Build in four controlled layers:

1. **Deterministic core first**
   - workbook parsing
   - schema contracts
   - canonical writer
   - validation
   - local runner

2. **Agent planning next**
   - prompt construction
   - Foundry client
   - response contract validation
   - script generation

3. **Sandboxed execution**
   - AST policy
   - compile checks
   - controlled runtime
   - artifact capture

4. **Cloud packaging**
   - Azure Functions surface
   - storage + monitoring + identity
   - Bicep deployment
   - integration tests

This sequence keeps the system usable before the LLM layer is fully wired.

---

## 2. Build Phases

## Phase 0: Repository Bootstrap

### Goals
- Create repository skeleton
- Establish Python tooling
- Establish docs and contracts
- Lock local developer workflow

### Deliverables
- repository folders
- `pyproject.toml` or `requirements.txt`
- linting and formatting config
- `README.md`
- `.env.example`
- `.gitignore`
- `/docs/software_spec.md`
- `/docs/implementation_plan.md`

### Tasks
- Initialize project structure
- Choose Python version target for local and Azure
- Add `pytest`
- Add type checking with `mypy` or pyright
- Add formatter, preferably `black`
- Add linter, preferably `ruff`
- Add pre-commit config if desired

### Definition of done
- local virtual environment works
- tests run
- format/lint runs clean
- docs committed

---

## Phase 1: Define Contracts and Core Models

### Goals
Create strict contracts before any agent logic is added.

### Deliverables
- `contracts.py`
- schema JSON files
- execution result schema
- workbook profile schema
- agent response schema

### Tasks
- Define Pydantic models for:
  - workbook profile
  - sheet profile
  - column profile
  - canonical schema
  - planner response
  - execution result
  - validation result
- Define enums:
  - run status
  - validation severity
  - sheet classification
  - output format
- Create `canonical_schema.freight_bid_v1.json`
- Create `planner_response.schema.json`

### Definition of done
- schema contracts can serialize and validate
- unit tests cover valid and invalid payloads

---

## Phase 2: Build Workbook Profiler

### Goals
Profile a workbook without any LLM involvement.

### Deliverables
- `workbook_profiler.py`
- `sheet_classifier.py`
- unit tests using provided sample workbook

### Tasks
- Load workbook with `openpyxl`
- Capture:
  - sheet names
  - hidden flags
  - dimensions
  - merged ranges
  - header-row candidates
  - first 10 data rows
  - inferred data types
- Implement heuristics:
  - detect likely header row
  - detect likely data-bearing sheet
  - detect non-data sheets
- Emit a clean JSON profile
- Add classifier hints such as:
  - `instructional`
  - `reference`
  - `tabular_data`
  - `likely_exclude`

### Definition of done
- profiler correctly identifies the main tabular sheets in the provided example
- non-data tabs are labeled sensibly
- unit tests pass

---

## Phase 3: Build Template Loader and Canonical Writer

### Goals
Support deterministic target generation before the agent exists.

### Deliverables
- `template_loader.py`
- `output_writer.py`
- `templates/output_template.xlsx`
- tests for writing canonical xlsx and csv

### Tasks
- Load canonical schema JSON
- Define output dataframe column order
- Implement canonical dataframe normalization helpers
- Write output to:
  - xlsx
  - csv
- Optionally write a second metadata sheet for diagnostics in non-production mode

### Definition of done
- given a mock canonical dataframe, system emits correct xlsx and csv
- output column order exactly matches template

---

## Phase 4: Build Reference Resolver

### Goals
Move enrichment logic out of the LLM whenever possible.

### Deliverables
- `reference_resolver.py`
- seed reference files under `/reference_data`
- tests for country, city, and zip normalization

### Tasks
- Create versioned lookup interfaces
- Add resolvers for:
  - country normalization
  - city alias normalization
  - zip3/state to city + zip
  - Canada destination normalization
- Define precedence:
  1. customer-specific overrides
  2. curated internal lookup
  3. explicit planner-provided constant
  4. leave blank with warning

### Definition of done
- sample workbook enrichment cases resolve deterministically
- unresolved lookups generate structured warnings

---

## Phase 5: Create Planner Prompt Assets

### Goals
Prepare the Foundry planner interface in a way that is constrained and testable.

### Deliverables
- `/prompts/transform_planner_system.txt`
- `/prompts/transform_planner_user.txt.j2`
- prompt rendering helper
- few-shot examples if needed

### Tasks
- Write system prompt that:
  - defines the task narrowly
  - requires JSON output
  - requires explicit assumptions
  - requires a single Python `transform(context)` function
  - disallows unsafe imports
- Write user prompt template that injects:
  - workbook profile
  - canonical schema
  - reference rules
  - transformation instructions
- Add prompt snapshots in tests so changes are reviewable

### Definition of done
- prompt rendering tests pass
- prompt size stays within acceptable token limits for expected workbook profile sizes

---

## Phase 6: Implement Foundry Planner Client

### Goals
Call Foundry Agent Service and validate its response.

### Deliverables
- `foundry_agent_client.py`
- `planning_service.py`
- integration seam for mock and live modes

### Tasks
- Implement authenticated Foundry client
- Use managed identity or configured auth path
- Submit structured planner request
- Parse planner response
- Validate against Pydantic or JSON schema
- Persist raw prompt and raw response as artifacts
- Add retry policy for transient failures

### Definition of done
- mock response path works
- live test path works in development environment
- malformed planner output fails cleanly

---

## Phase 7: Implement Script Policy Enforcement

### Goals
Reject unsafe or structurally invalid code before execution.

### Deliverables
- `script_policy.py`
- AST scanners
- compile validator
- policy unit tests

### Tasks
- Parse agent-produced Python into AST
- Block:
  - banned imports
  - dynamic import
  - subprocess usage
  - socket/network use
  - filesystem writes outside allowed paths
  - eval/exec
- Require:
  - `transform(context)` function
  - imports from allowlist only
  - no top-level side effects beyond imports/constants/helpers
- Run compile check
- Return policy findings with severity

### Definition of done
- malicious sample scripts are rejected
- valid scripts pass
- rejection messages are actionable

---

## Phase 8: Implement Sandbox Executor

### Goals
Run the generated transformation safely and capture artifacts.

### Deliverables
- `sandbox_executor.py`
- local isolated execution mode
- structured execution report

### Tasks
- Create per-run temp workspace
- Stage input workbook and config
- Execute generated module in a restricted subprocess
- Inject only approved context
- enforce:
  - timeout
  - memory budget where feasible
  - output directory restriction
- capture:
  - stdout
  - stderr
  - return object
  - execution time
- write returned canonical dataframe through the controlled writer, not from arbitrary script paths when possible

### Important design choice
Prefer this pattern:
- generated script transforms data and returns dataframe
- host application writes final files

This gives the host control over final file format and limits script authority.

### Definition of done
- simple generated transform runs successfully
- failure conditions produce clear execution reports
- no writes occur outside temp folder

---

## Phase 9: Implement Deterministic Validation

### Goals
Make validation a first-class component before the optional LLM validator.

### Deliverables
- `validation_service.py`
- `validation_rules.py`
- machine-readable validation report

### Tasks
- Validate:
  - schema shape
  - exact output columns
  - required fields
  - null thresholds
  - duplicate checks
  - type coercion
  - row counts
  - reference-data consistency
- Add lineage-oriented checks:
  - source row IDs preserved where applicable
  - relevant sheet inclusion documented
- Return:
  - pass/fail
  - warnings
  - errors
  - metrics

### Definition of done
- deterministic validation catches intentional bad outputs in tests
- good output passes

---

## Phase 10: Implement Optional Validator Agent

### Goals
Provide semantic audit on top of deterministic checks.

### Deliverables
- validator prompts
- validator service
- advisory report format

### Tasks
- create:
  - `transform_validator_system.txt`
  - `transform_validator_user.txt.j2`
- send summarized evidence only, not entire workbook
- request:
  - suspicious mappings
  - omissions
  - confidence
  - manual review recommendations
- mark validator result as advisory unless configured otherwise

### Definition of done
- validator returns structured findings
- validator cannot block output unless explicitly enabled by configuration

---

## Phase 11: Function App Surface

### Goals
Wrap the services behind Azure Functions endpoints.

### Deliverables
- `function_app.py`
- function routes
- local settings template
- host.json

### Recommended endpoints
- `POST /api/runs`
  - submit workbook for processing
- `GET /api/runs/{run_id}`
  - get status
- `GET /api/runs/{run_id}/artifacts`
  - list artifacts
- `GET /api/runs/{run_id}/output`
  - fetch output
- `POST /api/runs/{run_id}/revalidate`
  - rerun validation only

### Tasks
- Use Python v2 decorator model
- Add request validation
- Add correlation IDs
- Add structured responses
- Keep orchestration logic in services, not handlers

### Definition of done
- local `func start` works
- submit/status flow works end to end on local sample

---

## Phase 12: Artifact Storage and Run State

### Goals
Make every run inspectable and resumable.

### Deliverables
- `artifact_store.py`
- run manifest format
- local and cloud storage adapter

### Tasks
- Store by `run_id`
- Persist:
  - input workbook copy
  - profile JSON
  - planner request
  - planner response
  - generated script
  - policy report
  - execution report
  - deterministic validation report
  - LLM validation report
  - final output
- Provide both:
  - local file-system adapter for dev
  - blob-backed adapter for cloud

### Definition of done
- every run produces complete artifact tree
- cloud mode persists artifacts outside ephemeral function storage

---

## Phase 13: Golden Test with Provided Example

### Goals
Use the uploaded workbook pair as the first approved regression case.

### Deliverables
- `/tests/golden/test_input8.py`
- test fixtures
- approved baseline output comparison logic

### Tasks
- Load provided input workbook
- Run planner in either:
  - mocked approved plan mode first
  - live planner mode second
- Compare produced canonical output to approved output workbook
- Define comparison rules:
  - exact columns
  - row count
  - key field equality
  - tolerant comparison for formatting-only differences

### Definition of done
- test passes with approved transformation path
- deviations produce readable diff output

---

## Phase 14: Bicep Infrastructure

### Goals
Provision all Azure resources from Bicep.

### Deliverables
```text
/infra
  main.bicep
  main.dev.bicepparam
  main.test.bicepparam
  main.prod.bicepparam
  /modules
    storage.bicep
    monitoring.bicep
    keyVault.bicep
    functionPlan.bicep
    functionApp.bicep
    roles.bicep
    containerWorker.bicep
```

### Required resources
- storage account
- blob containers
- queue storage if used
- log analytics
- application insights
- function hosting plan
- function app
- key vault
- role assignments

### Optional resources
- container app environment
- container app or job for sandbox executor

### Bicep implementation notes
- parameterize environment name
- parameterize location
- parameterize SKU and scaling settings
- surface outputs:
  - function app name
  - storage endpoints
  - key vault URI
  - managed identity principal IDs

### Definition of done
- `az deployment group create` works for dev
- outputs are usable by application config
- RBAC assignments are correct

---

## Phase 15: Configuration and Secrets

### Goals
Make local and cloud config explicit and safe.

### Deliverables
- `local.settings.template.json`
- config loader
- environment variable docs

### Configuration keys to support
- `FOUNDRY_PROJECT_ENDPOINT`
- `FOUNDRY_AGENT_NAME`
- `CANONICAL_SCHEMA_NAME`
- `ARTIFACT_STORAGE_MODE`
- `ARTIFACT_BLOB_CONTAINER`
- `EXECUTION_MODE`
- `ENABLE_LLM_VALIDATION`
- `MAX_SCRIPT_EXECUTION_SECONDS`
- `MAX_PROFILE_SAMPLE_ROWS`

### Definition of done
- local developer can run without guessing environment variables
- secrets never committed

---

## Phase 16: Observability

### Goals
Add traceability before production rollout.

### Deliverables
- logging helpers
- correlation middleware
- telemetry events
- dashboard query examples

### Tasks
- add structured logger
- log each stage start/finish
- capture durations
- emit warning/error categories
- associate all logs with `run_id`

### Definition of done
- local logs are readable
- Azure logs can trace one run end to end

---

## Phase 17: CI/CD

### Goals
Enable build, test, and deployment automation.

### Deliverables
- GitHub Actions workflows:
  - lint/test
  - package/deploy
  - infra deploy
- deployment docs

### Tasks
- run unit tests
- run golden tests
- validate Bicep
- deploy infra
- deploy function app

### Definition of done
- pipeline can deploy dev environment
- failures stop before production deployment

---

## 3. Suggested File-by-File Build Order for GHCP

1. `docs/software_spec.md`
2. `docs/implementation_plan.md`
3. `src/function_app/models/contracts.py`
4. `src/function_app/models/enums.py`
5. `src/function_app/templates/canonical_schema.freight_bid_v1.json`
6. `src/function_app/services/workbook_profiler.py`
7. `src/function_app/services/template_loader.py`
8. `src/function_app/services/output_writer.py`
9. `src/function_app/services/reference_resolver.py`
10. `src/function_app/prompts/transform_planner_system.txt`
11. `src/function_app/prompts/transform_planner_user.txt.j2`
12. `src/function_app/services/foundry_agent_client.py`
13. `src/function_app/services/planning_service.py`
14. `src/function_app/services/script_policy.py`
15. `src/function_app/services/sandbox_executor.py`
16. `src/function_app/services/validation_service.py`
17. `src/function_app/prompts/transform_validator_system.txt`
18. `src/function_app/prompts/transform_validator_user.txt.j2`
19. `src/function_app/function_app.py`
20. `infra/modules/*.bicep`
21. `infra/main.bicep`
22. tests
23. CI/CD workflow

---

## 4. GHCP Prompting Guidance

Use GitHub Copilot iteratively with bounded tasks.  
Do not ask it to generate the whole solution in one prompt.

### Example prompt sequence
1. "Create Pydantic contracts for workbook profiling and planner response."
2. "Implement workbook profiling for xlsx files with header-row detection and sample-row extraction."
3. "Create a strict AST policy checker for generated Python transform code."
4. "Implement a sandbox executor that runs `transform(context)` from generated code in a restricted subprocess."
5. "Create Bicep modules for storage, monitoring, function app, key vault, and RBAC."

### Copilot guardrails
Always instruct GHCP to:
- preserve existing contracts
- write tests with each service
- avoid hidden magic
- keep methods small
- use explicit exceptions
- produce structured logs
- avoid unsafe execution shortcuts

---

## 5. Key Engineering Decisions to Lock Early

These should be finalized before significant coding continues:

### A. Execution mode
Choose one:
- local subprocess in Function App for v1
- separate container worker from day one

Recommended:
- design abstraction for both
- implement local subprocess first
- keep swap seam ready

### B. Persistence model
Choose whether cloud runs persist artifacts only to blob or also metadata to table/db.

Recommended:
- blob first
- manifest json per run
- optional table later

### C. Validation gate
Choose:
- deterministic validation is blocking
- LLM validation is advisory

Recommended:
- deterministic blocking
- LLM advisory

### D. Template versioning
Choose whether template is file-based or DB-based.

Recommended:
- file-based JSON in repo for v1

---

## 6. Testing Matrix

### Unit
- contracts
- workbook profiler
- classifier
- reference resolver
- policy checker
- validator

### Integration
- mocked planner
- live planner
- sandbox execution
- xlsx writer
- artifact persistence

### Golden
- provided input -> approved output

### Negative
- malformed workbook
- planner malformed JSON
- banned import in script
- timeout
- unresolved reference mapping
- duplicate output key rows

---

## 7. Manual Review Checklist Before Production

- [ ] Planner output schema is validated
- [ ] Generated script is persisted and reviewable
- [ ] Unsafe imports are blocked
- [ ] Timeouts are enforced
- [ ] Final output column order is exact
- [ ] Golden sample passes
- [ ] Non-data tabs are excluded correctly in sample
- [ ] Validation report is human-readable
- [ ] Bicep deploys from clean subscription/resource group
- [ ] Managed identity auth works
- [ ] Application Insights captures run IDs
- [ ] Local developer workflow is documented

---

## 8. Definition of Overall Done

The project is done for v1 when:

1. Local developer can run the workflow in VS Code on the provided workbook.
2. The system profiles the workbook and generates a valid planner request.
3. Foundry returns a structured mapping plan and Python transform script.
4. The script passes static safety checks.
5. The system executes the script and produces canonical `.xlsx` and optional `.csv`.
6. Deterministic validation passes.
7. Optional LLM validation produces an advisory report.
8. Artifacts are persisted by run ID.
9. Bicep deploys a working Azure environment.
10. Automated tests cover the golden sample and core failure paths.

---

## 9. Recommended Immediate Next Coding Step

Start with this exact slice:

1. contracts
2. workbook profiler
3. canonical schema file
4. deterministic canonical writer
5. golden test harness using the provided sample workbook

That gives a solid base before the LLM and sandbox layers are added.
