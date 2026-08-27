# Telemedicine & Secure Messaging Security Model

## Patient authorization

Patient routes require:
1. authenticated Odoo user;
2. existing Clinic Portal Profile;
3. Portal Profile state = Active;
4. exact Patient Contact / Patient Card match;
5. exact Company match;
6. explicit feature grant:
   - Teleconsultation, or
   - Secure Messaging;
7. browser record ID intersected with that exact ownership domain.

No broad commercial-family domain is used.

## Secure Messaging

Message text:
- stored in a dedicated model;
- not posted to generic `mail.thread`;
- not sent by email as a substitute for secure chat;
- immutable after send;
- has controlled read evidence.

## Files

Patient/clinic file sharing:
- PDF/JPEG/PNG only;
- extension and MIME validation;
- configured size ceiling;
- SHA-256 evidence;
- immutable after upload;
- custom authenticated download route;
- no-store/no-cache response headers;
- exact patient/company or authorized internal-user check.

## Teleconsultation URL

Only HTTPS meeting URLs with a valid host are accepted.
The meeting URL is exposed to the patient only after exact-patient
authorization and only during the configured join window.

## Encryption statement

This application-layer design does **not** claim end-to-end encryption.
Transport and infrastructure confidentiality require HTTPS/TLS plus properly
secured Odoo database, filestore, backups, reverse proxy, host, and operations.

