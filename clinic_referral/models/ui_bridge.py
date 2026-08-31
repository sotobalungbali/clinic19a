# -*- coding: utf-8 -*-
"""Runtime-safe optional UI bridges for Clinic Referral.

Why this exists
---------------
ClinicOne is upgraded addon-by-addon. An installed upstream addon can therefore
have a valid business model but an older database view/XML-ID layout than the
source currently present on disk.

A hard XML ``inherit_id`` is evaluated while module data is loading. If the
foreign parent cannot be resolved, Odoo aborts the entire Referral upgrade.
Patient/Branch smart buttons are presentation integrations, so they must never
be allowed to block the Referral business workflow.

This module follows the same defensive pattern already used by
``clinic_triage_vitals`` and ``clinic_package``:
- prefer the expected external ID;
- fall back to an installed technical form view;
- validate the required XPath anchor against combined architecture;
- create/update the local extension inside a savepoint;
- log and skip an incompatible decoration without weakening business security.
"""

import logging

from odoo import api, models


_logger = logging.getLogger(__name__)


PATIENT_VIEW_ARCH = """
<data>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_open_referrals"
                type="object"
                class="oe_stat_button"
                icon="fa-share-alt"
                groups="clinic_referral.group_referral_user">
            <field name="referral_count"
                   widget="statinfo"
                   string="Inbound Referrals"/>
        </button>
        <button name="action_open_outgoing_referrals"
                type="object"
                class="oe_stat_button"
                icon="fa-users"
                groups="clinic_referral.group_referral_user">
            <field name="outgoing_referral_count"
                   widget="statinfo"
                   string="Referrals Made"/>
        </button>
    </xpath>
</data>
"""


BRANCH_VIEW_ARCH = """
<data>
    <xpath expr="//div[@name='button_box']" position="inside">
        <button name="action_open_referrals"
                type="object"
                class="oe_stat_button"
                icon="fa-share-alt"
                groups="clinic_referral.group_referral_user">
            <field name="referral_count"
                   widget="statinfo"
                   string="Referrals"/>
        </button>
    </xpath>
</data>
"""


class ClinicReferralSourceUiBridge(models.Model):
    """Install optional ClinicOne presentation bridges idempotently."""

    _inherit = "clinic.referral.source"

    @api.model
    def _find_usable_form_parent(
        self,
        *,
        model_name,
        preferred_xmlid,
        preferred_view_name,
    ):
        """Return a usable installed form view without requiring one XML-ID."""
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

        # Source/database XML-ID drift often leaves the actual view record
        # intact. Stable technical view name is therefore the first fallback.
        parent = View.search(
            [
                ("model", "=", model_name),
                ("type", "=", "form"),
                ("name", "=", preferred_view_name),
                ("active", "=", True),
            ],
            order="priority, id",
            limit=1,
        )
        if parent:
            return parent

        # Match the proven ClinicOne triage fallback: prefer the primary
        # installed form, but do not require inherit_id=False because old
        # databases can have different primary/inheritance bookkeeping.
        parent = View.search(
            [
                ("model", "=", model_name),
                ("type", "=", "form"),
                ("mode", "=", "primary"),
                ("active", "=", True),
            ],
            order="priority, id",
            limit=1,
        )
        if parent:
            return parent

        # Last presentation-only fallback: an active form whose combined
        # architecture is a real <form>. This still avoids selecting blindly.
        candidates = View.search(
            [
                ("model", "=", model_name),
                ("type", "=", "form"),
                ("active", "=", True),
            ],
            order="priority, id",
        )
        for candidate in candidates:
            try:
                combined = candidate._get_combined_arch()
            except Exception:
                continue
            if getattr(combined, "tag", None) == "form":
                return candidate

        return View.browse()

    @api.model
    def _parent_supports_button_box(self, parent):
        """Validate the single anchor used by Referral smart-button bridges."""
        try:
            combined = parent._get_combined_arch()
        except Exception:
            _logger.exception(
                "Clinic Referral could not build combined architecture for %s.",
                parent.display_name,
            )
            return False

        return bool(
            getattr(combined, "xpath", None)
            and combined.xpath(".//div[@name='button_box']")
        )

    @api.model
    def _get_existing_optional_view(
        self,
        *,
        local_xmlid_name,
        view_name,
        model_name,
    ):
        """Resolve an existing local extension via XML-ID or stable view name."""
        XmlId = self.env["ir.model.data"].sudo()
        View = self.env["ir.ui.view"].sudo()

        xmlid_row = XmlId.search(
            [
                ("module", "=", "clinic_referral"),
                ("name", "=", local_xmlid_name),
                ("model", "=", "ir.ui.view"),
            ],
            limit=1,
        )

        if xmlid_row:
            view = View.browse(xmlid_row.res_id).exists()
            if view:
                return view, xmlid_row

        view = View.search(
            [
                ("name", "=", view_name),
                ("model", "=", model_name),
            ],
            limit=1,
        )
        return view, xmlid_row

    @api.model
    def _upsert_optional_form_bridge(
        self,
        *,
        model_name,
        preferred_xmlid,
        preferred_view_name,
        local_xmlid_name,
        local_view_name,
        arch_db,
    ):
        """Create/update one optional inherited form without load-time fragility."""
        parent = self._find_usable_form_parent(
            model_name=model_name,
            preferred_xmlid=preferred_xmlid,
            preferred_view_name=preferred_view_name,
        )

        if not parent:
            _logger.warning(
                "Clinic Referral UI bridge skipped: no installed %s form view "
                "is available. Core Referral functions remain installed.",
                model_name,
            )
            return False

        if not self._parent_supports_button_box(parent):
            _logger.warning(
                "Clinic Referral UI bridge skipped: %s parent %s has no "
                "button_box anchor. Core Referral functions remain installed.",
                model_name,
                parent.display_name,
            )
            return False

        View = self.env["ir.ui.view"].sudo()
        XmlId = self.env["ir.model.data"].sudo()

        view, xmlid_row = self._get_existing_optional_view(
            local_xmlid_name=local_xmlid_name,
            view_name=local_view_name,
            model_name=model_name,
        )

        values = {
            "name": local_view_name,
            "model": model_name,
            "inherit_id": parent.id,
            "priority": 90,
            "arch_db": arch_db,
            "active": True,
        }

        try:
            # View validation can fail when a historical parent layout differs.
            # The savepoint guarantees this optional decoration cannot roll
            # back the Referral business-domain upgrade.
            with self.env.cr.savepoint():
                if view:
                    view.write(values)
                else:
                    view = View.create(values)

                if xmlid_row:
                    if xmlid_row.res_id != view.id:
                        xmlid_row.write(
                            {
                                "res_id": view.id,
                                "noupdate": False,
                            }
                        )
                else:
                    XmlId.create(
                        {
                            "module": "clinic_referral",
                            "name": local_xmlid_name,
                            "model": "ir.ui.view",
                            "res_id": view.id,
                            "noupdate": False,
                        }
                    )
        except Exception:
            _logger.exception(
                "Clinic Referral optional UI bridge %s failed validation. "
                "The bridge was skipped; core Referral installation continues.",
                local_xmlid_name,
            )
            return False

        _logger.info(
            "Clinic Referral UI bridge %s active on parent %s.",
            local_xmlid_name,
            parent.display_name,
        )
        return True

    @api.model
    def _find_patient_root_menu(self):
        """Find a compatible installed Patient/ClinicOne root menu safely."""
        preferred = self.env.ref(
            "clinic_patient.menu_root",
            raise_if_not_found=False,
        )
        if preferred and preferred._name == "ir.ui.menu":
            return preferred

        XmlId = self.env["ir.model.data"].sudo()
        Menu = self.env["ir.ui.menu"].sudo()

        rows = XmlId.search(
            [
                ("module", "=", "clinic_patient"),
                ("model", "=", "ir.ui.menu"),
            ]
        )
        menus = Menu.browse(rows.mapped("res_id")).exists()
        roots = menus.filtered(lambda menu: not menu.parent_id)

        if len(roots) == 1:
            return roots

        named = roots.filtered(
            lambda menu: menu.name in {
                "ClinicOne",
                "Patients",
                "Patient Management",
            }
        )
        if named:
            return named[:1]

        # Final safe presentation fallback: an existing top-level ClinicOne
        # menu can host Referral. If ambiguous, do not guess.
        named_global = Menu.search(
            [
                ("name", "=", "ClinicOne"),
                ("parent_id", "=", False),
            ],
            limit=1,
        )
        return named_global

    @api.model
    def _ensure_referral_menu_parent(self):
        """Reparent local Referral root only when a compatible menu exists."""
        local_menu = self.env.ref(
            "clinic_referral.menu_referral_root",
            raise_if_not_found=False,
        )
        if not local_menu:
            _logger.warning(
                "Clinic Referral local root menu is unavailable; "
                "menu reparenting skipped."
            )
            return False

        parent = self._find_patient_root_menu()
        if not parent:
            _logger.warning(
                "No compatible Clinic Patient/ClinicOne root menu exists. "
                "Referral remains available as its own top-level app."
            )
            return False

        if local_menu.parent_id != parent:
            local_menu.sudo().write(
                {"parent_id": parent.id}
            )

        return True

    @api.model
    def _ensure_optional_cross_addon_ui(self):
        """Install presentation bridges without hard cross-addon XML coupling."""
        bridge_specs = (
            {
                "model_name": "clinic.patient",
                "preferred_xmlid": (
                    "clinic_patient."
                    "view_clinic_patient_form"
                ),
                "preferred_view_name": "clinic.patient.form",
                "local_xmlid_name": "view_patient_form_referral",
                "local_view_name": "clinic.patient.form.referral",
                "arch_db": PATIENT_VIEW_ARCH,
            },
            {
                "model_name": "clinic.branch",
                "preferred_xmlid": (
                    "clinic_branch."
                    "view_clinic_branch_form"
                ),
                "preferred_view_name": "clinic.branch.form",
                "local_xmlid_name": "view_branch_form_referral",
                "local_view_name": "clinic.branch.form.referral",
                "arch_db": BRANCH_VIEW_ARCH,
            },
        )

        for spec in bridge_specs:
            self._upsert_optional_form_bridge(**spec)

        try:
            with self.env.cr.savepoint():
                self._ensure_referral_menu_parent()
        except Exception:
            _logger.exception(
                "Clinic Referral menu reparenting failed. "
                "Referral remains available from its local root menu."
            )

        return True

