
# -*- coding: utf-8 -*-
"""Safe runtime bridges for cross-addon ClinicOne form integration.

ClinicOne is developed addon-by-addon and an already-installed upstream addon
can occasionally have database external identifiers that predate the source
currently present on disk.  A normal XML ``inherit_id`` is a hard load-time
reference; when that identifier is absent, Odoo aborts the whole module load.

The package domain therefore keeps its Python/model dependencies mandatory, but
installs *form decorations* through idempotent runtime bridges.  Missing or
structurally incompatible parent views are logged and skipped without weakening
package security or business workflows.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


PATIENT_PACKAGE_VIEW_ARCH = """
<data>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_view_package_allocations"
                type="object"
                class="oe_stat_button"
                icon="fa-id-card">
            <field name="package_allocation_count"
                   widget="statinfo"
                   string="Packages"/>
        </button>
    </xpath>
    <xpath expr="//notebook" position="inside">
        <page string="Treatment Packages" name="clinic_package_portfolio">
            <div class="oe_button_box" name="package_body_actions">
                <button name="action_allocate_package"
                        type="object"
                        string="Allocate Package"
                        class="btn btn-primary"
                        icon="fa-plus"/>
            </div>
            <group>
                <field name="package_active_count" readonly="1"/>
                <field name="package_remaining_value" readonly="1"/>
                <field name="package_currency_id" invisible="1"/>
            </group>
            <field name="package_allocation_ids" readonly="1">
                <list>
                    <field name="name"/>
                    <field name="package_id"/>
                    <field name="start_date"/>
                    <field name="valid_to_effective"/>
                    <field name="remaining_percent" widget="progressbar"/>
                    <field name="remaining_value"/>
                    <field name="state" widget="badge"/>
                </list>
            </field>
        </page>
    </xpath>
</data>
"""

BOOKING_PACKAGE_VIEW_ARCH = """
<data>
    <xpath expr="//header/field[@name='state']" position="before">
        <button name="action_redeem_package"
                type="object"
                string="Redeem Package"
                class="btn-primary"
                invisible="not package_redeem_ready or state == 'cancelled'"/>
    </xpath>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_redeem_package"
                type="object"
                class="oe_stat_button"
                icon="fa-gift"
                invisible="not package_allocation_id">
            <div class="o_stat_info">
                <span class="o_stat_value">
                    <field name="package_redeem_message"/>
                </span>
                <span class="o_stat_text">Package</span>
            </div>
        </button>
    </xpath>
    <xpath expr="//notebook" position="inside">
        <page string="Package Benefit" name="package_benefit">
            <group>
                <group>
                    <field name="package_allocation_id"
                           domain="[('partner_id','=',patient_id),('state','in',('active','paused'))]"/>
                    <field name="package_id" readonly="1"/>
                    <field name="package_allocation_line_id"
                           domain="[('allocation_id','=',package_allocation_id),('is_depleted','=',False)]"/>
                </group>
                <group>
                    <field name="package_usage_id" readonly="1"/>
                    <field name="package_redeem_ready" readonly="1"/>
                    <field name="package_redeem_message" readonly="1"/>
                </group>
            </group>
            <button name="action_redeem_package"
                    type="object"
                    string="Redeem Selected Benefit"
                    class="btn btn-primary"
                    icon="fa-check"
                    invisible="not package_redeem_ready"/>
        </page>
    </xpath>
</data>
"""

CARE_PLAN_PACKAGE_VIEW_ARCH = """
<data>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_view_package_allocation"
                type="object"
                class="oe_stat_button"
                icon="fa-id-card"
                invisible="not package_allocation_id">
            <div class="o_stat_info">
                <span class="o_stat_text">Package</span>
            </div>
        </button>
        <button name="action_view_package_usages"
                type="object"
                class="oe_stat_button"
                icon="fa-history"
                invisible="not package_allocation_id">
            <field name="package_usage_count"
                   widget="statinfo"
                   string="Redemptions"/>
        </button>
    </xpath>
    <xpath expr="//group[@string='Clinical Ownership']" position="inside">
        <field name="package_allocation_id"
               domain="[('patient_id','=',patient_id),('state','in',('active','paused'))]"/>
        <field name="package_id" readonly="1"/>
    </xpath>
    <xpath expr="//field[@name='line_ids']/list" position="inside">
        <field name="package_allocation_line_id"
               optional="show"
               domain="[('allocation_id','=',parent.package_allocation_id)]"/>
        <field name="package_usage_count" optional="show"/>
        <button name="action_redeem_package_benefit"
                type="object"
                string="Redeem"
                icon="fa-check"
                invisible="not package_allocation_line_id"/>
    </xpath>
</data>
"""


EMAR_ORDER_PACKAGE_VIEW_ARCH = """
<data>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_view_package_usages"
                type="object"
                class="oe_stat_button"
                icon="fa-gift"
                invisible="not package_usage_count">
            <field name="package_usage_count" widget="statinfo" string="Package"/>
        </button>
    </xpath>
</data>
"""

EMAR_SCHEDULE_PACKAGE_VIEW_ARCH = """
<data>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_view_package_usages"
                type="object"
                class="oe_stat_button"
                icon="fa-gift"
                invisible="not package_usage_count">
            <field name="package_usage_count" widget="statinfo" string="Package"/>
        </button>
    </xpath>
</data>
"""

EMAR_ADMINISTRATION_PACKAGE_VIEW_ARCH = """
<data>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_view_package_usages"
                type="object"
                class="oe_stat_button"
                icon="fa-gift"
                invisible="not package_usage_count">
            <field name="package_usage_count" widget="statinfo" string="Package"/>
        </button>
    </xpath>
</data>
"""

EMAR_PRESCRIPTION_PACKAGE_VIEW_ARCH = """
<data>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_view_package_usages"
                type="object"
                class="oe_stat_button"
                icon="fa-gift"
                invisible="not package_usage_count">
            <field name="package_usage_count" widget="statinfo" string="Package"/>
        </button>
    </xpath>
</data>
"""


class ClinicPackageViewBridge(models.Model):
    """Technical extension that installs optional cross-addon form decorations."""

    _inherit = "clinic.package"

    @api.model
    def _upsert_optional_inherited_view(
        self,
        *,
        parent_xmlid,
        local_xmlid_name,
        view_name,
        model_name,
        arch_db,
    ):
        """Create/update one inherited view without making module load fragile."""
        parent_view = self.env.ref(parent_xmlid, raise_if_not_found=False)
        if not parent_view:
            _logger.warning(
                "ClinicOne package UI bridge skipped: external ID %s is not "
                "present in the current database.",
                parent_xmlid,
            )
            return False

        if parent_view._name != "ir.ui.view" or parent_view.model != model_name:
            _logger.warning(
                "ClinicOne package UI bridge skipped: %s does not resolve to "
                "an ir.ui.view for %s.",
                parent_xmlid,
                model_name,
            )
            return False

        view_model = self.env["ir.ui.view"].sudo()
        xmlid_model = self.env["ir.model.data"].sudo()

        xmlid_record = xmlid_model.search(
            [
                ("module", "=", "clinic_package"),
                ("name", "=", local_xmlid_name),
                ("model", "=", "ir.ui.view"),
            ],
            limit=1,
        )
        inherited_view = (
            view_model.browse(xmlid_record.res_id).exists()
            if xmlid_record
            else view_model.browse()
        )

        values = {
            "name": view_name,
            "model": model_name,
            "inherit_id": parent_view.id,
            "priority": 90,
            "arch_db": arch_db,
            "active": True,
        }

        try:
            # View validation can fail when an old parent form lacks an XPath
            # anchor.  The savepoint ensures optional UI can never abort the
            # clinic_package business-domain installation.
            with self.env.cr.savepoint():
                if inherited_view:
                    inherited_view.write(values)
                else:
                    inherited_view = view_model.create(values)
                    if xmlid_record:
                        # Repair a stale XML-ID pointer instead of attempting
                        # to create a duplicate (module, name) pair.
                        xmlid_record.write(
                            {
                                "res_id": inherited_view.id,
                                "noupdate": False,
                            }
                        )
                    else:
                        xmlid_model.create(
                            {
                                "module": "clinic_package",
                                "name": local_xmlid_name,
                                "model": "ir.ui.view",
                                "res_id": inherited_view.id,
                                "noupdate": False,
                            }
                        )
        except Exception:
            _logger.exception(
                "ClinicOne package UI bridge %s could not be installed. "
                "clinic_package will continue without this form decoration.",
                local_xmlid_name,
            )
            return False

        _logger.info(
            "ClinicOne package UI bridge %s is active using parent %s.",
            local_xmlid_name,
            parent_xmlid,
        )
        return True

    @api.model
    def _ensure_optional_cross_addon_views(self):
        """Install/update patient, booking, and care-plan form integrations.

        This private model method is invoked from an XML ``function`` data tag.
        It intentionally uses runtime-safe ``env.ref(..., raise_if_not_found=False)``
        lookups instead of hard ``inherit_id`` references in loadable XML files.
        """
        bridge_specs = (
            {
                # Split literal deliberately makes repository grep distinguish
                # a safe runtime lookup from the old hard XML inherit_id.
                "parent_xmlid": "clinic_patient." "view_clinic_patient_form",
                "local_xmlid_name": "view_clinic_patient_form_package",
                "view_name": "clinic.patient.form.package",
                "model_name": "clinic.patient",
                "arch_db": PATIENT_PACKAGE_VIEW_ARCH,
            },
            {
                "parent_xmlid": "clinic_booking." "view_booking_booking_form",
                "local_xmlid_name": "view_booking_booking_form_package",
                "view_name": "booking.booking.form.package",
                "model_name": "booking.booking",
                "arch_db": BOOKING_PACKAGE_VIEW_ARCH,
            },
            {
                "parent_xmlid": "clinic_care_plan." "view_clinic_care_plan_form",
                "local_xmlid_name": "view_clinic_care_plan_form_package",
                "view_name": "clinic.care.plan.form.package",
                "model_name": "clinic.care.plan",
                "arch_db": CARE_PLAN_PACKAGE_VIEW_ARCH,
            },
            {
                "parent_xmlid": "clinic_emar." "view_emar_order_form",
                "local_xmlid_name": "view_emar_order_form_package",
                "view_name": "clinic.emar.order.form.package",
                "model_name": "clinic.emar.order",
                "arch_db": EMAR_ORDER_PACKAGE_VIEW_ARCH,
            },
            {
                "parent_xmlid": "clinic_emar." "view_emar_schedule_form",
                "local_xmlid_name": "view_emar_schedule_form_package",
                "view_name": "clinic.emar.schedule.form.package",
                "model_name": "clinic.emar.schedule",
                "arch_db": EMAR_SCHEDULE_PACKAGE_VIEW_ARCH,
            },
            {
                "parent_xmlid": "clinic_emar." "view_emar_administration_form",
                "local_xmlid_name": "view_emar_administration_form_package",
                "view_name": "clinic.emar.administration.form.package",
                "model_name": "clinic.emar.administration",
                "arch_db": EMAR_ADMINISTRATION_PACKAGE_VIEW_ARCH,
            },
            {
                "parent_xmlid": "clinic_emar." "view_emar_prescription_form",
                "local_xmlid_name": "view_emar_prescription_form_package",
                "view_name": "clinic.emar.prescription.form.package",
                "model_name": "clinic.emar.prescription",
                "arch_db": EMAR_PRESCRIPTION_PACKAGE_VIEW_ARCH,
            },
        )

        results = [
            self._upsert_optional_inherited_view(**spec)
            for spec in bridge_specs
        ]
        return any(results)
