# SECURITY MODEL — HARD GATE 10

- Authoritative event and event-line records are immutable from ordinary ORM/UI use.
- Event creation requires the internal audit context or superuser path used only by the service.
- Delete and copy are denied for immutable evidence.
- Policy/Review workflows have explicit backend permission checks where workflow authority matters.
- Evidence record rules enforce allowed company and branch scope.
- Global evidence rules are intentionally restrictive so wider group rules cannot bypass them.
- Historical ACLs on `clinic.audit.log` are additive and cannot be revoked by a narrower ACL;
  therefore the final legacy surface is hardened at registry time.
- Privacy-sensitive names/binaries/HTML and very large values are stored as digest/redaction
  metadata instead of blindly duplicating PHI/secrets.
- Fail-closed is enabled by default: if authoritative evidence persistence fails, the business
  mutation is rolled back unless an administrator explicitly disables that setting.
