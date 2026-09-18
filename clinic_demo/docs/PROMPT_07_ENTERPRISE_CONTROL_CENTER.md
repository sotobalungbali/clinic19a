




# MASTER PROMPT 07 — ENTERPRISE DEMO CONTROL CENTER

Version: `19.0.1.0.2`  
Authoritative source SHA-256: `8dcf324c4fd58ea7caec27ebeeb877626bcbfd1227a6c4468caf21d1e7905137`

Implemented:

- ClinicOne → Configuration → Demo Dataset → Control Center routing
- enterprise Demo Run List / Form / Search
- statusbar: Draft / Generating / Validating / Ready / Failed
- Generate Full Enterprise Dataset
- Generate Current Phase
- Continue Generation
- Validate
- Regenerate Missing
- Reset Demo Dataset with Manager-only confirmation wizard
- Open Golden Journeys
- Smart Buttons for Golden Journeys, Checkpoints, Logs and Validation
- dedicated List / Form / Search views for all persistent Control Center models
- body/One2many navigation buttons
- Safe Mode / Seed / Source Fingerprint / Current Scenario /
  Last Successful Checkpoint presentation
- backend Operator / Manager checks for executable actions
- reset preview and retained-evidence acknowledgement
- generation requests safely gated until Prompt 08+ domain generators are registered

The Control Center is a normal `clinic.demo.run` persistent business UI.
It does not use a primary `res.config.settings` form.
























