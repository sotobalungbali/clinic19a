from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "security/clinic_incident_security.xml"

root = ET.parse(SECURITY).getroot()
labels = {}

for record in root.findall("record"):
    model = record.attrib.get("model")
    if model not in {"ir.module.category", "res.groups.privilege"}:
        continue
    field = record.find("./field[@name='name']")
    labels[(model, record.attrib.get("id"))] = (field.text or "")

expected = "ClinicOne Incident and Event"

assert labels[("ir.module.category", "module_category_incident")] == expected
assert labels[("res.groups.privilege", "privilege_incident")] == expected
assert all("&" not in label for label in labels.values())

print("USER_SETTINGS_LABEL_SAFETY: PASS")
