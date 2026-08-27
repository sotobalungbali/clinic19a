# Runtime Repair 2026-08-19 — Native Migration Environment

## Evidence

During a module upgrade on Odoo 19 CE Windows, the registry stopped before the
`clinic_emar` pre-migration could execute:

`ImportError: cannot import name 'util' from 'odoo.upgrade'`

The failing script was:

`migrations/19.0.3.0.0/pre-10-preserve_company_settings.py`

The paired post-migration script used the same unsupported import and would have
failed later in the same upgrade path.

## Root cause

The migration scripts depended on `odoo.upgrade.util.env(cr)`.  That helper is
not part of the guaranteed runtime surface of the target Community Windows
installation.  The addon therefore had an undeclared deployment dependency in
its migration layer.

## Corrective action

Both migration scripts now use only native Odoo core APIs:

```python
from odoo import SUPERUSER_ID
from odoo.api import Environment

env = Environment(cr, SUPERUSER_ID, {})
```

No business model, field, workflow, security rule, view, sequence, integration,
or data-preservation behavior is removed.  The pre-migration still preserves
legacy company settings and remains idempotent.  The post-migration still
verifies all eMAR-owned tables and the non-stored company-setting contract.

## Prevention

`tools/clinic_emar_guardrail.py` rejects migration scripts that reintroduce
`odoo.upgrade` imports and asserts use of the native `Environment` API.

## Acceptance

Source/static validation is necessary but not sufficient.  Runtime status
remains PENDING until the target Odoo 19 CE Windows upgrade completes.
