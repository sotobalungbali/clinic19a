# clinic_referral 19.0.2.0.6 — Historical Business Effective Dates

MASTER PROMPT 14 exposed a source-driven historical-generation gap: Referral workflow actions persisted current system time only, which prevented business-valid deterministic historical Referral events without falsifying technical audit timestamps.

This additive repair introduces optional effective business datetime/date parameters to Confirm, Convert, downstream mark_converted, Cancel, and Expire workflows. Existing callers that omit the optional parameter retain the original current-time/date behavior. No state transition, ACL, record rule, sequence, or conversion ownership is changed.
