# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# Init for models package
#
# URUTAN PENTING (dependency-aware):
# 1) mixin_pricing            : util mixin yg dipakai banyak model (compose result, rounding, dsb)
# 2) master data dasar        : category, tag, attribute
# 3) treatment                : entitas utama yang memanfaatkan master di atas
# 4) bundle                   : bergantung pada treatment
# 5) pricelist header & items : referensi ke treatment/bundle (+ Odoo product.pricelist bridge)
# 6) res_config_settings      : setting & company fields (mengacu ke model-model di atas)
# 7) subpackages engines      : membutuhkan model-model di atas sudah terdaftar
# 8) subpackages bridges      : membutuhkan engines & model-model di atas

from . import mixin_pricing

from . import treatment_category
from . import treatment_tag
from . import treatment_attribute

from . import treatment
from . import treatment_bundle

from . import treatment_pricelist
from . import treatment_pricelist_item
from . import treatment_public # ditambahkan ChatGPT 2025-10-23
from . import res_config_settings

# Subpackages (harus di bawah karena bergantung pada model-model di atas)
# from . import engines
from . import bridges

