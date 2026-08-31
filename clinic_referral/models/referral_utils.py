# -*- coding: utf-8 -*-


def optional_model(env, model_name):
    """Return an Odoo model proxy only when the model exists."""
    try:
        return env[model_name]
    except KeyError:
        return False


def normalize_boolean_search(operator, value):
    """Normalize Odoo Boolean search forms including `in` / `not in`."""
    if operator not in {"=", "!=", "in", "not in"}:
        return NotImplemented
    if operator in {"=", "!="}:
        requested = bool(value)
        return not requested if operator == "!=" else requested
    raw_values = list(value) if isinstance(value, (list, tuple, set)) else [value]
    normalized = {bool(item) for item in raw_values}
    if operator == "in":
        if not normalized:
            return "none"
        if normalized == {True, False}:
            return "all"
        return True in normalized
    if not normalized:
        return "all"
    if normalized == {True, False}:
        return "none"
    return False in normalized


def default_working_branch(env):
    """Resolve a safe working/default branch for the active company."""
    user = env.user
    company = env.company
    if "working_branch_id" in user._fields:
        branch = user.working_branch_id
        if branch and branch.company_id == company:
            return branch
    if "default_branch_id" in company._fields:
        branch = company.default_branch_id
        if branch and branch.company_id == company:
            return branch
    return env["clinic.branch"].browse()

