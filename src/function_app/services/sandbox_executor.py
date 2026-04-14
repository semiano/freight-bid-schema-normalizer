from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any


def execute_script_in_sandbox(
    script_source: str,
    context: dict[str, Any],
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    start = time.perf_counter()

    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        script_path = workspace / "generated_transform.py"
        runner_path = workspace / "sandbox_runner.py"
        context_path = workspace / "context.json"
        result_path = workspace / "result.json"

        script_path.write_text(script_source, encoding="utf-8")
        context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")

        runner_code = textwrap.dedent(
            """
            import importlib.util
            import json
            import traceback
            from pathlib import Path

            SCRIPT_PATH = Path("generated_transform.py")
            CONTEXT_PATH = Path("context.json")
            RESULT_PATH = Path("result.json")

            def make_json_safe(value):
                try:
                    json.dumps(value)
                    return value
                except TypeError:
                    if isinstance(value, dict):
                        return {str(k): make_json_safe(v) for k, v in value.items()}
                    if isinstance(value, list):
                        return [make_json_safe(item) for item in value]
                    return str(value)

            try:
                spec = importlib.util.spec_from_file_location("generated_transform", SCRIPT_PATH)
                module = importlib.util.module_from_spec(spec)
                assert spec is not None and spec.loader is not None
                spec.loader.exec_module(module)

                if not hasattr(module, "transform"):
                    raise AttributeError("transform(context) function not found")

                context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
                result = module.transform(context)

                payload = {
                    "status": "Succeeded",
                    "result": make_json_safe(result),
                    "error": None,
                }
            except Exception:
                payload = {
                    "status": "Failed",
                    "result": None,
                    "error": traceback.format_exc(),
                }

            RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            """
        )
        runner_path.write_text(runner_code, encoding="utf-8")

        try:
            process = subprocess.run(
                [sys.executable, str(runner_path)],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            timed_out = False
        except subprocess.TimeoutExpired as timeout_error:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return {
                "status": "TimedOut",
                "passed": False,
                "timed_out": True,
                "duration_ms": duration_ms,
                "return_code": None,
                "stdout": timeout_error.stdout or "",
                "stderr": timeout_error.stderr or "",
                "result": None,
                "error": f"Execution exceeded {timeout_seconds} seconds",
            }

        duration_ms = int((time.perf_counter() - start) * 1000)

        payload: dict[str, Any] = {
            "status": "Failed",
            "result": None,
            "error": "Runner did not produce result payload",
        }
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))

        passed = process.returncode == 0 and payload.get("status") == "Succeeded"

        return {
            "status": payload.get("status", "Failed"),
            "passed": passed,
            "timed_out": timed_out,
            "duration_ms": duration_ms,
            "return_code": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "result": payload.get("result"),
            "error": payload.get("error"),
        }
