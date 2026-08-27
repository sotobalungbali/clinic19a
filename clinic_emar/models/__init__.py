# -*- coding: utf-8 -*-
"""ClinicOne eMAR model loading order.

Mixins load first, owned core entities second, stock/account bridge fields third,
and cross-addon integrations last so they can safely extend the completed core.
"""
from . import mixins
from . import core
from . import external_bridges
from . import integrations
