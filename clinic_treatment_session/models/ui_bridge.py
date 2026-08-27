# -*- coding: utf-8 -*-

"""Optional cross-addon form decorations.

ClinicOne databases can have older ir.model.data/view layouts while the source
tree is newer. Presentation smart buttons must therefore never block this
business addon from installing/upgrading.
"""

import logging

from odoo import api, models


_logger = logging.getLogger(__name__)


BRIDGES = (
    {
        "model": "booking.booking",
        "preferred_xmlid": "clinic_booking.view_booking_booking_form",
        "view_name": "booking.booking.form",
        "local_name": "view_booking_form_treatment_session_runtime",
        "arch": """
            <data>
                <xpath expr="//div[@name='button_box']" position="inside">
                    <button name="action_view_treatment_sessions"
                            type="object"
                            class="oe_stat_button"
                            icon="fa-stethoscope"
                            groups="clinic_treatment_session.group_treatment_session_user">
                        <field name="treatment_session_count"
                               widget="statinfo"
                               string="Treatment Sessions"/>
                    </button>
                </xpath>
            </data>
        """,
    },
    {
        "model": "clinic.patient",
        "preferred_xmlid": "clinic_patient.view_clinic_patient_form",
        "view_name": "clinic.patient.form",
        "local_name": "view_patient_form_treatment_session_runtime",
        "arch": """
            <data>
                <xpath expr="//div[@name='button_box']" position="inside">
                    <button name="action_view_treatment_sessions"
                            type="object"
                            class="oe_stat_button"
                            icon="fa-stethoscope"
                            groups="clinic_treatment_session.group_treatment_session_user">
                        <field name="treatment_session_count"
                               widget="statinfo"
                               string="Treatment Sessions"/>
                    </button>
                </xpath>
            </data>
        """,
    },
    {
        "model": "clinic.doctor",
        "preferred_xmlid": "clinic_doctor.view_clinic_doctor_form",
        "view_name": "clinic.doctor.form",
        "local_name": "view_doctor_form_treatment_session_runtime",
        "arch": """
            <data>
                <xpath expr="//div[@name='button_box']" position="inside">
                    <button name="action_view_treatment_sessions"
                            type="object"
                            class="oe_stat_button"
                            icon="fa-stethoscope"
                            groups="clinic_treatment_session.group_treatment_session_user">
                        <field name="treatment_session_count"
                               widget="statinfo"
                               string="Treatment Sessions"/>
                    </button>
                </xpath>
            </data>
        """,
    },
    {
        "model": "clinic.encounter",
        "preferred_xmlid": "clinic_encounter.view_clinic_encounter_form",
        "view_name": "clinic.encounter.form",
        "local_name": "view_encounter_form_treatment_session_runtime",
        "arch": """
            <data>
                <xpath expr="//div[@name='button_box']" position="inside">
                    <button name="action_view_treatment_sessions"
                            type="object"
                            class="oe_stat_button"
                            icon="fa-stethoscope"
                            groups="clinic_treatment_session.group_treatment_session_user">
                        <field name="treatment_session_count"
                               widget="statinfo"
                               string="Treatment Sessions"/>
                    </button>
                </xpath>
            </data>
        """,
    },
    {
        "model": "clinic.branch",
        "preferred_xmlid": "clinic_branch.view_clinic_branch_form",
        "view_name": "clinic.branch.form",
        "local_name": "view_branch_form_treatment_session_runtime",
        "arch": """
            <data>
                <xpath expr="//div[@name='button_box']" position="inside">
                    <button name="action_view_treatment_sessions"
                            type="object"
                            class="oe_stat_button"
                            icon="fa-stethoscope"
                            groups="clinic_treatment_session.group_treatment_session_user">
                        <field name="treatment_session_count"
                               widget="statinfo"
                               string="Treatment Sessions"/>
                    </button>
                </xpath>
            </data>
        """,
    },
)


class ClinicTreatmentSessionUiBridge(models.Model):
    """Install optional presentation bridges idempotently."""

    _inherit = "clinic.treatment.session"

    @api.model
    def _find_bridge_parent(
        self,
        model_name,
        preferred_xmlid,
        preferred_view_name,
    ):
        parent = self.env.ref(
            preferred_xmlid,
            raise_if_not_found=False,
        )
        if (
            parent
            and parent._name == "ir.ui.view"
            and parent.model == model_name
        ):
            return parent

        View = self.env["ir.ui.view"].sudo()
        parent = View.search(
            [
                ("model", "=", model_name),
                ("type", "=", "form"),
                ("name", "=", preferred_view_name),
                ("active", "=", True),
            ],
            order="priority,id",
            limit=1,
        )
        if parent:
            return parent

        candidates = View.search(
            [
                ("model", "=", model_name),
                ("type", "=", "form"),
                ("active", "=", True),
            ],
            order="priority,id",
        )
        for candidate in candidates:
            try:
                combined = candidate._get_combined_arch()
            except Exception:
                continue
            if (
                getattr(combined, "tag", None) == "form"
                and combined.xpath(".//div[@name='button_box']")
            ):
                return candidate

        return View.browse()

    @api.model
    def _upsert_bridge(self, spec):
        parent = self._find_bridge_parent(
            spec["model"],
            spec["preferred_xmlid"],
            spec["view_name"],
        )
        if not parent:
            _logger.warning(
                "Treatment Session UI bridge skipped for %s: "
                "no compatible form view.",
                spec["model"],
            )
            return False

        try:
            combined = parent._get_combined_arch()
            if not combined.xpath(".//div[@name='button_box']"):
                _logger.warning(
                    "Treatment Session UI bridge skipped for %s: "
                    "no button_box anchor.",
                    spec["model"],
                )
                return False
        except Exception:
            _logger.exception(
                "Treatment Session UI bridge parent validation failed for %s.",
                spec["model"],
            )
            return False

        View = self.env["ir.ui.view"].sudo()
        XmlId = self.env["ir.model.data"].sudo()

        xmlid = XmlId.search(
            [
                ("module", "=", "clinic_treatment_session"),
                ("name", "=", spec["local_name"]),
                ("model", "=", "ir.ui.view"),
            ],
            limit=1,
        )
        view = (
            View.browse(xmlid.res_id).exists()
            if xmlid
            else View.search(
                [
                    ("name", "=", spec["local_name"]),
                    ("model", "=", spec["model"]),
                ],
                limit=1,
            )
        )

        values = {
            "name": spec["local_name"],
            "model": spec["model"],
            "inherit_id": parent.id,
            "priority": 90,
            "arch_db": spec["arch"],
            "active": True,
        }

        try:
            with self.env.cr.savepoint():
                if view:
                    view.write(values)
                else:
                    view = View.create(values)

                if xmlid:
                    if xmlid.res_id != view.id:
                        xmlid.write(
                            {
                                "res_id": view.id,
                                "noupdate": False,
                            }
                        )
                else:
                    XmlId.create(
                        {
                            "module": "clinic_treatment_session",
                            "name": spec["local_name"],
                            "model": "ir.ui.view",
                            "res_id": view.id,
                            "noupdate": False,
                        }
                    )
        except Exception:
            _logger.exception(
                "Treatment Session optional UI bridge failed for %s; "
                "core addon continues.",
                spec["model"],
            )
            return False

        return True

    @api.model
    def _ensure_optional_cross_addon_ui(self):
        for spec in BRIDGES:
            self._upsert_bridge(spec)
        return True
