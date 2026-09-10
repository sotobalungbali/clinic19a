# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Mixins
Abstract mixins used by core models. Keep these first.
"""

# Development order: audit → inventory → billing
from . import emar_mixin_audit
from . import emar_mixin_inventory
from . import emar_mixin_billing

