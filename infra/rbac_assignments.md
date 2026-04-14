# RBAC Assignments for RXO Document Normalizer

Use this document as a public-safe checklist for validating required RBAC assignments.

## Required Identities
- Function App system-assigned managed identity
- Optional container worker system-assigned managed identity (when enabled)

## Required Scopes
- Storage account scope
- Key Vault scope
- Optional Foundry account scope
- Optional Foundry project scope

## Expected Roles
1) Storage Blob Data Contributor
- Role definition ID: `ba92f5b4-2d11-453d-a403-e96b0029c9fe`

2) Storage Queue Data Contributor (if queue workflow is enabled)
- Role definition ID: `974c5e8b-45b9-4653-ba55-5f855dd0fb88`

3) Key Vault Secrets User
- Role definition ID: `4633458b-17de-408a-b874-0445c86b69e6`

4) Cognitive Services OpenAI User (Foundry account scope, when Foundry access is required)
- Role definition ID: `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`

5) Azure AI User (Foundry project scope, when Foundry access is required)
- Role definition ID: `53ca6127-db72-4b80-b1b0-d745d6d5456d`

## Verification Commands (Template)
- List assignments for principal:
  - `az role assignment list --assignee-object-id <principal-object-id> --all --output table`
- Filter by specific scope:
  - `az role assignment list --assignee-object-id <principal-object-id> --scope <scope-resource-id> --output table`

## Notes
- Keep tenant IDs, subscription IDs, principal object IDs, and concrete resource IDs out of public repositories.
- Prefer Bicep-managed RBAC assignments to keep infrastructure reproducible and auditable.
