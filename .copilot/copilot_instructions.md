# Copilot Instructions

Always consult these files before making significant implementation changes:
- `./software_spec.md`
- `./implementation_plan.md`

Repository operating rules:
- Treat the software spec and implementation plan as the source of truth.
- Keep `./.copilot/TODO.md` updated as persistent build memory.
- Keep `./README.md` synchronized with the actual implementation state.
- Prefer incremental, testable changes over large speculative scaffolds.
- Avoid undocumented architectural drift.
- If implementation reveals a necessary design change, update the relevant markdown docs and explain the change clearly.

Working loop for every meaningful session:
1. Read:
   - `./software_spec.md`
   - `./implementation_plan.md`
   - `./.copilot/TODO.md`
   - `./README.md`
2. Determine the next highest-value implementation step.
3. Implement in small, testable increments.
4. Add or update tests.
5. Update `./.copilot/TODO.md`.
6. Update `./README.md` if setup, architecture, configuration, testing, or usage changed.
7. Summarize what changed, what remains, and the recommended next step.

Implementation expectations:
- Build toward the documented Azure Function App + Azure AI Foundry architecture.
- Use AI for schema reasoning, transform-planning, and script generation only where the spec calls for it.
- Keep transformation execution deterministic and controlled.
- Keep deterministic validation as the primary gate.
- Treat secondary LLM-based validation as advisory unless explicitly promoted by the spec.
- Implement all infrastructure as code in Bicep.

Quality bar:
- No stale README.
- No stale TODO state.
- No hidden assumptions.
- No silent divergence from the spec.
- No broad code dump without clear structure and explanation.
- Favor vertical slices that can be run and tested.

If the repo is partially scaffolded:
- Reconcile current repo contents against the spec and plan.
- Update TODO and README first.
- Then continue with the next foundational implementation step.

If ambiguity exists:
- Choose the option that best aligns with the software spec and implementation plan.
- Document the decision in `./.copilot/TODO.md`.
