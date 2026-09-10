# -*- coding: utf-8 -*-
"""ORM workflow hard gates for eMAR clinical ledgers.

Why this file is intentionally repetitive
-----------------------------------------
Odoo 19 rebuilds model bases while preparing the registry.  These extensions
therefore inherit *only* from ``models.Model``.  Do not add a plain Python
mixin base beside ``models.Model`` here: that pattern can make the dynamically
rebuilt Odoo class layout incompatible and prevent the entire registry from
loading.

The form statusbar is a UX control, not a security boundary.  Direct public
``write({"state": ...})`` calls are blocked.  Approved workflow actions call
the private ``_emar_guarded_write`` helper, which bypasses only this guard
extension and continues through the normal Odoo ``write`` MRO.

No context flag is used as an authorization token because RPC callers can
supply arbitrary context values.
"""

from odoo import _, models
from odoo.exceptions import UserError


def _check_direct_state_write(records, vals):
    """Reject state mutation unless it comes through an approved action.

    This is a module-level helper rather than a Python mixin class on purpose.
    Concrete Odoo extensions below stay single-base ``models.Model`` classes,
    which is safe for Odoo 19 registry base reconstruction.
    """
    if "state" not in vals:
        return

    target = vals.get("state")
    changing = records.filtered(lambda rec: rec.state != target)
    if changing:
        raise UserError(
            _(
                "Direct eMAR state changes are blocked. Use the approved "
                "workflow action so clinical safety, governance, inventory, "
                "and audit gates cannot be bypassed."
            )
        )


class ClinicEmarPrescriptionWorkflowGuard(models.Model):
    _inherit = "clinic.emar.prescription"

    def _emar_check_direct_state_write(self, vals):
        return _check_direct_state_write(self, vals)

    def _emar_guarded_write(self, vals):
        """Continue after this guard layer for an approved internal transition."""
        return super(ClinicEmarPrescriptionWorkflowGuard, self).write(vals)

    def write(self, vals):
        self._emar_check_direct_state_write(vals)
        return super().write(vals)


class ClinicEmarOrderWorkflowGuard(models.Model):
    _inherit = "clinic.emar.order"

    def _emar_check_direct_state_write(self, vals):
        return _check_direct_state_write(self, vals)

    def _emar_guarded_write(self, vals):
        """Continue after this guard layer for an approved internal transition."""
        return super(ClinicEmarOrderWorkflowGuard, self).write(vals)

    def write(self, vals):
        self._emar_check_direct_state_write(vals)
        return super().write(vals)


class ClinicEmarScheduleWorkflowGuard(models.Model):
    _inherit = "clinic.emar.schedule"

    def _emar_check_direct_state_write(self, vals):
        return _check_direct_state_write(self, vals)

    def _emar_guarded_write(self, vals):
        """Continue after this guard layer for an approved internal transition."""
        return super(ClinicEmarScheduleWorkflowGuard, self).write(vals)

    def write(self, vals):
        self._emar_check_direct_state_write(vals)
        return super().write(vals)


class ClinicEmarAdministrationWorkflowGuard(models.Model):
    _inherit = "clinic.emar.administration"

    def _emar_check_direct_state_write(self, vals):
        return _check_direct_state_write(self, vals)

    def _emar_guarded_write(self, vals):
        """Continue after this guard layer for an approved internal transition."""
        return super(ClinicEmarAdministrationWorkflowGuard, self).write(vals)

    def write(self, vals):
        self._emar_check_direct_state_write(vals)
        return super().write(vals)

