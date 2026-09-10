# -*- coding: utf-8 -*-
"""
ClinicOne - Clinic Billing
Models package initializer

Import order rationale (keep this order):
1) Core billing models (invoice, line, payment)
2) Pricing/benefit engines (discount, voucher, membership)
3) Insurance & commission domain
4) Gateway transactions (depends on payment & invoice)
5) Cross-app hooks (patient, treatment, doctor)
6) Accounting bridges (account.move, account.payment)
7) Settings (res.config.settings)

This order minimizes cross-file initialization issues and keeps extensions
(_inherit) loaded after their base models.
"""

# 1) Core
from . import billing_invoice
from . import billing_line
from . import billing_payment

# 2) Pricing / Benefit Engines
from . import billing_discount
from . import billing_voucher
from . import billing_membership_wallet

# 3) Domain: Insurance & Commission
from . import billing_insurance
from . import billing_commission

# 4) Gateway
from . import billing_gateway_tx

# 5) Cross-app Hooks
from . import patient_hook
from . import treatment_hook
from . import doctor_hook

# 6) Accounting Bridges
from . import account_move_hook
from . import account_payment_hook

# 7) Enterprise integration & upstream navigation
from . import integration_event
from . import source_model_bridges
from . import ui_bridge
from . import cron

# 8) Settings
from . import res_config_settings



