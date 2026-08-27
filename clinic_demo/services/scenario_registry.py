"""Version-controlled scenario identities from MASTER PROMPT 04."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioDefinition:
    key: str
    name: str
    profiles: tuple
    domain: str
    generator_key: str
    phase: str
    temporal: str
    golden_refs: str


_SCENARIO_DATA = [{'key': 'SCN-FOUNDATION-01', 'name': 'Multi-branch ClinicOne Foundation', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Foundation', 'generator_key': 'foundation.native', 'phase': '08_foundation', 'temporal': 'T0', 'golden_refs': 'DEMO-BRANCH-*'}, {'key': 'SCN-WORKFORCE-01', 'name': 'Enterprise Workforce & Provider Roster', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Workforce', 'generator_key': 'workforce.staff', 'phase': '09_workforce', 'temporal': 'T0 + future schedule', 'golden_refs': 'DEMO-DOC-*; DEMO-NUR-*; DEMO-STAFF-*'}, {'key': 'SCN-PATIENT-NEW-01', 'name': 'New Patient Registration', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Patient', 'generator_key': 'patient.personas', 'phase': '10_patient', 'temporal': 'T0', 'golden_refs': 'DEMO-PAT-NEW-*'}, {'key': 'SCN-PATIENT-RET-01', 'name': 'Returning Patient Longitudinal View', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Patient', 'generator_key': 'patient.personas', 'phase': '10_patient', 'temporal': 'T-365..T0', 'golden_refs': 'DEMO-PAT-RET-*'}, {'key': 'SCN-REFERRAL-01', 'name': 'Referral Source to Converted Booking', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Referral', 'generator_key': 'operations.referral', 'phase': '14_frontoffice', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-REF-001'}, {'key': 'SCN-REFERRAL-02', 'name': 'Referral Exception Mix', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Referral', 'generator_key': 'operations.referral', 'phase': '14_frontoffice', 'temporal': 'T-30..T+30', 'golden_refs': 'DEMO-REF-EXC-*'}, {'key': 'SCN-BOOKING-TODAY-01', 'name': 'Active Clinic Day Schedule', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Booking', 'generator_key': 'resources.rooms_devices', 'phase': '12_resources', 'temporal': 'T0', 'golden_refs': 'DEMO-BOOK-TODAY-*'}, {'key': 'SCN-BOOKING-HIST-01', 'name': 'Historical Booking Trend', 'profiles': ['Standard', 'Full Enterprise'], 'domain': 'Booking', 'generator_key': 'operations.booking', 'phase': '14_frontoffice', 'temporal': 'T-365..T-1', 'golden_refs': 'DEMO-BOOK-HIST-*'}, {'key': 'SCN-QUEUE-01', 'name': 'Arrival, Queue & Room Flow', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Queue/Triage', 'generator_key': 'resources.rooms_devices', 'phase': '12_resources', 'temporal': 'T0', 'golden_refs': 'DEMO-QUEUE-*; DEMO-TRIAGE-*'}, {'key': 'SCN-TRIAGE-ABN-01', 'name': 'Abnormal Vitals Requires Attention', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Triage', 'generator_key': 'operations.queue_triage', 'phase': '15_arrival', 'temporal': 'T0', 'golden_refs': 'DEMO-TRIAGE-ABN-001'}, {'key': 'SCN-ENCOUNTER-01', 'name': 'New Patient Core Encounter', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Encounter', 'generator_key': 'master.catalog', 'phase': '11_master', 'temporal': 'T0', 'golden_refs': 'DEMO-ENC-001'}, {'key': 'SCN-ENCOUNTER-RET-01', 'name': 'Returning Patient Encounter with History', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Encounter', 'generator_key': 'operations.encounter', 'phase': '16_clinical', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-ENC-RET-*'}, {'key': 'SCN-SESSION-01', 'name': 'Treatment Session with Consumption and Billing', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Treatment Session', 'generator_key': 'master.catalog', 'phase': '11_master', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-SESSION-001'}, {'key': 'SCN-SESSION-02', 'name': 'Treatment Session No-show / Cancel', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Treatment Session', 'generator_key': 'operations.treatment_session', 'phase': '16_clinical', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-SESSION-EXC-*'}, {'key': 'SCN-CONSENT-01', 'name': 'Consent Lifecycle', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Consent/Legal', 'generator_key': 'master.consent', 'phase': '11_master', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-CONSENT-*'}, {'key': 'SCN-IMAGING-01', 'name': 'Imaging Request to Reviewed Result', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Imaging', 'generator_key': 'clinical.imaging', 'phase': '17_advanced', 'temporal': 'Historical + T0 + Future', 'golden_refs': 'DEMO-IMG-*'}, {'key': 'SCN-EMAR-01', 'name': 'Medication Order & Administration', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'eMAR', 'generator_key': 'clinical.emar', 'phase': '17_advanced', 'temporal': 'Historical + T0 + Future schedule', 'golden_refs': 'DEMO-EMAR-*'}, {'key': 'SCN-CARE-01', 'name': 'Recurring Care Plan', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Care Plan', 'generator_key': 'clinical.care_postcare', 'phase': '17_advanced', 'temporal': 'Historical + T0 + Future', 'golden_refs': 'DEMO-CARE-*'}, {'key': 'SCN-TELE-01', 'name': 'Telemedicine with Secure Messaging', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Telemedicine', 'generator_key': 'clinical.telemedicine', 'phase': '17_advanced', 'temporal': 'Historical + T0 + Future', 'golden_refs': 'DEMO-TELE-*'}, {'key': 'SCN-PACKAGE-01', 'name': 'Package Allocation & Consumption', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Commercial', 'generator_key': 'master.commercial', 'phase': '11_master', 'temporal': 'Historical + T0 + Future entitlement', 'golden_refs': 'DEMO-PKG-*'}, {'key': 'SCN-MEMBERSHIP-01', 'name': 'Membership Contract & Benefits', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Commercial', 'generator_key': 'master.commercial', 'phase': '11_master', 'temporal': 'Historical + T0 + Future renewal', 'golden_refs': 'DEMO-MEM-*'}, {'key': 'SCN-BILLING-01', 'name': 'Self-pay Billing & Payment', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Billing/Finance', 'generator_key': 'commercial.billing', 'phase': '18_commercial', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-BILL-*'}, {'key': 'SCN-AR-01', 'name': 'Receivable / Partial / Overdue', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Finance', 'generator_key': 'commercial.ar', 'phase': '18_commercial', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-AR-*'}, {'key': 'SCN-AP-01', 'name': 'Vendor Payable & Aging', 'profiles': ['Standard', 'Full Enterprise'], 'domain': 'Finance', 'generator_key': 'commercial.ap', 'phase': '18_commercial', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-AP-*'}, {'key': 'SCN-WALLET-01', 'name': 'Wallet Top-up and Service Payment', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Finance', 'generator_key': 'master.commercial', 'phase': '11_master', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-WALLET-*'}, {'key': 'SCN-INSURANCE-01', 'name': 'Insurance Authorization & Claim', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Insurance', 'generator_key': 'master.commercial', 'phase': '11_master', 'temporal': 'Historical + T0 + Future auth', 'golden_refs': 'DEMO-INS-*'}, {'key': 'SCN-FEEDBACK-01', 'name': 'Feedback to Service Recovery', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Experience', 'generator_key': 'exception.feedback', 'phase': '19_exception', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-FB-*'}, {'key': 'SCN-INCIDENT-01', 'name': 'Incident Investigation & CAPA', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Incident/Quality', 'generator_key': 'exception.incident_quality', 'phase': '19_exception', 'temporal': 'Historical + T0 + Future CAPA due', 'golden_refs': 'DEMO-INC-*'}, {'key': 'SCN-QUALITY-01', 'name': 'Quality Check with Nonconformity', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Incident/Quality', 'generator_key': 'exception.incident_quality', 'phase': '19_exception', 'temporal': 'Historical + T0', 'golden_refs': 'DEMO-QUAL-*'}, {'key': 'SCN-API-01', 'name': 'Safe Simulated Integration Failure', 'profiles': ['Standard', 'Full Enterprise'], 'domain': 'Integration', 'generator_key': 'digital.ecommerce_marketing_portal', 'phase': '19_exception', 'temporal': 'T0', 'golden_refs': 'DEMO-API-*'}, {'key': 'SCN-PIPELINE-01', 'name': '90-day Future Operational Pipeline', 'profiles': ['Standard', 'Full Enterprise'], 'domain': 'Future Pipeline', 'generator_key': 'operations.booking', 'phase': '14_frontoffice', 'temporal': 'T+1..T+90', 'golden_refs': 'DEMO-FUT-*'}, {'key': 'SCN-REPORT-01', 'name': 'Management Report Run', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Reports', 'generator_key': 'management.reports', 'phase': '21_reports', 'temporal': 'after source dataset', 'golden_refs': 'DEMO-REPORT-*'}, {'key': 'SCN-DASH-01', 'name': 'Executive Dashboard Refresh', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Dashboard', 'generator_key': 'management.dashboard', 'phase': '22_management', 'temporal': 'after reports/source data', 'golden_refs': 'DEMO-DASH-*'}, {'key': 'SCN-ANALYTICS-01', 'name': 'KPI Snapshot / Cohort / Forecast', 'profiles': ['Compact', 'Standard', 'Full Enterprise'], 'domain': 'Analytics', 'generator_key': 'management.analytics', 'phase': '22_management', 'temporal': 'multiple time periods after source data', 'golden_refs': 'DEMO-ANL-*'}]

SCENARIOS = {
    item["key"]: ScenarioDefinition(
        key=item["key"],
        name=item["name"],
        profiles=tuple(item["profiles"]),
        domain=item["domain"],
        generator_key=item["generator_key"],
        phase=item["phase"],
        temporal=item["temporal"],
        golden_refs=item["golden_refs"],
    )
    for item in _SCENARIO_DATA
}


class ScenarioRegistry:
    @staticmethod
    def get(key):
        return SCENARIOS[key]

    @staticmethod
    def all():
        return tuple(SCENARIOS[key] for key in sorted(SCENARIOS))

    @staticmethod
    def for_profile(profile):
        label = {
            "compact": "Compact",
            "standard": "Standard",
            "full_enterprise": "Full Enterprise",
        }[profile]
        return tuple(
            scenario for scenario in ScenarioRegistry.all()
            if label in scenario.profiles
        )

    @staticmethod
    def validate():
        keys = [scenario.key for scenario in ScenarioRegistry.all()]
        if len(keys) != len(set(keys)):
            raise ValueError("Scenario keys must be unique.")
        if len(keys) != 34:
            raise ValueError(f"Expected 34 Prompt-04 scenarios, found {len(keys)}.")
        return True
