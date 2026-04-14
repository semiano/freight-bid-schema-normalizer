# Streamlit Companion App UI/UX Plan

## Objective
Create a companion Streamlit app for testing and visualization of RXO normalization runs that supports:
1. Selecting and inspecting prior runs.
2. Launching new runs from `examples/inputs/*.xlsx`.
3. Visualizing final outputs, planner payload, validation report, and execution logs.

The app is intentionally scoped as an operations/testing cockpit (not an end-user portal).

---

## Primary Users
- Developer/QA engineer validating pipeline behavior.
- Prompt engineer reviewing planner output and generated transform script.
- Data quality reviewer checking validation outcomes and row-level shape.

---

## Information Architecture

### Global Layout
- **Sidebar**: run mode controls, run picker, execution controls.
- **Main area**: selected run details split into tabs.

### Main Navigation Modes (Sidebar)
1. **Browse Prior Runs**
   - List discovered run artifacts across known local directories.
   - Select one run and inspect details.
2. **Create New Run**
   - Choose an input workbook from `examples/inputs`.
   - Choose `run_mode` and `planner_mode`.
   - Execute run and auto-focus to latest run.

---

## Run Discovery Model

### Discovery Sources
- `artifacts/function_runs/**/pipeline_*` (blob-trigger persisted runs)
- `artifacts/live_pipeline/pipeline_*`
- `artifacts/local_pipeline/pipeline_*`
- `artifacts/local_real_run/pipeline_*`
- `artifacts/streamlit_runs/pipeline_*` (new app-generated runs)

### Run Metadata for List View
Each run card/row exposes:
- Run directory path
- Last modified timestamp
- Status from `execution_result.json` if available
- Validation status + counts from `validation_report.json`
- Output row count from validation metrics or CSV row count fallback

### Sort Behavior
- Default descending by last modified (most recent first).

---

## Detailed View UX

### Header Summary
- Run path
- Planner mode
- Validation status badge
- Metrics: rows, errors, warnings, duration (if available)

### Tabs
1. **Final Results**
   - Preview canonical output table from `canonical_output.csv`.
   - CSV download button.
   - Optional XLSX path display.
2. **Planner Output**
   - Structured summary (`relevant_sheets`, `ignored_sheets`, assumptions).
   - Mapping/constant/enrichment JSON sections.
   - `python_script` rendered with syntax highlighting.
3. **Validation**
   - High-level status and issue counts.
   - Issues table with severity/code/message.
   - Metrics panel (`row_count`, `column_count`, null-rate map).
4. **Execution Logs**
   - Sandbox execution report (`status`, `duration_ms`, `return_code`, timed out).
   - stdout/stderr text blocks.
   - Raw `execution_result.json` preview.

---

## New Run Flow UX

### Inputs
- Example workbook selector (`examples/inputs/*.xlsx`)
- `run_mode`: `draft` | `execute_with_validation`
- `planner_mode`: `mock` | `live`
- Output root for Streamlit-triggered runs: `artifacts/streamlit_runs`

### Trigger
- `Run Pipeline` button.

### Feedback
- Spinner while executing.
- Success/failure toast/banner.
- On success, auto-select created run in detailed view.
- On failure, display exception details and keep app responsive.

---

## Error Handling and Resilience
- Missing artifact files should render warnings, not crash UI.
- Corrupt JSON should render parse error with raw content fallback.
- Empty CSV should render empty-state message.
- Live planner failures should show traceback/error from execution artifacts if present.

---

## Performance Guidelines
- Load heavy files lazily per tab.
- Avoid reading entire huge JSON sections unless requested.
- Cache run index in session state and provide manual refresh button.

---

## Visual Design Principles
- Keep default Streamlit theme and components.
- Focus on scanability: compact metrics, short labels, consistent naming.
- No extra pages/modals beyond required two-mode workflow.

---

## Implementation Plan
1. Build run discovery helpers and metadata extraction.
2. Implement sidebar mode switch + run selector.
3. Implement `Create New Run` execution path via existing `run_pipeline`.
4. Implement detail tabs for output/planner/validation/logs.
5. Add dependency/docs updates (`streamlit`, `pandas`, README run command).
6. Validate app imports and basic execution health.
