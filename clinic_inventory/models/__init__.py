# -*- coding: utf-8 -*-

from . import models
# -*- coding: utf-8 -*-
# ClinicOne - clinic_inventory/models/__init__.py
#
# Load order notes:
# - Keep hooks first, then product core, then stock core, then clinic-specific link models.
# - This order helps avoid indirect import issues and keeps dependencies predictable.

# Base hooks & mixins used by other models

# Product core (extends Odoo product models & settings)
from . import product_template # 
from . import product_product #
from . import product_category # 

# Stock core (extends Odoo stock models)
from . import stock_warehouse #
from . import stock_location # 
from . import stock_picking #
from . import stock_move #
from . import stock_quant #
from . import stock_lot #
from . import stock_scrap #
from . import stock_rule #
from . import stock_reorderpoint #

# Clinic-specific link models (Inventory ↔︎ Clinic domain)
from . import res_config_settings # 
from . import treatment_product_usage #
from . import patient_product_history #
from . import doctor_allowed_products #
from . import inventory_adjustment #
# from . import procurement_group # sudah tidak ada lagi di Odoo 19 CE
from . import integration_hooks #

