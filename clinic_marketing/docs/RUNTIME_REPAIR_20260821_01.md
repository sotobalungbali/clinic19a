# Runtime Repair 2026-08-21 / 01

## Failed baseline

`clinic_marketing` 19.0.1.0.0

Runtime failure during module import:

```text
NameError: name 'api' is not defined
```

Location:

```text
clinic_marketing/models/campaign_delivery.py
class ClinicMarketingCampaignDelivery(models.Model)
@api.model
def _cron_sync_running_campaigns(self):
```

## Proven root cause

During the prior human-friendly refactor, Campaign delivery logic was split out
of `campaign.py` into `campaign_delivery.py`.

The new file imported:

```python
from odoo import fields, models, _
```

but still contained:

```python
@api.model
```

Because Python evaluates decorators while the class body is being created,
module loading failed before the Odoo registry could finish loading the addon.

This was not an ORM, XML, database, dependency, or business-logic defect. It was
a Python module load-time symbol/import defect introduced by the file split.

## Exact repair

The import is now:

```python
from odoo import api, fields, models, _
```

No model, field, workflow, dependency, view, ACL, campaign behavior, promotion
ownership, Email Marketing delegation, or WhatsApp behavior was removed or
simplified.

## Regression prevention

The Enterprise Development Guardrail now performs an AST-based
**load-time decorator/base symbol audit** across every Python file. It rejects
missing imported Odoo symbols such as `api`, `fields`, or `models` when those
symbols are referenced by decorators or class bases.

This closes the exact defect class that allowed 19.0.1.0.0 to pass syntax/static
checks while still failing at Python class evaluation time.

## Repair target

`clinic_marketing` 19.0.1.0.1

Runtime installation remains PENDING until the repaired full addon is activated
successfully on the target Odoo 19 CE instance.
