
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo.tools import safe_eval
import pytz
import re


class ClinicBranch(models.Model):
    _name = 'clinic.branch'
    _description = 'Clinic Branch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'company_id, sequence, name'
    _rec_name = 'display_name'

    # -------------------------------------------------------------------------
    # CORE FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='Branch Name',
        required=True,
        tracking=True,
        index=True
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        size=16,
        index=True,
        help='Unique short code for the branch (e.g., JKT01, SBY-A).'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Ordering in menus and selections.'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company.id,
        help='Owning company of this branch.'
    )

    parent_id = fields.Many2one(
        'clinic.branch',
        string='Parent Branch',
        domain='[("company_id", "=", company_id)]',
        check_company=True,
        help='Optional parent branch (for grouping, region, etc.).'
    )
    child_ids = fields.One2many(
        'clinic.branch', 'parent_id',
        string='Child Branches'
    )

    # Display helper
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # Branding & identity
    image_1920 = fields.Image(string='Logo', max_width=1920, max_height=1920)
    image_1024 = fields.Image(related='image_1920', max_width=1024, max_height=1024, readonly=True)
    image_512 = fields.Image(related='image_1920', max_width=512, max_height=512, readonly=True)
    image_256 = fields.Image(related='image_1920', max_width=256, max_height=256, readonly=True)
    image_128 = fields.Image(related='image_1920', max_width=128, max_height=128, readonly=True)

    color = fields.Integer(string='Color Index')

    # Contact / address
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')

    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')

    # Geo & timezone
    tz = fields.Selection(
        selection=lambda self: self._tz_get(),
        string='Timezone',
        default=lambda self: self.env.user.tz or 'UTC',
        help='Branch timezone for scheduling/SLA.'
    )
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))

    # Default mappings (STOCK)
    default_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Default Warehouse',
        domain='[("company_id", "=", company_id)]',
        check_company=True,
        help='Default warehouse for this branch.'
    )
    picking_type_in_id = fields.Many2one(
        'stock.picking.type', string='Incoming Operation Type',
        domain='[("warehouse_id", "=", default_warehouse_id)]',
        help='Default incoming picking type (linked to the default warehouse).'
    )
    picking_type_out_id = fields.Many2one(
        'stock.picking.type', string='Outgoing Operation Type',
        domain='[("warehouse_id", "=", default_warehouse_id)]'
    )
    picking_type_internal_id = fields.Many2one(
        'stock.picking.type', string='Internal Operation Type',
        domain='[("warehouse_id", "=", default_warehouse_id)]'
    )

    # Default mappings (ACCOUNTING)
    journal_sale_id = fields.Many2one(
        'account.journal', string='Sales Journal',
        domain='[("type", "=", "sale"), ("company_id", "=", company_id)]',
        check_company=True
    )
    journal_purchase_id = fields.Many2one(
        'account.journal', string='Purchase Journal',
        domain='[("type", "=", "purchase"), ("company_id", "=", company_id)]',
        check_company=True
    )
    journal_bank_id = fields.Many2one(
        'account.journal', string='Bank Journal',
        domain='[("type", "=", "bank"), ("company_id", "=", company_id)]',
        check_company=True
    )
    journal_cash_id = fields.Many2one(
        'account.journal', string='Cash Journal',
        domain='[("type", "=", "cash"), ("company_id", "=", company_id)]',
        check_company=True
    )

    tax_sale_id = fields.Many2one(
        'account.tax', string='Default Sales Tax',
        domain='[("type_tax_use", "in", ["sale", "none"]), ("company_id", "=", company_id)]',
        check_company=True
    )
    tax_purchase_id = fields.Many2one(
        'account.tax', string='Default Purchase Tax',
        domain='[("type_tax_use", "in", ["purchase", "none"]), ("company_id", "=", company_id)]',
        check_company=True
    )

    # Generic document sequence (optional, for downstream modules)
    sequence_id = fields.Many2one(
        'ir.sequence', string='Branch Sequence',
        help='Generic branch-wide sequence (prefix will use branch code).'
    )

    # Policy flags
    is_franchise = fields.Boolean(
        string='Franchise',
        help='Tick if this branch operates under franchise agreement.'
    )

    # Report header/footer (text/plain to be used by QWeb header/footer)
    report_header = fields.Char(string='Report Header')
    report_footer = fields.Text(string='Report Footer')

    # Counts (smart buttons)
    location_count = fields.Integer(compute='_compute_counts', string='Locations')
    user_count = fields.Integer(compute='_compute_counts', string='Users')
    warehouse_count = fields.Integer(compute='_compute_counts', string='Warehouses')

    # -------------------------------------------------------------------------
    # CONSTRAINTS & SQL
    # -------------------------------------------------------------------------
    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "Branch code must be unique per company.",
    )
    @api.constrains('code')
    def _check_code_format(self):
        """
        Keep the code short and clean for document numbering/display.
        """
        for rec in self:
            if rec.code:
                if len(rec.code) > 16:
                    raise ValidationError(_("Branch code must be 16 characters or less."))
                if not re.match(r'^[0-9A-Za-z\-\._]+$', rec.code):
                    raise ValidationError(_("Branch code may only contain letters, digits, dot, hyphen, or underscore."))

    @api.constrains('parent_id', 'company_id')
    def _check_parent_company(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.company_id != rec.company_id:
                raise ValidationError(_("Parent branch must belong to the same company."))

    @api.constrains('default_warehouse_id', 'picking_type_in_id', 'picking_type_out_id', 'picking_type_internal_id')
    def _check_stock_company_consistency(self):
        for rec in self:
            wh = rec.default_warehouse_id
            if wh and wh.company_id != rec.company_id:
                raise ValidationError(_("Default warehouse must belong to the same company as the branch."))
            for pt in (rec.picking_type_in_id, rec.picking_type_out_id, rec.picking_type_internal_id):
                if pt and pt.warehouse_id and wh and pt.warehouse_id != wh:
                    raise ValidationError(_("Picking types must belong to the selected default warehouse."))

    @api.constrains('journal_sale_id', 'journal_purchase_id', 'journal_bank_id', 'journal_cash_id')
    def _check_account_company_consistency(self):
        for rec in self:
            for j in (rec.journal_sale_id, rec.journal_purchase_id, rec.journal_bank_id, rec.journal_cash_id):
                if j and j.company_id != rec.company_id:
                    raise ValidationError(_("Journals must belong to the same company as the branch."))

    @api.constrains('tax_sale_id', 'tax_purchase_id')
    def _check_tax_company_consistency(self):
        for rec in self:
            for t in (rec.tax_sale_id, rec.tax_purchase_id):
                if t and t.company_id != rec.company_id:
                    raise ValidationError(_("Taxes must belong to the same company as the branch."))

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------
    @api.depends('name', 'code', 'company_id')
    def _compute_display_name(self):
        for rec in self:
            comp = rec.company_id and rec.company_id.name or ''
            if rec.code:
                rec.display_name = "[%s] %s%s" % (rec.code, rec.name or '', f" — {comp}" if comp else '')
            else:
                rec.display_name = "%s%s" % (rec.name or '', f" — {comp}" if comp else '')

    @api.depends('default_warehouse_id')
    def _compute_counts(self):
        BranchLoc = self.env['clinic.branch.location']
        Users = self.env['res.users']
        for rec in self:
            # Locations count
            try:
                rec.location_count = BranchLoc.search_count([('branch_id', '=', rec.id)])
            except Exception:
                rec.location_count = 0

            # Users count (soft: depends on custom field allowed_branch_ids or working_branch_id)
            count_users = 0
            try:
                if 'allowed_branch_ids' in Users._fields:
                    count_users = Users.search_count([('allowed_branch_ids', 'in', rec.id)])
                elif 'working_branch_id' in Users._fields:
                    count_users = Users.search_count([('working_branch_id', '=', rec.id)])
            except Exception:
                count_users = 0
            rec.user_count = count_users

            # Warehouses count
            rec.warehouse_count = self.env['stock.warehouse'].search_count([('company_id', '=', rec.company_id.id)])

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('company_id')
    def _onchange_company_id(self):
        """
        Reset dependent mappings if company changes.
        """
        if self.company_id:
            # Reset stock mappings
            if self.default_warehouse_id and self.default_warehouse_id.company_id != self.company_id:
                self.default_warehouse_id = False
            self.picking_type_in_id = False
            self.picking_type_out_id = False
            self.picking_type_internal_id = False

            # Reset accounting mappings
            for fld in ('journal_sale_id', 'journal_purchase_id', 'journal_bank_id', 'journal_cash_id',
                        'tax_sale_id', 'tax_purchase_id'):
                if getattr(self, fld):
                    model = self._fields[fld].comodel_name
                    rec = getattr(self, fld)
                    if hasattr(rec, 'company_id') and rec.company_id != self.company_id:
                        setattr(self, fld, False)

    @api.onchange('default_warehouse_id')
    def _onchange_default_warehouse_id(self):
        """
        Suggest default picking types from the selected warehouse.
        """
        wh = self.default_warehouse_id
        if not wh:
            self.picking_type_in_id = False
            self.picking_type_out_id = False
            self.picking_type_internal_id = False
            return
        pts = self.env['stock.picking.type'].search([('warehouse_id', '=', wh.id)])
        # Try to auto pick types by code usage
        self.picking_type_in_id = pts.filtered(lambda p: p.code == 'incoming')[:1]
        self.picking_type_out_id = pts.filtered(lambda p: p.code == 'outgoing')[:1]
        self.picking_type_internal_id = pts.filtered(lambda p: p.code == 'internal')[:1]

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Normalize code to upper
        - Create default sequence if absent
        - Auto-suggest default warehouse if company has exactly 1 warehouse
        """
        Company = self.env['res.company'].sudo()
        Warehouse = self.env['stock.warehouse'].sudo()
        IrSeq = self.env['ir.sequence'].sudo()

        for vals in vals_list:
            # Normalize code
            if vals.get('code'):
                vals['code'] = str(vals['code']).upper()

            # Ensure company
            comp_id = vals.get('company_id') or self.env.company.id
            comp = Company.browse(comp_id)

            # Default warehouse suggestion (single-warehouse company)
            if not vals.get('default_warehouse_id'):
                whs = Warehouse.search([('company_id', '=', comp.id)])
                if len(whs) == 1:
                    vals['default_warehouse_id'] = whs.id

            # Create a generic sequence when absent
            if not vals.get('sequence_id'):
                code = vals.get('code') or 'BR'
                seq = IrSeq.create({
                    'name': f"[{code}] Branch Generic Sequence",
                    'implementation': 'no_gap',
                    'prefix': f"{code}/%(y)s/",
                    'padding': 5,
                    'company_id': comp.id,
                })
                vals['sequence_id'] = seq.id

        recs = super().create(vals_list)
        return recs

    def write(self, vals):
        """
        - Keep code uppercase
        - Update sequence prefix if code changed
        - Guard mapping consistency (via constrains already)
        """
        IrSeq = self.env['ir.sequence'].sudo()
        change_code = 'code' in vals and vals.get('code')
        if change_code:
            vals['code'] = str(vals['code']).upper()

        res = super().write(vals)

        if change_code:
            for rec in self:
                if rec.sequence_id:
                    # Update sequence prefix to reflect new code
                    new_prefix = f"{rec.code}/%(y)s/"
                    if rec.sequence_id.prefix != new_prefix:
                        rec.sequence_id.prefix = new_prefix
        return res

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('name', _("%s (copy)") % (self.name,))
        default.setdefault('code', f"{self.code}-COPY")
        default.setdefault('image_1920', self.image_1920)
        return super().copy(default=default)

    # -------------------------------------------------------------------------
    # NAME & SEARCH
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or rec.name
            res.append((rec.id, name))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=80):
        args = list(args or [])
        if name:
            # Allow quick search by code exact/startswith
            branches = self.search([('code', '=ilike', name)] + args, limit=limit)
            if not branches:
                branches = self.search([('code', operator, name)] + args, limit=limit)
            if not branches:
                branches = self.search([('name', operator, name)] + args, limit=limit)
            return branches.name_get()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    @api.model
    def _tz_get(self):
        # Use common timezones for better UX list length
        return [(tz, tz) for tz in pytz.common_timezones]

    def _ensure_user_can_manage(self):
        if not self.env.user.has_group('clinic_branch.group_branch_manager'):
            raise AccessError(_("You need Branch Manager rights to perform this action."))

    # -------------------------------------------------------------------------
    # SMART BUTTON ACTIONS
    # -------------------------------------------------------------------------
    def action_view_locations(self):
        """
        Open Branch Locations list/form filtered by this branch.
        """
        self.ensure_one()
        action = None
        try:
            action = self.env.ref('clinic_branch.action_branch_location').read()[0]
        except Exception:
            # Fallback generic action
            action = {
                'name': _('Branch Locations'),
                'type': 'ir.actions.act_window',
                'res_model': 'clinic.branch.location',
                'view_mode': 'tree,form,kanban,search',
                'target': 'current',
            }
        action.setdefault('domain', [])
        action['domain'] = [('branch_id', '=', self.id)]
        action.setdefault('context', {})
        action['context'] = dict(action['context'], default_branch_id=self.id, search_default_branch_id=self.id)
        return action

    def action_view_users(self):
        """
        Open Users related to this branch (allowed_branch_ids or working_branch_id).
        """
        self.ensure_one()
        Users = self.env['res.users']
        domain = ['|']
        if 'allowed_branch_ids' in Users._fields:
            domain += [('allowed_branch_ids', 'in', self.id)]
        else:
            domain += [('id', '=', 0)]  # no-op when field missing
        if 'working_branch_id' in Users._fields:
            domain += [('working_branch_id', '=', self.id)]
        else:
            domain += [('id', '=', 0)]
        return {
            'name': _('Users'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'tree,form',
            'domain': domain,
            'target': 'current',
            'context': {'search_default_company_id': self.company_id.id},
        }

    def action_view_warehouses(self):
        """
        Open warehouses within the same company (informational).
        """
        self.ensure_one()
        return {
            'name': _('Warehouses'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.warehouse',
            'view_mode': 'tree,form',
            'domain': [('company_id', '=', self.company_id.id)],
            'target': 'current',
            'context': {'default_company_id': self.company_id.id},
        }

    # -------------------------------------------------------------------------
    # COMPANY DEFAULTS HELPERS (used by res.company inherit / settings)
    # -------------------------------------------------------------------------
    def action_set_company_default(self):
        """
        Set this branch as company's default branch (if company supports that field).
        """
        self.ensure_one()
        self._ensure_user_can_manage()
        comp = self.company_id.sudo()
        if 'default_branch_id' not in comp._fields:
            raise UserError(_("The company model does not support default branch field."))
        comp.default_branch_id = self.id
        return True

    # -------------------------------------------------------------------------
    # INTEGRATION HOOKS (for bridges & downstream modules)
    # -------------------------------------------------------------------------
    def integration_values(self):
        """
        Return a dictionary of default mapping values commonly used by other apps.
        This avoids direct coupling; consumers can pick keys they recognize.
        """
        self.ensure_one()
        return {
            'branch_id': self.id,
            'company_id': self.company_id.id,
            'warehouse_id': self.default_warehouse_id.id or False,
            'picking_type_in_id': self.picking_type_in_id.id or False,
            'picking_type_out_id': self.picking_type_out_id.id or False,
            'picking_type_internal_id': self.picking_type_internal_id.id or False,
            'journal_sale_id': self.journal_sale_id.id or False,
            'journal_purchase_id': self.journal_purchase_id.id or False,
            'journal_bank_id': self.journal_bank_id.id or False,
            'journal_cash_id': self.journal_cash_id.id or False,
            'tax_sale_id': self.tax_sale_id.id or False,
            'tax_purchase_id': self.tax_purchase_id.id or False,
            'tz': self.tz or 'UTC',
        }

