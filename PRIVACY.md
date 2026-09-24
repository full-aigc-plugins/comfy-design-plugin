# Privacy

PartMe Comfy is a local-first plugin foundation for ComfyUI workflows. It does not include telemetry, advertising, or a hosted data service.

By default the plugin runs against a local ComfyUI MCP (`comfy-mcp`): prompts, workflow inputs, and generated artifacts stay on your own machine and nothing is sent to a third-party service. Local generation spends no credits.

Only when a step needs the cloud-only tool surface (partner models, `upload_file`, saved workflows) does the plugin escalate to the hosted Comfy Cloud service — and only after telling you that the step will send data off-machine and may incur charges. In that case user-approved prompts and workflow inputs are sent to the Comfy Cloud service to perform generation, and generated artifacts are downloaded to user-selected paths. Credentials are stored only in the user's local configuration and are never embedded in this repository.

Users should review Comfy Cloud's own privacy terms before enabling the escalation path, and are responsible for the content they submit to third-party generation services.

---
