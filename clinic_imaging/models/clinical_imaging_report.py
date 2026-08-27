# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import safe_eval
from datetime import date, datetime
import re


# =============================================================================
# Report Template (Master)
# =============================================================================
class ClinicalImagingReportTemplate(models.Model):
    _name = "clinical.imaging.report.template"
    _description = "Clinical Imaging Report Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(string="Template Name", required=True, tracking=True)
    code = fields.Char(string="Code", index=True, tracking=True,
                       help="Short unique code for referencing this template (e.g., 'XR_CHEST_STD').")
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one("res.company", string="Company", required=True,
                                 default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    # -------------------------------------------------------------------------
    # Applicability / Scoping
    # -------------------------------------------------------------------------
    modality = fields.Selection(
        [
            ("XR", "X-Ray"),
            ("CT", "CT"),
            ("MR", "MRI"),
            ("US", "Ultrasound"),
            ("DX", "Digital Radiography"),
            ("MG", "Mammography"),
            ("NM", "Nuclear Medicine"),
            ("OT", "Other"),
        ],
        string="Modality",
        help="If set, this template is recommended for the selected modality.",
        tracking=True,
    )
    imaging_type_ids = fields.Many2many(
        "clinical.imaging.type",
        "clinical_imaging_report_template_type_rel",
        "template_id", "type_id",
        string="Imaging Types",
        help="Restrict usage to selected imaging types (leave empty for all).",
    )
    default_language = fields.Selection(
        lambda self: self.env['res.lang'].get_installed(),
        string="Default Language",
        help="Default language used when rendering this template.",
    )
    is_default_company = fields.Boolean(
        string="Company Default",
        help="If checked, acts as the fallback template for the company "
             "when result/imaging type does not specify one.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Layout & Components
    # -------------------------------------------------------------------------
    paperformat_id = fields.Many2one(
        "report.paperformat", string="Paper Format",
        help="Optional paper format override (otherwise report default is used).",
    )
    include_findings = fields.Boolean(string="Include Findings", default=True)
    include_key_images = fields.Boolean(string="Include Key Images", default=True)
    include_measurements = fields.Boolean(string="Include Measurements", default=True)
    show_author_signature = fields.Boolean(string="Show Author Signature", default=True)
    show_cosigner_signature = fields.Boolean(string="Show Co-signer Signature", default=False)

    header_html = fields.Html(
        string="Header (HTML)",
        sanitize=False,
        help="HTML fragment for the report header. Supports ${placeholders}.",
    )
    body_html = fields.Html(
        string="Body (HTML)",
        sanitize=False,
        help="Main body HTML. You can include ${placeholders} and sections below.",
    )
    footer_html = fields.Html(
        string="Footer (HTML)",
        sanitize=False,
        help="HTML fragment for the report footer. Supports ${placeholders}.",
    )

    section_ids = fields.One2many(
        "clinical.imaging.report.template.section", "template_id",
        string="Sections", copy=True
    )
    variable_ids = fields.One2many(
        "clinical.imaging.report.template.variable", "template_id",
        string="Variables", copy=True
    )
    asset_ids = fields.One2many(
        "clinical.imaging.report.template.asset", "template_id",
        string="Assets (CSS)", copy=True
    )

    # -------------------------------------------------------------------------
    # Versioning & Audit
    # -------------------------------------------------------------------------
    version = fields.Integer(string="Version", default=1, tracking=True)
    locked = fields.Boolean(
        string="Locked",
        help="Locked templates cannot be edited (use 'Duplicate' to create a new version).",
        tracking=True,
    )
    notes = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # COMPUTES / HELPERS
    # -------------------------------------------------------------------------
    section_count = fields.Integer(string="Section Count", compute="_compute_counts", store=False)
    variable_count = fields.Integer(string="Variable Count", compute="_compute_counts", store=False)

    def _compute_counts(self):
        for rec in self:
            rec.section_count = len(rec.section_ids)
            rec.variable_count = len(rec.variable_ids)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code_upper(self):
        for rec in self:
            if rec.code and rec.code.strip() != rec.code.strip().upper():
                rec.code = rec.code.strip().upper()

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Template Code must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    def write(self, vals):
        if any(field in vals for field in ["name", "code", "modality", "imaging_type_ids",
                                           "header_html", "body_html", "footer_html"]) and any(self.mapped("locked")):
            raise UserError(_("Locked templates cannot be edited. Duplicate to create a new version."))
        return super().write(vals)

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("%s (Copy)") % (self.name or "Template"))
        default.setdefault("version", (self.version or 1) + 1)
        default.setdefault("locked", False)
        default.setdefault("is_default_company", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # Rendering Pipeline (for preview / portal)
    # -------------------------------------------------------------------------
    PLACEHOLDER_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_\.]*)\}")

    def _ctx_get(self, ctx, dotted_key):
        """Get dot.notation value from dict-like context."""
        cur = ctx
        for part in dotted_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return ""
        return cur if cur is not None else ""

    def _replace_placeholders(self, html, ctx):
        if not html:
            return ""
        def repl(match):
            key = match.group(1)
            val = self._ctx_get(ctx, key)
            return str(val) if val is not None else ""
        return self.PLACEHOLDER_RE.sub(repl, html)

    def _build_base_context(self, result):
        """Build a base dict used to render placeholders."""
        patient = result.patient_id
        imaging = result.imaging_id
        studies = imaging.study_ids if imaging else self.env["clinical.imaging.study"]
        latest_study = studies[:1]
        appt = result.appointment_id
        enc = result.encounter_id

        # age in years (approx)
        age_years = ""
        if patient and patient.birthdate_date:
            today = date.today()
            bd = patient.birthdate_date
            age_years = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))

        # findings for convenience
        findings = []
        for f in result.finding_ids:
            findings.append({
                "title": f.display_name,
                "category": f.category or "",
                "severity": f.severity or "",
                "trend": f.trend or "",
                "body_region": f.body_region or "",
                "organ": f.organ or "",
                "segment": f.organ_segment or "",
                "side": f.side or "",
                "long_axis_mm": f.long_axis_mm or "",
                "short_axis_mm": f.short_axis_mm or "",
                "desc": f.description or "",
            })

        ctx = {
            # entities
            "company_name": result.company_id.name or "",
            "patient_name": patient.display_name if patient else "",
            "patient_code": patient.ref or "",
            "patient_dob": patient.birthdate_date and fields.Date.to_string(patient.birthdate_date) or "",
            "patient_age_years": age_years,
            "patient_phone": patient.phone or "",
            "patient_email": patient.email or "",
            "patient_gender": (patient.gender if hasattr(patient, "gender") else "") or "",
            "imaging_number": imaging.name if imaging else "",
            "imaging_type": imaging.imaging_type_id.name if imaging and imaging.imaging_type_id else "",
            "modality": imaging.imaging_type_id.modality if imaging and imaging.imaging_type_id else "",
            "device_name": imaging.device_id.name if imaging and imaging.device_id else "",
            "study_date": latest_study.study_datetime and fields.Datetime.to_string(latest_study.study_datetime) or "",
            "result_number": result.name,
            "result_datetime": result.signed_datetime and fields.Datetime.to_string(result.signed_datetime)
                               or (result.result_datetime and fields.Datetime.to_string(result.result_datetime)) or "",
            "doctor_name": result.author_doctor_id.name if result.author_doctor_id else "",
            "cosigner_name": result.co_signer_id.name if result.co_signer_id else "",
            "appointment_number": appt and appt.name or "",
            "encounter_number": enc and enc.name or "",
            # structured content
            "technique": result.technique or "",
            "comparison": result.comparison or "",
            "findings_text": result.findings or "",
            "impression": result.impression or "",
            "recommendations": result.recommendations or "",
            "findings": findings,
            # counts
            "finding_count": len(result.finding_ids),
            "key_image_count": len(result.key_image_ids),
            # misc
            "today": fields.Datetime.to_string(fields.Datetime.now()),
        }
        return ctx

    def _eval_variables(self, ctx):
        """Evaluate template-level variables with safe_eval."""
        local_ctx = {"ctx": ctx}
        # Do NOT expose env or records to safe_eval
        for var in self.variable_ids:
            try:
                value = safe_eval(var.expr or "None", local_ctx, nocopy=True)
            except Exception as e:
                value = _("(error: %s)") % str(e)
            ctx[var.code] = value
        return ctx

    def _render_sections(self, ctx):
        """Render sections to a single HTML string (ordered by sequence)."""
        parts = []
        for sec in self.section_ids.sorted(key=lambda s: (s.sequence, s.id)):
            if not sec.active:
                continue
            if sec.condition_expr:
                try:
                    if not safe_eval(sec.condition_expr, {"ctx": ctx}, nocopy=True):
                        continue
                except Exception:
                    # If condition fails, skip section silently (do not break report)
                    continue
            title_html = f"<h3>{sec.title}</h3>" if sec.title else ""
            body_html = self._replace_placeholders(sec.body_html or "", ctx)
            parts.append(f'<div class="cim-section cim-sec-{sec.code or sec.id}">{title_html}{body_html}</div>')
        return "\n".join(parts)

    def render_html_from_template(self, result):
        """
        Build a complete HTML string by combining header/body/footer with
        placeholder replacement and conditional sections.
        """
        if not result or result._name != "clinical.imaging.result":
            raise UserError(_("Rendering requires a 'clinical.imaging.result' record."))

        ctx = self._build_base_context(result)
        ctx = self._eval_variables(ctx)

        # default 'sections' placeholder for body_html
        sections_html = self._render_sections(ctx)
        ctx["sections"] = sections_html

        header = self._replace_placeholders(self.header_html or "", ctx)
        body = self._replace_placeholders(self.body_html or "", ctx)
        footer = self._replace_placeholders(self.footer_html or "", ctx)

        # Append CSS assets
        css_blocks = [a.css or "" for a in self.asset_ids if a.active]
        css_bundle = "\n".join(css_blocks)
        css_wrap = f"<style>{css_bundle}</style>" if css_bundle else ""

        # Final HTML
        html = f"""
        <div class="cim-report">
          {css_wrap}
          <div class="cim-header">{header}</div>
          <div class="cim-body">{body}</div>
          <div class="cim-footer">{footer}</div>
        </div>
        """
        return html

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_preview_with_result(self, result_id=None):
        """
        Preview this template with a selected Result in the standard PDF report.
        Requires the report action:
          - clinic_imaging.report_clinical_imaging_result
        The actual QWeb will read result.report_template_id or context override below.
        """
        self.ensure_one()
        if not result_id:
            raise UserError(_("Please provide a Clinical Imaging Result to preview with this template."))
        result = self.env["clinical.imaging.result"].browse(result_id).exists()
        if not result:
            raise UserError(_("The provided Result was not found."))
        # temporarily force template via context so QWeb can use it
        action = self.env.ref("clinic_imaging.report_clinical_imaging_result", raise_if_not_found=False)
        if not action:
            raise UserError(_("Report action 'clinic_imaging.report_clinical_imaging_result' not found."))
        ctx = dict(self.env.context or {})
        ctx["force_report_template_id"] = self.id
        return action.with_context(ctx).report_action(result)


# =============================================================================
# Report Template Sections
# =============================================================================
class ClinicalImagingReportTemplateSection(models.Model):
    _name = "clinical.imaging.report.template.section"
    _description = "Imaging Report Template Section"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one(
        "clinical.imaging.report.template", string="Template",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="template_id.company_id", store=True, readonly=True
    )

    active = fields.Boolean(default=True)
    sequence = fields.Integer(string="Sequence", default=10)
    code = fields.Char(string="Code", help="Short code used for CSS hooks or references.")
    title = fields.Char(string="Title", help="Optional section title (e.g., 'Technique', 'Findings').")
    body_html = fields.Html(
        string="Body (HTML)", sanitize=False,
        help="HTML with ${placeholders}. Example: '<p>${technique}</p>'."
    )
    condition_expr = fields.Char(
        string="Condition (safe_eval)",
        help="Python expression evaluated with 'ctx' dict. If True, the section is shown. "
             "Example: 'ctx.get(\"finding_count\",0) > 0'."
    )

    @api.constrains("condition_expr")
    def _check_condition_expr(self):
        # Try a dry-run with empty ctx to catch syntax errors early.
        for rec in self:
            if rec.condition_expr:
                try:
                    safe_eval(rec.condition_expr, {"ctx": {}}, nocopy=True)
                except Exception as e:
                    raise ValidationError(_("Invalid condition expression: %s") % str(e))


# =============================================================================
# Report Template Variables
# =============================================================================
class ClinicalImagingReportTemplateVariable(models.Model):
    _name = "clinical.imaging.report.template.variable"
    _description = "Imaging Report Template Variable"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one(
        "clinical.imaging.report.template", string="Template",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="template_id.company_id", store=True, readonly=True
    )

    sequence = fields.Integer(string="Sequence", default=10)
    code = fields.Char(
        string="Variable Code", required=True,
        help="Name used as ${code} in placeholders."
    )
    expr = fields.Text(
        string="Expression (safe_eval)", required=True,
        help="Python expression evaluated with 'ctx' dict. "
             "Result will be injected into placeholders as ${code}. "
             "Example: 'f\"Age: {ctx.get('patient_age_years','')} years\"'"
    )
    description = fields.Char(string="Description")
    active = fields.Boolean(default=True)

    _code_template_unique = models.Constraint(
        'unique(code, template_id)',
        'Variable Code must be unique per template.',
    )


# =============================================================================
# Report Template Assets (CSS)
# =============================================================================
class ClinicalImagingReportTemplateAsset(models.Model):
    _name = "clinical.imaging.report.template.asset"
    _description = "Imaging Report Template Asset"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one(
        "clinical.imaging.report.template", string="Template",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="template_id.company_id", store=True, readonly=True
    )

    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Asset Name", required=True)
    css = fields.Text(string="CSS", help="Raw CSS to include inside <style>...</style>.")
    active = fields.Boolean(default=True)

# DIPINDAH KE FILE clinical_imaging_kpi.py
# =============================================================================
# Extensions on Result: defaulting & rendering helpers
# =============================================================================
# class ClinicalImagingResult(models.Model):
#     _inherit = "clinical.imaging.result"

#     report_template_id = fields.Many2one(
#         "clinical.imaging.report.template",
#         string="Report Template",
#         help="Template used to render this result. "
#              "Defaults from Imaging Type or company default.",
#     )

#     @api.onchange("imaging_id")
#     def _onchange_imaging_set_default_template(self):
#         for rec in self:
#             if rec.report_template_id:
#                 continue
#             tmpl = rec._get_default_report_template()
#             if tmpl:
#                 rec.report_template_id = tmpl.id

#     def _get_default_report_template(self):
#         """Resolve default template by priority:
#            1) Imaging Type's default report_template_id (if set in type)
#            2) Company default template (is_default_company)
#            3) Any template filtered by modality
#         """
#         self.ensure_one()
#         imaging = self.imaging_id
#         # from type
#         if imaging and imaging.imaging_type_id and imaging.imaging_type_id.report_template_id:
#             return imaging.imaging_type_id.report_template_id
#         # company default
#         tmpl = self.env["clinical.imaging.report.template"].search([
#             ("company_id", "=", self.company_id.id),
#             ("is_default_company", "=", True),
#             ("active", "=", True),
#         ], limit=1, order="sequence, id")
#         if tmpl:
#             return tmpl
#         # modality match
#         modality = imaging.imaging_type_id.modality if imaging and imaging.imaging_type_id else False
#         if modality:
#             tmpl = self.env["clinical.imaging.report.template"].search([
#                 ("company_id", "=", self.company_id.id),
#                 ("modality", "=", modality),
#                 ("active", "=", True),
#             ], limit=1, order="sequence, id")
#             if tmpl:
#                 return tmpl
#         # fallback any active
#         return self.env["clinical.imaging.report.template"].search([
#             ("company_id", "=", self.company_id.id),
#             ("active", "=", True),
#         ], limit=1, order="sequence, id")

#     def action_preview_current_template(self):
#         """Preview currently selected template using standard PDF report."""
#         self.ensure_one()
#         if not self.report_template_id:
#             tmpl = self._get_default_report_template()
#             if tmpl:
#                 self.report_template_id = tmpl.id
#         report = self.env.ref("clinic_imaging.report_clinical_imaging_result", raise_if_not_found=False)
#         if not report:
#             raise UserError(_("Report action 'clinic_imaging.report_clinical_imaging_result' not found."))
#         return report.report_action(self)

#     # Expose HTML (useful for portal/wizard)
#     def get_rendered_html(self):
#         """Return the HTML string produced by the selected template."""
#         self.ensure_one()
#         tmpl = self.report_template_id or self._get_default_report_template()
#         if not tmpl:
#             raise UserError(_("No report template available for rendering."))
#         return tmpl.render_html_from_template(self)
