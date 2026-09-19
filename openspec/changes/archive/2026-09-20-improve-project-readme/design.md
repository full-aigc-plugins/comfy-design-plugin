## Context

The existing README is preserved outside a managed `full-stack-doc` block. Confirmed facts come from repository manifests, skill directories, lock files, tests, CI workflows, OpenSpec, and licenses.

## Goals / Non-Goals

### Goals

- Provide a first-screen mental model and the shortest verified success path.
- Distinguish source, installation, host loading, provider execution, and release proof levels.
- Make boundaries, security, troubleshooting, and maintenance discoverable.

### Non-Goals

- Change runtime behavior or public contracts.
- Invent compatibility, production readiness, credentials, or installation claims.
- Delete existing examples or vendor-specific guidance.

## Decisions

### Preserve original content around one managed block

The standard block is generated from repository evidence and enclosed by stable markers. Re-running generation must be idempotent. Existing content outside the block remains author-owned.

### Use the 插件 template only

Product PRD, market analysis, domain-model, UI, deployment, and unrelated enterprise sections are omitted because this task improves repository entry documentation rather than scaffolding a product-document tree.
