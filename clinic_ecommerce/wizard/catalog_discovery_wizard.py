from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicEcommerceCatalogDiscoveryWizard(models.TransientModel):
    """Idempotently discover online-eligible ClinicOne offerings for one Website."""

    _name = "clinic.ecommerce.catalog.discovery.wizard"
    _description = "Discover Clinic eCommerce Catalog"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    website_id = fields.Many2one(
        "website",
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    include_treatments = fields.Boolean(default=True)
    include_treatment_bundles = fields.Boolean(default=True)
    include_packages = fields.Boolean(default=True)
    include_memberships = fields.Boolean(default=True)
    result_summary = fields.Text(readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        company = self.env["res.company"].browse(
            values.get("company_id")
        ) or self.env.company
        website = (
            company.clinic_ecommerce_default_website_id
            or self.env["website"].search(
                [("company_id", "=", company.id)],
                order="id",
                limit=1,
            )
        )
        if website:
            values.setdefault("website_id", website.id)
        return values

    @api.constrains("company_id", "website_id")
    def _check_website_company(self):
        for wizard in self:
            if wizard.website_id.company_id != wizard.company_id:
                raise ValidationError(
                    _("Discovery Website must belong to the selected company.")
                )

    def action_discover(self):
        self.ensure_one()
        types = []
        if self.include_treatments:
            types.append("treatment")
        if self.include_treatment_bundles:
            types.append("treatment_bundle")
        if self.include_packages:
            types.append("package")
        if self.include_memberships:
            types.append("membership")

        created, skipped = self.env["clinic.ecommerce.catalog.item"].discover_sources(
            self.company_id,
            self.website_id,
            types,
        )
        self.result_summary = _(
            "Created %(created)s new Catalog Item(s). Skipped %(skipped)s source(s) without a valid/ready product mapping."
        ) % {
            "created": len(created),
            "skipped": len(skipped),
        }
        return {
            "type": "ir.actions.act_window",
            "name": _("Discovered Clinic Catalog"),
            "res_model": "clinic.ecommerce.catalog.item",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("website_id", "=", self.website_id.id),
            ],
        }
