from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicMarketingPromotion(models.Model):
    """Marketing presentation wrapper around owner-module commercial rules.

    No discount is calculated here. The selected Voucher / Pricelist / Package /
    eCommerce record remains the authoritative commercial rule.
    """

    _name = "clinic.marketing.promotion"
    _description = "Clinic Marketing Promotion"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "valid_from desc, sequence, name, id"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Marketing Promotion code must be unique per company.",
    )
    _date_order_valid = models.Constraint(
        "CHECK(valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)",
        "Promotion end date must be on or after its start date.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, branch_id, valid_from, valid_to)"
    )

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        domain="[('company_id', '=', company_id)]",
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    promotion_type = fields.Selection(
        [
            ("information", "Informational Promotion"),
            ("billing_voucher", "Billing Voucher Program"),
            ("package_voucher", "Package Voucher Batch"),
            ("treatment_price", "Treatment Pricelist Rule"),
            ("ecommerce", "Clinic eCommerce Offering"),
        ],
        default="information",
        required=True,
        tracking=True,
        index=True,
    )

    billing_voucher_program_id = fields.Many2one(
        "clinic.billing.voucher.program",
        string="Billing Voucher Program",
        ondelete="restrict",
        domain="[('company_id', '=', company_id)]",
    )
    package_voucher_batch_id = fields.Many2one(
        "clinic.package.voucher.batch",
        string="Package Voucher Batch",
        ondelete="restrict",
        domain="[('company_id', '=', company_id)]",
    )
    treatment_pricelist_item_id = fields.Many2one(
        "clinic.treatment.pricelist.item",
        string="Treatment Pricelist Rule",
        ondelete="restrict",
        domain="[('company_id', '=', company_id)]",
    )
    ecommerce_item_id = fields.Many2one(
        "clinic.ecommerce.catalog.item",
        string="Clinic eCommerce Offering",
        ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', '=', 'published')]",
    )

    valid_from = fields.Date(index=True)
    valid_to = fields.Date(index=True)
    headline = fields.Char(required=True)
    summary = fields.Text()
    terms_html = fields.Html()
    cta_label = fields.Char(string="Call-to-Action Label", default="Learn More")
    landing_url = fields.Char(
        help="Optional public destination. eCommerce Offering URL is used as fallback.",
    )
    image_1920 = fields.Image(max_width=1920, max_height=1920)

    source_display_name = fields.Char(
        compute="_compute_source_display_name",
        store=True,
    )
    campaign_ids = fields.One2many(
        "clinic.marketing.campaign",
        "promotion_id",
        string="Campaigns",
    )
    campaign_count = fields.Integer(compute="_compute_campaign_count")

    @api.depends(
        "promotion_type",
        "billing_voucher_program_id",
        "package_voucher_batch_id",
        "treatment_pricelist_item_id",
        "ecommerce_item_id",
    )
    def _compute_source_display_name(self):
        for record in self:
            source = record._source_record()
            record.source_display_name = source.display_name if source else _("Informational")

    def _compute_campaign_count(self):
        for record in self:
            record.campaign_count = len(record.campaign_ids)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("code"):
                vals["code"] = vals["code"].strip().upper()
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        if "state" in vals and not self.env.context.get("marketing_promotion_transition"):
            raise AccessError(_("Use Promotion workflow actions to change status."))
        if vals.get("code"):
            vals["code"] = vals["code"].strip().upper()
        return super().write(vals)

    @api.constrains(
        "company_id",
        "branch_id",
        "promotion_type",
        "billing_voucher_program_id",
        "package_voucher_batch_id",
        "treatment_pricelist_item_id",
        "ecommerce_item_id",
    )
    def _check_source_contract(self):
        mapping = {
            "billing_voucher": "billing_voucher_program_id",
            "package_voucher": "package_voucher_batch_id",
            "treatment_price": "treatment_pricelist_item_id",
            "ecommerce": "ecommerce_item_id",
        }
        all_fields = set(mapping.values())

        for record in self:
            if record.branch_id and record.branch_id.company_id != record.company_id:
                raise ValidationError(_("Promotion Branch must belong to its company."))

            required_field = mapping.get(record.promotion_type)
            populated = {
                field_name
                for field_name in all_fields
                if record[field_name]
            }

            if required_field and required_field not in populated:
                raise ValidationError(
                    _("Promotion type requires its matching owner-source record.")
                )
            if record.promotion_type == "information" and populated:
                raise ValidationError(
                    _("Informational Promotions cannot reference commercial owner rules.")
                )
            if required_field and populated != {required_field}:
                raise ValidationError(
                    _("A Promotion can reference only the owner source matching its type.")
                )

            source = record._source_record()
            if (
                source
                and "company_id" in source._fields
                and source.company_id
                and source.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Promotion source record belongs to another company.")
                )

    # The source record remains the commercial truth; this wrapper contributes presentation and campaign provenance only.
    def _source_record(self):
        self.ensure_one()
        mapping = {
            "billing_voucher": self.billing_voucher_program_id,
            "package_voucher": self.package_voucher_batch_id,
            "treatment_price": self.treatment_pricelist_item_id,
            "ecommerce": self.ecommerce_item_id,
        }
        return mapping.get(self.promotion_type) or self.env["ir.model"].browse()

    def _effective_landing_url(self):
        self.ensure_one()
        if self.landing_url:
            return self.landing_url
        if self.ecommerce_item_id:
            return self.ecommerce_item_id.website_url or "/clinic/shop"
        return False

    def _validate_source_ready(self):
        """Validate owner readiness without duplicating its commercial rules."""
        self.ensure_one()
        source = self._source_record()
        if not source:
            return True

        today = fields.Date.context_today(self)

        if "active" in source._fields and not source.active:
            raise UserError(_("The linked Promotion source is inactive."))

        if source._name == "clinic.billing.voucher.program":
            # The current Billing Voucher Program owner has `active` plus
            # date_start/date_end and deliberately has no state field.
            if source.date_start and source.date_start > today:
                raise UserError(_("Billing Voucher Program has not started yet."))
            if source.date_end and source.date_end < today:
                raise UserError(_("Billing Voucher Program is expired."))

        elif source._name == "clinic.package.voucher.batch":
            if source.state != "issued":
                raise UserError(_("Package Voucher Batch must be Issued before promotion."))
            if source.valid_from and source.valid_from > today:
                raise UserError(_("Package Voucher Batch has not started yet."))
            if source.valid_to and source.valid_to < today:
                raise UserError(_("Package Voucher Batch is expired."))

        elif source._name == "clinic.treatment.pricelist.item":
            if source.valid_from and source.valid_from > today:
                raise UserError(_("Treatment Pricelist Rule has not started yet."))
            if source.valid_to and source.valid_to < today:
                raise UserError(_("Treatment Pricelist Rule is expired."))

        elif source._name == "clinic.ecommerce.catalog.item":
            if source.state != "published":
                raise UserError(_("Clinic eCommerce Offering must be Published."))

        return True

    def action_activate(self):
        for record in self:
            record._check_source_contract()
            record._validate_source_ready()
            today = fields.Date.context_today(record)
            if record.valid_to and record.valid_to < today:
                raise UserError(_("An already expired Promotion cannot be activated."))
        self.with_context(marketing_promotion_transition=True).write({
            "state": "active",
            "active": True,
        })
        return True

    def action_expire(self):
        self.with_context(marketing_promotion_transition=True).write({
            "state": "expired",
        })
        return True

    def action_archive(self):
        self.with_context(marketing_promotion_transition=True).write({
            "state": "archived",
            "active": False,
        })
        return True

    def action_reset_to_draft(self):
        self.with_context(marketing_promotion_transition=True).write({
            "state": "draft",
            "active": True,
        })
        return True

    def action_open_source(self):
        self.ensure_one()
        source = self._source_record()
        if not source:
            raise UserError(_("This is an informational Promotion without an owner source."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Promotion Source"),
            "res_model": source._name,
            "view_mode": "form",
            "res_id": source.id,
        }

    def action_open_campaigns(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Campaigns"),
            "res_model": "clinic.marketing.campaign",
            "view_mode": "list,form",
            "domain": [("promotion_id", "=", self.id)],
        }

    @api.model
    # Expiry affects Marketing presentation state only and never mutates the linked voucher/pricelist/eCommerce owner record.
    def _cron_expire_promotions(self):
        today = fields.Date.context_today(self)
        expired = self.sudo().search([
            ("state", "=", "active"),
            ("valid_to", "!=", False),
            ("valid_to", "<", today),
        ])
        if expired:
            expired.with_context(marketing_promotion_transition=True).write({
                "state": "expired",
            })
        return True

