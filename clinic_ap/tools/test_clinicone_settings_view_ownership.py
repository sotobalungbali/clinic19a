from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
settings = ROOT / "views" / "res_config_settings_views.xml"
root = ET.parse(settings).getroot()

view = root.find(".//record[@id='view_clinic_ap_settings_form'][@model='ir.ui.view']")
assert view is not None
assert view.find("field[@name='inherit_id']").get("ref") == "base.res_config_settings_view_form"
assert (view.find("field[@name='mode']").text or "").strip() == "extension"

action = root.find(".//record[@id='action_clinic_ap_settings'][@model='ir.actions.act_window']")
assert action is not None
assert action.find("field[@name='view_id']").get("eval") == "False"
assert (action.find("field[@name='path']").text or "").strip() == "clinic-ap-settings"

print("CLINIC_AP_SETTINGS_OWNERSHIP: PASS")

