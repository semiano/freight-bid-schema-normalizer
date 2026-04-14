from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from azure.storage.blob import BlobServiceClient

from src.function_app.services.foundry_agent_client import FoundryAgentClient
from src.function_app.services.pipeline_runner import run_pipeline

WORKSPACE_ROOT = Path(__file__).resolve().parent
EXAMPLE_INPUTS_DIR = WORKSPACE_ROOT / "examples" / "inputs"
STREAMLIT_OUTPUT_ROOT = WORKSPACE_ROOT / "artifacts" / "streamlit_runs"
LOCAL_SETTINGS_PATH = WORKSPACE_ROOT / "local.settings.json"
AZURITE_COMPAT_API_VERSION = "2021-12-02"

DISCOVERY_ROOTS = [
    WORKSPACE_ROOT / "artifacts" / "function_runs",
    WORKSPACE_ROOT / "artifacts" / "live_pipeline",
    WORKSPACE_ROOT / "artifacts" / "local_pipeline",
    WORKSPACE_ROOT / "artifacts" / "local_real_run",
    STREAMLIT_OUTPUT_ROOT,
]


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_local_settings_env() -> None:
    payload = _read_json(LOCAL_SETTINGS_PATH)
    if not payload:
        return

    values = payload.get("Values", {})
    if not isinstance(values, dict):
        return

    for key, value in values.items():
        if isinstance(value, str) and key not in os.environ:
            os.environ[key] = value


def _validate_live_mode_configuration() -> list[str]:
    missing: list[str] = []
    required = ["FOUNDRY_PROJECT_ENDPOINT"]
    for key in required:
        if not os.getenv(key, "").strip():
            missing.append(key)
    return missing


def _validate_blob_trigger_configuration() -> list[str]:
    missing: list[str] = []
    required = ["AzureWebJobsStorage", "INPUT_CONTAINER", "OUTPUT_CONTAINER"]
    for key in required:
        if not os.getenv(key, "").strip():
            missing.append(key)
    return missing


def _create_blob_service_client(connection_string: str) -> BlobServiceClient:
    is_local_emulator = "UseDevelopmentStorage=true" in connection_string or "127.0.0.1" in connection_string
    if is_local_emulator:
        api_version = os.getenv("AZURE_BLOB_API_VERSION", AZURITE_COMPAT_API_VERSION).strip()
        if api_version:
            return BlobServiceClient.from_connection_string(connection_string, api_version=api_version)
    return BlobServiceClient.from_connection_string(connection_string)


def _submit_blob_trigger_run(input_workbook: Path) -> str:
    connection_string = os.getenv("AzureWebJobsStorage", "")
    input_container = os.getenv("INPUT_CONTAINER", "input")

    blob_service = _create_blob_service_client(connection_string)
    container_client = blob_service.get_container_client(input_container)
    try:
        container_client.create_container()
    except Exception:
        pass

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    blob_name = f"{input_workbook.stem}-streamlit-{timestamp}{input_workbook.suffix}"
    container_client.upload_blob(blob_name, input_workbook.read_bytes(), overwrite=True)
    return blob_name


def _wait_for_blob_outputs(blob_name: str, timeout_seconds: int = 90) -> dict[str, bool]:
    connection_string = os.getenv("AzureWebJobsStorage", "")
    output_container = os.getenv("OUTPUT_CONTAINER", "output")

    expected_blobs = {
        f"{blob_name}.canonical.csv": False,
        f"{blob_name}.validation.json": False,
        f"{blob_name}.planner.json": False,
    }

    blob_service = _create_blob_service_client(connection_string)
    container_client = blob_service.get_container_client(output_container)

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        all_ready = True
        for expected_blob in list(expected_blobs.keys()):
            blob_client = container_client.get_blob_client(expected_blob)
            if expected_blobs[expected_blob]:
                continue
            if blob_client.exists():
                expected_blobs[expected_blob] = True
            else:
                all_ready = False

        if all_ready:
            break

        time.sleep(2)

    return expected_blobs


@st.cache_data(show_spinner=False)
def _fetch_foundry_agents_snapshot(
    endpoint: str,
    api_version: str,
    agent_name: str,
    assistant_id: str,
) -> dict[str, Any]:
    if not endpoint.strip():
        return {"agents": [], "error": "FOUNDRY_PROJECT_ENDPOINT is not configured."}

    client = FoundryAgentClient(
        endpoint=endpoint,
        agent_name=agent_name,
        mode="live",
    )
    client.assistant_id = assistant_id

    try:
        payload = client._get_json(f"{endpoint.rstrip('/')}/assistants?api-version={api_version}")
    except Exception as error:
        return {"agents": [], "error": str(error)}

    agents: list[dict[str, Any]] = []
    data = payload.get("data", []) if isinstance(payload, dict) else []
    for item in data:
        if not isinstance(item, dict):
            continue
        agents.append(
            {
                "assistant_id": item.get("id") or "",
                "agent_name": item.get("name") or item.get("id") or "Unknown",
                "endpoint": endpoint,
                "system_prompt": item.get("instructions") or "",
            }
        )

    selected_assistant_id = ""
    selected_agent_name = ""

    configured_assistant_id = assistant_id.strip()
    configured_agent_name = agent_name.strip()

    if configured_assistant_id:
        by_id = next((agent for agent in agents if agent.get("assistant_id") == configured_assistant_id), None)
        if by_id is not None:
            selected_assistant_id = str(by_id.get("assistant_id") or "")
            selected_agent_name = str(by_id.get("agent_name") or "")

    if not selected_assistant_id and configured_agent_name:
        by_name = [agent for agent in agents if str(agent.get("agent_name") or "") == configured_agent_name]
        if by_name:
            selected_assistant_id = str(by_name[0].get("assistant_id") or "")
            selected_agent_name = str(by_name[0].get("agent_name") or "")

    for agent in agents:
        agent["is_selected"] = bool(
            selected_assistant_id and str(agent.get("assistant_id") or "") == selected_assistant_id
        )

    return {
        "agents": agents,
        "error": None,
        "selected_assistant_id": selected_assistant_id,
        "selected_agent_name": selected_agent_name,
        "configured_assistant_id": configured_assistant_id,
        "configured_agent_name": configured_agent_name,
    }


def _render_foundry_agents_page(snapshot: dict[str, Any]) -> None:
    st.subheader("Foundry Agents")
    error = snapshot.get("error")
    if isinstance(error, str) and error.strip():
        st.error(f"Unable to fetch agents: {error}")
        return

    agents = snapshot.get("agents", [])
    if not isinstance(agents, list) or not agents:
        st.info("No Foundry agents were returned by the configured endpoint.")
        return

    configured_assistant_id = str(snapshot.get("configured_assistant_id", "") or "")
    configured_agent_name = str(snapshot.get("configured_agent_name", "") or "")
    selected_assistant_id = str(snapshot.get("selected_assistant_id", "") or "")
    selected_agent_name = str(snapshot.get("selected_agent_name", "") or "")

    st.markdown("**Configured Selection (from env)**")
    st.write(
        {
            "FOUNDRY_ASSISTANT_ID": configured_assistant_id or "(not set)",
            "FOUNDRY_AGENT_NAME": configured_agent_name or "(not set)",
        }
    )

    if selected_assistant_id:
        st.success(
            f"Using assistant ID {selected_assistant_id}"
            + (f" ({selected_agent_name})" if selected_agent_name else "")
            + "."
        )
    else:
        st.warning("No unique configured assistant could be resolved from current env values.")

    duplicates_by_name: dict[str, int] = {}
    for agent in agents:
        name = str(agent.get("agent_name", "Unknown"))
        duplicates_by_name[name] = duplicates_by_name.get(name, 0) + 1

    duplicate_names = [name for name, count in duplicates_by_name.items() if count > 1]
    if duplicate_names:
        st.info("Duplicate assistant names detected: " + ", ".join(sorted(duplicate_names)))

    for agent in agents:
        name = str(agent.get("agent_name", "Unknown"))
        assistant_id = str(agent.get("assistant_id", ""))
        endpoint = str(agent.get("endpoint", ""))
        system_prompt = str(agent.get("system_prompt", ""))
        is_selected = bool(agent.get("is_selected", False))

        label = f"{name} [{assistant_id}]" if assistant_id else name
        if is_selected:
            label = f"✅ {label}"

        with st.expander(label, expanded=is_selected):
            st.write(f"Assistant ID: {assistant_id or '(missing)'}")
            st.write(f"Endpoint: {endpoint}")
            st.markdown("**System Prompt**")
            st.code(system_prompt or "(empty)", language="text")


def _discover_pipeline_dirs() -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()

    for root in DISCOVERY_ROOTS:
        if not root.exists() or not root.is_dir():
            continue

        if root.name == "function_runs":
            for blob_run_dir in root.iterdir():
                if not blob_run_dir.is_dir():
                    continue
                for pipeline_dir in blob_run_dir.glob("pipeline_*"):
                    if pipeline_dir.is_dir() and pipeline_dir not in seen:
                        discovered.append(pipeline_dir)
                        seen.add(pipeline_dir)
        else:
            for pipeline_dir in root.glob("pipeline_*"):
                if pipeline_dir.is_dir() and pipeline_dir not in seen:
                    discovered.append(pipeline_dir)
                    seen.add(pipeline_dir)

    discovered.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return discovered


def _build_run_index() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_dir in _discover_pipeline_dirs():
        validation = _read_json(run_dir / "validation_report.json") or {}
        execution = _read_json(run_dir / "execution_result.json") or {}

        mtime = datetime.fromtimestamp(run_dir.stat().st_mtime)
        status = execution.get("status", "Unknown")
        validation_status = validation.get("status", "Unknown")
        issue_counts = validation.get("issue_counts", {})
        row_count = (validation.get("metrics", {}) or {}).get("row_count")

        rows.append(
            {
                "run_dir": run_dir,
                "modified": mtime,
                "status": status,
                "validation_status": validation_status,
                "errors": issue_counts.get("error", 0),
                "warnings": issue_counts.get("warning", 0),
                "row_count": row_count if row_count is not None else 0,
            }
        )
    return rows


def _run_label(entry: dict[str, Any]) -> str:
    return (
        f"{entry['modified'].strftime('%Y-%m-%d %H:%M:%S')} | "
        f"{entry['validation_status']} | rows={entry['row_count']} | {entry['run_dir']}"
    )


def _find_run_index_by_dir(run_index: list[dict[str, Any]], run_dir: Path) -> int | None:
    target = run_dir.resolve()
    for index, entry in enumerate(run_index):
        if entry["run_dir"].resolve() == target:
            return index
    return None


def _find_latest_run_for_blob_stem(run_index: list[dict[str, Any]], blob_stem: str) -> dict[str, Any] | None:
    for entry in run_index:
        if entry["run_dir"].parent.name == blob_stem:
            return entry
    return None


def _open_run_in_browse_mode(run_dir: Path) -> None:
    st.session_state["mode"] = "Browse Prior Runs"
    st.session_state["target_run_dir"] = str(run_dir.resolve())
    st.rerun()


def _render_overview(entry: dict[str, Any]) -> None:
    st.subheader("Run Summary")
    st.write(str(entry["run_dir"]))

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Run Status", str(entry["status"]))
    col2.metric("Validation", str(entry["validation_status"]))
    col3.metric("Rows", int(entry["row_count"]))
    col4.metric("Errors", int(entry["errors"]))
    col5.metric("Warnings", int(entry["warnings"]))


def _render_final_results(run_dir: Path) -> None:
    st.subheader("Canonical Output")
    csv_path = run_dir / "canonical_output.csv"
    xlsx_path = run_dir / "canonical_output.xlsx"

    if not csv_path.exists():
        st.warning("canonical_output.csv not found for this run.")
        return

    dataframe = pd.read_csv(csv_path)
    st.write(f"Rows: {len(dataframe)}")
    st.dataframe(dataframe, use_container_width=True, height=450)

    st.download_button(
        "Download canonical CSV",
        data=csv_path.read_bytes(),
        file_name=csv_path.name,
        mime="text/csv",
    )

    if xlsx_path.exists():
        st.caption(f"XLSX path: {xlsx_path}")


def _render_planner_output(run_dir: Path) -> None:
    st.subheader("Planner Output")
    planner_path = run_dir / "planner_response.json"
    planner = _read_json(planner_path)

    if planner is None:
        st.warning("planner_response.json not found or unreadable.")
        return

    left, right = st.columns(2)
    left.write("Relevant sheets")
    left.json(planner.get("relevant_sheets", []))
    right.write("Ignored sheets")
    right.json(planner.get("ignored_sheets", []))

    with st.expander("Mapping Plan", expanded=False):
        st.json(planner.get("mapping_plan", {}))

    with st.expander("Constants", expanded=False):
        st.json(planner.get("constants", {}))

    with st.expander("Enrichments", expanded=False):
        st.json(planner.get("enrichments", {}))

    with st.expander("Assumptions", expanded=False):
        st.json(planner.get("assumptions", []))

    script = planner.get("python_script", "")
    st.markdown("**Generated Transform Script**")
    st.code(script, language="python")


def _render_validation(run_dir: Path) -> None:
    st.subheader("Validation")
    validation = _read_json(run_dir / "validation_report.json")

    if validation is None:
        st.warning("validation_report.json not found or unreadable.")
        return

    issue_counts = validation.get("issue_counts", {})
    metrics = validation.get("metrics", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", str(validation.get("status", "Unknown")))
    c2.metric("Errors", int(issue_counts.get("error", 0)))
    c3.metric("Warnings", int(issue_counts.get("warning", 0)))
    c4.metric("Row Count", int((metrics or {}).get("row_count", 0)))

    issues = validation.get("issues", [])
    if issues:
        issues_frame = pd.DataFrame(issues)
        st.dataframe(issues_frame, use_container_width=True, height=350)
    else:
        st.success("No validation issues.")

    with st.expander("Validation Metrics", expanded=False):
        st.json(metrics)


def _render_execution_logs(run_dir: Path) -> None:
    st.subheader("Execution Logs")

    sandbox = _read_json(run_dir / "sandbox_execution_report.json")
    execution = _read_json(run_dir / "execution_result.json")

    if sandbox is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sandbox Status", str(sandbox.get("status", "Unknown")))
        c2.metric("Duration (ms)", int(sandbox.get("duration_ms", 0) or 0))
        c3.metric("Return Code", int(sandbox.get("return_code", 0) or 0))
        c4.metric("Timed Out", str(bool(sandbox.get("timed_out", False))))

        with st.expander("Sandbox stdout", expanded=False):
            st.text(sandbox.get("stdout", ""))

        with st.expander("Sandbox stderr", expanded=False):
            st.text(sandbox.get("stderr", ""))

    else:
        st.info("sandbox_execution_report.json not found for this run.")

    if execution is not None:
        with st.expander("Execution Result JSON", expanded=False):
            st.json(execution)


def _render_run_details(entry: dict[str, Any]) -> None:
    run_dir = entry["run_dir"]
    _render_overview(entry)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Final Results", "Planner Output", "Validation", "Execution Logs"]
    )

    with tab1:
        _render_final_results(run_dir)
    with tab2:
        _render_planner_output(run_dir)
    with tab3:
        _render_validation(run_dir)
    with tab4:
        _render_execution_logs(run_dir)


def _create_new_run() -> dict[str, Any] | None:
    st.subheader("Create New Run")

    example_inputs = sorted(EXAMPLE_INPUTS_DIR.glob("*.xlsx"))
    if not example_inputs:
        st.error("No example inputs found under examples/inputs.")
        return None

    selected_input = st.selectbox("Input workbook", options=example_inputs, format_func=lambda path: path.name)
    run_mode = st.selectbox("Run mode", options=["execute_with_validation", "draft"])
    planner_mode = st.selectbox("Planner mode", options=["live", "mock"])
    run_target = st.selectbox(
        "Run target",
        options=["Direct pipeline (local artifacts)", "Blob trigger (emulator input/output containers)"],
    )

    if planner_mode == "live":
        missing = _validate_live_mode_configuration()
        if missing:
            st.error(
                "Live planner mode is missing required configuration: "
                + ", ".join(missing)
                + ". Add these to local.settings.json (Values) or your environment."
            )

    st.caption(f"Output root: {STREAMLIT_OUTPUT_ROOT}")
    if run_target.startswith("Direct"):
        st.info(
            "Direct pipeline mode writes artifacts under artifacts/streamlit_runs and does not write to input/output blob containers."
        )
    else:
        missing_blob = _validate_blob_trigger_configuration()
        if missing_blob:
            st.error(
                "Blob trigger mode is missing required configuration: "
                + ", ".join(missing_blob)
                + ". Add these to local.settings.json (Values) or your environment."
            )

    if st.button("Run Pipeline", type="primary"):
        if planner_mode == "live":
            missing = _validate_live_mode_configuration()
            if missing:
                st.stop()

        if run_target.startswith("Blob trigger"):
            missing_blob = _validate_blob_trigger_configuration()
            if missing_blob:
                st.stop()

            with st.spinner("Uploading input blob and waiting for function output blobs..."):
                blob_name = _submit_blob_trigger_run(selected_input)
                outputs = _wait_for_blob_outputs(blob_name, timeout_seconds=90)

            st.success(f"Blob trigger submitted: {blob_name}")
            st.write("Output blob status")
            st.json(outputs)
            if all(outputs.values()):
                st.success("All expected output blobs are present in the output container.")
                blob_stem = Path(blob_name).stem
                run_index = _build_run_index()
                matching = _find_latest_run_for_blob_stem(run_index, blob_stem)
                if matching is not None:
                    if st.button("Open Finished Report", type="secondary"):
                        _open_run_in_browse_mode(matching["run_dir"])
            else:
                st.warning("Not all output blobs were detected before timeout. Check Function host logs and refresh run index.")
            return None

        with st.spinner("Running pipeline..."):
            result = run_pipeline(
                input_workbook=str(selected_input),
                output_root=str(STREAMLIT_OUTPUT_ROOT),
                run_mode=run_mode,
                planner_mode=planner_mode,
            )
        st.success("Run completed")
        if st.button("Open Finished Report", type="secondary"):
            _open_run_in_browse_mode(Path(result["run_dir"]))
        return result

    return None


def main() -> None:
    _load_local_settings_env()

    foundry_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    foundry_api_version = os.getenv("FOUNDRY_API_VERSION", "2025-05-15-preview")
    foundry_agent_name = os.getenv("FOUNDRY_AGENT_NAME", "")
    foundry_assistant_id = os.getenv("FOUNDRY_ASSISTANT_ID", "")
    foundry_agents_snapshot = _fetch_foundry_agents_snapshot(
        endpoint=foundry_endpoint,
        api_version=foundry_api_version,
        agent_name=foundry_agent_name,
        assistant_id=foundry_assistant_id,
    )

    st.set_page_config(page_title="RXO Pipeline Companion", layout="wide")
    st.title("RXO Normalizer - Companion Test & Visualization App")

    with st.sidebar:
        st.header("Controls")
        if "mode" not in st.session_state:
            st.session_state["mode"] = "Browse Prior Runs"
        mode = st.radio(
            "Mode",
            options=["Browse Prior Runs", "Create New Run", "Foundry Agents"],
            key="mode",
        )
        refresh = st.button("Refresh Run Index")

    if refresh:
        st.rerun()

    run_index = _build_run_index()

    if mode == "Create New Run":
        result = _create_new_run()
        if result is not None:
            run_dir = Path(result["run_dir"]).resolve()
            matching = [entry for entry in _build_run_index() if entry["run_dir"].resolve() == run_dir]
            if matching:
                st.divider()
                _render_run_details(matching[0])
            else:
                st.warning(f"Run created at {run_dir} but not found in discovery index yet.")
        return

    if mode == "Foundry Agents":
        _render_foundry_agents_page(foundry_agents_snapshot)
        return

    st.subheader("Prior Runs")
    if not run_index:
        st.info("No prior runs discovered yet.")
        return

    default_index = 0
    target_run_dir_text = st.session_state.get("target_run_dir")
    if isinstance(target_run_dir_text, str) and target_run_dir_text.strip():
        match_index = _find_run_index_by_dir(run_index, Path(target_run_dir_text))
        if match_index is not None:
            default_index = match_index
        st.session_state.pop("target_run_dir", None)

    selected_entry = st.selectbox("Select run", options=run_index, index=default_index, format_func=_run_label)
    _render_run_details(selected_entry)


if __name__ == "__main__":
    main()
