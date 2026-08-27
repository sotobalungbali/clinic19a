# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# Init for models/bridges subpackage
#
# URUTAN PENTING:
# - bridge_pricing   : fondasi (model "clinic.pricelist.bridge") yang dipakai bridge lain
# - bridge_booking   : membentuk context & memanggil bridge_pricing untuk booking/appointment
# - bridge_billing   : membentuk invoice/claim dari hasil bridge_booking/bridge_pricing
# - bridge_inventory : perencanaan/eksekusi konsumsi stok dari treatment/bundle/booking
# - bridge_reports   : agregasi pelaporan dari billing/booking/pricing

from . import bridge_pricing
# from . import bridge_booking
# from . import bridge_billing
# from . import bridge_inventory
# from . import bridge_reports

# pindahan dari addon clinic_staff
from . import integration_consent

