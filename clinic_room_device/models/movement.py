
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicDeviceMovement(models.Model):
    """
    Log perpindahan perangkat:
    - assign   : pertama kali ditempatkan ke suatu ruangan (from_room = False, to_room = X)
    - move     : pindah dari satu ruangan ke ruangan lain (from_room = A, to_room = B)
    - unassign : dilepas dari ruangan (from_room = X, to_room = False)

    Sumber utama pembuatan record:
    - Model assignment (clinic.room.device.assignment) memanggil create movement
      saat activate/end/move (lihat assignment.py).
    - Action manual pada device/room jika admin ingin menambah catatan.

    Integrasi lintas modul:
    - clinic.device  ← device_id (wajib)
    - clinic.room    ← from_room_id / to_room_id
    - stock/product  ← action_open_stock_moves: menampilkan move lines terkait product/lot
    - audit          ← mail.thread + activity
    """

    _name = "clinic.device.movement"
    _description = "Clinic Device Movement Log"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "display_name"

    # -----------------------
    # Identity
    # -----------------------
    name = fields.Char(
        string="Reference",
        index=True,
        tracking=True,
        help="Referensi movement. Jika kosong, akan diisi otomatis.",
    )
    code = fields.Char(
        string="Movement Code",
        index=True,
        help="Kode unik movement. Jika kosong akan diisi otomatis dari sequence (bila tersedia).",
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda s: s.env.company,
        index=True,
        required=True,
    )

    # -----------------------
    # Core
    # -----------------------
    device_id = fields.Many2one(
        "clinic.device",
        string="Device",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    from_room_id = fields.Many2one(
        "clinic.room",
        string="From Room",
        ondelete="restrict",
        index=True,
    )
    to_room_id = fields.Many2one(
        "clinic.room",
        string="To Room",
        ondelete="restrict",
        index=True,
    )

    reason = fields.Selection(
        selection=[
            ("assign", "Assign"),
            ("move", "Move"),
            ("unassign", "Unassign"),
            ("maintenance", "Maintenance Transfer"),
            ("replacement", "Replacement"),
            ("other", "Other"),
        ],
        string="Reason",
        required=True,
        default="move",
        tracking=True,
    )
    date = fields.Datetime(
        string="Date",
        required=True,
        default=lambda s: fields.Datetime.now(),
        tracking=True,
        help="Waktu perpindahan terjadi atau dicatat.",
    )
    note = fields.Text(string="Notes")

    # redundansi tipis utk laporan cepat
    from_room_type_id = fields.Many2one(
        "clinic.room.type",
        string="From Room Type",
        related="from_room_id.room_type_id",
        store=True,
        readonly=True,
    )
    to_room_type_id = fields.Many2one(
        "clinic.room.type",
        string="To Room Type",
        related="to_room_id.room_type_id",
        store=True,
        readonly=True,
    )

    # -----------------------
    # Status / Validation
    # -----------------------
    is_consistent = fields.Boolean(
        string="Consistency OK",
        compute="_compute_consistency",
        store=False,
        help="Penanda cepat validasi logis: assign/unassign tidak boleh punya kedua room.",
    )

    # -----------------------
    # Constraints
    # -----------------------
        # Odoo 19 table constraints
    _room_pair_ok = models.Constraint(
        'CHECK (from_room_id IS DISTINCT FROM to_room_id)',
        'From Room dan To Room tidak boleh identik.',
    )

    # -----------------------
    # Display
    # -----------------------
    @api.depends("code", "name", "reason", "device_id", "from_room_id", "to_room_id", "date")
    def _compute_display_name(self):
        for rec in self:
            if rec.name:
                rec.display_name = rec.name
                continue
            base = rec._format_default_name(
                reason=rec.reason,
                device=rec.device_id,
                from_room=rec.from_room_id,
                to_room=rec.to_room_id,
                date=rec.date,
            )
            rec.display_name = base

    def _format_default_name(self, reason, device, from_room, to_room, date):
        dt_str = date and fields.Datetime.to_string(date) or ""
        dev = device.display_name if device else _("(Device)")
        if reason == "assign":
            return _("%(dev)s → %(to)s @ %(dt)s") % {"dev": dev, "to": (to_room.display_name if to_room else "-"), "dt": dt_str}
        elif reason == "unassign":
            return _("%(dev)s → None @ %(dt)s") % {"dev": dev, "dt": dt_str}
        # move/maintenance/replacement/other
        return _("%(dev)s: %(fr)s → %(to)s @ %(dt)s") % {
            "dev": dev,
            "fr": (from_room.display_name if from_room else "-"),
            "to": (to_room.display_name if to_room else "-"),
            "dt": dt_str,
        }

    # -----------------------
    # Compute
    # -----------------------
    def _reason_requires(self):
        """Aturan logis minimal untuk kombinasi room."""
        return {
            "assign": {"from_required": False, "to_required": True},
            "unassign": {"from_required": True, "to_required": False},
            # sisanya butuh from & to
            "move": {"from_required": True, "to_required": True},
            "maintenance": {"from_required": True, "to_required": True},
            "replacement": {"from_required": True, "to_required": True},
            "other": {"from_required": False, "to_required": False},
        }

    @api.depends("reason", "from_room_id", "to_room_id")
    def _compute_consistency(self):
        req = self._reason_requires()
        for rec in self:
            rule = req.get(rec.reason, req["other"])
            ok = True
            if rule["from_required"] and not rec.from_room_id:
                ok = False
            if rule["to_required"] and not rec.to_room_id:
                ok = False
            if rec.from_room_id and rec.to_room_id and rec.from_room_id.id == rec.to_room_id.id:
                ok = False
            rec.is_consistent = ok

    # -----------------------
    # ORM
    # -----------------------
    def _sequence_next(self):
        seq_ref = self.env.ref("clinic_room_device.seq_clinic_device_movement", raise_if_not_found=False)
        return self.env["ir.sequence"].next_by_code("clinic.device.movement") if seq_ref else False

    @api.model_create_multi
    def create(self, vals_list):
        recs = self.browse()
        req = self._reason_requires()
        for vals in vals_list:
            # default company → ikut device jika ada
            if not vals.get("company_id") and vals.get("device_id"):
                vals["company_id"] = self.env["clinic.device"].browse(vals["device_id"]).company_id.id or self.env.company.id

            # sequence & name
            if not vals.get("code"):
                vals["code"] = self._sequence_next()
            if not vals.get("name"):
                device = self.env["clinic.device"].browse(vals.get("device_id")) if vals.get("device_id") else False
                from_room = self.env["clinic.room"].browse(vals.get("from_room_id")) if vals.get("from_room_id") else False
                to_room = self.env["clinic.room"].browse(vals.get("to_room_id")) if vals.get("to_room_id") else False
                vals["name"] = self._format_default_name(
                    reason=vals.get("reason"),
                    device=device,
                    from_room=from_room,
                    to_room=to_room,
                    date=fields.Datetime.to_datetime(vals.get("date")) if vals.get("date") else fields.Datetime.now(),
                )

            # validasi kombinasi room by reason
            reason = vals.get("reason") or "other"
            rule = req.get(reason, req["other"])
            if rule["from_required"] and not vals.get("from_room_id"):
                raise ValidationError(_("Perpindahan '%s' membutuhkan From Room.") % (dict(self._fields["reason"].selection).get(reason)))
            if rule["to_required"] and not vals.get("to_room_id"):
                raise ValidationError(_("Perpindahan '%s' membutuhkan To Room.") % (dict(self._fields["reason"].selection).get(reason)))
            if vals.get("from_room_id") and vals.get("to_room_id") and vals["from_room_id"] == vals["to_room_id"]:
                raise ValidationError(_("From Room dan To Room tidak boleh identik."))

            recs |= super().create(vals)
        return recs

    def write(self, vals):
        req = self._reason_requires()
        for rec in self:
            # prevent making illogical pairs on update
            n_reason = vals.get("reason", rec.reason)
            n_from = self.env["clinic.room"].browse(vals["from_room_id"]) if "from_room_id" in vals else rec.from_room_id
            n_to = self.env["clinic.room"].browse(vals["to_room_id"]) if "to_room_id" in vals else rec.to_room_id
            rule = req.get(n_reason, req["other"])
            if rule["from_required"] and not n_from:
                raise ValidationError(_("Perpindahan '%s' membutuhkan From Room.") % (dict(self._fields["reason"].selection).get(n_reason)))
            if rule["to_required"] and not n_to:
                raise ValidationError(_("Perpindahan '%s' membutuhkan To Room.") % (dict(self._fields["reason"].selection).get(n_reason)))
            if n_from and n_to and n_from.id == n_to.id:
                raise ValidationError(_("From Room dan To Room tidak boleh identik."))

            # auto name jika dikosongkan
            if vals.get("name") in (None, False):
                vals["name"] = rec._format_default_name(
                    reason=n_reason,
                    device=rec.device_id,
                    from_room=n_from,
                    to_room=n_to,
                    date=fields.Datetime.to_datetime(vals.get("date")) if vals.get("date") else rec.date,
                )
        return super().write(vals)

    # -----------------------
    # UI Helpers / Actions
    # -----------------------
    def action_open_device(self):
        self.ensure_one()
        return {
            "name": _("Device"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "form",
            "res_id": self.device_id.id,
        }

    def action_open_from_room(self):
        self.ensure_one()
        if not self.from_room_id:
            raise UserError(_("Movement ini tidak memiliki From Room."))
        return {
            "name": _("From Room"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "form",
            "res_id": self.from_room_id.id,
        }

    def action_open_to_room(self):
        self.ensure_one()
        if not self.to_room_id:
            raise UserError(_("Movement ini tidak memiliki To Room."))
        return {
            "name": _("To Room"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "form",
            "res_id": self.to_room_id.id,
        }

    def action_open_stock_moves(self):
        """
        Opsional: tampilkan stock move lines yang berkaitan dengan device ini
        (berdasarkan product/lot yang di-link di clinic.device).
        """
        self.ensure_one()
        if "stock.move.line" not in self.env:
            raise UserError(_("Modul Inventory belum terpasang."))
        device = self.device_id
        if not device or not device.product_id:
            raise UserError(_("Device belum ditautkan ke product."))
        domain = [("product_id", "=", device.product_id.id)]
        if device.lot_id and "lot_id" in self.env["stock.move.line"]._fields:
            domain.append(("lot_id", "=", device.lot_id.id))
        return {
            "name": _("Stock Move Lines"),
            "type": "ir.actions.act_window",
            "res_model": "stock.move.line",
            "view_mode": "list,form",
            "domain": domain,
        }

    # -----------------------
    # Name helpers
    # -----------------------
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or rec.name or ""
            res.append((rec.id, name))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        search_domain = []
        if name:
            search_domain = ["|", "|",
                      ("code", operator, name),
                      ("name", operator, name),
                      ("device_id.name", operator, name)]
        recs = self.search(search_domain + domain, limit=limit)
        return recs.name_get()
