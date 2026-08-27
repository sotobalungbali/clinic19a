from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


OFFERING_TYPE_SELECTION = [
    ("treatment", "Treatment"),
    ("treatment_bundle", "Treatment Bundle"),
    ("package", "Package"),
    ("membership", "Membership Plan"),
    ("product", "Clinic Product"),
]

FULFILLMENT_TYPE_SELECTION = [
    ("booking", "Create Booking Handoff"),
    ("package_allocation", "Create Package Allocation"),
    ("membership_contract", "Create Membership Contract"),
    ("native_sale", "Native Odoo Sale / Delivery"),
    ("manual", "Manual Fulfillment"),
]

SOURCE_FIELDS = {
    "treatment": "treatment_id",
    "treatment_bundle": "treatment_bundle_id",
    "package": "package_id",
    "membership": "membership_plan_id",
    "product": "generic_product_id",
}

DEFAULT_FULFILLMENT = {
    "treatment": "booking",
    "treatment_bundle": "native_sale",
    "package": "package_allocation",
    "membership": "membership_contract",
    "product": "native_sale",
}


class ClinicEcommerceCatalogItem(models.Model):
    """Govern one ClinicOne offering exposed through Odoo Website/eCommerce."""

    _name = "clinic.ecommerce.catalog.item"
    _description = "Clinic eCommerce Catalog Item"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "eCommerce Catalog Item code must be unique per company.",
    )
    _quantity_valid = models.Constraint(
        "CHECK(min_quantity > 0 AND (max_quantity = 0 OR max_quantity >= min_quantity))",
        "Maximum Quantity must be zero (unlimited) or greater than/equal to Minimum Quantity.",
    )
    _catalog_scope_idx = models.Index(
        "(company_id, website_id, state, offering_type, sequence)"
    )

    name = fields.Char(required=True, tracking=True, index=True)
    code = fields.Char(
        default="/",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    website_id = fields.Many2one(
        "website",
        required=True,
        index=True,
        domain="[('company_id', '=', company_id)]",
    )
    default_branch_id = fields.Many2one(
        "clinic.branch",
        string="Default Branch",
        domain="[('company_id', '=', company_id)]",
        ondelete="set null",
        tracking=True,
    )

    offering_type = fields.Selection(
        OFFERING_TYPE_SELECTION,
        required=True,
        default="treatment",
        tracking=True,
        index=True,
    )
    fulfillment_type = fields.Selection(
        FULFILLMENT_TYPE_SELECTION,
        required=True,
        default="booking",
        tracking=True,
        index=True,
    )

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        ondelete="restrict",
        index=True,
    )
    treatment_bundle_id = fields.Many2one(
        "clinic.treatment.bundle",
        string="Treatment Bundle",
        ondelete="restrict",
        index=True,
    )
    package_id = fields.Many2one(
        "clinic.package",
        string="Package",
        ondelete="restrict",
        index=True,
    )
    membership_plan_id = fields.Many2one(
        "membership.plan",
        string="Membership Plan",
        ondelete="restrict",
        index=True,
    )
    generic_product_id = fields.Many2one(
        "product.product",
        string="Clinic Product",
        ondelete="restrict",
        index=True,
        domain="[('sale_ok', '=', True)]",
    )

    sale_product_id = fields.Many2one(
        "product.product",
        string="Sale Product",
        compute="_compute_sale_product",
        readonly=True,
    )
    sale_product_tmpl_id = fields.Many2one(
        "product.template",
        string="Sale Product Template",
        compute="_compute_sale_product",
        readonly=True,
    )
    source_display_name = fields.Char(
        compute="_compute_source_display_name",
        string="Clinic Source",
    )

    image_1920 = fields.Image(max_width=1920, max_height=1920)
    public_summary = fields.Char(
        help="Short human-friendly summary shown on the Clinic Shop catalog card."
    )
    public_description = fields.Html(sanitize=True)
    customer_disclaimer = fields.Html(
        sanitize=True,
        help="Offering-specific disclaimer shown before Add to Cart.",
    )

    requires_login = fields.Boolean(default=True)
    requires_patient = fields.Boolean(default=True)
    requires_branch = fields.Boolean(default=False)
    requires_schedule = fields.Boolean(default=False)
    terms_required = fields.Boolean(default=True)
    single_quantity_only = fields.Boolean(default=True)
    min_quantity = fields.Float(default=1.0)
    max_quantity = fields.Float(
        default=1.0,
        help="Zero means unlimited. Single-quantity offerings always resolve to quantity 1.",
    )
    publish_native_product = fields.Boolean(
        string="Also Publish on Native Odoo Shop",
        default=False,
        help=(
            "Normally Clinic offerings are sold through /clinic/shop so patient, branch, "
            "terms and scheduling metadata cannot be bypassed. Enable only when native "
            "Odoo /shop exposure is intentionally acceptable."
        ),
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("review", "In Review"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    website_url = fields.Char(compute="_compute_website_url")

    sale_order_line_ids = fields.One2many(
        "sale.order.line",
        "clinic_ecommerce_catalog_item_id",
        string="Sales Lines",
    )
    fulfillment_ids = fields.One2many(
        "clinic.ecommerce.fulfillment",
        "catalog_item_id",
        string="Fulfillments",
    )
    sale_order_count = fields.Integer(compute="_compute_counts")
    sale_line_count = fields.Integer(compute="_compute_counts")
    fulfillment_count = fields.Integer(compute="_compute_counts")
    error_fulfillment_count = fields.Integer(compute="_compute_counts")

    @api.model
    def _default_website(self, company):
        return self.env["website"].search(
            [("company_id", "=", company.id)],
            order="id",
            limit=1,
        )

    @api.model_create_multi
    # Catalog creation normalizes identity and fills Website/fulfillment defaults without mutating the source offering.
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = self.env["res.company"].browse(
                vals.get("company_id")
            ) or self.env.company
            if vals.get("code", "/") in (False, "/", "New"):
                vals["code"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.ecommerce.catalog.item")
                    or "/"
                )
            if not vals.get("website_id"):
                website = self._default_website(company)
                if website:
                    vals["website_id"] = website.id
            offering = vals.get("offering_type", "treatment")
            vals.setdefault(
                "fulfillment_type",
                DEFAULT_FULFILLMENT.get(offering, "manual"),
            )
            if offering in ("treatment", "package", "membership"):
                vals.setdefault("requires_login", True)
                vals.setdefault("requires_patient", True)
                vals.setdefault("single_quantity_only", True)
                vals.setdefault("max_quantity", 1.0)
            if offering == "treatment":
                vals.setdefault("requires_schedule", True)
            prepared.append(vals)
        return super().create(prepared)

    # Source identity and Website scope are frozen once published or referenced by a Sales Line.
    def write(self, vals):
        if "state" in vals and not self.env.context.get("ecommerce_catalog_transition"):
            raise AccessError(
                _("Use Catalog workflow actions to change publication status.")
            )

        locked_fields = {
            "company_id",
            "website_id",
            "offering_type",
            "treatment_id",
            "treatment_bundle_id",
            "package_id",
            "membership_plan_id",
            "generic_product_id",
        }
        if locked_fields.intersection(vals):
            if self.filtered(lambda rec: rec.state == "published"):
                raise UserError(
                    _("Unpublish the Catalog Item before changing its source or Website.")
                )
            if self.filtered("sale_order_line_ids"):
                raise UserError(
                    _("Catalog source identity cannot change after it has Sales Lines.")
                )
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda rec: rec.state == "published"):
            raise UserError(_("Published Catalog Items must be unpublished before deletion."))
        if self.filtered("sale_order_line_ids"):
            raise UserError(
                _("Catalog Items referenced by Sales Lines cannot be deleted; archive them instead.")
            )
        return super().unlink()

    @api.onchange("offering_type")
    # Offering Type drives safe defaults only; backend constraints remain authoritative when records arrive through RPC.
    def _onchange_offering_type(self):
        for item in self:
            item.fulfillment_type = DEFAULT_FULFILLMENT.get(
                item.offering_type,
                "manual",
            )
            item.requires_schedule = item.offering_type == "treatment"
            item.requires_patient = item.offering_type in (
                "treatment",
                "package",
                "membership",
            )
            item.requires_login = item.requires_patient
            item.single_quantity_only = item.offering_type in (
                "treatment",
                "package",
                "membership",
            )
            if item.single_quantity_only:
                item.min_quantity = 1.0
                item.max_quantity = 1.0

    @api.depends(
        "offering_type",
        "treatment_id",
        "treatment_bundle_id",
        "package_id",
        "membership_plan_id",
        "generic_product_id",
    )
    # Commercial Product mapping is derived from the owner addon instead of duplicating clinic pricing/product ownership.
    def _compute_sale_product(self):
        for item in self:
            product = self.env["product.product"]
            if item.offering_type == "treatment" and item.treatment_id:
                product = item.treatment_id.get_service_product()
            elif item.offering_type == "treatment_bundle" and item.treatment_bundle_id:
                product = item.treatment_bundle_id.get_service_product()
            elif item.offering_type == "package" and item.package_id.product_template_id:
                product = (
                    item.package_id.product_template_id.product_variant_id
                    or item.package_id.product_template_id.product_variant_ids[:1]
                )
            elif item.offering_type == "membership" and item.membership_plan_id:
                product = item.membership_plan_id.product_id
            elif item.offering_type == "product":
                product = item.generic_product_id
            item.sale_product_id = product
            item.sale_product_tmpl_id = product.product_tmpl_id if product else False

    @api.depends(
        "offering_type",
        "treatment_id",
        "treatment_bundle_id",
        "package_id",
        "membership_plan_id",
        "generic_product_id",
    )
    def _compute_source_display_name(self):
        for item in self:
            source = item._source_record()
            item.source_display_name = source.display_name if source else False

    @api.depends("state")
    def _compute_website_url(self):
        for item in self:
            item.website_url = (
                f"/clinic/shop/item/{item.id}"
                if item.id and item.state == "published"
                else False
            )

    @api.depends(
        "sale_order_line_ids",
        "fulfillment_ids",
        "fulfillment_ids.state",
    )
    def _compute_counts(self):
        for item in self:
            item.sale_line_count = len(item.sale_order_line_ids)
            item.sale_order_count = len(item.sale_order_line_ids.mapped("order_id"))
            item.fulfillment_count = len(item.fulfillment_ids)
            item.error_fulfillment_count = len(
                item.fulfillment_ids.filtered(
                    lambda rec: rec.state in ("error", "reversal_required")
                )
            )

    @api.constrains("company_id", "website_id", "default_branch_id")
    def _check_scope(self):
        for item in self:
            if item.website_id.company_id != item.company_id:
                raise ValidationError(
                    _("Catalog Website must belong to the selected company.")
                )
            if (
                item.default_branch_id
                and item.default_branch_id.company_id != item.company_id
            ):
                raise ValidationError(
                    _("Default Branch must belong to the selected company.")
                )

    @api.constrains(
        "offering_type",
        "treatment_id",
        "treatment_bundle_id",
        "package_id",
        "membership_plan_id",
        "generic_product_id",
        "fulfillment_type",
    )
    # Exactly one source keeps every Catalog Item traceable and prevents ambiguous multi-owner fulfillment.
    def _check_source_contract(self):
        for item in self:
            expected_field = SOURCE_FIELDS[item.offering_type]
            populated = [
                field_name
                for field_name in SOURCE_FIELDS.values()
                if item[field_name]
            ]
            if populated != [expected_field]:
                raise ValidationError(
                    _(
                        "Exactly one source must be set and it must match Offering Type %(type)s."
                    )
                    % {"type": item.offering_type}
                )

            expected_fulfillment = DEFAULT_FULFILLMENT.get(item.offering_type)
            if (
                expected_fulfillment
                and item.fulfillment_type not in (expected_fulfillment, "manual")
            ):
                raise ValidationError(
                    _(
                        "Offering Type %(type)s supports %(expected)s or Manual fulfillment, not %(actual)s."
                    )
                    % {
                        "type": item.offering_type,
                        "expected": expected_fulfillment,
                        "actual": item.fulfillment_type,
                    }
                )

    @api.constrains("requires_branch", "company_id")
    # Branch requirements are enforced in Python so UI visibility cannot bypass company policy.
    def _check_branch_policy(self):
        for item in self:
            if (
                item.requires_branch
                and "policy_branch_scope_ecommerce" in item.company_id._fields
                and not item.company_id.policy_branch_scope_ecommerce
            ):
                raise ValidationError(
                    _(
                        "Branch is required by this Catalog Item, but eCommerce Branch scoping is disabled for the company."
                    )
                )

    @api.constrains(
        "company_id",
        "website_id",
        "offering_type",
        "treatment_id",
        "treatment_bundle_id",
        "package_id",
        "membership_plan_id",
        "generic_product_id",
    )
    def _check_unique_source_per_website(self):
        for item in self:
            source_field = SOURCE_FIELDS[item.offering_type]
            source = item[source_field]
            if not source:
                continue
            duplicate = self.search_count([
                ("id", "!=", item.id),
                ("company_id", "=", item.company_id.id),
                ("website_id", "=", item.website_id.id),
                ("offering_type", "=", item.offering_type),
                (source_field, "=", source.id),
                ("active", "=", True),
            ])
            if duplicate:
                raise ValidationError(
                    _("This Clinic source already has an active Catalog Item on this Website.")
                )

    def _source_record(self):
        self.ensure_one()
        return self[SOURCE_FIELDS[self.offering_type]]

    # Publication readiness reads each owner module's active/online/validity contract; it does not invent a second lifecycle.
    def _source_ready_error(self):
        """Return a human-readable readiness error, or False when publishable."""
        self.ensure_one()
        source = self._source_record()
        if not source:
            return _("Clinic source is missing.")

        if item_company := getattr(source, "company_id", False):
            if item_company != self.company_id:
                return _("Clinic source belongs to a different company.")

        if self.offering_type == "treatment":
            if not source.active:
                return _("Treatment is archived/inactive.")
            if not source.allow_online_booking:
                return _("Treatment does not allow Online Booking.")
            catalog = source.catalog_id
            if catalog and not catalog.is_currently_valid:
                return _("Treatment is outside its validity period.")

        elif self.offering_type == "treatment_bundle":
            if not source.active:
                return _("Treatment Bundle is inactive.")
            if not source.allow_online_sale:
                return _("Treatment Bundle does not allow Online Sale.")
            if not source.is_currently_valid:
                return _("Treatment Bundle is outside its validity period.")

        elif self.offering_type == "package":
            if not source.active or source.state != "active":
                return _("Package must be Active before it can be sold online.")

        elif self.offering_type == "membership":
            if not source.active or source.state != "active":
                return _("Membership Plan must be Active before it can be sold online.")

        elif self.offering_type == "product":
            if not source.active or not source.sale_ok:
                return _("Product must be active and saleable.")

        if (
            self.requires_branch
            and "policy_branch_scope_ecommerce" in self.company_id._fields
            and not self.company_id.policy_branch_scope_ecommerce
        ):
            return _(
                "This offering requires a Branch, but eCommerce Branch scoping is currently disabled for the company."
            )

        product = self.sale_product_id
        if not product or not product.active or not product.sale_ok:
            return _("A valid saleable Odoo Product is required.")
        if product.company_id and product.company_id != self.company_id:
            return _("Sale Product belongs to a different company.")
        return False

    def _ensure_publishable(self):
        for item in self:
            error = item._source_ready_error()
            if error:
                raise UserError(error)
        return True

    def _require_manager(self):
        if self.env.su:
            return True
        if not self.env.user.has_group("clinic_ecommerce.group_ecommerce_manager"):
            raise AccessError(
                _("Only an eCommerce Manager can change Catalog publication status.")
            )
        return True

    def action_submit_review(self):
        self._require_manager()
        for item in self:
            if item.state != "draft":
                raise UserError(_("Only Draft Catalog Items can be submitted for review."))
            item._ensure_publishable()
        self.with_context(ecommerce_catalog_transition=True).write({"state": "review"})
        return True

    def action_publish(self):
        self._require_manager()
        for item in self:
            if item.state not in ("draft", "review"):
                raise UserError(_("Only Draft/In Review Catalog Items can be published."))
            item._ensure_publishable()
            if item.publish_native_product:
                item._set_native_product_publication(True)
        self.with_context(ecommerce_catalog_transition=True).write({
            "state": "published",
            "active": True,
        })
        return True

    def action_unpublish(self):
        self._require_manager()
        for item in self:
            if item.state != "published":
                raise UserError(_("Only Published Catalog Items can be unpublished."))
        self.with_context(ecommerce_catalog_transition=True).write({"state": "review"})
        for item in self:
            if item.publish_native_product:
                item._set_native_product_publication(False)
        return True

    def action_archive(self):
        self._require_manager()
        for item in self:
            if item.state == "published" and item.publish_native_product:
                item._set_native_product_publication(False)
        self.with_context(ecommerce_catalog_transition=True).write({
            "state": "archived",
            "active": False,
        })
        return True

    def action_reset_to_draft(self):
        self._require_manager()
        self.with_context(ecommerce_catalog_transition=True).write({
            "state": "draft",
            "active": True,
        })
        return True

    # Native /shop publication is explicit opt-in; the governed /clinic/shop remains the default storefront.
    def _set_native_product_publication(self, publish):
        """Publish/unpublish only the mapped Product; never alter source pricing/workflow."""
        self.ensure_one()
        template = self.sale_product_tmpl_id
        if not template:
            raise UserError(_("No Product Template is mapped to this Catalog Item."))

        values = {}
        if "website_id" in template._fields:
            if template.website_id and template.website_id != self.website_id:
                raise UserError(
                    _("Product is already assigned to another Website.")
                )
            if publish and not template.website_id:
                values["website_id"] = self.website_id.id
        if "is_published" in template._fields:
            if not publish:
                other = self.search_count([
                    ("id", "!=", self.id),
                    ("state", "=", "published"),
                    ("active", "=", True),
                    ("website_id", "=", self.website_id.id),
                    ("publish_native_product", "=", True),
                ])
                # A generic count cannot prove same product; refine in Python.
                if other:
                    sibling = self.search([
                        ("id", "!=", self.id),
                        ("state", "=", "published"),
                        ("active", "=", True),
                        ("website_id", "=", self.website_id.id),
                        ("publish_native_product", "=", True),
                    ]).filtered(lambda rec: rec.sale_product_tmpl_id == template)
                    if sibling:
                        return True
            values["is_published"] = bool(publish)
        if values:
            template.sudo().write(values)
        return True

    # Patient lookup never auto-creates clinical identity from a website Contact.
    def _find_patient_for_partner(self, partner):
        self.ensure_one()
        if not partner:
            return self.env["clinic.patient"]
        partner_ids = {partner.id}
        if partner.commercial_partner_id:
            partner_ids.add(partner.commercial_partner_id.id)
        return self.env["clinic.patient"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
            ("partner_id", "in", list(partner_ids)),
        ], order="id", limit=1)

    def _website_price(self, pricelist=None):
        self.ensure_one()
        product = self.sale_product_id
        if not product:
            return 0.0
        try:
            product_ctx = product.with_context(
                pricelist=pricelist.id if pricelist else False
            )
            return product_ctx._get_contextual_price()
        except Exception:
            return product.lst_price

    def _website_card_values(self, pricelist=None):
        self.ensure_one()
        product = self.sale_product_id
        price = self._website_price(pricelist)
        currency = pricelist.currency_id if pricelist else self.company_id.currency_id
        symbol = currency.symbol or currency.name or ""
        return {
            "item": self,
            "offering_label": dict(
                self._fields["offering_type"].selection
            ).get(self.offering_type, self.offering_type),
            "price": price,
            "price_display": f"{symbol} {price:,.2f}",
            "currency": currency,
            "product": product,
        }

    def action_open_source(self):
        self.ensure_one()
        source = self._source_record()
        if not source:
            raise UserError(_("Clinic source is missing."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Source"),
            "res_model": source._name,
            "view_mode": "form",
            "res_id": source.id,
        }

    def action_open_product(self):
        self.ensure_one()
        if not self.sale_product_tmpl_id:
            raise UserError(_("No Odoo Product is mapped."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Sale Product"),
            "res_model": "product.template",
            "view_mode": "form",
            "res_id": self.sale_product_tmpl_id.id,
        }

    def action_open_website(self):
        self.ensure_one()
        if self.state != "published":
            raise UserError(_("Publish the Catalog Item before opening its public page."))
        return {
            "type": "ir.actions.act_url",
            "url": self.website_url,
            "target": "self",
        }

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("eCommerce Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("order_line.clinic_ecommerce_catalog_item_id", "=", self.id)],
        }

    def action_view_fulfillments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("eCommerce Fulfillments"),
            "res_model": "clinic.ecommerce.fulfillment",
            "view_mode": "list,form",
            "domain": [("catalog_item_id", "=", self.id)],
            "context": {"default_catalog_item_id": self.id},
        }

    @api.model
    # Discovery is idempotent and creates Draft mappings only; Managers still review/publish every offering.
    def discover_sources(self, company, website, offering_types=None):
        """Idempotently create Draft Catalog Items for online-eligible upstream offerings."""
        offering_types = offering_types or list(SOURCE_FIELDS)
        created = self.browse()
        skipped = []

        def create_if_missing(offering_type, source, values):
            source_field = SOURCE_FIELDS[offering_type]
            existing = self.search([
                ("company_id", "=", company.id),
                ("website_id", "=", website.id),
                ("offering_type", "=", offering_type),
                (source_field, "=", source.id),
                ("active", "=", True),
            ], limit=1)
            if existing:
                return existing
            vals = {
                "name": source.display_name,
                "company_id": company.id,
                "website_id": website.id,
                "offering_type": offering_type,
                source_field: source.id,
                **values,
            }
            rec = self.create(vals)
            nonlocal created
            created |= rec
            return rec

        if "treatment" in offering_types:
            sources = self.env["clinic.treatment"].sudo().search([
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("allow_online_booking", "=", True),
            ])
            for source in sources:
                if source.catalog_id and not source.catalog_id.is_currently_valid:
                    skipped.append(source.display_name)
                    continue
                create_if_missing("treatment", source, {
                    "fulfillment_type": "booking",
                    "requires_login": True,
                    "requires_patient": True,
                    "requires_schedule": True,
                    "single_quantity_only": True,
                    "max_quantity": 1.0,
                    "public_summary": _("Book this treatment online and complete scheduling after purchase."),
                })

        if "treatment_bundle" in offering_types:
            sources = self.env["clinic.treatment.bundle"].sudo().search([
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("allow_online_sale", "=", True),
            ])
            for source in sources.filtered("is_currently_valid"):
                create_if_missing("treatment_bundle", source, {
                    "fulfillment_type": "native_sale",
                    "requires_login": True,
                    "requires_patient": False,
                    "requires_schedule": False,
                    "single_quantity_only": True,
                    "max_quantity": 1.0,
                })

        if "package" in offering_types:
            for source in self.env["clinic.package"].sudo().search([
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("state", "=", "active"),
            ]):
                if not source.product_template_id:
                    skipped.append(source.display_name)
                    continue
                create_if_missing("package", source, {
                    "fulfillment_type": "package_allocation",
                    "requires_login": True,
                    "requires_patient": True,
                    "single_quantity_only": True,
                    "max_quantity": 1.0,
                })

        if "membership" in offering_types:
            for source in self.env["membership.plan"].sudo().search([
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("state", "=", "active"),
            ]):
                if not source.product_id:
                    skipped.append(source.display_name)
                    continue
                create_if_missing("membership", source, {
                    "fulfillment_type": "membership_contract",
                    "requires_login": True,
                    "requires_patient": True,
                    "single_quantity_only": True,
                    "max_quantity": 1.0,
                })

        return created, skipped
