




# ClinicOne Demo Framework — MASTER PROMPT 07

Build contract:

- addon version: `19.0.1.0.2`
- authoritative latest ClinicOne source SHA-256: `8dcf324c4fd58ea7caec27ebeeb877626bcbfd1227a6c4468caf21d1e7905137`
- expected 41-core-addon version vector SHA-256:
  `8b16194ce2de3736aa2a91cfad6569dcb0f174eff1b3d9ac2e86961a198fc8ed`

Prompt 06 identity/ownership/idempotency foundations are preserved.

Prompt 07 adds the Enterprise Demo Control Center:

- persistent `clinic.demo.run` Control Center
- List / Form / Search views
- statusbar
- Generate Full / Current Phase / Continue controls
- Validate
- Regenerate Missing
- Reset Demo Dataset with explicit Manager confirmation
- Golden Journey registry navigation
- Checkpoint monitoring
- persistent Logs
- Validation evidence
- Smart Buttons and One2many row navigation
- Source Fingerprint / Safe Mode / Current Scenario /
  Last Successful Checkpoint presentation
- backend Operator / Manager authorization
- reset preview with immutable/reused evidence acknowledgement

Domain generators remain bounded implementation work for MASTER PROMPT 08–22.
The Prompt-07 generation buttons are deliberately safe-gated when zero executable
domain generators are registered; they do not create fake business data.

The Control Center is **not** a standalone primary `res.config.settings` form.









