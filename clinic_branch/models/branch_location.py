
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError
import pytz
import re


class ClinicBranchLocation(models.Model):
    _name = 'clinic.branch.location'
    _description = 'Clinic Branch Location'
    _inherit = ['clinic.branch.mixin', 'mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'branch_id, sequence, name'
    _rec_name = 'display_name'

    # -------------------------------------------------------------------------
    # CORE
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='Location Name',
        required=True,
        tracking=True,
        index=True,
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        size=24,
        index=True,
        help='Short unique code per branch (e.g., LOBY1, RM-201, CHAIR-A).',
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Ordering for lists and selection widgets.'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
    )

    # Hierarchy (site/building/floor/room/bed)
    type = fields.Selection([
        ('site', 'Site / Area'),
        ('building', 'Building'),
        ('floor', 'Floor'),
        ('room', 'Room'),
        ('chair', 'Chair / Bed / Station'),
        ('kiosk', 'Kiosk / Reception Desk'),
        ('storage', 'Storage / Utility'),
    ], string='Type', required=True, default='room', tracking=True)

    parent_id = fields.Many2one(
        'clinic.branch.location',
        string='Parent Location',
        domain='[("branch_id", "=", branch_id)]',
        check_company=True,
    )
    child_ids = fields.One2many(
        'clinic.branch.location', 'parent_id',
        string='Child Locations'
    )

    # Address / Contact (opsional; dipakai jika lokasi terpisah alamat)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')

    # Geo & timezone (default mengikuti branch, bisa override di level lokasi)
    tz = fields.Selection(
        selection=lambda self: self._tz_get(),
        string='Timezone',
        default=lambda self: (self.branch_tz or self.env.user.tz or 'UTC'),
        help='Location timezone for scheduling/SLA. Defaults to the branch timezone.'
    )
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    color = fields.Integer(string='Color Index')

    # Scheduling
    allow_booking = fields.Boolean(
        string='Allow Booking / Scheduling',
        default=True,
        help='If enabled, this location can be assigned to bookings/encounters/sessions.'
    )
    capacity = fields.Integer(
        string='Capacity',
        default=1,
        help='How many patients/procedures can be served concurrently in this location.'
    )
    booking_strategy = fields.Selection([
        ('sequential', 'Sequential (1-by-1)'),
        ('parallel', 'Parallel (ignore capacity)'),
        ('capacity', 'Use Capacity'),
    ], string='Booking Strategy', default='capacity')

    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Working Hours',
        help='Working hours / availability for this location (used by scheduling).'
    )
    # (opsional) representasi resource; dibuat otomatis bila model tersedia
    resource_id = fields.Many2one(
        'resource.resource',
        string='Resource',
        help='Resource record representing this location for calendar scheduling.'
    )

    # Stock / Inventory mapping (opsional tapi berguna untuk integrasi Inventory)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse (Default)',
        domain='[("company_id", "=", company_id)]',
        check_company=True,
        help='Default warehouse for stock operations related to this location.'
    )
    stock_location_id = fields.Many2one(
        'stock.location', string='Stock Location (Default)',
        domain='[("company_id", "=", company_id)]',
        help='Default internal stock location mapped to this clinical location.',
    )

    # Reporting aids
    # encounter_count = fields.Integer(string='Encounters', compute='_compute_counts')
    # booking_count = fields.Integer(string='Bookings', compute='_compute_counts')
    # stock_quant_count = fields.Integer(string='Stock Quants', compute='_compute_counts')
    # device_count = fields.Integer(string='Devices/Rooms', compute='_compute_counts')

    # -------------------------------------------------------------------------
    # SQL & CONSTRAINTS
    # -------------------------------------------------------------------------
    _code_branch_unique = models.Constraint(
        "UNIQUE(code, branch_id, company_id)",
        "Location code must be unique per branch.",
    )
    @api.constrains('code')
    def _check_code_format(self):
        for rec in self:
            if rec.code:
                if len(rec.code) > 24:
                    raise ValidationError(_("Location code must be 24 characters or less."))
                if not re.match(r'^[0-9A-Za-z\-\._]+$', rec.code):
                    raise ValidationError(_("Location code may only contain letters, digits, dot, hyphen, or underscore."))

    @api.constrains('parent_id', 'branch_id', 'company_id')
    def _check_parent_consistency(self):
        for rec in self:
            if rec.parent_id:
                if rec.parent_id.branch_id != rec.branch_id:
                    raise ValidationError(_("Parent location must be in the same branch."))
                if rec.parent_id.company_id != rec.company_id:
                    raise ValidationError(_("Parent location must belong to the same company."))

    @api.constrains('warehouse_id', 'stock_location_id', 'company_id')
    def _check_stock_company_consistency(self):
        for rec in self:
            if rec.warehouse_id and rec.warehouse_id.company_id != rec.company_id:
                raise ValidationError(_("Warehouse must belong to the same company as the location."))
            if rec.stock_location_id and hasattr(rec.stock_location_id, 'company_id'):
                if rec.stock_location_id.company_id and rec.stock_location_id.company_id != rec.company_id:
                    raise ValidationError(_("Stock location must belong to the same company as the location."))
            # Jika stock.location punya field branch_id (di modul lain), cek kecocokan cabang
            if rec.stock_location_id and 'branch_id' in rec.stock_location_id._fields:
                if rec.stock_location_id.branch_id and rec.stock_location_id.branch_id != rec.branch_id:
                    raise ValidationError(_("Stock location branch must match this location's branch."))

    @api.constrains('capacity')
    def _check_capacity_positive(self):
        for rec in self:
            if rec.capacity is not None and rec.capacity < 0:
                raise ValidationError(_("Capacity cannot be negative."))

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------
    @api.depends('name', 'code', 'type', 'branch_id')
    def _compute_display_name(self):
        for rec in self:
            type_lbl = dict(self._fields['type'].selection).get(rec.type or '', '')
            branch_code = rec.branch_id.code or ''
            code = f"[{rec.code}]" if rec.code else ''
            type_part = f" ({type_lbl})" if type_lbl else ''
            branch_part = f" — {branch_code}" if branch_code else ''
            rec.display_name = f"{code} {rec.name}{type_part}{branch_part}".strip()

    # @api.depends('stock_location_id')
    # def _compute_counts(self):
    #     """
    #     Hitung jumlah terkait secara soft-coupled agar tidak error bila modul lain tak terpasang.
    #     """
    #     Booking = None
    #     Encounter = None
    #     RoomDevice = None
    #     # aman cek model existence
    #     reg = self.env.registry
    #     if reg.get('booking.booking'):
    #         Booking = self.env['booking.booking']
    #     if reg.get('clinic.encounter'):
    #         Encounter = self.env['clinic.encounter']
    #     if reg.get('clinic.device'):
    #         RoomDevice = self.env['clinic.device']

    #     for rec in self:
    #         # Booking count
    #         try:
    #             if Booking and 'location_id' in Booking._fields:
    #                 rec.booking_count = Booking.search_count([('location_id', '=', rec.id)])
    #             else:
    #                 rec.booking_count = 0
    #         except Exception:
    #             rec.booking_count = 0

    #         # Encounter count
    #         try:
    #             if Encounter and 'location_id' in Encounter._fields:
    #                 rec.encounter_count = Encounter.search_count([('location_id', '=', rec.id)])
    #             else:
    #                 rec.encounter_count = 0
    #         except Exception:
    #             rec.encounter_count = 0

    #         # Devices count (clinic_room_device)
    #         try:
    #             if RoomDevice and 'branch_location_id' in RoomDevice._fields:
    #                 rec.device_count = RoomDevice.search_count([('branch_location_id', '=', rec.id)])
    #             else:
    #                 rec.device_count = 0
    #         except Exception:
    #             rec.device_count = 0

    #         # Stock quants count (selalu ada di stock)
    #         try:
    #             if rec.stock_location_id:
    #                 Quant = self.env['stock.quant']
    #                 rec.stock_quant_count = Quant.search_count([('location_id', 'child_of', rec.stock_location_id.id)])
    #             else:
    #                 rec.stock_quant_count = 0
    #         except Exception:
    #             rec.stock_quant_count = 0

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        """
        Sinkronkan company dan default warehouse dari branch.
        """
        if self.branch_id:
            # company sinkron by mixin via onchange
            if not self.warehouse_id:
                self.warehouse_id = self.branch_id.default_warehouse_id

            # default timezone mengikuti branch jika kosong
            if not self.tz:
                self.tz = self.branch_id.tz or self.env.user.tz or 'UTC'

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        """
        Kosongkan stock location jika warehouse berubah (menghindari inkonsistensi).
        """
        self.stock_location_id = False

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Normalisasi code ke UPPER
        - Set default warehouse dari branch bila kosong
        - Buat resource.resource otomatis (jika model tersedia) saat allow_booking=True
        """
        reg = self.env.registry
        Resource = self.env['resource.resource'] if reg.get('resource.resource') else None

        for vals in vals_list:
            # normalize code
            if vals.get('code'):
                vals['code'] = str(vals['code']).upper()

            # default warehouse from branch
            if not vals.get('warehouse_id') and vals.get('branch_id'):
                try:
                    b = self.env['clinic.branch'].browse(vals['branch_id'])
                    if b.exists() and b.default_warehouse_id:
                        vals['warehouse_id'] = b.default_warehouse_id.id
                    if not vals.get('tz'):
                        vals['tz'] = b.tz or self.env.user.tz or 'UTC'
                except Exception:
                    pass

        records = super().create(vals_list)

        # auto-create resource after record has ID
        if Resource:
            for rec in records:
                try:
                    if rec.allow_booking and not rec.resource_id:
                        rec.resource_id = Resource.create({
                            'name': rec.display_name or rec.name,
                            'company_id': rec.company_id.id,
                            'resource_type': 'material',   # room/chair is material resource
                            'time_efficiency': 1.0,
                            'calendar_id': rec.resource_calendar_id.id if rec.resource_calendar_id else False,
                            'tz': rec.tz or rec.branch_tz or self.env.user.tz or 'UTC',
                        }).id
                except Exception:
                    # Jika resource module/constraints tak memadai, lanjut tanpa gagal
                    pass

        return records

    def write(self, vals):
        """
        - Jaga konsistensi code uppercase
        - Update resource info jika nama/jadwal/tz berubah
        - Guard: perubahan branch/company sudah dijaga oleh mixin
        """
        reg = self.env.registry
        Resource = self.env['resource.resource'] if reg.get('resource.resource') else None

        change_code = 'code' in vals and vals.get('code')
        if change_code:
            vals['code'] = str(vals['code']).upper()

        res = super().write(vals)

        # sinkronisasi resource
        if Resource and any(k in vals for k in ('name', 'display_name', 'resource_calendar_id', 'tz', 'allow_booking')):
            for rec in self:
                try:
                    if rec.allow_booking:
                        # pastikan resource ada
                        if not rec.resource_id:
                            rec.resource_id = Resource.create({
                                'name': rec.display_name or rec.name,
                                'company_id': rec.company_id.id,
                                'resource_type': 'material',
                                'time_efficiency': 1.0,
                                'calendar_id': rec.resource_calendar_id.id if rec.resource_calendar_id else False,
                                'tz': rec.tz or rec.branch_tz or self.env.user.tz or 'UTC',
                            }).id
                        else:
                            # update resource attributes
                            updates = {}
                            if 'name' in vals or 'display_name' in vals:
                                updates['name'] = rec.display_name or rec.name
                            if 'resource_calendar_id' in vals:
                                updates['calendar_id'] = rec.resource_calendar_id.id if rec.resource_calendar_id else False
                            if 'tz' in vals:
                                updates['tz'] = rec.tz or rec.branch_tz or self.env.user.tz or 'UTC'
                            if updates:
                                rec.resource_id.write(updates)
                    else:
                        # jika allow_booking dimatikan, biarkan resource tetap ada (riwayat)
                        pass
                except Exception:
                    pass

        return res

    def unlink(self):
        """
        Cegah hapus jika masih ada booking/encounter mendatang (jika modul terkait terpasang).
        """
        # Soft guard hanya bila model & field tersedia
        reg = self.env.registry
        Booking = self.env['booking.booking'] if reg.get('booking.booking') else None
        Encounter = self.env['clinic.encounter'] if reg.get('clinic.encounter') else None

        for rec in self:
            # Booking mendatang
            try:
                if Booking and 'location_id' in Booking._fields and 'date_start' in Booking._fields and 'state' in Booking._fields:
                    future = Booking.search_count([
                        ('location_id', '=', rec.id),
                        ('date_start', '>=', fields.Datetime.now()),
                        ('state', 'not in', ['cancel', 'done']),
                    ])
                    if future:
                        raise UserError(_("Cannot delete: there are upcoming bookings referencing this location."))
            except Exception:
                pass

            # Encounter mendatang
            try:
                if Encounter and 'location_id' in Encounter._fields and 'state' in Encounter._fields:
                    future2 = Encounter.search_count([
                        ('location_id', '=', rec.id),
                        ('state', 'not in', ['cancel', 'done']),
                    ])
                    if future2:
                        raise UserError(_("Cannot delete: there are pending encounters referencing this location."))
            except Exception:
                pass

        return super().unlink()

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
            locs = self.search([('code', '=ilike', name)] + args, limit=limit)
            if not locs:
                locs = self.search([('code', operator, name)] + args, limit=limit)
            if not locs:
                locs = self.search([('name', operator, name)] + args, limit=limit)
            return locs.name_get()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    @api.model
    def _tz_get(self):
        return [(tz, tz) for tz in pytz.common_timezones]

    # -------------------------------------------------------------------------
    # SMART BUTTONS
    # -------------------------------------------------------------------------

    def action_view_children(self):
        """Open direct child locations while preserving the current branch scope."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Child Locations"),
            "res_model": "clinic.branch.location",
            "view_mode": "list,form",
            "domain": [("parent_id", "=", self.id)],
            "context": {
                "default_parent_id": self.id,
                "default_branch_id": self.branch_id.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_view_bookings(self):
        """
        Tampilkan daftar booking yang memakai location ini (jika modul booking tersedia).
        """
        self.ensure_one()
        reg = self.env.registry
        model_name = 'booking.booking'
        if not reg.get(model_name):
            # fallback
            return {
                'type': 'ir.actions.act_window_close'
            }
        action = {
            'name': _('Bookings'),
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'view_mode': 'tree,form,calendar,kanban',
            'domain': [('location_id', '=', self.id)],
            'context': {'default_location_id': self.id},
            'target': 'current',
        }
        # coba pakai action terdaftar jika ada
        try:
            action_ref = self.env.ref('clinic_booking.action_clinic_booking')
            if action_ref:
                action = action_ref.read()[0]
                action['domain'] = [('location_id', '=', self.id)]
                action['context'] = dict(action.get('context', {}), default_location_id=self.id)
        except Exception:
            pass
        return action

    def action_view_encounters(self):
        """
        Tampilkan encounter/visit terkait lokasi ini (jika modul encounter tersedia).
        """
        self.ensure_one()
        reg = self.env.registry
        model_name = 'clinic.encounter'
        if not reg.get(model_name):
            return {
                'type': 'ir.actions.act_window_close'
            }
        action = {
            'name': _('Encounters'),
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'view_mode': 'tree,form,kanban',
            'domain': [('location_id', '=', self.id)],
            'context': {'default_location_id': self.id},
            'target': 'current',
        }
        try:
            action_ref = self.env.ref('clinic_encounter.action_clinic_encounter')
            if action_ref:
                action = action_ref.read()[0]
                action['domain'] = [('location_id', '=', self.id)]
                action['context'] = dict(action.get('context', {}), default_location_id=self.id)
        except Exception:
            pass
        return action

    def action_view_stock(self):
        """
        Tampilkan persediaan (stock.quants) untuk stock_location_id (jika ada).
        """
        self.ensure_one()
        if not self.stock_location_id:
            raise UserError(_("No default stock location set on this record."))
        action = {
            'name': _('Stock at Location'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'tree,form',
            'domain': [('location_id', 'child_of', self.stock_location_id.id)],
            'context': {'search_default_internal_loc': True},
            'target': 'current',
        }
        try:
            action_ref = self.env.ref('stock.quants_act_window')
            if action_ref:
                action = action_ref.read()[0]
                action['domain'] = [('location_id', 'child_of', self.stock_location_id.id)]
        except Exception:
            pass
        return action

    def action_view_devices(self):
        """
        Tampilkan perangkat/room devices (jika modul clinic_room_device tersedia).
        """
        self.ensure_one()
        reg = self.env.registry
        model_name = 'clinic.device'
        if not reg.get(model_name):
            return {'type': 'ir.actions.act_window_close'}
        return {
            'name': _('Devices / Rooms'),
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'view_mode': 'tree,form,kanban',
            'domain': [('branch_location_id', '=', self.id)],
            'context': {'default_branch_location_id': self.id, 'default_branch_id': self.branch_id.id},
            'target': 'current',
        }

