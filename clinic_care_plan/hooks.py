# -*- coding: utf-8 -*-
"""Installation-safe UI integration for already-installed ClinicOne addons.

Presentation XML-IDs are intentionally *not* hard dependencies of the manifest.
ClinicOne installations can contain an older XML-data revision of an already
installed sibling addon. The care-plan business models must still install in
that situation.
"""

import logging

_logger = logging.getLogger(__name__)


def _find_form_view(env, model_name):
    """Return a usable primary/base form view for a model, if one exists."""
    View = env["ir.ui.view"].sudo()
    return View.search(
        [
            ("model", "=", model_name),
            ("type", "=", "form"),
            ("active", "=", True),
            ("inherit_id", "=", False),
        ],
        order="priority, id",
        limit=1,
    )


def _ensure_optional_view(env, *, name, model, parent, arch):
    """Create one optional inherited view, without turning it into a blocker."""
    if not parent:
        return False

    View = env["ir.ui.view"].sudo()
    existing = View.search(
        [("name", "=", name), ("model", "=", model)],
        limit=1,
    )
    values = {
        "name": name,
        "model": model,
        "inherit_id": parent.id,
        "arch_db": arch,
        "priority": 90,
    }
    if existing:
        existing.write(values)
        return existing
    return View.create(values)


def _install_patient_view(env):
    parent = _find_form_view(env, "clinic.patient")
    if not parent:
        return

    arch = parent.arch_db or ""
    fragments = []
    if 'name="button_box"' in arch or "name='button_box'" in arch:
        fragments.append("""
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_view_care_plans" type="object"
                        class="oe_stat_button" icon="fa-heartbeat">
                    <field name="care_plan_count" widget="statinfo" string="Care Plans"/>
                </button>
            </xpath>
        """)
    if "<notebook" in arch:
        fragments.append("""
            <xpath expr="//notebook" position="inside">
                <page string="Care Plans" name="care_plan_integration">
                    <group>
                        <button name="action_create_care_plan" type="object"
                                string="New Care Plan" class="btn-primary" icon="fa-plus"/>
                        <field name="active_care_plan_count" readonly="1"/>
                    </group>
                    <field name="care_plan_ids" readonly="1">
                        <list decoration-success="state == 'completed'"
                              decoration-warning="state == 'on_hold'"
                              decoration-muted="state in ('cancelled','archived')">
                            <field name="name"/>
                            <field name="display_name"/>
                            <field name="doctor_id"/>
                            <field name="plan_type"/>
                            <field name="start_date"/>
                            <field name="progress" widget="progressbar"/>
                            <field name="state" widget="badge"/>
                        </list>
                    </field>
                </page>
            </xpath>
        """)
    if fragments:
        _ensure_optional_view(
            env,
            name="clinic.patient.form.care.plan.integration",
            model="clinic.patient",
            parent=parent,
            arch="<data>%s</data>" % "\n".join(fragments),
        )


def _install_doctor_view(env):
    parent = _find_form_view(env, "clinic.doctor")
    if not parent:
        return
    arch = parent.arch_db or ""
    if 'name="button_box"' not in arch and "name='button_box'" not in arch:
        return
    _ensure_optional_view(
        env,
        name="clinic.doctor.form.care.plan.integration",
        model="clinic.doctor",
        parent=parent,
        arch="""
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_view_care_plans" type="object"
                        class="oe_stat_button" icon="fa-heartbeat">
                    <field name="care_plan_count" widget="statinfo" string="Care Plans"/>
                </button>
            </xpath>
        """,
    )


def _install_encounter_view(env):
    parent = _find_form_view(env, "clinic.encounter")
    if not parent:
        return
    arch = parent.arch_db or ""
    if 'name="button_box"' not in arch and "name='button_box'" not in arch:
        return
    _ensure_optional_view(
        env,
        name="clinic.encounter.form.care.plan.integration",
        model="clinic.encounter",
        parent=parent,
        arch="""
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_view_care_plans" type="object"
                        class="oe_stat_button" icon="fa-heartbeat">
                    <field name="care_plan_count" widget="statinfo" string="Care Plans"/>
                </button>
            </xpath>
        """,
    )


def _reparent_root_menu(env):
    """Attach the local root below ClinicOne when the upstream menu exists."""
    menu = env.ref(
        "clinic_care_plan.menu_clinic_care_plan_root",
        raise_if_not_found=False,
    )
    if not menu:
        return

    parent = env.ref("clinic_base.menu_root", raise_if_not_found=False)
    if not parent:
        parent = env.ref("clinic_patient.menu_root", raise_if_not_found=False)
    if parent and menu.parent_id != parent:
        menu.sudo().parent_id = parent


def post_init_hook(env):
    """Apply optional presentation integrations after the core addon installs."""
    # Odoo 19 calls post-init hooks with an Environment. Keep all sibling view
    # integration optional so presentation drift cannot block installation.
    for installer in (
        _reparent_root_menu,
        _install_patient_view,
        _install_doctor_view,
        _install_encounter_view,
    ):
        try:
            with env.cr.savepoint():
                installer(env)
        except Exception:
            _logger.exception(
                "Optional clinic_care_plan integration failed in %s; core addon remains installed.",
                installer.__name__,
            )
