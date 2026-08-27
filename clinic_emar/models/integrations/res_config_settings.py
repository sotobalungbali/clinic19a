# -*- coding: utf-8 -*-
"""Schema-safe, company-scoped eMAR operational configuration.

Why this file deliberately avoids stored fields on ``res.company``
-------------------------------------------------------------------
``res.company`` is read by almost every Odoo web request.  A source/database
version skew on a newly added stored company field therefore has a very large
blast radius: the registry can know the field while PostgreSQL does not yet
have its column, making even the login/website shell return HTTP 500.

The public field names are preserved for ClinicOne compatibility, but they are
non-stored computed proxies backed by ``ir.config_parameter`` keys that include
the company id.  This keeps the API human-friendly and multi-company while
making source replacement safe before the module upgrade has synchronized the
rest of the eMAR schema.
"""

from __future__ import annotations

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


_PARAM_PREFIX = "clinic_emar.company"

_CONFIG_SPECS = {
    "emar_default_warehouse_id": ("default_warehouse_id", "many2one", False),
    "emar_auto_generate_schedules": ("auto_generate_schedules", "bool", True),
    "emar_require_patient_scan": ("require_patient_scan", "bool", False),
    "emar_require_product_scan": ("require_product_scan", "bool", False),
    "emar_require_double_check_high_alert": (
        "require_double_check_high_alert",
        "bool",
        True,
    ),
    "emar_overdue_grace_minutes": ("overdue_grace_minutes", "int", 30),
}


def _as_bool(value, default=False):
    """Convert an ``ir.config_parameter`` value to bool deterministically."""
    if value in (None, False, ""):
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value, default=0):
    """Convert an ``ir.config_parameter`` value to a non-negative integer."""
    if value in (None, False, ""):
        return int(default)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return int(default)


class ResCompany(models.Model):
    _inherit = "res.company"

    # ------------------------------------------------------------------
    # Public compatibility API
    # ------------------------------------------------------------------
    # Keep the established field names because core eMAR workflows access
    # ``company_id.emar_*`` directly.  ``store=False`` is intentional and is a
    # hard runtime-safety contract: these fields must never become physical
    # columns on res_company again.
    emar_default_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="eMAR Default Warehouse",
        compute="_compute_emar_configuration",
        store=False,
        check_company=True,
    )
    emar_auto_generate_schedules = fields.Boolean(
        string="Auto-generate eMAR Schedules",
        compute="_compute_emar_configuration",
        store=False,
    )
    emar_require_patient_scan = fields.Boolean(
        string="Require Patient Barcode Verification",
        compute="_compute_emar_configuration",
        store=False,
    )
    emar_require_product_scan = fields.Boolean(
        string="Require Medication Barcode Verification",
        compute="_compute_emar_configuration",
        store=False,
    )
    emar_require_double_check_high_alert = fields.Boolean(
        string="Require Independent Check for High-alert Medication",
        compute="_compute_emar_configuration",
        store=False,
    )
    emar_overdue_grace_minutes = fields.Integer(
        string="eMAR Overdue Grace (minutes)",
        compute="_compute_emar_configuration",
        store=False,
    )

    # ------------------------------------------------------------------
    # Parameter helpers
    # ------------------------------------------------------------------
    def _emar_parameter_key(self, suffix):
        self.ensure_one()
        if not self.id:
            return False
        return f"{_PARAM_PREFIX}.{self.id}.{suffix}"

    def _emar_read_parameter_values(self):
        """Return one normalized configuration dictionary for this company."""
        self.ensure_one()
        if not self.id:
            return {
                "emar_default_warehouse_id": False,
                "emar_auto_generate_schedules": True,
                "emar_require_patient_scan": False,
                "emar_require_product_scan": False,
                "emar_require_double_check_high_alert": True,
                "emar_overdue_grace_minutes": 30,
            }

        Param = self.env["ir.config_parameter"].sudo()
        raw = {}
        for field_name, (suffix, _kind, _default) in _CONFIG_SPECS.items():
            raw[field_name] = Param.get_param(self._emar_parameter_key(suffix))

        warehouse = self.env["stock.warehouse"].sudo()
        warehouse_id = _as_int(raw["emar_default_warehouse_id"], 0)
        if warehouse_id:
            warehouse = warehouse.browse(warehouse_id).exists()
            if warehouse and warehouse.company_id != self:
                # Never leak a warehouse from another company because somebody
                # manually edited the config parameter.
                warehouse = self.env["stock.warehouse"]
        else:
            warehouse = self.env["stock.warehouse"]

        return {
            "emar_default_warehouse_id": warehouse,
            "emar_auto_generate_schedules": _as_bool(
                raw["emar_auto_generate_schedules"], True
            ),
            "emar_require_patient_scan": _as_bool(
                raw["emar_require_patient_scan"], False
            ),
            "emar_require_product_scan": _as_bool(
                raw["emar_require_product_scan"], False
            ),
            "emar_require_double_check_high_alert": _as_bool(
                raw["emar_require_double_check_high_alert"], True
            ),
            "emar_overdue_grace_minutes": _as_int(
                raw["emar_overdue_grace_minutes"], 30
            ),
        }

    def _emar_write_parameter_values(self, values):
        """Persist normalized eMAR settings for each company in ``self``.

        This method is intentionally explicit instead of allowing arbitrary
        writes to ``ir.config_parameter`` from unrelated code.
        """
        allowed = set(_CONFIG_SPECS)
        unknown = set(values) - allowed
        if unknown:
            raise ValidationError(
                _("Unsupported eMAR configuration key(s): %s")
                % ", ".join(sorted(unknown))
            )

        Param = self.env["ir.config_parameter"].sudo()
        for company in self:
            if not company.id:
                continue

            if "emar_default_warehouse_id" in values:
                warehouse_value = values["emar_default_warehouse_id"]
                warehouse = (
                    self.env["stock.warehouse"].browse(warehouse_value)
                    if isinstance(warehouse_value, int)
                    else warehouse_value
                )
                warehouse = warehouse.exists() if warehouse else self.env["stock.warehouse"]
                if warehouse and warehouse.company_id != company:
                    raise ValidationError(
                        _(
                            "The eMAR default warehouse must belong to company %s."
                        )
                        % company.display_name
                    )
                Param.set_param(
                    company._emar_parameter_key("default_warehouse_id"),
                    warehouse.id if warehouse else "",
                )

            bool_fields = (
                "emar_auto_generate_schedules",
                "emar_require_patient_scan",
                "emar_require_product_scan",
                "emar_require_double_check_high_alert",
            )
            for field_name in bool_fields:
                if field_name not in values:
                    continue
                suffix = _CONFIG_SPECS[field_name][0]
                Param.set_param(
                    company._emar_parameter_key(suffix),
                    "1" if bool(values[field_name]) else "0",
                )

            if "emar_overdue_grace_minutes" in values:
                grace = _as_int(values["emar_overdue_grace_minutes"], 30)
                Param.set_param(
                    company._emar_parameter_key("overdue_grace_minutes"),
                    str(grace),
                )

            # ``ir.config_parameter`` is outside the dependency graph of the
            # non-stored proxy fields, so clear their ORM cache explicitly.
            company.invalidate_recordset(list(_CONFIG_SPECS))
        return True

    # ------------------------------------------------------------------
    # Non-stored proxy computation
    # ------------------------------------------------------------------
    @api.depends_context("uid")
    def _compute_emar_configuration(self):
        for company in self:
            values = company._emar_read_parameter_values()
            company.emar_default_warehouse_id = values[
                "emar_default_warehouse_id"
            ]
            company.emar_auto_generate_schedules = values[
                "emar_auto_generate_schedules"
            ]
            company.emar_require_patient_scan = values[
                "emar_require_patient_scan"
            ]
            company.emar_require_product_scan = values[
                "emar_require_product_scan"
            ]
            company.emar_require_double_check_high_alert = values[
                "emar_require_double_check_high_alert"
            ]
            company.emar_overdue_grace_minutes = values[
                "emar_overdue_grace_minutes"
            ]


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # These are ordinary transient fields.  They are loaded/saved explicitly
    # below so no physical ``res_company.emar_*`` column is required.
    emar_default_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="eMAR Default Warehouse",
        check_company=True,
    )
    emar_auto_generate_schedules = fields.Boolean(
        string="Auto-generate eMAR Schedules",
    )
    emar_require_patient_scan = fields.Boolean(
        string="Require Patient Barcode Verification",
    )
    emar_require_product_scan = fields.Boolean(
        string="Require Medication Barcode Verification",
    )
    emar_require_double_check_high_alert = fields.Boolean(
        string="Require Independent Check for High-alert Medication",
    )
    emar_overdue_grace_minutes = fields.Integer(
        string="eMAR Overdue Grace (minutes)",
    )

    @api.model
    def get_values(self):
        values = super().get_values()
        company = self.env.company
        config = company._emar_read_parameter_values()
        values.update(
            {
                "emar_default_warehouse_id": (
                    config["emar_default_warehouse_id"].id
                    if config["emar_default_warehouse_id"]
                    else False
                ),
                "emar_auto_generate_schedules": config[
                    "emar_auto_generate_schedules"
                ],
                "emar_require_patient_scan": config[
                    "emar_require_patient_scan"
                ],
                "emar_require_product_scan": config[
                    "emar_require_product_scan"
                ],
                "emar_require_double_check_high_alert": config[
                    "emar_require_double_check_high_alert"
                ],
                "emar_overdue_grace_minutes": config[
                    "emar_overdue_grace_minutes"
                ],
            }
        )
        return values

    def set_values(self):
        super().set_values()
        if not self.env.is_superuser() and not self.env.user.has_group(
            "clinic_emar.group_emar_manager"
        ):
            raise AccessError(
                _("Only an eMAR Manager may change medication administration settings.")
            )

        for wizard in self:
            company = wizard.company_id or self.env.company
            company._emar_write_parameter_values(
                {
                    "emar_default_warehouse_id": wizard.emar_default_warehouse_id,
                    "emar_auto_generate_schedules": wizard.emar_auto_generate_schedules,
                    "emar_require_patient_scan": wizard.emar_require_patient_scan,
                    "emar_require_product_scan": wizard.emar_require_product_scan,
                    "emar_require_double_check_high_alert": (
                        wizard.emar_require_double_check_high_alert
                    ),
                    "emar_overdue_grace_minutes": wizard.emar_overdue_grace_minutes,
                }
            )
        return True
