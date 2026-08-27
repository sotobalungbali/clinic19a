
# -*- coding: utf-8 -*-
from odoo import api, models, fields

class IrModel(models.Model):
    _inherit = "ir.model"

    # Catatan:
    # - Beberapa field yang biasa dihitung di _compute_count antara lain:
    #   'count' dan 'count_active' (nama bisa berbeda antar versi, jadi kita cek dulu).
    # - Kita fallback ke 0 jika model tidak ada di registry (KeyError) atau jika pencarian gagal.

    def _compute_count(self):
        for rec in self:
            # Ambil model dari registry tanpa melempar KeyError
            ModelClass = self.env.registry.models.get(rec.model)
            if not ModelClass:
                # Model tidak tersedia di registry (mis. sedang preview uninstall)
                if "count" in rec._fields:
                    rec.count = 0
                if "count_active" in rec._fields:
                    rec.count_active = 0
                # Lanjut ke record berikutnya
                continue

            # Jika ada di registry, lakukan perhitungan dengan aman
            try:
                Model = self.env[rec.model].sudo()
                if "count" in rec._fields:
                    rec.count = Model.search_count([])
                if "count_active" in rec._fields:
                    if "active" in Model._fields:
                        rec.count_active = Model.search_count([("active", "=", True)])
                    else:
                        # Jika tidak ada kolom active di model tsb, samakan dengan count
                        rec.count_active = rec.count if "count" in rec._fields else 0
            except Exception:
                # Fallback aman jika ada kendala lain
                if "count" in rec._fields:
                    rec.count = 0
                if "count_active" in rec._fields:
                    rec.count_active = 0

