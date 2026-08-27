# Clinic Inventory — UI/UX Matrix per Model

| Model | Role | Search | List | Form | Enterprise UX |
|---|---|---:|---:|---:|---|
| clinic.treatment.product.usage | Business document | YES | YES | YES | Statusbar; Confirm/Consume/Reset/Cancel; Stock Moves smart button; One2many open-parent button |
| clinic.treatment.product.usage.line | Embedded line | YES | YES | YES | Embedded editable list + standalone diagnostic views + open-parent button |
| clinic.inventory.adjustment | Business document | YES | YES | YES | Statusbar; Prepare/Confirm/Apply/Reset/Cancel; Stock Moves smart button |
| clinic.inventory.adjustment.line | Embedded line | YES | YES | YES | Embedded count list + standalone diagnostic views + open-parent button |
| clinic.patient.product.history | Audit/traceability | YES | YES | YES | Picking and Stock Move smart buttons; read-oriented action |
| clinic.doctor.allowed.product | Governance rule | YES | YES | YES | Allowed Products smart button; manager configuration menu |
| clinic.integration.event.log | Technical audit | YES | YES | YES | Manager-only read UI; statusbar; no create/edit/delete from UI |
| clinic.integration.mixin | Abstract technical | N/A | N/A | N/A | No user UI by design |
| clinic.integration.service | Technical service | N/A | N/A | N/A | No user UI by design; service API only |
| clinic.integration.event.catalog | Technical catalog | N/A | N/A | N/A | No user UI by design |
| product.template | Odoo extension | Odoo native | Odoo native | Inherited Odoo form | Clinic Inventory page + expiring lots/stock moves smart actions |
| stock.warehouse | Odoo extension | Odoo native | Odoo native | Inherited Odoo form | Clinic Inventory page + location/on-hand smart actions |
| stock.location | Odoo extension | Odoo native | Odoo native | Inherited Odoo form | Clinic classification/governance + quants/moves smart actions |
| stock.lot | Odoo extension | Odoo native | Odoo native | Inherited Odoo form | Quality/expiry block + quants/moves + quarantine action |

Odoo core extensions not listed above continue to use their canonical Odoo 19 Search/List/Form surfaces. Their ClinicOne APIs/fields remain preserved; dedicated UI is added only where it materially improves inventory operation.

