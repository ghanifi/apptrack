# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in AppTrack, please **do not open a public issue**.

Instead, email **devaikaga@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept if possible)
- Any suggested mitigation

We aim to acknowledge reports within **48 hours** and provide a fix or mitigation plan within **14 days** for confirmed issues.

## Scope

In scope:
- The AppTrack gateway API and microservices (`backend/`)
- The web dashboard (`frontend/`)
- Workflow templates (`docs/workflow-templates/`) — e.g. injection via template inputs
- Credential handling (encryption at rest, token flow to build providers)

Out of scope:
- Vulnerabilities in third-party services (GitHub Actions, EAS, Codemagic, app stores)
- Denial of service against your own self-hosted instance
- Issues requiring physical access or a compromised host

## Security Model Highlights

- **Credentials at rest**: all provider tokens and signing materials are encrypted with Fernet
  (PBKDF2-derived key from `SECRET_KEY` + `FERNET_SALT`, 100k iterations). Key rotation is
  supported via `SECRET_KEY_OLD`.
- **Webhooks**: GitHub, EAS, Codemagic and App Store Connect webhooks are HMAC-SHA256
  verified and replay-protected (nonce store).
- **Build isolation**: builds run on GitHub-hosted runners in the *user's own* repository —
  AppTrack never executes user code on its own infrastructure.
- **Audit**: security-relevant actions are recorded with actor, IP and UTC timestamp;
  an immutable hash-chained audit log is available for compliance use.

## Supported Versions

Only the latest release on `main` receives security fixes.
