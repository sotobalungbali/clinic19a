# -*- coding: utf-8 -*-
"""Installation hooks for optional presentation integration.

The business dependency on ``clinic_base`` is hard, but its menu XML-ID may be
missing in databases installed from an older source revision.  Presentation
hierarchy must never block installation of the clinical models.
"""

import logging

_logger = logging.getLogger(__name__)


def _post_init_hook(env):
    """Attach the local Encounter root below ClinicOne when safely available."""
    local_root = env.ref("clinic_encounter.menu_clinic_encounter_root", raise_if_not_found=False)
    if not local_root:
        return

    clinic_root = env.ref("clinic_base.menu_root", raise_if_not_found=False)
    if clinic_root:
        local_root.parent_id = clinic_root
        return

    _logger.info(
        "ClinicOne Encounter installed with its local root menu because "
        "clinic_base.menu_root is not present in this database revision."
    )
