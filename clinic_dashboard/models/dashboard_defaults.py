"""Built-in dashboard blueprints.

Only report keys and metric codes owned by `clinic_reports` appear here.
No transactional KPI formula is duplicated in Dashboard.
"""

DASHBOARD_TYPE_SELECTION = [
    ("executive", "Executive Overview"),
    ("financial", "Financial Performance"),
    ("operational", "Operations Performance"),
    ("clinical", "Clinical Performance"),
    ("room", "Room Utilization"),
    ("experience", "Patient Experience"),
]

DISPLAY_STYLE_SELECTION = [
    ("kpi", "KPI Card"),
    ("progress", "Progress / Target"),
    ("trend", "Trend Card"),
]

DIRECTION_SELECTION = [
    ("neutral", "Neutral"),
    ("higher_good", "Higher is Better"),
    ("lower_good", "Lower is Better"),
]

DEFAULT_DASHBOARDS = [
    {
        "code": "EXECUTIVE",
        "name": "Executive Overview",
        "dashboard_type": "executive",
        "sequence": 10,
        "default_period": "month",
        "description": "Cross-functional executive view of revenue, collection, operations, clinical throughput and patient experience.",
        "widgets": [
            ("fin_revenue", "GROSS_REVENUE", "Gross Revenue", "fa-money", "trend", "neutral", 3, False, False, False),
            ("fin_revenue", "COLLECTION_RATE", "Collection Rate", "fa-line-chart", "progress", "higher_good", 3, 95.0, 80.0, 60.0),
            ("fin_receivables", "AR_OVERDUE_AMOUNT", "Overdue Receivables", "fa-exclamation-circle", "trend", "lower_good", 3, False, False, False),
            ("fin_cashflow", "NET_CASHFLOW", "Net Cash Flow", "fa-bank", "trend", "neutral", 3, False, False, False),
            ("ops_booking", "BOOKING_COMPLETION_RATE", "Booking Completion", "fa-calendar-check-o", "progress", "higher_good", 3, 90.0, 80.0, 60.0),
            ("ops_queue", "QUEUE_AVG_WAIT", "Average Queue Wait", "fa-clock-o", "trend", "lower_good", 3, 10.0, 20.0, 40.0),
            ("clinical_encounter", "ENCOUNTER_COMPLETION_RATE", "Encounter Completion", "fa-stethoscope", "progress", "higher_good", 3, 95.0, 80.0, 60.0),
            ("clinical_feedback", "FEEDBACK_NPS", "Patient NPS", "fa-smile-o", "trend", "higher_good", 3, 50.0, 30.0, 0.0),
        ],
    },
    {
        "code": "FINANCIAL",
        "name": "Financial Performance",
        "dashboard_type": "financial",
        "sequence": 20,
        "default_period": "month",
        "description": "Revenue, collection, receivable, payable, cash-flow, tax and payer performance.",
        "widgets": [
            ("fin_revenue", "GROSS_REVENUE", "Gross Revenue", "fa-money", "trend", "neutral", 3, False, False, False),
            ("fin_revenue", "COLLECTED_AMOUNT", "Collected Amount", "fa-check-circle", "trend", "higher_good", 3, False, False, False),
            ("fin_revenue", "OUTSTANDING_AMOUNT", "Billing Outstanding", "fa-hourglass-half", "trend", "lower_good", 3, False, False, False),
            ("fin_revenue", "COLLECTION_RATE", "Collection Rate", "fa-percent", "progress", "higher_good", 3, 95.0, 80.0, 60.0),
            ("fin_receivables", "AR_OVERDUE_AMOUNT", "AR Overdue", "fa-warning", "trend", "lower_good", 3, False, False, False),
            ("fin_payables", "AP_RESIDUAL", "AP Outstanding", "fa-credit-card", "trend", "lower_good", 3, False, False, False),
            ("fin_cashflow", "NET_CASHFLOW", "Net Cash Flow", "fa-bank", "trend", "neutral", 3, False, False, False),
            ("fin_tax", "NET_PPN", "Net PPN", "fa-calculator", "kpi", "neutral", 3, False, False, False),
            ("fin_insurance", "AUTH_APPROVAL_RATE", "Insurance Approval Rate", "fa-shield", "progress", "higher_good", 3, 90.0, 75.0, 50.0),
        ],
    },
    {
        "code": "OPERATIONS",
        "name": "Operations Performance",
        "dashboard_type": "operational",
        "sequence": 30,
        "default_period": "month",
        "description": "Booking, queue, room, inventory, membership and wallet operating performance.",
        "widgets": [
            ("ops_booking", "BOOKING_COUNT", "Bookings", "fa-calendar", "trend", "neutral", 3, False, False, False),
            ("ops_booking", "BOOKING_COMPLETION_RATE", "Booking Completion", "fa-check-square-o", "progress", "higher_good", 3, 90.0, 80.0, 60.0),
            ("ops_booking", "BOOKING_CANCEL_RATE", "Booking Cancellation", "fa-times-circle", "progress", "lower_good", 3, 5.0, 15.0, 30.0),
            ("ops_queue", "QUEUE_AVG_WAIT", "Average Queue Wait", "fa-clock-o", "trend", "lower_good", 3, 10.0, 20.0, 40.0),
            ("ops_queue", "QUEUE_SLA_BREACH_RATE", "Queue SLA Breach", "fa-bell", "progress", "lower_good", 3, 5.0, 10.0, 25.0),
            ("ops_room", "ROOM_AVG_OCCUPANCY", "Average Room Occupancy", "fa-building-o", "trend", "neutral", 3, False, False, False),
            ("ops_inventory", "INVENTORY_TOTAL_QTY", "Clinical Inventory Used", "fa-cubes", "trend", "neutral", 3, False, False, False),
            ("ops_membership", "MEMBERSHIP_ACTIVE", "Active Memberships", "fa-id-card-o", "trend", "higher_good", 3, False, False, False),
            ("ops_wallet", "WALLET_NET", "Net Wallet Movement", "fa-google-wallet", "trend", "neutral", 3, False, False, False),
        ],
    },
    {
        "code": "CLINICAL",
        "name": "Clinical Performance",
        "dashboard_type": "clinical",
        "sequence": 40,
        "default_period": "month",
        "description": "Encounter, procedure, triage, safety, post-care and experience performance.",
        "widgets": [
            ("clinical_encounter", "ENCOUNTER_COUNT", "Encounters", "fa-stethoscope", "trend", "neutral", 3, False, False, False),
            ("clinical_encounter", "ENCOUNTER_COMPLETION_RATE", "Encounter Completion", "fa-check-circle-o", "progress", "higher_good", 3, 95.0, 80.0, 60.0),
            ("clinical_procedure", "PROCEDURE_COMPLETION_RATE", "Procedure Completion", "fa-medkit", "progress", "higher_good", 3, 95.0, 80.0, 60.0),
            ("clinical_triage", "TRIAGE_SLA_BREACH_RATE", "Triage SLA Breach", "fa-heartbeat", "progress", "lower_good", 3, 5.0, 10.0, 25.0),
            ("clinical_triage", "TRIAGE_ABNORMAL_VITALS", "Abnormal Vitals Signals", "fa-thermometer-half", "trend", "neutral", 3, False, False, False),
            ("clinical_adverse", "AE_SERIOUS", "Serious Adverse Events", "fa-exclamation-triangle", "trend", "lower_good", 3, 0.0, 1.0, 5.0),
            ("clinical_postcare", "POSTCARE_COMPLETION_RATE", "Post-Care Completion", "fa-refresh", "progress", "higher_good", 3, 90.0, 75.0, 50.0),
            ("clinical_postcare", "POSTCARE_RED_FLAGS", "Post-Care Red Flags", "fa-flag", "trend", "lower_good", 3, 0.0, 1.0, 5.0),
            ("clinical_feedback", "FEEDBACK_NPS", "Patient NPS", "fa-smile-o", "trend", "higher_good", 3, 50.0, 30.0, 0.0),
        ],
    },
    {
        "code": "ROOM",
        "name": "Room Utilization",
        "dashboard_type": "room",
        "sequence": 50,
        "default_period": "month",
        "description": "Room assignment volume, occupancy, service duration and queue context.",
        "widgets": [
            ("ops_room", "ROOM_ASSIGNMENTS", "Room Assignments", "fa-exchange", "trend", "neutral", 4, False, False, False),
            ("ops_room", "ROOMS_USED", "Rooms Used", "fa-building", "trend", "neutral", 4, False, False, False),
            ("ops_room", "ROOM_ACTIVE", "Active Assignments", "fa-sign-in", "kpi", "neutral", 4, False, False, False),
            ("ops_room", "ROOM_TOTAL_OCCUPANCY", "Total Occupancy Minutes", "fa-clock-o", "trend", "neutral", 4, False, False, False),
            ("ops_room", "ROOM_AVG_OCCUPANCY", "Average Occupancy", "fa-hourglass-half", "trend", "neutral", 4, False, False, False),
            ("ops_room", "ROOM_AVG_SERVICE", "Average Service Duration", "fa-user-md", "trend", "neutral", 4, False, False, False),
            ("ops_queue", "QUEUE_AVG_WAIT", "Queue Wait Context", "fa-users", "trend", "lower_good", 4, 10.0, 20.0, 40.0),
        ],
    },
    {
        "code": "EXPERIENCE",
        "name": "Patient Experience",
        "dashboard_type": "experience",
        "sequence": 60,
        "default_period": "month",
        "description": "Satisfaction, NPS, complaints, escalation and post-care outcome signals.",
        "widgets": [
            ("clinical_feedback", "FEEDBACK_COUNT", "Feedback Responses", "fa-comments", "trend", "neutral", 3, False, False, False),
            ("clinical_feedback", "FEEDBACK_AVG_RATING", "Average Rating", "fa-star", "progress", "higher_good", 3, 4.5, 4.0, 3.0),
            ("clinical_feedback", "FEEDBACK_NPS", "Net Promoter Score", "fa-smile-o", "trend", "higher_good", 3, 50.0, 30.0, 0.0),
            ("clinical_feedback", "FEEDBACK_PROMOTERS", "Promoters", "fa-thumbs-up", "trend", "higher_good", 3, False, False, False),
            ("clinical_feedback", "FEEDBACK_DETRACTORS", "Detractors", "fa-thumbs-down", "trend", "lower_good", 3, False, False, False),
            ("clinical_feedback", "FEEDBACK_COMPLAINTS", "Complaints", "fa-commenting-o", "trend", "lower_good", 3, False, False, False),
            ("clinical_feedback", "FEEDBACK_ESCALATION_RATE", "Escalation Threshold Rate", "fa-level-up", "progress", "lower_good", 3, 5.0, 10.0, 25.0),
            ("clinical_postcare", "POSTCARE_COMPLETION_RATE", "Post-Care Completion", "fa-refresh", "progress", "higher_good", 3, 90.0, 75.0, 50.0),
        ],
    },
]

