
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError


"""
ClinicOne — clinic_branch
File: models/hr_employee_inherit.py

Tujuan
------
- Menambahkan branch & branch location pada hr.employee
- Menjaga konsistensi multi-company (branch.company = employee.company)
- Default cerdas: context -> user.working_branch -> company.default_branch -> allowed branches
- Domain dinamis berdasarkan allowed branches user (soft-coupled)
- Integrasi halus dengan 38 addon lain (booking/encounter/inventory/accounting/portal/reports), via pengecekan registry

Catatan
-------
- TIDAK mewarisi clinic.branch.mixin untuk menghindari bentrok dengan company_id bawaan hr.employee.
- Validasi & helper dibuat spesifik untuk hr.employee.
"""


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    # -------------------------------------------------------------------------
    # BRANCH ACCESS & MAPPING
    # -------------------------------------------------------------------------
    # Daftar cabang yang boleh dipilih user saat ini (virtual; untuk domain branch_id)
    employee_allowed_branch_ids = fields.Many2many(
        'clinic.branch',
        string='Allowed Branches (Virtual)',
        compute='_compute_employee_allowed_branches',
        help='Daftar cabang yang bisa dipilih sesuai hak akses user saat ini.',
    )

    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        index=True,
        required=True,
        domain='[("id", "in", employee_allowed_branch_ids)]',
        check_company=True,
        help='Cabang utama tempat karyawan ini ditempatkan.'
    )

    branch_location_id = fields.Many2one(
        'clinic.branch.location',
        string='Branch Location',
        domain='[("branch_id", "=", branch_id), ("company_id", "=", company_id)]',
        check_company=True,
        help='Lokasi/ruang kerja default karyawan di cabang terkait.'
    )

    # Informasi turunan (untuk laporan/UX)
    branch_company_id = fields.Many2one(
        'res.company',
        string='Branch Company',
        compute='_compute_branch_meta'
    )
    branch_tz = fields.Char(
        string='Branch Timezone',
        compute='_compute_branch_meta'
    )

    # Pelaporan ringan (smart buttons — soft-coupled)
    # booking_count = fields.Integer(string='Bookings', compute='_compute_counts')
    # encounter_count = fields.Integer(string='Encounters', compute='_compute_counts')

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------
    @api.model
    def _default_branch_for_employee(self, vals=None):
        """
        Default branch untuk employee:
        1) context['branch_id'] (jika valid & diizinkan)
        2) user.working_branch_id (jika ada & diizinkan)
        3) company.default_branch_id (jika ada & diizinkan)
        4) allowed branches pertama dalam company aktif
        """
        Branch = self.env['clinic.branch']
        user = self.env.user
        company = self.env.company

        # 1) context
        ctx_bid = self.env.context.get('branch_id')
        if ctx_bid:
            b = Branch.browse(int(ctx_bid)).exists()
            if b and self._is_branch_allowed_for_user(b):
                return b.id

        # 2) user.working_branch_id (soft check)
        if 'working_branch_id' in user._fields:
            wb = user.sudo().working_branch_id
            if wb and self._is_branch_allowed_for_user(wb):
                return wb.id

        # 3) company.default_branch_id (soft check)
        if 'default_branch_id' in company._fields:
            db = company.sudo().default_branch_id
            if db and self._is_branch_allowed_for_user(db):
                return db.id

        # 4) fallback: allowed branches di company
        allowed = self._user_allowed_branches(company=company)
        return allowed[:1].id if allowed else False

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------
    @api.depends_context('uid', 'company')
    def _compute_employee_allowed_branches(self):
        for rec in self:
            rec.employee_allowed_branch_ids = rec._user_allowed_branches(company=rec.company_id or self.env.company)

    @api.depends('branch_id', 'branch_id.company_id', 'branch_id.tz')
    def _compute_branch_meta(self):
        for rec in self:
            rec.branch_company_id = rec.branch_id.company_id if rec.branch_id else False
            rec.branch_tz = rec.branch_id.tz if rec.branch_id else False

    # @api.depends('branch_id', 'branch_location_id')
    # def _compute_counts(self):
    #     """
    #     Hitung jumlah booking/encounter terkait karyawan ini secara soft-coupled:
    #     - Jika model/field tidak ada, hasil dihitung 0 tanpa error.
    #     """
    #     reg = self.env.registry
    #     Booking = self.env['booking.booking'] if reg.get('booking.booking') else None
    #     Encounter = self.env['clinic.encounter'] if reg.get('clinic.encounter') else None

    #     for rec in self:
    #         # Booking: prefer field employee_id; fallback doctor_employee_id
    #         try:
    #             count = 0
    #             if Booking:
    #                 if 'employee_id' in Booking._fields:
    #                     count = Booking.search_count([('employee_id', '=', rec.id)])
    #                 elif 'doctor_employee_id' in Booking._fields:
    #                     count = Booking.search_count([('doctor_employee_id', '=', rec.id)])
    #             rec.booking_count = count
    #         except Exception:
    #             rec.booking_count = 0

    #         # Encounter: prefer field employee_id; fallback doctor_employee_id
    #         try:
    #             count = 0
    #             if Encounter:
    #                 if 'employee_id' in Encounter._fields:
    #                     count = Encounter.search_count([('employee_id', '=', rec.id)])
    #                 elif 'doctor_employee_id' in Encounter._fields:
    #                     count = Encounter.search_count([('doctor_employee_id', '=', rec.id)])
    #             rec.encounter_count = count
    #         except Exception:
    #             rec.encounter_count = 0

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('company_id')
    def _onchange_company_id_set_branch(self):
        """
        Saat company berubah:
        - Reset branch jika tidak se-company
        - Tetapkan default branch berdasarkan company baru
        - Kosongkan branch_location bila tak cocok
        """
        for rec in self:
            if rec.company_id:
                if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                    rec.branch_id = False
                if not rec.branch_id:
                    default_bid = rec._default_branch_for_employee()
                    if default_bid:
                        rec.branch_id = default_bid
                if rec.branch_location_id and rec.branch_location_id.company_id != rec.company_id:
                    rec.branch_location_id = False

    @api.onchange('branch_id')
    def _onchange_branch_sync_company_and_location(self):
        """
        Saat branch dipilih:
        - Sinkronkan company bila belum diisi
        - Reset lokasi bila tak cocok
        """
        for rec in self:
            if rec.branch_id:
                # sinkron company jika kosong
                if not rec.company_id:
                    rec.company_id = rec.branch_id.company_id
                # jaga konsistensi lokasi
                if rec.branch_location_id and rec.branch_location_id.branch_id != rec.branch_id:
                    rec.branch_location_id = False
                # Set default tz jika employee tidak punya tz pada kalender (informasi ringan)
                # (Tidak mengubah resource_calendar; hanya metadata di field branch_tz yang sudah compute)

    @api.onchange('branch_location_id')
    def _onchange_location_guard(self):
        for rec in self:
            if rec.branch_location_id:
                if rec.branch_id and rec.branch_location_id.branch_id != rec.branch_id:
                    rec.branch_location_id = False
                    return {
                        'warning': {
                            'title': _('Location mismatch'),
                            'message': _('Selected location belongs to a different branch.')
                        }
                    }
                if rec.company_id and rec.branch_location_id.company_id != rec.company_id:
                    rec.branch_location_id = False
                    return {
                        'warning': {
                            'title': _('Company mismatch'),
                            'message': _('Selected location belongs to a different company.')
                        }
                    }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('branch_id', 'company_id', 'branch_location_id')
    def _check_branch_company_consistency(self):
        for rec in self:
            if not rec.branch_id:
                raise ValidationError(_("Branch is required for employees."))
            if rec.company_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(_("Employee's branch company must match the employee's company."))
            if rec.branch_location_id:
                if rec.branch_location_id.branch_id != rec.branch_id:
                    raise ValidationError(_("Location branch must match employee branch."))
                if rec.company_id and rec.branch_location_id.company_id != rec.company_id:
                    raise ValidationError(_("Location company must match employee company."))

    # -------------------------------------------------------------------------
    # CREATE / WRITE (GUARDRAILS)
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Tetapkan default branch bila tidak diisi (mengikuti _default_branch_for_employee).
        - Sinkronkan company bila kosong dan branch ditentukan.
        - Guard hak akses: user harus diizinkan memilih branch tsb.
        - Sinkronisasi ringan dengan user_id (allowed/working branches) secara soft-coupled.
        """
        for vals in vals_list:
            # default branch
            if not vals.get('branch_id'):
                default_bid = self._default_branch_for_employee(vals=vals)
                if default_bid:
                    vals['branch_id'] = default_bid

            # sinkron company dari branch bila kosong
            if vals.get('branch_id') and not vals.get('company_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if b.exists():
                    vals['company_id'] = b.company_id.id

            # guard hak akses terhadap branch
            if vals.get('branch_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if not self._is_branch_allowed_for_user(b):
                    raise AccessError(_("You are not allowed to create an employee in the selected branch."))

            # konsistensi location
            if vals.get('branch_location_id'):
                loc = self.env['clinic.branch.location'].browse(vals['branch_location_id'])
                if loc.exists():
                    if vals.get('branch_id') and loc.branch_id.id != vals['branch_id']:
                        raise ValidationError(_("Selected location belongs to a different branch."))
                    if vals.get('company_id') and loc.company_id.id != vals['company_id']:
                        raise ValidationError(_("Selected location belongs to a different company."))

        employees = super().create(vals_list)

        # Sinkronisasi ringan ke user (opsional, soft)
        for emp, vals in zip(employees, vals_list):
            if vals.get('user_id') and emp.user_id:
                emp._soft_sync_user_branch_policy()

        return employees

    def write(self, vals):
        """
        - Guard perubahan branch/company/location
        - Hanya HR Manager atau Branch Manager boleh memindahkan branch bila kontrak aktif (jika modul kontrak ada)
        - Soft-sync ke res.users bila user_id terkait
        """
        change_branch = 'branch_id' in vals
        change_company = 'company_id' in vals
        change_location = 'branch_location_id' in vals

        # Jika ada kontrak aktif, pembatasan lebih ketat (soft-coupled)
        if change_branch:
            self._guard_contract_when_change_branch(vals.get('branch_id'))

        # Konsistensi branch<->company
        if change_branch and vals.get('branch_id'):
            new_branch = self.env['clinic.branch'].browse(vals['branch_id'])
            if new_branch.exists() and not self._is_branch_allowed_for_user(new_branch):
                raise AccessError(_("You are not allowed to move an employee to the selected branch."))

            if change_company and vals.get('company_id'):
                new_company = self.env['res.company'].browse(vals['company_id'])
                if new_branch.company_id != new_company:
                    raise ValidationError(_("Branch company and employee company must match."))
            else:
                # sinkronkan company jika record belum punya company
                for rec in self:
                    if not rec.company_id:
                        vals.setdefault('company_id', new_branch.company_id.id)
                    elif rec.company_id != new_branch.company_id:
                        raise ValidationError(_("Employee already belongs to a different company than the selected branch."))

        if change_company and vals.get('company_id') and not change_branch:
            new_company = self.env['res.company'].browse(vals['company_id'])
            conflict = self.filtered(lambda r: r.branch_id and r.branch_id.company_id != new_company)
            if conflict:
                # kosongkan branch agar dipilih ulang sesuai company baru
                vals['branch_id'] = False
                vals.pop('branch_location_id', None)

        if change_location and vals.get('branch_location_id'):
            loc = self.env['clinic.branch.location'].browse(vals['branch_location_id'])
            if loc.exists():
                # pastikan konsisten dengan branch & company (yang baru jika ikut berubah)
                target_company = self.env['res.company'].browse(vals['company_id']) if change_company and vals.get('company_id') else None
                target_branch = self.env['clinic.branch'].browse(vals['branch_id']) if change_branch and vals.get('branch_id') else None
                for rec in self:
                    b = target_branch or rec.branch_id
                    c = target_company or rec.company_id
                    if b and loc.branch_id != b:
                        raise ValidationError(_("Selected location belongs to a different branch."))
                    if c and loc.company_id != c:
                        raise ValidationError(_("Selected location belongs to a different company."))

        res = super().write(vals)

        # Soft-sync ke res.users (jika ada user_id & field pendukung)
        if any(k in vals for k in ('branch_id', 'company_id', 'user_id')):
            for rec in self:
                rec._soft_sync_user_branch_policy()

        return res

    # -------------------------------------------------------------------------
    # PERMISSIONS & CONTRACT GUARD (soft-coupled)
    # -------------------------------------------------------------------------
    def _guard_contract_when_change_branch(self, new_branch_id):
        """
        Jika modul kontrak tersedia (hr.contract), batasi perubahan branch pada
        employee yang memiliki kontrak aktif. Hanya HR Manager atau Branch Manager
        yang boleh melakukan perubahan tersebut.
        """
        reg = self.env.registry
        Contract = self.env['hr.contract'] if reg.get('hr.contract') else None
        if not Contract:
            return  # tidak ada modul kontrak, abaikan guard ini

        # Pastikan pemanggil memiliki hak jika ada kontrak aktif
        need_manager = False
        for emp in self:
            try:
                # deteksi kontrak aktif (heuristik umum)
                active_cnt = Contract.search_count([
                    ('employee_id', '=', emp.id),
                    '|', ('state', '=', 'open'), ('state', '=', 'active')
                ])
                if active_cnt:
                    need_manager = True
                    break
            except Exception:
                continue

        if need_manager:
            if not (self.env.user.has_group('hr.group_hr_manager') or
                    self.env.user.has_group('clinic_branch.group_branch_manager')):
                raise AccessError(_("You need HR Manager or Branch Manager rights to change branch for employees with active contracts."))

    # -------------------------------------------------------------------------
    # INTEGRASI ke res.users (soft)
    # -------------------------------------------------------------------------
    def _soft_sync_user_branch_policy(self):
        """
        Sinkronkan kebijakan branch ke user terkait (tanpa memaksa dependensi):
        - Jika user tidak memiliki allowed_branch_ids → tambahkan branch employee
        - Jika user tidak memiliki working_branch_id → set ke branch employee
        - Tidak menghapus cabang lain milik user
        """
        for emp in self:
            user = emp.user_id
            if not user:
                continue

            has_allowed = 'allowed_branch_ids' in user._fields
            has_working = 'working_branch_id' in user._fields

            updates = {}
            if has_allowed and emp.branch_id and emp.branch_id.id not in user.allowed_branch_ids.ids:
                updates.setdefault('allowed_branch_ids', []).append((4, emp.branch_id.id))
            if has_working and not user.working_branch_id and emp.branch_id:
                updates['working_branch_id'] = emp.branch_id.id

            if updates:
                try:
                    user.sudo().write(updates)
                except Exception:
                    # Jangan gagalkan operasi utama jika sync user gagal
                    pass

    # -------------------------------------------------------------------------
    # HELPERS (soft-coupled)
    # -------------------------------------------------------------------------
    def _user_allowed_branches(self, user=None, company=None):
        """
        Recordset branch yang diizinkan untuk user sekarang.
        Jika user punya allowed_branch_ids → gunakan; jika tidak, fallback ke seluruh branch di company aktif.
        """
        user = user or self.env.user
        Branch = self.env['clinic.branch'].sudo()
        company = company or self.env.company

        if 'allowed_branch_ids' in user._fields and user.allowed_branch_ids:
            allowed = user.sudo().allowed_branch_ids
            if company:
                allowed = allowed.filtered(lambda b: b.company_id == company)
            return allowed

        dom = []
        if company:
            dom.append(('company_id', '=', company.id))
        return Branch.search(dom)

    def _is_branch_allowed_for_user(self, branch):
        if not branch:
            return False
        allowed = self._user_allowed_branches(company=branch.company_id)
        return branch.id in allowed.ids

    def with_branch(self, branch):
        """
        Terapkan context branch untuk operasi turunan (berguna untuk create terkait).
        """
        branch = branch if isinstance(branch, models.BaseModel) else self.env['clinic.branch'].browse(branch)
        return self.with_context(branch_id=branch.id if branch else False)

    # -------------------------------------------------------------------------
    # SMART BUTTONS / ACTIONS (opsional; soft)
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """
        Tampilkan booking yang terkait employee ini.
        Menggunakan field employee_id atau doctor_employee_id bila tersedia.
        """
        self.ensure_one()
        reg = self.env.registry
        model_name = 'booking.booking'
        if not reg.get(model_name):
            return {'type': 'ir.actions.act_window_close'}

        Booking = self.env[model_name]
        domain = ['|', ('id', '=', 0), ('id', '=', 0)]
        if 'employee_id' in Booking._fields:
            domain[0] = ('employee_id', '=', self.id)
        if 'doctor_employee_id' in Booking._fields:
            domain[2] = ('doctor_employee_id', '=', self.id)

        action = {
            'name': _('Bookings'),
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'view_mode': 'tree,form,calendar,kanban',
            'domain': domain,
            'context': {'search_default_my_branch': True, 'default_branch_id': self.branch_id.id},
            'target': 'current',
        }
        # gunakan action terdaftar bila ada
        try:
            action_ref = self.env.ref('clinic_booking.action_clinic_booking')
            if action_ref:
                action = action_ref.read()[0]
                action['domain'] = domain
                action['context'] = dict(action.get('context', {}), default_branch_id=self.branch_id.id)
        except Exception:
            pass
        return action

    def action_view_encounters(self):
        """
        Tampilkan encounter/visit yang terkait employee ini.
        Menggunakan field employee_id atau doctor_employee_id bila tersedia.
        """
        self.ensure_one()
        reg = self.env.registry
        model_name = 'clinic.encounter'
        if not reg.get(model_name):
            return {'type': 'ir.actions.act_window_close'}

        Encounter = self.env[model_name]
        domain = ['|', ('id', '=', 0), ('id', '=', 0)]
        if 'employee_id' in Encounter._fields:
            domain[0] = ('employee_id', '=', self.id)
        if 'doctor_employee_id' in Encounter._fields:
            domain[2] = ('doctor_employee_id', '=', self.id)

        action = {
            'name': _('Encounters'),
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'view_mode': 'tree,form,kanban',
            'domain': domain,
            'context': {'search_default_my_branch': True, 'default_branch_id': self.branch_id.id},
            'target': 'current',
        }
        try:
            action_ref = self.env.ref('clinic_encounter.action_clinic_encounter')
            if action_ref:
                action = action_ref.read()[0]
                action['domain'] = domain
                action['context'] = dict(action.get('context', {}), default_branch_id=self.branch_id.id)
        except Exception:
            pass
        return action

    def action_open_branch(self):
        """
        Buka form branch terkait employee ini.
        """
        self.ensure_one()
        if not self.branch_id:
            raise UserError(_("Employee has no branch assigned."))
        return {
            'name': _('Branch'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.branch',
            'view_mode': 'form',
            'res_id': self.branch_id.id,
            'target': 'current',
        }

