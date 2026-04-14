# AI-Driven Excel Schema Standardization Platform
Version: 0.1  
Target runtime: Azure Functions (Python) + Microsoft Foundry Agent Service  
Authoring target: GitHub Copilot in VS Code  
Infrastructure as Code: Bicep only

---

## 1. Purpose

Build a Python-based Azure Functions solution that accepts Excel workbooks with inconsistent input schemas, potentially containing multiple tabs, and converts them into a fixed standard output workbook or CSV format.

The system must **not** rely on direct one-shot generative extraction into rows.  
Instead, the system uses an AI agent to:

1. Inspect the **fixed output template schema**
2. Inspect the **input workbook structure**
3. Inspect each candidate input tab's schema plus a small row sample
4. Generate a deterministic **Python transformation script**
5. Execute that script in a controlled sandbox
6. Validate the transformed output with rule-based checks and an optional second LLM validation pass

This design keeps the final transform deterministic, replayable, inspectable, testable, and auditable.

---

## 2. Problem Statement

Input Excel files vary by:
- Sheet names
- Column names
- Header row position
- Presence of non-data tabs
- Presence of merged headers, intro text, or instructions
- Zip, city, state, and country representations
- Optional multiple data tabs representing different business cases
- Different row inclusion rules
- Different semantics for fields with similar names

Output format is fixed and must always conform to one canonical schema.

The system therefore needs a two-step intelligence pattern:
- **Reasoning step**: understand how the current workbook maps to the canonical schema
- **Execution step**: run code that applies the mapping consistently to all rows

---

## 3. Example Observations from Provided Files

### Input workbook characteristics observed
Workbook contains these tabs:
- `SINGLE FTL LIVE LOAD TRAILERS`
- `Canada lane`
- `MULTI STOP FTL LIVE LOAD TRAILE`
- `MULTI STOP FTL DROP TRAILER`
- `INBOUND`
- `REQUIREMENTS`
- `FSC`
- `LOCATIONS`

Observed data-bearing tabs:
- `SINGLE FTL LIVE LOAD TRAILERS`
- `Canada lane`
- `MULTI STOP FTL LIVE LOAD TRAILE`
- `MULTI STOP FTL DROP TRAILER`
- `INBOUND`

Observed non-transform tabs:
- `REQUIREMENTS`
- `FSC`
- `LOCATIONS`

### Output workbook characteristics observed
Output contains one standardized sheet with 40 columns:

1. Customer Lane ID
2. FO Code
3. Origin City
4. Origin State
5. Origin Zip
6. Origin Country
7. Origin Note
8. Destination City
9. Destination State
10. Destination Zip
11. Destination Country
12. Destination Note
13. Equipment Category
14. Equipment Type Detail
15. Customer Miles
16. Annual Volume
17. Incumbent Rate
18. Target Rate
19. Additional Fee
20. Target
21. Rate Type
22. Drop Trailer (Origin)
23. Drop Trailer (Destination)
24. Permit
25. HRHV
26. Hazmat
27. Team
28. Round Trip
29. Multi Stop
30. Other
31. Fuel Surcharge
32. FSC Type
33. Bid Note
34. MX Cost
35. Border Crossing Fee
36. Transload Fee
37. Border Crossing City
38. Border Crossing State
39. Border Crossing Country
40. Strategic Quantile

### Sample behavioral inferences from the example
These are important because the software must support this class of logic:

- Non-data tabs must be ignored
- Some tabs map into the final output, some must be excluded
- In the sample, `MULTI STOP FTL DROP TRAILER` appears excluded from the output
- `Origin Country` is normalized from `US` to `USA`
- Canada output uses `CAN`
- Destination and origin 3-digit zip prefixes are expanded to city + 5-digit postal/zip values
- Some city values are normalized, for example `ALEXANDRIA / TYRONE` -> `ALEXANDRIA`
- Some fields are fixed constants in the standardized output, for example:
  - `FO Code` = `RXOCode`
  - `Equipment Category` = `V`
  - `Rate Type` = `5T3`
  - `Fuel Surcharge` = `0.78`
  - `FSC Type` = `PerMileAmount`
- `Annual Volume` appears to be sourced from:
  - `SHIPMENT COUNT`
  - `LOADS PER YEAR`
  - `VOLUME`
- For this example, several output columns are intentionally left blank when the source workbook does not provide them

These observations strongly suggest that the system needs:
- sheet classification
- semantic column mapping
- field-level transformation logic
- reference-data enrichment
- explicit inclusion/exclusion decisions
- deterministic post-validation

---

## 4. Goals

### Functional goals
- Accept `.xlsx` input
- Read all tabs and profile them
- Identify data-bearing sheets
- Infer how each relevant input tab maps to the fixed target schema
- Generate Python transformation code dynamically
- Execute the code to produce canonical output
- Emit `.xlsx` and optionally `.csv`
- Produce a machine-readable validation report
- Preserve a full audit trail of:
  - input schema summary
  - mapping plan
  - generated script
  - execution logs
  - validation results

### Non-functional goals
- Deterministic execution after generation
- Human-inspectable transformation script
- Secure execution boundary for generated code
- Support local development in VS Code
- Deployable to Azure with Bicep
- Observable end to end
- Retryable and resumable
- Extensible to new workbook patterns without code rewrites for each customer format

### Out of scope for v1
- Arbitrary macro-enabled workbooks
- OCR-based interpretation of scanned files
- Full fidelity preservation of workbook formatting
- Fully autonomous execution of unsafe generated code without review gates
- Supporting every exotic Excel feature on day one

---

## 5. High-Level Architecture

```text
Client / Caller
    |
    v
Azure Function HTTP Trigger or Blob Trigger
    |
    v
Workbook Intake + Sheet Profiler
    |
    v
Transformation Planning Service
    |      \
    |       -> Reference Data Resolver
    v
Foundry Agent Service
    |
    v
Generated Python Transform Script
    |
    v
Sandboxed Script Executor
    |
    v
Canonical Output Writer (.xlsx/.csv)
    |
    +--> Rule-Based Validator
    |
    +--> Optional LLM Validation Agent
    |
    v
Validation Report + Artifacts + Status
```

---

## 6. Recommended Runtime Topology

### Preferred topology
Use **Azure Functions as the orchestration surface** and **separate script execution from reasoning**.

Recommended components:
- Azure Function App (Python)
- Azure Storage Account
- Azure Queue Storage or Durable Functions orchestration
- Azure AI Foundry Agent Service
- Application Insights
- Key Vault
- Optional Azure Container Apps job or isolated worker for code execution
- Optional Blob container for durable artifact retention

### Why this topology
The generated Python script is code, not just content.  
That means the system must treat it as untrusted until validated.

Therefore:
- Function App should orchestrate
- Generated transform script should execute in an isolated sandbox
- Validation should run after script execution
- Durable state should exist outside local temp storage

---

## 7. Core Processing Flow

### 7.1 Intake
Function receives:
- uploaded workbook path or blob URL
- template schema identifier
- optional output type: `xlsx`, `csv`, or both
- optional run mode:
  - `draft`
  - `execute`
  - `execute_with_validation`

### 7.2 Workbook profiling
System loads workbook and creates a compact metadata package:
- sheet names
- visible/hidden
- used range per sheet
- header row candidates
- inferred data types per column
- sample rows, usually first 10 data rows
- duplicate headers
- empty-column ratios
- likely business meaning of sheet
- workbook-level notes on reference tabs

### 7.3 Template schema loading
System loads the canonical output definition:
- ordered columns
- data types
- required fields
- normalization rules
- default constants
- allowed enumerations
- derived-field formulas or business rules
- output writer configuration

### 7.4 Agent planning
Function sends the following to Foundry agent:
- canonical schema
- workbook profile
- sample rows per candidate sheet
- transformation constraints
- allowed Python libraries
- required output contract
- required security restrictions
- required structured JSON response

The agent returns:
- relevant sheet list
- ignored sheet list
- per-sheet mapping plan
- identified constants
- identified enrichments
- assumptions
- confidence scores
- Python transformation script
- tests or assertions for the script

### 7.5 Pre-execution guardrails
Before execution, system performs:
- JSON schema validation of the agent response
- static validation of generated Python source
- restricted import allowlist checks
- banned operation detection
- optional AST-based policy checks
- compilation check
- optional dry-run on small row subset

### 7.6 Script execution
Script runs in sandbox with:
- read-only access to staged input workbook
- read-only access to template definition
- write access only to temp output folder
- no internet egress
- time limit
- memory limit
- CPU limit
- structured stdout/stderr capture

### 7.7 Output writing
Script produces:
- canonical dataframe
- canonical workbook
- optional csv
- transform metadata json
- row lineage metadata

### 7.8 Validation
Validation runs in two layers:

#### Layer 1: deterministic validation
- target column set exactly matches template
- required columns populated where possible
- type validation
- null-rate thresholds
- row count expectations
- duplicate lane ID checks
- enum validation
- cross-field logic
- source-to-output lineage checks
- reference-data resolution checks

#### Layer 2: optional LLM validation
A second agent compares:
- sheet profiles
- mapping plan
- generated script summary
- sample source rows
- sample output rows
- validation metrics

The validator agent returns:
- whether output appears semantically faithful
- suspicious transformations
- dropped columns that seem important
- probable row omissions
- probable mis-mappings
- confidence score
- narrative findings

### 7.9 Final persistence
Persist:
- generated script
- run manifest
- validation report
- output workbook/csv
- prompt and response artifacts
- execution logs
- status event

---

## 8. Architectural Decision: Orchestrator vs Direct Function

### Direct single HTTP function
Use only for:
- small files
- fast proof of concept
- low concurrency
- internal manual testing

### Durable orchestration or queue-driven fan-in
Recommended for production because:
- workbook parsing + agent call + sandbox execution + validation can exceed normal HTTP comfort windows
- retries should happen per stage
- artifacts should survive transient errors
- long-running status tracking is easier

### Recommendation
For v1:
- start with one HTTP-trigger orchestration endpoint plus internal service classes
- keep stage boundaries explicit
- be ready to move to Durable Functions without rewriting core logic

---

## 9. Security Model

This is the most important non-functional part of the design.

### 9.1 Treat generated code as untrusted
The LLM-generated transformation script must never be treated as trusted application code.

### 9.2 Execution restrictions
Minimum restrictions:
- allowlist imports only
- block `os.system`, `subprocess`, `socket`, `requests`, `urllib`, dynamic import, file deletion, process spawning
- block writes outside temp workspace
- block environment variable enumeration except specific injected values
- block network egress
- block package installation
- block shell access

### 9.3 Sandboxing options
#### Good
Subprocess in the same Function App instance with AST policy and strict runtime checks

#### Better
Isolated worker container invoked by Function App

#### Best
Ephemeral sandbox container or job per execution with hardened runtime

### Recommendation
Use an isolated execution worker even if the first release keeps it simple.  
Design the interface so execution can be swapped from local subprocess to remote sandbox without changing orchestration.

### 9.4 Secrets
- Use managed identity wherever possible
- Store connection secrets in Key Vault
- Do not place Foundry keys or storage keys in source control
- Prefer Entra + RBAC over shared secrets

---

## 10. Data Contracts

## 10.1 Workbook profile contract
Example JSON shape:

```json
{
  "workbook_name": "Input 8.xlsx",
  "sheets": [
    {
      "sheet_name": "SINGLE FTL LIVE LOAD TRAILERS",
      "is_hidden": false,
      "used_range": "A1:K202",
      "header_row_index": 1,
      "candidate_data_sheet": true,
      "columns": [
        {"name": "ID", "dtype_hint": "int"},
        {"name": "ORIGIN_CITY", "dtype_hint": "string"},
        {"name": "ORIGIN_STATE", "dtype_hint": "string"}
      ],
      "sample_rows": [
        {"ID": 1, "ORIGIN_CITY": "ALEXANDRIA", "ORIGIN_STATE": "PA"}
      ]
    }
  ]
}
```

## 10.2 Canonical schema contract
```json
{
  "schema_name": "freight_bid_v1",
  "columns": [
    {"name": "Customer Lane ID", "required": true, "dtype": "int"},
    {"name": "FO Code", "required": false, "dtype": "string", "default": "RXOCode"}
  ]
}
```

## 10.3 Agent response contract
The agent should return **structured JSON**, not prose-first output.

```json
{
  "relevant_sheets": [],
  "ignored_sheets": [],
  "sheet_mapping_plan": [],
  "constants": {},
  "reference_data_requirements": [],
  "assumptions": [],
  "confidence": 0.0,
  "python_script": "..."
}
```

## 10.4 Execution result contract
```json
{
  "status": "Succeeded",
  "row_count": 394,
  "output_paths": {
    "xlsx": "...",
    "csv": "..."
  },
  "warnings": [],
  "validation_summary": {}
}
```

---

## 11. Reference Data Strategy

The sample strongly suggests a need for enrichment tables, especially:
- state + zip3 -> representative city + postal code
- country normalization
- city normalization alias tables
- sheet-type-specific defaults

### Recommendation
Do not force the LLM to invent reference mappings inline.

Instead support a **Reference Resolver** with:
- internal lookup tables packaged with the app
- optional customer-specific reference datasets
- versioned lookup dictionaries
- deterministic resolution precedence

### Reference resolver responsibilities
- expand zip3 + state to canonical destination city and zip
- map `US` -> `USA`
- map `ON Canada` -> `ON` + `CAN`
- normalize city aliases
- apply business-approved constants

The agent may request reference lookups, but the app should execute them deterministically.

---

## 12. Transformation Script Contract

The generated script must conform to a strict interface.

### Required entry point
```python
def transform(context: dict) -> dict:
    ...
```

### Context includes
- `input_workbook_path`
- `output_dir`
- `template_schema`
- `reference_data`
- `run_id`
- `settings`

### Return contract
```python
{
  "dataframe": canonical_df,
  "artifacts": {
    "notes": [],
    "sheet_stats": {}
  }
}
```

### Script rules
- Use Python only
- Allowed libraries only
- Must not write final files outside the supplied output directory
- Must not access network
- Must not depend on external packages not already bundled in the worker
- Must preserve row lineage when feasible
- Must raise structured exceptions

---

## 13. Recommended Python Library Set

Allow:
- `pandas`
- `openpyxl`
- `re`
- `json`
- `math`
- `typing`
- `dataclasses`
- `collections`
- `datetime`

Disallow in generated scripts:
- `requests`
- `subprocess`
- `socket`
- `pathlib.Path.home()` patterns for unrestricted access
- `os.system`
- `eval`
- `exec`
- `importlib`
- package installers

---

## 14. Validation Design

## 14.1 Deterministic validation checks

### Schema checks
- exact output column order
- no unexpected columns
- data types coercible to target schema
- required fields present

### Content checks
- source lane ID uniqueness preserved when expected
- included sheet row counts roughly align to output row counts
- excluded sheets explicitly documented
- constants applied consistently
- output null percentages within thresholds
- if origin/destination country is Canada, zip/postal format is consistent
- no impossible country/state combinations
- no blank rows in final output
- no duplicate canonical rows unless explicitly allowed

### Cross-source logic checks
- sample source rows can be traced to output rows
- if a source sheet contains rate columns but output rate fields are blank by design, that choice is documented
- if a source tab is excluded, the reason is documented

## 14.2 LLM validation design

Use a second Foundry agent with a narrower task:
- it does not generate transform code
- it only audits the proposed transform result

### Validator input
- workbook profile summary
- canonical schema
- transformation plan
- generated script summary
- deterministic validation summary
- row count summary
- source/output samples

### Validator output
- pass / review / fail
- confidence
- suspicious fields
- suspected dropped business meaning
- suspected row omissions
- natural-language rationale
- recommended manual review areas

### Important constraint
LLM validation should be advisory, not the sole release gate.

---

## 15. Failure Modes and Recovery

### Likely failure modes
- wrong header row inferred
- wrong sheet inclusion or exclusion
- zip3 expansion ambiguity
- Canada postal normalization mismatch
- script compilation error
- runtime transform error
- row explosion from bad joins
- row loss from over-filtering
- partial output written before failure
- validator disagreement

### Recovery design
- stage outputs by run ID
- keep every intermediate artifact
- fail with actionable status codes
- allow rerun from:
  - profile step
  - plan step
  - execute step
  - validate step
- preserve generated script for manual debugging

---

## 16. Observability

Use structured logging throughout.

### Required log dimensions
- run_id
- workbook_name
- sheet_name
- stage
- agent_request_id
- execution_worker_id
- validation_status
- row_count_in
- row_count_out
- duration_ms

### Recommended telemetry events
- `WorkbookProfileStarted`
- `WorkbookProfileCompleted`
- `TransformationPlanRequested`
- `TransformationPlanReceived`
- `ScriptStaticValidationPassed`
- `ScriptExecutionStarted`
- `ScriptExecutionCompleted`
- `DeterministicValidationCompleted`
- `LLMValidationCompleted`
- `RunCompleted`
- `RunFailed`

### Metrics
- success rate
- median end-to-end duration
- average agent generation latency
- execution error rate
- validation warning rate
- percent of runs needing manual review

---

## 17. Deployment Architecture

## 17.1 Azure resources
Minimum production set:
- Resource Group
- Storage Account
- Function App
- Function App Hosting Plan
- Application Insights
- Log Analytics Workspace
- Key Vault
- Microsoft Foundry project / agent endpoint resources
- Managed Identity assignments

Optional:
- Azure Queue Storage
- Durable Functions storage dependencies
- Container Apps environment for sandbox executor
- Blob containers for artifacts

## 17.2 Identity model
- Function App uses system-assigned managed identity
- Execution worker uses its own managed identity if separate
- Access to:
  - Storage
  - Key Vault
  - Foundry runtime / project APIs
- RBAC only, no embedded secrets when possible

---

## 18. Bicep Expectations

The GHCP implementation should produce Bicep files for:
- base resource group deployment
- storage account and containers
- function app plan + app
- application insights + log analytics
- key vault
- RBAC role assignments
- optional queue resources
- optional container app execution worker
- environment-specific parameters

### Suggested Bicep file layout
```text
/infra
  main.bicep
  main.dev.bicepparam
  main.test.bicepparam
  main.prod.bicepparam
  /modules
    storage.bicep
    functionApp.bicep
    monitoring.bicep
    keyVault.bicep
    roles.bicep
    containerWorker.bicep
```

---

## 19. Repository Structure Recommendation

```text
/src
  /function_app
    function_app.py
    host.json
    local.settings.template.json
    requirements.txt
    /functions
      http_submit.py
      status_get.py
    /services
      workbook_profiler.py
      sheet_classifier.py
      template_loader.py
      planning_service.py
      foundry_agent_client.py
      script_policy.py
      sandbox_executor.py
      validation_service.py
      output_writer.py
      reference_resolver.py
      artifact_store.py
    /models
      contracts.py
      enums.py
    /prompts
      transform_planner_system.txt
      transform_planner_user.txt.j2
      transform_validator_system.txt
      transform_validator_user.txt.j2
    /templates
      canonical_schema.freight_bid_v1.json
      output_template.xlsx
    /reference_data
      state_zip3_lookup.csv
      city_aliases.json
      country_codes.json
    /tests
      /unit
      /integration
      /golden
/infra
/docs
  software_spec.md
  implementation_plan.md
```

---

## 20. Prompting Strategy for the Planner Agent

The planner agent should be constrained to:
- identify relevant sheets
- identify mapping logic
- generate only the transformation logic
- avoid commentary-heavy output
- return structured JSON only
- include assumptions explicitly
- include confidence per mapped field
- avoid inventing fields not derivable from source, defaults, or reference data

### Planner prompt must include
- output schema
- business rules
- examples of allowed transformations
- examples of fields that may remain blank
- allowed libraries
- exact function signature to emit
- prohibition on network access and unsafe APIs

---

## 21. Prompting Strategy for the Validator Agent

The validator agent prompt should focus on:
- semantic fidelity
- dropped information
- suspicious constants
- row count mismatches
- likely sheet inclusion mistakes
- confidence scoring

It should explicitly avoid rewriting the transform script.

---

## 22. Testing Strategy

## 22.1 Unit tests
- workbook profiling
- header row detection
- reference resolver
- AST security policy
- schema validation
- output writer

## 22.2 Golden-file tests
Given example input workbook, output should match approved canonical output exactly or within declared tolerances.

## 22.3 Integration tests
- full run with Foundry mocked
- full run with real Foundry in test subscription
- execution worker timeout behavior
- failed script compile behavior
- bad workbook behavior

## 22.4 Adversarial tests
- malicious code returned by agent
- workbook with fake headers
- workbook with merged cells above header
- workbook with two valid-looking data tabs and one decoy
- workbook with extreme nulls
- workbook with duplicate columns

---

## 23. Versioning Strategy

Version separately:
- canonical template schema
- prompt templates
- reference data
- script policy rules
- validator rules

Each run artifact should record all version identifiers so outputs are reproducible.

---

## 24. Recommended v1 Delivery Scope

### v1 should include
- one canonical target schema
- Excel input support
- workbook profiling
- planner agent call
- script generation
- script static validation
- sandbox execution
- xlsx and csv output
- deterministic validation
- optional validator agent
- Bicep deployment
- local run path in VS Code
- golden-file test using the provided example

### v1 should not include
- arbitrary user-authored execution plugins
- full multi-tenant control plane
- UI portal
- document OCR
- unsupported file types

---

## 25. Key Design Principles

1. **Reason with AI, execute deterministically**
2. **Treat generated code as untrusted**
3. **Separate planning from execution**
4. **Prefer reference-data resolution over model hallucination**
5. **Keep all artifacts for auditability**
6. **Make every run replayable**
7. **Use validation as a first-class subsystem**
8. **Design local and cloud paths to behave the same**
9. **Constrain the LLM output contract aggressively**
10. **Optimize for maintainability, not magic**

---

## 26. Acceptance Criteria

The system is acceptable when:
- it can ingest the provided example workbook
- it can generate a transformation plan
- it can generate a Python transform script conforming to the app contract
- the generated script passes policy checks
- execution produces a standardized workbook in the target schema
- deterministic validation passes
- optional validator agent returns acceptable confidence
- artifacts are persisted for debugging
- local execution works in VS Code
- cloud deployment works from Bicep
- GHCP can use this spec to scaffold the implementation

---

## 27. Open Questions for Implementation

These should be resolved during implementation planning:
- Should execution remain in-process for v1 or move immediately to isolated container execution?
- What is the exact approved zip3-to-city/zip5 reference source?
- Which output fields are mandatory vs allowed blank in the canonical template?
- Should the validator agent be blocking or advisory?
- Do we need a human approval gate before executing first-time mappings from a new customer format?
- Should row lineage be persisted per output row in v1?
- Should outputs stay only in local temp cache or also be copied to blob for audit retention?

---

## 28. References

- Azure Functions Python v2 model and local development
- Azure Functions Bicep deployment patterns
- Microsoft Foundry Agent Service
- Foundry tools and auth guidance

These references should be pinned in the implementation repository README and used for final code generation.
