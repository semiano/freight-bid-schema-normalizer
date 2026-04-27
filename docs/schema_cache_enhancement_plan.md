# Schema Cache Enhancement Plan

## Executive Intent
Add a schema-memory capability that stores previously seen input schema signatures together with approved planner outputs, then consults that memory before invoking the planner. The goal is to reduce repeated planning cost and latency, increase consistency for known formats, and enable a controlled path from human-reviewed approval to safe auto-approval.

---

## 1. Problem Statement
Today, every run profiles the workbook and then immediately invokes the planning layer, even when the input workbook structure is effectively identical to a previously processed format. This causes:
- redundant LLM/assistant calls,
- higher latency and cost,
- inconsistent planner output for equivalent schemas,
- no native memory of approved mappings.

The enhancement should introduce a reusable cache of **known input schemas** and their associated **planner outputs** so the system can:
1. look for an exact prior match before planning,
2. reuse previously approved planner output when appropriate,
3. support human-in-the-loop approval for new schemas,
4. optionally auto-approve exact known schemas after prior approval.

---

## 2. Design Goals
- Insert a deterministic cache lookup before planner invocation.
- Separate **schema recognition** from **planner generation**.
- Preserve full auditability for cache hits, misses, approvals, and overrides.
- Support both local development and cloud production deployments.
- Allow future extension from exact-match to near-match/similarity match.
- Keep the initial implementation simple and low-risk.

---

## 3. Scope for v1
### In Scope
- Exact schema fingerprinting from `WorkbookProfile`.
- Storage of schema fingerprints + planner output + approval state.
- Cache lookup before `build_plan()`.
- Human approval state model (`draft`, `approved`, `rejected`, `superseded`).
- Auto-reuse only for exact approved matches.
- Local store implementation.
- Cosmos-backed implementation seam and recommended production path.

### Out of Scope for v1
- Fuzzy/semantic schema similarity search.
- Automatic diff/merge between old and new planner outputs.
- Multiple competing approved plans for the same fingerprint.
- UI workflow implementation for approval itself (plan only, hooks included).
- Cross-tenant learning/shared schema memory.

---

## 4. Proposed Processing Flow
### Current flow
1. Profile workbook.
2. Render prompt.
3. Call planner.
4. Validate policy.
5. Execute script.

### Proposed flow
1. Profile workbook.
2. Compute deterministic schema fingerprint.
3. Query schema cache for exact fingerprint match.
4. If exact approved match exists:
   - reuse stored planner output,
   - skip live planner call,
   - write `schema_cache_lookup.json` artifact,
   - proceed to policy + sandbox.
5. If no approved exact match exists:
   - invoke planner as normal,
   - write planner artifacts,
   - store candidate schema record in cache with `approval_status=draft` (or `unapproved`),
   - require human approval for future auto-reuse.

---

## 5. Fingerprinting Strategy
The cache key must be stable for materially identical input schemas and insensitive to values that should not affect mapping.

### 5.1 Fingerprint Inputs
Build the fingerprint from normalized `WorkbookProfile` data:
- workbook-level sheet count,
- ordered sheet signatures,
- for each sheet:
  - normalized sheet name,
  - visibility flag,
  - selected header row,
  - normalized ordered column names,
  - inferred types per column,
  - business classification,
  - classifier hints.

### 5.2 Normalization Rules
- lowercase all names,
- trim whitespace,
- collapse repeated spaces,
- preserve column order,
- omit sample row values from the exact-match fingerprint,
- omit workbook file name,
- optionally normalize punctuation in sheet names if needed.

### 5.3 Fingerprint Outputs
Store both:
1. `schema_fingerprint_sha256` — exact deterministic match key,
2. `schema_signature_payload` — canonical JSON used to compute the fingerprint, for diagnostics and future similarity work.

### 5.4 Why not include row samples?
Sample row values are useful for planner reasoning but too volatile for exact schema identity. Including them would cause unnecessary cache misses.

---

## 6. Cache Record Model
Introduce a new persisted record type, for example `SchemaCacheEntry`.

### Suggested fields
- `id`
- `schema_fingerprint_sha256`
- `schema_signature_payload`
- `canonical_schema_name`
- `planner_output`
- `planner_output_hash`
- `approval_status` (`draft`, `approved`, `rejected`, `superseded`)
- `approval_source` (`human`, `system`, `migration`)
- `auto_approve_enabled` (bool)
- `first_seen_at`
- `last_seen_at`
- `use_count`
- `created_from_run_id`
- `last_used_run_id`
- `notes`
- `metadata`

### Optional future fields
- `similarity_group_id`
- `parent_entry_id`
- `schema_version`
- `customer_scope`
- `business_domain`

---

## 7. Approval Model
### 7.1 States
- `draft`: planner output exists but cannot be auto-reused.
- `approved`: safe for exact-match reuse.
- `rejected`: explicitly not reusable.
- `superseded`: previously approved but replaced by newer approved planner output.

### 7.2 Human-in-the-loop workflow
For new schemas:
1. run completes using planner output,
2. schema cache entry is stored as `draft`,
3. reviewer inspects planner output / validation / sandbox results,
4. reviewer approves entry,
5. future exact matches use cached planner output automatically.

### 7.3 Auto-approval policy
For v1, auto-approval should apply only when:
- exact fingerprint match,
- approval status is `approved`,
- same canonical schema target,
- not manually disabled.

---

## 8. Storage Options: Decision Matrix

| Criterion | Local JSON/SQLite | Cosmos DB |
|---|---|---|
| Setup complexity | Very low | Medium/high |
| Best for | Local dev, demos, small single-user use | Shared prod, multi-instance function apps |
| Concurrency | Weak/moderate | Strong |
| Query flexibility | Basic | Strong |
| Operational overhead | Minimal | Azure resource + RU planning |
| Deployment dependency | None | Requires new infra |
| Cost | Near-zero | Ongoing cloud cost |
| Offline use | Excellent | No |
| Audit/history | Good if structured | Excellent |
| Scaling across hosts | Poor | Excellent |
| Recommended environment | Dev/test local | Production/shared environments |

### Recommendation
- **v1 implementation:** local file-backed repository for speed and low risk.
- **target production architecture:** Cosmos DB repository behind the same interface.

### Why this recommendation
A local implementation proves the fingerprint model and approval lifecycle quickly without blocking on new infra. Cosmos is the right long-term production system because the planner cache must be shared across function instances and environments to deliver real operational value.

---

## 9. Storage Interface Proposal
Create a repository seam, for example:
- `SchemaCacheRepository` (interface/protocol)
- `LocalSchemaCacheRepository`
- `CosmosSchemaCacheRepository`

### Suggested methods
- `get_by_fingerprint(fingerprint: str) -> SchemaCacheEntry | None`
- `upsert_candidate(entry: SchemaCacheEntry) -> SchemaCacheEntry`
- `mark_approved(entry_id: str, approver: str | None = None) -> None`
- `mark_rejected(entry_id: str, approver: str | None = None) -> None`
- `list_entries(...)`
- `record_usage(entry_id: str, run_id: str) -> None`

---

## 10. Local Storage Design
### Preferred local format
Use one JSON file per cache entry under a folder such as:
- `artifacts/schema_cache/entries/<fingerprint>.json`

### Why file-per-entry over one large JSON file?
- easier diffing,
- simpler manual inspection,
- lower merge risk,
- no full-file rewrite on each update.

### Local metadata indexes
Optionally maintain:
- `artifacts/schema_cache/index.json` for quick listing,
- but v1 can work without an index if entry counts are low.

---

## 11. Cosmos DB Design
### Container suggestion
- Database: `rxo-normalizer`
- Container: `schema-cache`
- Partition key: `/canonicalSchemaName` or `/tenantScope`

### Item design
One item per schema fingerprint containing current approved planner output and lifecycle metadata.

### Query pattern
- point read or indexed query on `schema_fingerprint_sha256` + `canonical_schema_name`

### Why not store only planner output hash?
The fingerprint is the lookup key; planner hash is secondary metadata for drift/change detection.

---

## 12. Pipeline Integration Plan
Insert cache operations into `run_pipeline()` after workbook profiling and before planner invocation.

### Proposed integration sequence
1. `profile = profile_workbook(...)`
2. `fingerprint_payload = build_schema_signature(profile)`
3. `fingerprint = hash_signature(fingerprint_payload)`
4. `cache_entry = schema_cache_repo.get_by_fingerprint(fingerprint)`
5. Branch:
   - **Approved exact hit:** reuse `cache_entry.planner_output`
   - **Miss or unapproved hit:** call planner, persist candidate
6. Persist `schema_cache_lookup.json` artifact with:
   - hit/miss,
   - fingerprint,
   - matched entry id,
   - approval status,
   - decision path (`cache_hit_exact`, `cache_miss`, `cache_hit_unapproved`, etc.)

### Suggested result payload additions
Return in `run_pipeline()`:
- `schema_cache_lookup`
- `schema_fingerprint`
- `planning_source` (`cache` or `planner_live/mock`)

---

## 13. Human Approval Enablement Plan
### Minimal v1 mechanism
Implement approval as file/record state changes outside the core runtime:
- CLI helper, admin script, or Streamlit admin panel later.

### Suggested next-step admin affordance
Add a small Streamlit admin view to:
- list draft cache entries,
- show planner output,
- approve/reject entry.

This is the simplest HITL path and matches the new companion app direction.

---

## 14. Artifacts and Auditability
New artifacts to add per run:
- `schema_signature.json`
- `schema_cache_lookup.json`
- `schema_cache_entry_snapshot.json` (optional for hit cases)

These should explain:
- why a cache hit/miss occurred,
- which entry was reused,
- whether human approval existed,
- whether planner was skipped.

---

## 15. Risks and Mitigations
### Risk: false exact misses due to unstable normalization
Mitigation: keep signature logic small, deterministic, and test-backed.

### Risk: false exact hits on materially different workbooks
Mitigation: preserve ordered columns, header row, and sheet classification in fingerprint.

### Risk: stale approved planner output
Mitigation: support `superseded` state and planner hash/version metadata.

### Risk: approval bypass
Mitigation: only allow auto-reuse for `approved` entries.

### Risk: local store divergence from cloud behavior
Mitigation: keep repository interface identical and reuse contract tests across implementations.

---

## 16. Recommended Rollout Phases
### Phase A — Foundation
- Add schema signature builder + fingerprint hashing.
- Add local repository.
- Add cache lookup artifact and pipeline branch.
- Store misses as `draft`.

### Phase B — Approval Workflow
- Add admin script or Streamlit approval view.
- Allow approving/rejecting cache entries.
- Enable exact-match auto-reuse for approved entries.

### Phase C — Cloud Hardening
- Add Cosmos repository implementation.
- Add Bicep resources/configuration.
- Add deployment documentation and migration path.

### Phase D — Optimization
- Add similarity lookup candidates.
- Add hit-rate metrics and planner-cost reduction reporting.
- Add selective auto-approval rules by customer/domain.

---

## 17. Test Strategy
### Unit tests
- signature normalization stability,
- fingerprint determinism,
- local repository CRUD,
- pipeline cache-hit vs cache-miss branching.

### Integration tests
- approved exact match skips planner,
- unapproved hit still invokes planner,
- candidate entry written on miss,
- `schema_cache_lookup.json` artifact correctness.

### Manual validation
- process same workbook twice,
- approve first-run cache entry,
- confirm second run uses cache and avoids planner call.

---

## 18. Acceptance Criteria
- The system computes and persists a schema fingerprint per run.
- The system checks the schema cache before planner invocation.
- Approved exact matches reuse stored planner output without live planner call.
- Misses or unapproved matches still use the planner and persist a candidate entry.
- All decisions are auditable through run artifacts.
- Local store works in development; Cosmos seam exists for production adoption.

---

## 19. Recommended Implementation Decision
**Proceed with a repository-based design using local file-backed schema cache in v1, while defining the same contract for Cosmos DB in production.**

This gives the fastest path to value, preserves future scalability, and directly supports the requested human-in-the-loop approval and known-schema auto-approval model.
