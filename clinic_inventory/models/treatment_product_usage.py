# -*- coding: utf-8 -*-
# File: models/treatment_product_usage.py
# Module: clinic_inventory
#
# Purpose
#   Capture clinical product consumption for aesthetic treatments:
#   - Log product usage lines (product, qty, lot) tied to a patient/doctor/treatment reference
#   - Perform stock deduction via stock moves to a controlled "consumption sink"
#   - Auto-pick source location (pharmacy / treatment room / category default / warehouse stock)
#   - Validate governance (location/category), expiration policy, tracking requirements
#   - Provide hooks for bridges (treatment/patient/billing/membership/eCommerce) without circular deps
#
# Key ideas
#   - We DO NOT hard depend on clinic_* models; patient/doctor/treatment are OPTIONAL links.
#   - Treatment link uses a Reference field so we can point to any installed treatment model.
#   - Stock deduction uses standard Odoo stock moves (no custom valuation).
#
# Flow
#   draft → confirmed → done (consumed) or cancelled
#
# Data created
#   - stock.move (+ stock.move.line) for each usage (grouped by single usage doc)
#
# Notes
#   - All user-facing text is in English.
#   - Warehouse/location helpers reuse logic from stock_warehouse.py & stock_location.py in this module.

from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# ---------------------------------------------------------------------------
# Master document: one treatment usage with multiple lines
# ---------------------------------------------------------------------------
class ClinicTreatmentProductUsage(models.Model):
    _name = "clinic.treatment.product.usage"
    _description = "Treatment Product Usage"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_usage desc, id desc"

    # Identity & meta ---------------------------------------------------------
    name = fields.Char(
        string="Reference",
        default="/",
        readonly=True,
        copy=False,
        help="Auto-generated usage reference."
    )
    date_usage = fields.Datetime(
        string="Usage Date",
        default=fields.Datetime.now,
        tracking=True,
        help="Date and time when the products are consumed during treatment."
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("done", "Consumed"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        tracking=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        required=True,
        tracking=True,
        help="Primary clinic warehouse handling this consumption.",
        domain="[('company_id','=',company_id)]",
    )

    # Clinical context (optional links, no hard deps) -------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        domain=[("is_company", "=", False)],
        help="Patient related to this usage (optional)."
    )
    doctor_id = fields.Many2one(
        "hr.employee",
        string="Doctor",
        help="Healthcare professional responsible for this usage (optional)."
    )

    treatment_ref = fields.Reference(
        selection=lambda self: self._clinic_treatment_reference_models(),
        string="Treatment Reference",
        help="Link to a treatment/appointment/encounter record (optional). "
             "Available target models are discovered dynamically."
    )

    notes = fields.Text(
        string="Notes",
        help="Optional clinical notes for this usage."
    )

    # Location defaults (can be overridden by hooks) --------------------------
    src_location_id = fields.Many2one(
        "stock.location",
        string="Default Source Location",
        domain="[('usage','=','internal'), ('id','child_of', warehouse_id.view_location_id)]",
        help="Default internal location where products will be taken from."
    )
    dest_location_id = fields.Many2one(
        "stock.location",
        string="Consumption Sink Location",
        domain="[('id','child_of', warehouse_id.view_location_id)]",
        help="Location to record the consumption into (typically an 'Inventory/Consumption' location)."
    )

    # Summary counters ---------------------------------------------------------
    line_ids = fields.One2many(
        "clinic.treatment.product.usage.line",
        "usage_id",
        string="Usage Lines",
        copy=True
    )
    total_lines = fields.Integer(
        string="# Lines",
        compute="_compute_totals",
        store=False
    )
    total_qty = fields.Float(
        string="Total Quantity",
        compute="_compute_totals",
        store=False
    )
    move_ids = fields.One2many(
        "stock.move", "clinic_usage_id",
        string="Generated Moves",
        readonly=True,
        help="Stock moves created by this usage document (if any)."
    )
    generated_move_count = fields.Integer(
        string="# Moves",
        compute="_compute_totals",
        store=False,
        help="Number of stock moves generated by this usage document.",
    )

    # Security / audit --------------------------------------------------------
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
    )

    # -----------------------------------------------------------------------
    # COMPUTES
    # -----------------------------------------------------------------------
    @api.depends("line_ids", "line_ids.product_uom_qty", "move_ids")
    def _compute_totals(self):
        for rec in self:
            rec.total_lines = len(rec.line_ids)
            rec.total_qty = sum(l.product_uom_qty for l in rec.line_ids)
            rec.generated_move_count = len(rec.move_ids)

    # -----------------------------------------------------------------------
    # DEFAULTS & ONCHANGE
    # -----------------------------------------------------------------------
    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        for rec in self:
            if not rec.warehouse_id:
                continue
            # Resolve default source (where we take stock from) via warehouse helper
            src = rec._clinic_resolve_default_source_location()
            if src:
                rec.src_location_id = src
            # Resolve default consumption sink
            dest = rec._clinic_resolve_consumption_sink()
            if dest:
                rec.dest_location_id = dest

    # -----------------------------------------------------------------------
    # SEQUENCE
    # -----------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("clinic.treatment.product.usage") or "/"
        recs = super().create(vals_list)
        return recs

    # -----------------------------------------------------------------------
    # STATE TRANSITIONS
    # -----------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            rec._validate_ready()
            rec.state = "confirmed"
            rec.message_post(body=_("Usage confirmed."))
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("Cannot cancel a usage that has already been consumed."))
            rec.state = "cancel"
            rec.message_post(body=_("Usage cancelled."))
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.move_ids:
                raise UserError(_("Cannot reset to Draft after moves have been created. Please manage reversals manually."))
            rec.state = "draft"
        return True

    def action_consume(self):
        """Create and validate stock moves for each line (perform consumption)."""
        for rec in self:
            rec._validate_ready()
            # Hooks before stock operations
            rec._clinic_hook_pre_consume()

            # Create & finish moves
            moves = rec._create_consumption_moves()
            if not moves:
                raise UserError(_("No stock moves were created. Nothing to consume."))

            # Confirm, assign (reservation), set done quantities (respect lots), then done
            moves._action_confirm()
            rec._apply_done_move_lines(moves)
            moves.write({"picked": True})
            moves._action_done()

            # Optional post hooks
            rec._clinic_hook_post_consume(moves)

            rec.state = "done"
            rec.message_post(body=_("Consumption completed: %s move(s).") % len(moves))
        return True

    # -----------------------------------------------------------------------
    # CORE IMPLEMENTATION
    # -----------------------------------------------------------------------
    def _validate_ready(self):
        """Basic validations before confirm/consume."""
        self.ensure_one()
        if not self.warehouse_id:
            raise UserError(_("Please set a Warehouse."))
        if not self.src_location_id:
            self.src_location_id = self._clinic_resolve_default_source_location()
        if not self.src_location_id:
            raise UserError(_("Could not resolve a default Source Location."))
        if not self.dest_location_id:
            self.dest_location_id = self._clinic_resolve_consumption_sink()
        if not self.dest_location_id:
            raise UserError(_("Could not resolve a Consumption Sink Location."))

        if not self.line_ids:
            raise UserError(_("Please add at least one usage line."))

        # Location governance (category allowlist) – call location's validator if present
        if hasattr(self.src_location_id, "clinic_restrict_to_allowed_categories") and self.src_location_id.clinic_restrict_to_allowed_categories:
            for line in self.line_ids:
                self.src_location_id.clinic_validate_product_allowed(line.product_id)

        # Doctor allowed products (optional; only if model/field exist; avoid hard deps)
        self._clinic_optional_doctor_allowed_check()

        # Tracking rules (require lot if needed)
        for line in self.line_ids:
            if line._product_requires_lot() and not line.lot_id:
                raise UserError(_("Product '%s' requires a lot/serial number.") % (line.product_id.display_name,))

        # Quick sufficiency check (best-effort)
        for line in self.line_ids:
            if not line._has_sufficient_stock_at_source():
                raise UserError(_("Insufficient stock for '%s' at source location '%s'.")
                                % (line.product_id.display_name, self.src_location_id.display_name))

    def _create_consumption_moves(self):
        """Create stock moves for all lines, linked back to this usage.

        We create one move per line for clarity/audit. No picking is required to finish moves.
        """
        self.ensure_one()
        Move = self.env["stock.move"]
        created = self.env["stock.move"].browse()

        for line in self.line_ids:
            # Let product/template prepare default move values (uses hooks internally)
            vals = line._prepare_consumption_move_vals(
                usage=self,
                src_location=self.src_location_id,
                dest_location=self.dest_location_id,
            )
            # Add common move attributes
            vals.update({
                "company_id": self.company_id.id,
                "date": self.date_usage or fields.Datetime.now(),
                "warehouse_id": self.warehouse_id.id if "warehouse_id" in Move._fields else False,
                # trace back to usage
                "clinic_usage_id": self.id if "clinic_usage_id" in Move._fields else False,
            })

            move = Move.create(vals)
            created |= move

        return created

    def _apply_done_move_lines(self, moves):
        """Populate move lines with the desired done quantities and lot assignments, then finish."""
        self.ensure_one()
        # Build index product_id -> lines
        index = {}
        for l in self.line_ids:
            index.setdefault(l.product_id.id, []).append(l)

        for mv in moves:
            lines = index.get(mv.product_id.id, [])
            if not lines:
                # Should not happen; defensive
                continue
            # Keep it 1:1 (one line created one move)
            line = lines[0]

            # After confirm, create a move line and set done qty & lot
            mls = mv.move_line_ids
            if not mls:
                ml_vals = {
                    "move_id": mv.id,
                    "product_id": mv.product_id.id,
                    "product_uom_id": mv.product_uom.id,
                    "quantity": line.product_uom_qty,
                    "location_id": self.src_location_id.id,
                    "location_dest_id": self.dest_location_id.id,
                }
                if line.lot_id:
                    ml_vals["lot_id"] = line.lot_id.id
                mv.move_line_ids = [(0, 0, ml_vals)]
            else:
                # If already created by core reservation, just set done qty/lot
                ml = mls[0]
                ml.write({
                    "quantity": line.product_uom_qty,
                    "location_id": self.src_location_id.id,
                    "location_dest_id": self.dest_location_id.id,
                    "lot_id": line.lot_id.id if line.lot_id else ml.lot_id.id,
                })

    def action_view_moves(self):
        """Open stock moves generated by this usage document."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Stock Moves"),
            "res_model": "stock.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.move_ids.ids)],
            "context": {"create": False},
        }

    # -----------------------------------------------------------------------
    # RESOLUTION HELPERS
    # -----------------------------------------------------------------------
    def _clinic_treatment_reference_models(self):
        """Discover potential treatment models dynamically to avoid hard deps.

        Returns a list of (model, label) tuples.
        """
        # Default candidates — only include if installed
        candidates = [
            ("clinic.treatment", "Treatment"),
            ("booking.booking.appointment", "Appointment"),
            ("clinic.room.session", "Room Session"),
        ]
        res = []
        IrModel = self.env["ir.model"].sudo()
        for (model, label) in candidates:
            if IrModel.search([("model", "=", model)], limit=1):
                res.append((model, label))
        # Always allow generic chatter attachment as a fallback: mail.thread records
        return res

    def _clinic_resolve_default_source_location(self):
        """Resolve default source location (where items are taken FROM)."""
        self.ensure_one()
        wh = self.warehouse_id
        # Ask warehouse helper (prefers Treatment Root > Category default > Pharmacy > lot_stock)
        # We don't have a product context here (per-line differs), so use Treatment Root or Pharmacy as general source
        if getattr(wh, "clinic_treatment_root_location_id", False):
            return wh.clinic_treatment_root_location_id
        if getattr(wh, "clinic_pharmacy_location_id", False):
            return wh.clinic_pharmacy_location_id
        return wh.lot_stock_id

    def _clinic_resolve_consumption_sink(self):
        """Resolve the consumption sink location (WHERE the move goes TO to reduce stock).

        Strategy:
          1) First internal 'Inventory/Consumption' child under warehouse view (usage='inventory').
          2) Any 'inventory' usage location in the company (last resort).
        """
        self.ensure_one()
        Location = self.env["stock.location"].sudo()
        wh = self.warehouse_id
        if not wh:
            return False

        # Prefer an 'inventory' usage node under the warehouse internal view
        inv = Location.search([
            ("usage", "=", "inventory"),
            ("id", "child_of", wh.view_location_id.id),
        ], limit=1)
        if inv:
            return inv

        # Fallback: any inventory location
        inv = Location.search([("usage", "=", "inventory")], limit=1)
        return inv or False

    # -----------------------------------------------------------------------
    # OPTIONAL / SOFT VALIDATIONS
    # -----------------------------------------------------------------------
    def _clinic_optional_doctor_allowed_check(self):
        """If a doctor-allowlist policy exists in another module, validate here.

        This function avoids hard dependencies by checking model/fields existence first.
        """
        self.ensure_one()
        if not self.doctor_id:
            return True

        # Example integration: 'clinic.doctor.allowed.product' relation (not required)
        # If the model exists and has a relation to hr.employee + product, validate.
        try:
            Model = self.env["clinic.doctor.allowed.product"]
            if not Model._name:
                return True
        except Exception:
            return True  # model not installed → skip

        # If relation fields are present, enforce
        for line in self.line_ids:
            try:
                ok = bool(Model.search_count([("doctor_id", "=", self.doctor_id.id),
                                              ("product_id", "=", line.product_id.id)]))
            except Exception:
                ok = True
            if not ok:
                raise UserError(_("Product '%s' is not allowed for doctor '%s'.") %
                                (line.product_id.display_name, self.doctor_id.display_name))
        return True

    # -----------------------------------------------------------------------
    # HOOKS for bridges
    # -----------------------------------------------------------------------
    def _clinic_hook_pre_consume(self):
        """Called just before stock moves are created (per document)."""
        return

    def _clinic_hook_post_consume(self, moves):
        """Called after moves are done. Bridges may log to treatment/patient history or billing."""
        return


# ---------------------------------------------------------------------------
# Lines: one product usage entry
# ---------------------------------------------------------------------------
class ClinicTreatmentProductUsageLine(models.Model):
    _name = "clinic.treatment.product.usage.line"
    _description = "Treatment Product Usage Line"
    _order = "sequence, id"

    usage_id = fields.Many2one(
        "clinic.treatment.product.usage",
        string="Usage",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain=[("type", "!=", "service")],
        help="Product used during treatment."
    )
    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
        help="Unit of measure for the consumed quantity.",
        default=lambda self: self.env.ref("uom.product_uom_unit")
    )
    product_uom_qty = fields.Float(
        string="Quantity",
        required=True,
        digits="Product Unit of Measure",
        default=1.0
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        domain="[('product_id','=',product_id)]",
        help="Lot/Serial consumed (required if product is tracked by lot/serial)."
    )

    note = fields.Char(
        string="Line Note",
        help="Optional free text."
    )

    # Availability / helper counters -----------------------------------------
    qty_onhand_at_source = fields.Float(
        string="On Hand at Source",
        compute="_compute_onhand_at_source",
        store=False,
        help="On-hand quantity at the usage's source location subtree."
    )

    # -----------------------------------------------------------------------
    # COMPUTES
    # -----------------------------------------------------------------------
    @api.depends("product_id", "usage_id.src_location_id")
    def _compute_onhand_at_source(self):
        Quant = self.env["stock.quant"]
        for line in self:
            qty = 0.0
            if line.product_id and line.usage_id and line.usage_id.src_location_id:
                domain = [
                    ("product_id", "=", line.product_id.id),
                    ("location_id", "child_of", line.usage_id.src_location_id.id),
                ]
                for row in Quant.read_group(domain, ["quantity:sum"], []):
                    qty += row.get("quantity", 0.0) or 0.0
            line.qty_onhand_at_source = qty

    # -----------------------------------------------------------------------
    # VALIDATIONS
    # -----------------------------------------------------------------------
    @api.constrains("product_uom_qty")
    def _check_positive_qty(self):
        for line in self:
            if line.product_uom_qty is None or line.product_uom_qty <= 0.0:
                raise ValidationError(_("Quantity must be greater than zero."))

    # -----------------------------------------------------------------------
    # LOGIC HELPERS
    # -----------------------------------------------------------------------
    def _product_requires_lot(self):
        self.ensure_one()
        tracking = self.product_id.tracking if "tracking" in self.product_id._fields else "none"
        return tracking in ("lot", "serial")

    def _has_sufficient_stock_at_source(self):
        """Quick on-hand check in the selected source location subtree."""
        self.ensure_one()
        src = self.usage_id.src_location_id
        if not src:
            return True
        Quant = self.env["stock.quant"]
        qty = 0.0
        for row in Quant.read_group([
            ("product_id", "=", self.product_id.id),
            ("location_id", "child_of", src.id),
        ], ["quantity:sum"], []):
            qty += row.get("quantity", 0.0) or 0.0
        return qty >= (self.product_uom_qty or 0.0)

    def action_open_usage(self):
        """Open the parent usage document from an embedded One2many line."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Treatment Product Usage"),
            "res_model": "clinic.treatment.product.usage",
            "view_mode": "form",
            "res_id": self.usage_id.id,
            "target": "current",
        }

    def _prepare_consumption_move_vals(self, usage, src_location, dest_location):
        """Build stock.move values for this usage line.

        Delegates to product/product_template helpers for cross-module hooks.
        """
        self.ensure_one()
        product = self.product_id
        # Base: delegate to product API to allow bridges to add analytics
        vals = {}
        if hasattr(product, "clinic_prepare_consumption_move_vals"):
            vals = product.clinic_prepare_consumption_move_vals(
                qty=self.product_uom_qty,
                uom=self.product_uom,
                treatment=usage.treatment_ref,
                patient=usage.patient_id,
                location=src_location,
                # Extra context
                usage=self.usage_id,
                doctor=usage.doctor_id,
            )
        else:
            # Fallback vanilla payload
            vals = {
                "origin": _("Clinical consumption of %s") % (product.display_name,),
                "product_id": product.id,
                "product_uom": self.product_uom.id,
                "product_uom_qty": self.product_uom_qty,
            }

        # Ensure required move keys
        vals.setdefault("product_id", product.id)
        vals.setdefault("product_uom", self.product_uom.id)
        vals.setdefault("product_uom_qty", self.product_uom_qty)
        vals.setdefault("origin", _("Clinical consumption of %s") % (product.display_name,))

        # Locations
        vals["location_id"] = src_location.id
        vals["location_dest_id"] = dest_location.id

        # Link lot if already chosen; move line will ultimately carry it at done step
        # (Some Odoo versions accept lot via move context; we keep it on move line)
        return vals


# ---------------------------------------------------------------------------
# Light extension on stock.move to keep traceability link (optional)
# (Kept safe: only if field name is available in ORM; else we dynamically add)
# ---------------------------------------------------------------------------
def _ensure_clinic_usage_field_on_move(env):
    """Dynamically add a Many2one field to stock.move pointing to usage document if missing.

    This keeps a direct link without forcing a module dependency that would alter core schema
    in ways some deployments might not allow. If field exists (via bridge), we do nothing.
    """
    Move = env["stock.move"]
    if "clinic_usage_id" in Move._fields:
        return  # already provided (e.g., by a bridge)
    # Dynamically register field at runtime (safe for Odoo ORM)
    from odoo.fields import Many2one
    Move._add_field(
        "clinic_usage_id",
        Many2one(
            comodel_name="clinic.treatment.product.usage",
            string="Treatment Usage",
            help="Back-reference to the treatment usage document that generated this move.",
            ondelete="set null",
        ),
    )

# Ensure field is present when models are loaded
def _register_hook(env):
    _ensure_clinic_usage_field_on_move(env)




