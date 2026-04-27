#!/usr/bin/env python
"""Deploy updated system prompt to the Azure AI Foundry agent.

This script:
1. Reads the current system prompt from src/function_app/prompts/transform_planner_system.txt
2. Connects to the Foundry project via azure-ai-projects SDK
3. Finds the existing agent by name (FOUNDRY_AGENT_NAME)
4. Updates the agent instructions with the new prompt
5. Optionally bumps FOUNDRY_AGENT_VERSION in local.settings.json

Usage:
    python scripts/deploy-foundry-agent.py [--bump-version] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "src" / "function_app" / "prompts" / "transform_planner_system.txt"
LOCAL_SETTINGS = ROOT / "local.settings.json"


def _load_env_from_local_settings() -> None:
    """Inject Values from local.settings.json into os.environ (unless already set)."""
    if not LOCAL_SETTINGS.exists():
        return
    settings = json.loads(LOCAL_SETTINGS.read_text(encoding="utf-8"))
    for key, value in settings.get("Values", {}).items():
        if key not in os.environ:
            os.environ[key] = value


def _read_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        print(f"ERROR: System prompt not found at {PROMPT_PATH}", file=sys.stderr)
        sys.exit(1)
    return PROMPT_PATH.read_text(encoding="utf-8")


def _bump_version_in_settings(new_version: str) -> None:
    if not LOCAL_SETTINGS.exists():
        return
    raw = LOCAL_SETTINGS.read_text(encoding="utf-8")
    settings = json.loads(raw)
    old_version = settings.get("Values", {}).get("FOUNDRY_AGENT_VERSION", "")
    settings["Values"]["FOUNDRY_AGENT_VERSION"] = new_version
    LOCAL_SETTINGS.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"  Bumped FOUNDRY_AGENT_VERSION: {old_version} -> {new_version}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy updated system prompt to Azure AI Foundry agent.")
    parser.add_argument("--bump-version", action="store_true", help="Increment FOUNDRY_AGENT_VERSION in local.settings.json")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without making changes")
    args = parser.parse_args()

    _load_env_from_local_settings()

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    agent_name = os.environ.get("FOUNDRY_AGENT_NAME", "").strip()
    api_key = os.environ.get("FOUNDRY_API_KEY", "").strip()
    current_version = os.environ.get("FOUNDRY_AGENT_VERSION", "").strip()

    if not endpoint:
        print("ERROR: FOUNDRY_PROJECT_ENDPOINT is not set.", file=sys.stderr)
        sys.exit(1)
    if not agent_name:
        print("ERROR: FOUNDRY_AGENT_NAME is not set.", file=sys.stderr)
        sys.exit(1)

    system_prompt = _read_system_prompt()
    print(f"System prompt loaded ({len(system_prompt)} chars) from {PROMPT_PATH}")
    print(f"  Endpoint:      {endpoint}")
    print(f"  Agent name:    {agent_name}")
    print(f"  Current ver:   {current_version or '(none)'}")

    if args.dry_run:
        print("\n[DRY RUN] Would update agent instructions. No changes made.")
        if args.bump_version and current_version:
            next_ver = str(int(current_version) + 1) if current_version.isdigit() else current_version + ".1"
            print(f"[DRY RUN] Would bump version to {next_ver}")
        return

    # ── Connect via azure-ai-projects SDK ──────────────────────────
    try:
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import PromptAgentDefinition
    except ImportError:
        print("ERROR: azure-ai-projects is required.  pip install azure-ai-projects>=2.0.0", file=sys.stderr)
        sys.exit(1)

    if api_key:
        from azure.core.credentials import AzureKeyCredential
        credential = AzureKeyCredential(api_key)
    else:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)

    project_client = AIProjectClient(endpoint=endpoint, credential=credential)

    # ── Find existing agent ───────────────────────────────────────
    print("\nListing agents...")
    agents_client = project_client.agents
    found_agent = None

    for agent in agents_client.list():
        name = getattr(agent, "name", None) or ""
        agent_id = getattr(agent, "id", None) or ""
        if name == agent_name:
            found_agent = agent
            print(f"  Found agent: {name} (id={agent_id})")
            break

    if found_agent is None:
        print(f"\nERROR: Agent '{agent_name}' not found in Foundry. Create it in the portal first.", file=sys.stderr)
        sys.exit(1)

    # ── Create new version with updated instructions ──────────────
    next_ver = str(int(current_version) + 1) if current_version.isdigit() else "1"
    model_name = os.environ.get("FOUNDRY_MODEL", "gpt-4.1")

    print(f"\nCreating version {next_ver} for agent '{agent_name}'...")
    definition = PromptAgentDefinition(
        model=model_name,
        instructions=system_prompt,
    )
    new_version = agents_client.create_version(
        agent_name=agent_name,
        definition=definition,
        description=f"System prompt update v{next_ver} — added notes_json output format",
    )
    created_ver = getattr(new_version, "version", next_ver)
    print(f"  Created version: {created_ver}")

    # ── Bump local version ────────────────────────────────────────
    if args.bump_version:
        _bump_version_in_settings(str(created_ver))

    print("\nDone.")


if __name__ == "__main__":
    main()
