from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicPortalProfile(models.Model):
    """Staff-governed access profile for one patient contact in one company.

    Native Odoo remains the authentication and portal-user owner. This model
    governs which ClinicOne patient surfaces are enabled after authentication.
    """

    _name = "clinic.portal.profile"
    _description = "Clinic Patient Portal Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "partner_id, company_id, id"
    _check_company_auto = True

    _partner_company_unique = models.Constraint(
        "UNIQUE(company_id, partner_id)",
        "Only one Clinic Portal Profile is allowed per patient and company.",
    )
    _company_state_idx = models.Index("(company_id, state, partner_id)")

    name = fields.Char(
        compute="_compute_name",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Patient Contact",
        required=True,
        ondelete="cascade",
        domain="[('is_patient', '=', True)]",
        index=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        related="partner_id.patient_id",
        string="Patient Card",
        store=True,
        readonly=True,
        index=True,
    )
    portal_user_id = fields.Many2one(
        "res.users",
        string="Portal User",
        compute="_compute_portal_user",
        compute_sudo=True,
    )
    is_portal_user = fields.Boolean(
        compute="_compute_portal_user",
        compute_sudo=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("archived", "Archived"),
        ],
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    allow_booking_view = fields.Boolean(
        string="Bookings",
        default=True,
        tracking=True,
    )
    allow_invoice_view = fields.Boolean(
        string="Invoices",
        default=True,
        tracking=True,
    )
    allow_treatment_history_view = fields.Boolean(
        string="Treatment History",
        default=True,
        tracking=True,
    )

    show_wallet_link = fields.Boolean(
        string="Wallet Shortcut",
        default=True,
    )
    show_consent_link = fields.Boolean(
        string="Consent Shortcut",
        default=True,
    )
    show_order_link = fields.Boolean(
        string="Orders Shortcut",
        default=True,
    )
    show_shop_link = fields.Boolean(
        string="Book / Buy Services Shortcut",
        default=True,
    )

    last_access_at = fields.Datetime(
        readonly=True,
        index=True,
    )
    last_access_page = fields.Selection(
        [
            ("home", "Clinic Home"),
            ("bookings", "Bookings"),
            ("booking", "Booking Detail"),
            ("invoices", "Invoices"),
            ("invoice", "Invoice Detail"),
            ("treatments", "Treatment History"),
            ("treatment", "Treatment Detail"),
        ],
        readonly=True,
    )

    booking_count = fields.Integer(compute="_compute_counts")
    invoice_count = fields.Integer(compute="_compute_counts")
    treatment_count = fields.Integer(compute="_compute_counts")

    @api.depends("partner_id", "company_id")
    def _compute_name(self):
        for profile in self:
            if profile.partner_id:
                profile.name = _("%(patient)s - %(company)s") % {
                    "patient": profile.partner_id.display_name,
                    "company": profile.company_id.display_name,
                }
            else:
                profile.name = _("New Patient Portal Profile")

    @api.depends("partner_id", "partner_id.user_ids", "partner_id.user_ids.active")
    def _compute_portal_user(self):
        for profile in self:
            portal_users = profile.partner_id.user_ids.filtered(
                lambda user: user.active and user._is_portal()
            )
            profile.portal_user_id = portal_users[:1]
            profile.is_portal_user = bool(portal_users)

    @api.depends("partner_id", "company_id")
    def _compute_counts(self):
        Booking = self.env["booking.booking"].sudo()
        Billing = self.env["clinic.billing.invoice"].sudo()
        Encounter = self.env["clinic.encounter"].sudo()

        for profile in self:
            if not profile.partner_id or not profile.company_id:
                profile.booking_count = 0
                profile.invoice_count = 0
                profile.treatment_count = 0
                continue

            partner_id = profile.partner_id.id
            company_id = profile.company_id.id

            profile.booking_count = Booking.search_count([
                ("company_id", "=", company_id),
                ("patient_id", "=", partner_id),
            ])
            profile.invoice_count = Billing.search_count([
                ("company_id", "=", company_id),
                ("patient_id", "=", partner_id),
                ("state", "in", ("confirmed", "posted", "paid")),
            ])
            profile.treatment_count = Encounter.search_count([
                ("company_id", "=", company_id),
                ("partner_id", "=", partner_id),
                ("state", "=", "done"),
            ])

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = self.env["res.company"].browse(
                vals.get("company_id")
            ) or self.env.company

            vals.setdefault(
                "allow_booking_view",
                company.clinic_portal_default_booking_view,
            )
            vals.setdefault(
                "allow_invoice_view",
                company.clinic_portal_default_invoice_view,
            )
            vals.setdefault(
                "allow_treatment_history_view",
                company.clinic_portal_default_treatment_view,
            )
            vals.setdefault(
                "show_wallet_link",
                company.clinic_portal_show_wallet_link,
            )
            vals.setdefault(
                "show_consent_link",
                company.clinic_portal_show_consent_link,
            )
            vals.setdefault(
                "show_order_link",
                company.clinic_portal_show_order_link,
            )
            vals.setdefault(
                "show_shop_link",
                company.clinic_portal_show_shop_link,
            )

            if (
                vals.get("state", "draft") != "draft"
                and not self.env.context.get("portal_profile_transition")
            ):
                raise AccessError(
                    _("Use Portal Profile workflow actions to activate access.")
                )

            prepared.append(vals)

        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)

        if self.env.context.get("portal_runtime_access"):
            allowed = {"last_access_at", "last_access_page"}
            if set(vals) - allowed:
                raise AccessError(
                    _("Portal runtime may update only access telemetry fields.")
                )

        if (
            "state" in vals
            and not self.env.context.get("portal_profile_transition")
        ):
            raise AccessError(
                _("Use Portal Profile workflow actions to change access state.")
            )

        return super().write(vals)

    @api.constrains("company_id", "partner_id", "patient_id")
    def _check_patient_scope(self):
        for profile in self:
            if not profile.partner_id.is_patient:
                raise ValidationError(
                    _("Clinic Portal Profiles require a patient contact.")
                )
            if not profile.patient_id:
                raise ValidationError(
                    _("Patient Contact must have a linked Clinic Patient Card.")
                )
            if profile.patient_id.partner_id != profile.partner_id:
                raise ValidationError(
                    _("Patient Card and Patient Contact linkage is inconsistent.")
                )
            if (
                profile.patient_id.company_id
                and profile.patient_id.company_id != profile.company_id
            ):
                raise ValidationError(
                    _("Portal Profile company must match the Patient Card company.")
                )

    def _require_manager(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_portal.group_patient_portal_manager"
        ):
            raise AccessError(
                _("Only a Patient Portal Manager can change portal access.")
            )
        return True

    def action_activate(self):
        self._require_manager()
        for profile in self:
            if not profile.patient_id:
                raise UserError(
                    _("Link a Patient Card before activating the Portal Profile.")
                )
            if not profile.is_portal_user:
                raise UserError(
                    _(
                        "The patient does not yet have active native Odoo Portal "
                        "access. Open Portal Access Management first."
                    )
                )
        self.with_context(portal_profile_transition=True).write({
            "state": "active",
            "active": True,
        })
        return True

    def action_suspend(self):
        self._require_manager()
        self.with_context(portal_profile_transition=True).write({
            "state": "suspended",
        })
        return True

    def action_archive(self):
        self._require_manager()
        self.with_context(portal_profile_transition=True).write({
            "state": "archived",
            "active": False,
        })
        return True

    def action_reset_to_draft(self):
        self._require_manager()
        self.with_context(portal_profile_transition=True).write({
            "state": "draft",
            "active": True,
        })
        return True

    def action_open_portal_access_management(self):
        self.ensure_one()
        self._require_manager()
        return self.env["portal.wizard"].with_context(
            default_partner_ids=self.partner_id.ids,
            active_ids=self.partner_id.ids,
            active_model="res.partner",
        ).action_open_wizard()

    def action_open_partner(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Contact"),
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.partner_id.id,
        }

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Card"),
            "res_model": "clinic.patient",
            "view_mode": "form",
            "res_id": self.patient_id.id,
        }

    def action_open_portal_user(self):
        self.ensure_one()
        if not self.portal_user_id:
            raise UserError(_("This patient has no active Portal User."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Portal User"),
            "res_model": "res.users",
            "view_mode": "form",
            "res_id": self.portal_user_id.id,
        }

    def action_open_bookings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Bookings"),
            "res_model": "booking.booking",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("patient_id", "=", self.partner_id.id),
            ],
        }

    def action_open_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Clinic Invoices"),
            "res_model": "clinic.billing.invoice",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("patient_id", "=", self.partner_id.id),
            ],
        }

    def action_open_treatments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Treatment History"),
            "res_model": "clinic.encounter",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("partner_id", "=", self.partner_id.id),
                ("state", "=", "done"),
            ],
        }

    def action_open_portal_home(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/my/clinic",
            "target": "new",
        }

    def _record_portal_access(self, page):
        self.ensure_one()
        if page not in dict(self._fields["last_access_page"].selection):
            return False
        self.sudo().with_context(portal_runtime_access=True).write({
            "last_access_at": fields.Datetime.now(),
            "last_access_page": page,
        })
        return True

    @api.model
    def _find_for_user(self, user, company):
        """Find an existing exact-patient profile without performing writes.

        This helper is safe for Odoo's read-only `/my/counters` JSON route.
        """
        user = user.exists()
        company = company.exists()
        if not user or not company:
            return self.browse()

        partner = user.partner_id
        patient = user.patient_id or partner.patient_id
        if (
            not user.active
            or not user._is_portal()
            or not partner
            or not patient
            or patient.partner_id != partner
            or patient.company_id != company
        ):
            return self.browse()

        return self.sudo().with_context(active_test=False).search([
            ("company_id", "=", company.id),
            ("partner_id", "=", partner.id),
        ], limit=1)

    @api.model
    def _seed_draft_for_user(self, user, company):
        """Seed a staff-reviewable Draft profile for an existing portal patient."""
        profile = self._find_for_user(user, company)
        if profile:
            return profile

        user = user.exists()
        company = company.exists()
        if not user or not company:
            return self.browse()

        partner = user.partner_id
        patient = user.patient_id or partner.patient_id
        if (
            not user.active
            or not user._is_portal()
            or not partner
            or not patient
            or patient.partner_id != partner
            or patient.company_id != company
        ):
            return self.browse()

        return self.sudo().create({
            "company_id": company.id,
            "partner_id": partner.id,
            "state": "draft",
        })

    @api.model
    def _ensure_for_user(self, user, company):
        """Return/create the user's own profile without granting authentication.

        A new profile is created only for an already-active native Portal User
        whose exact partner has a Clinic Patient Card in the selected company.
        """
        profile = self._find_for_user(user, company)
        if profile:
            return profile

        user = user.exists()
        company = company.exists()
        if not user or not company:
            return self.browse()

        partner = user.partner_id
        patient = user.patient_id or partner.patient_id
        if (
            not user.active
            or not user._is_portal()
            or not partner
            or not patient
            or patient.partner_id != partner
            or patient.company_id != company
            or not company.clinic_portal_auto_profile
        ):
            return self.browse()

        return self.sudo().with_context(
            portal_profile_transition=True
        ).create({
            "company_id": company.id,
            "partner_id": partner.id,
            "state": "active",
        })

    def _portal_booking_domain(self):
        self.ensure_one()
        return [
            ("company_id", "=", self.company_id.id),
            ("patient_id", "=", self.partner_id.id),
        ]

    def _portal_invoice_domain(self):
        self.ensure_one()
        return [
            ("company_id", "=", self.company_id.id),
            ("patient_id", "=", self.partner_id.id),
            ("state", "in", ("confirmed", "posted", "paid")),
        ]

    def _portal_treatment_domain(self):
        self.ensure_one()
        return [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "done"),
        ]

    def _portal_summary_counts(self):
        self.ensure_one()
        values = {
            "clinic_booking_count": 0,
            "clinic_invoice_count": 0,
            "clinic_treatment_count": 0,
        }

        if self.state != "active":
            return values

        if self.allow_booking_view:
            values["clinic_booking_count"] = self.env[
                "booking.booking"
            ].sudo().search_count(self._portal_booking_domain())

        if self.allow_invoice_view:
            values["clinic_invoice_count"] = self.env[
                "clinic.billing.invoice"
            ].sudo().search_count(self._portal_invoice_domain())

        if self.allow_treatment_history_view:
            values["clinic_treatment_count"] = self.env[
                "clinic.encounter"
            ].sudo().search_count(self._portal_treatment_domain())

        return values
