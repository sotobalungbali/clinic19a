# HARD GATE 7 — UI/UX Matrix

| Owner model | Search | List | Form | Extra enterprise UX |
|---|---|---|---|---|
| `clinic.quality.sop` | Yes | Yes | Yes | Kanban, statusbar, smart buttons, body actions, nested Versions/Acknowledgements/Templates |
| `clinic.quality.sop.version` | Yes | Yes | Yes | statusbar, Submit/Approve/Return/Withdraw |
| `clinic.quality.sop.acknowledgement` | Yes | Yes | Yes | immutable evidence, explicit Void |
| `clinic.quality.check.template` | Yes | Yes | Yes | statusbar, smart buttons, editable Draft controls |
| `clinic.quality.check.template.line` | Yes | Yes | Yes | Template navigation |
| `clinic.quality.check` | Yes | Yes | Yes | Kanban/Pivot/Graph, statusbar, source smart buttons, review/nonconformity actions, nested control actions |
| `clinic.quality.check.line` | Yes | Yes | Yes | evidence, Incident escalation/open actions |
| `clinic.quality.schedule` | Yes | Yes | Yes | statusbar, Run/Pause/Resume, check smart buttons, error evidence |

UI modifiers are convenience only. Security and lifecycle validation are
enforced in Python backend methods.
