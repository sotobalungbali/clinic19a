# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - External Bridges
Single place for all _inherit into external apps to avoid collisions.
"""

# Development order: stock bridge first, then accounting bridge
from . import stock_bridge
from . import account_bridge
