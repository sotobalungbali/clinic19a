from odoo import fields, http, _
from odoo.http import request


class ClinicEcommerceController(http.Controller):
    """Small governed storefront that delegates cart/checkout to Odoo website_sale."""

    # Public routes use a narrow sudo domain limited to Published items on the current Website/company; no public backend ACL is granted.
    def _published_item(self, item_id):
        website = request.website
        return request.env["clinic.ecommerce.catalog.item"].sudo().search([
            ("id", "=", int(item_id)),
            ("active", "=", True),
            ("state", "=", "published"),
            ("website_id", "=", website.id),
            ("company_id", "=", website.company_id.id),
        ], limit=1)

    def _pricelist(self):
        try:
            return request.pricelist
        except Exception:
            return request.website._get_and_cache_current_pricelist()

    def _branch_options(self, company):
        if (
            "policy_branch_scope_ecommerce" in company._fields
            and not company.policy_branch_scope_ecommerce
        ):
            return request.env["clinic.branch"]
        return request.env["clinic.branch"].sudo().search([
            ("company_id", "=", company.id),
            ("active", "=", True),
        ], order="sequence, name")

    def _render_error(self, message, back_url="/clinic/shop"):
        return request.render(
            "clinic_ecommerce.clinic_shop_error",
            {
                "message": message,
                "back_url": back_url,
            },
        )

    @http.route(
        "/clinic/shop",
        type="http",
        auth="public",
        website=True,
        sitemap=True,
        methods=["GET"],
    )
    def clinic_shop(self, **kwargs):
        website = request.website
        items = request.env["clinic.ecommerce.catalog.item"].sudo().search([
            ("active", "=", True),
            ("state", "=", "published"),
            ("website_id", "=", website.id),
            ("company_id", "=", website.company_id.id),
        ], order="sequence, name")
        pricelist = self._pricelist()
        cards = [item._website_card_values(pricelist) for item in items]
        return request.render(
            "clinic_ecommerce.clinic_shop_catalog",
            {
                "cards": cards,
                "company": website.company_id,
            },
        )

    @http.route(
        "/clinic/shop/item/<int:item_id>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        methods=["GET"],
    )
    def clinic_shop_item(self, item_id, **kwargs):
        item = self._published_item(item_id)
        if not item:
            return request.not_found()
        pricelist = self._pricelist()
        company = request.website.company_id
        patient = (
            item._find_patient_for_partner(request.env.user.partner_id)
            if not request.env.user._is_public()
            else request.env["clinic.patient"]
        )
        return request.render(
            "clinic_ecommerce.clinic_shop_item",
            {
                "card": item._website_card_values(pricelist),
                "branches": self._branch_options(company),
                "patient": patient,
                "is_public_user": request.env.user._is_public(),
                "company": company,
            },
        )

    @http.route(
        "/clinic/shop/add/<int:item_id>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        methods=["POST"],
        csrf=True,
    )
    # The Clinic route validates identity/scope/terms, then delegates cart mutation to Odoo website_sale._cart_add().
    def clinic_shop_add(self, item_id, **post):
        item = self._published_item(item_id)
        if not item:
            return request.not_found()
        company = request.website.company_id
        back_url = f"/clinic/shop/item/{item.id}"

        source_error = item._source_ready_error()
        if source_error:
            return self._render_error(source_error, back_url)

        is_public = request.env.user._is_public()
        if item.requires_login or not company.clinic_ecommerce_allow_guest:
            if is_public:
                return request.redirect(
                    f"/web/login?redirect={back_url}"
                )

        partner = request.env.user.partner_id
        patient = (
            item._find_patient_for_partner(partner)
            if not is_public
            else request.env["clinic.patient"]
        )
        if item.requires_patient and not patient:
            return self._render_error(
                _(
                    "This offering requires a Clinic Patient card linked to your signed-in Contact. Please contact the clinic before checkout."
                ),
                back_url,
            )

        policy_branch_enabled = not (
            "policy_branch_scope_ecommerce" in company._fields
            and not company.policy_branch_scope_ecommerce
        )
        branch = request.env["clinic.branch"]
        branch_id = post.get("branch_id")
        if policy_branch_enabled and branch_id:
            try:
                branch_id = int(branch_id)
            except (TypeError, ValueError):
                return self._render_error(_("Invalid Branch selection."), back_url)
            branch = request.env["clinic.branch"].sudo().search([
                ("id", "=", branch_id),
                ("company_id", "=", company.id),
                ("active", "=", True),
            ], limit=1)
            if not branch:
                return self._render_error(_("Selected Branch is not available."), back_url)
        elif policy_branch_enabled and item.requires_branch:
            branch = item.default_branch_id
            if not branch:
                return self._render_error(
                    _("Please select a Branch for this offering."),
                    back_url,
                )

        terms_required = item.terms_required or company.clinic_ecommerce_require_terms
        terms_accepted = str(post.get("terms_accepted", "")).lower() in {
            "1", "true", "on", "yes"
        }
        if terms_required and not terms_accepted:
            return self._render_error(
                _("You must accept the Clinic purchase terms before adding this offering to the cart."),
                back_url,
            )

        preferred_date = False
        if post.get("preferred_date"):
            try:
                preferred_date = fields.Date.to_date(post["preferred_date"])
            except (TypeError, ValueError):
                return self._render_error(_("Preferred Date is invalid."), back_url)
        if item.requires_schedule and not preferred_date:
            return self._render_error(
                _("Please provide a Preferred Date. Staff will assign the exact booking time after purchase."),
                back_url,
            )

        time_window = post.get("time_window") or "flexible"
        if time_window not in {"morning", "afternoon", "evening", "flexible"}:
            return self._render_error(_("Preferred Time Window is invalid."), back_url)

        try:
            quantity = float(post.get("quantity") or 1.0)
        except (TypeError, ValueError):
            quantity = 1.0
        if quantity <= 0:
            quantity = 1.0

        product = item.sale_product_id
        if not product:
            return self._render_error(_("This offering has no saleable Product mapping."), back_url)

        order = (
            getattr(request, "cart", False)
            or request.website._get_and_cache_current_cart()
            or request.website._create_cart()
        )

        if (
            company.clinic_ecommerce_single_branch_cart
            and branch
            and order.clinic_ecommerce_branch_id
            and order.clinic_ecommerce_branch_id != branch
        ):
            return self._render_error(
                _(
                    "Your current Clinic cart belongs to another Branch. Complete or clear that cart before choosing a different Branch."
                ),
                back_url,
            )

        order_values = {}
        if branch and not order.clinic_ecommerce_branch_id:
            order_values["clinic_ecommerce_branch_id"] = branch.id
        if patient and not order.clinic_ecommerce_patient_id:
            order_values["clinic_ecommerce_patient_id"] = patient.id
        if terms_accepted:
            order_values["clinic_ecommerce_terms_accepted_at"] = fields.Datetime.now()
        if order_values:
            order.sudo().write(order_values)

        result = order._cart_add(
            product.id,
            quantity,
            clinic_ecommerce_catalog_item_id=item.id,
            clinic_ecommerce_branch_id=branch.id if branch else False,
            clinic_ecommerce_preferred_date=preferred_date,
            clinic_ecommerce_time_window=time_window,
            clinic_ecommerce_notes=post.get("notes") or False,
            clinic_ecommerce_terms_accepted=terms_accepted,
        )
        if result.get("warning"):
            order.shop_warning = result["warning"]
        return request.redirect("/shop/cart")
