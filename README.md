<div align="center">

# 📱 AppTrack

### Build, sign, and publish mobile apps to the App Store & Google Play — **without owning a Mac.**

*The open, self-hostable CI/CD & release platform for mobile teams. A modern alternative to Ionic Appflow.*

<br/>

[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm%20Noncommercial-e11d48.svg)](LICENSE)
[![Frameworks](https://img.shields.io/badge/Frameworks-9-6366f1.svg)](#-supported-frameworks)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](#-architecture)
[![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61dafb.svg)](#-architecture)
[![iOS](https://img.shields.io/badge/iOS%20builds-without%20a%20Mac-000000.svg?logo=apple)](#-ios-without-a-mac)
[![AI](https://img.shields.io/badge/AI-BYOK%20%C2%B7%205%20providers-8b5cf6.svg)](#-ai-powered-self-healing)
[![Stars](https://img.shields.io/github/stars/holladevai/apptrackv2?style=social)](https://github.com/holladevai/apptrackv2/stargazers)

<br/>

**[Why AppTrack](#-why-apptrack) · [Features](#-features) · [How it works](#-how-it-works) · [Quick Start](#-quick-start) · [Roadmap](#-roadmap) · [Contact](#-contact)**

</div>

---

## 💡 Why AppTrack

Shipping a mobile app to the stores is still painful: you juggle build farms, signing certificates, provisioning profiles, store APIs — and for iOS, you're told you **need a Mac**.

**AppTrack removes all of that.** Connect a GitHub repo, and AppTrack auto-detects your framework, builds it in the cloud, signs it, and ships it to the App Store and Google Play — from a single dashboard, self-hosted, on infrastructure you control.

> ### 🍏 iOS without a Mac
> AppTrack's founding purpose: let people **who don't own any Apple hardware** produce **signed iOS builds**. It routes iOS builds to cloud-hosted macOS runners (`macos-26`) and automates the entire signing chain — certificates, profiles, and store submission.

<div align="center">

| 😖 The old way | 🚀 With AppTrack |
|---|---|
| Buy a Mac for iOS builds | Cloud macOS runners — **no Mac needed** |
| Wrestle with certs & profiles | **Signing Doctor** diagnoses & auto-repairs |
| Build fails → you debug for hours | **AI self-healing** opens a fix PR for you |
| Separate tools for build & deploy | **One platform**, idea → store |
| Per-seat SaaS pricing | **Self-host, bring your own keys** |

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🏗️ Build anything
- **9 frameworks**, 6 languages, auto-detected
- GitHub Actions · EAS · Codemagic
- Cloud macOS for iOS — **no Mac required**
- Free provider fallback (GitHub Actions)

### 🔐 Secure by design
- Fernet-encrypted credential vault (zero plaintext)
- HMAC-verified, replay-protected webhooks
- Immutable, hash-chained audit log (SOC2-ready)
- Builds run in **your** repo, never on ours

### 🩺 Signing Doctor
- Project-scoped iOS signing diagnosis
- Detects cert/profile/bundle-id/expiry issues
- **One-click repair** — regenerate cert + profile

</td>
<td width="50%" valign="top">

### 🤖 AI-powered self-healing
- Build fails → **agentic AI opens a fix PR**
- Reads your repo, patches, validates, self-critiques
- **BYOK** — Claude · OpenAI · Gemini · OpenRouter · NVIDIA
- Pick any model, free or paid — your keys, your cost

### 🚦 Safe releases
- Staged rollout: 10% → 25% → 50% → 100%
- **Auto-halt** on error-rate / crash spikes
- Canary deploys with automatic rollback

### ⚡ OTA live updates
- Ship JS/HTML/CSS instantly — no rebuild, no review
- Channels: production · staging · beta
- Runtime-version matching + rollback

</td>
</tr>
</table>

---

## 📦 Supported Frameworks

<div align="center">

| Category | Frameworks | Build Provider |
|----------|-----------|----------------|
| **Native** | Swift · Kotlin | GitHub Actions (macOS `macos-26` for iOS) |
| **Cross-platform** | React Native · Flutter · Expo | EAS · Codemagic |
| **Hybrid** | Capacitor · Ionic · Cordova | GitHub Actions |
| **Web** | PWA (+ TWA for Android) | GitHub Actions |

**9 frameworks · 6 languages · one dashboard**

</div>

---

## 🔭 How it works

```mermaid
flowchart LR
    A[GitHub repo] --> B[Repo Sync]
    B --> C[Framework<br/>Detection]
    C --> D[Project Ready]
    D --> E{Build}
    E -->|GitHub Actions<br/>EAS · Codemagic| F[Signed<br/>APK / IPA]
    E -->|fails| G[🤖 AI Autofix<br/>opens fix PR]
    G --> E
    F --> H{Deploy}
    H --> I[Google Play<br/>staged rollout]
    H --> J[App Store<br/>TestFlight → review]
    I --> K[📊 Health monitor<br/>auto-halt on spike]
    J --> K
    K --> L[⚡ OTA updates]
```

Every asynchronous state transition flows through **RabbitMQ events** — services never call each other directly for state changes, so the pipeline is resilient and observable end-to-end.

---

## 🧱 Architecture

```mermaid
flowchart TB
    UI[React + Vite Dashboard :3000]
    GW[FastAPI Gateway :8000]
    UI -->|/api proxy| GW
    GW <--> DB[(PostgreSQL)]
    GW <--> RMQ{{RabbitMQ}}
    GW <--> RD[(Redis)]
    GW <--> MO[(MinIO)]
    RMQ --> S1[auth :8001]
    RMQ --> S2[project :8002]
    RMQ --> S3[repo-sync :8003]
    RMQ --> S4[framework-detection :8004]
    RMQ --> S5[preview :8005]
    RMQ --> S6[build :8006]
    RMQ --> S7[artifact :8007]
    RMQ --> S8[store-deploy :8008]
```

**Stack:** Python/FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · RabbitMQ · Redis · MinIO · React/TypeScript/Vite/Tailwind · Docker Compose.

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/holladevai/apptrackv2.git
cd apptrackv2

# 2. Configure
cp .env.example .env      # fill in your secrets

# 3. Launch everything (Docker)
make dev

# 4. Open
#   Dashboard : http://localhost:3000
#   API docs  : http://localhost:8000/api/docs
#   RabbitMQ  : http://localhost:15672
#   MinIO     : http://localhost:9001
```

```bash
# Tests
make test            # backend (pytest) + frontend (vitest)
make lint-backend    # ruff
make lint-frontend   # eslint
```

---

## 🧭 Moat — what makes AppTrack different

<div align="center">

| Pillar | What it does |
|--------|--------------|
| 🖥️ **Self-hosted runners** | Bring your own build machines — cut cost, keep control |
| 🤖 **Self-healing pipeline** | Deterministic fixes **+ agentic AI** that writes fix PRs |
| 🚦 **Staged rollout + auto-halt** | Ship gradually, stop automatically when health degrades |
| 🩺 **Signing Doctor** | Diagnose & repair iOS signing in one click |
| 🍏 **iOS without a Mac** | Signed iOS builds on cloud macOS — the founding principle |

</div>

---

## 🗺️ Roadmap

- ✅ Multi-provider AI gateway (BYOK) + selectable free/paid models
- ✅ Agentic autofix — AI reads repo, patches, validates, opens PR *(live-proven)*
- ✅ Signing Doctor (iOS signing diagnosis + one-click repair)
- ✅ Staged rollout + auto-halt, OTA updates, immutable audit
- 🔜 **AI App Factory** — describe an idea, AppTrack generates the app, you preview & publish
- 🔜 Signed IPA end-to-end demo · streaming AI · hosted runner wizard

---

## 🔒 Security

Found a vulnerability? Please **don't** open a public issue — see [SECURITY.md](SECURITY.md) and email **devaikaga@gmail.com**.

Highlights: Fernet credential encryption (PBKDF2, 100k iterations, key rotation) · HMAC-verified webhooks · immutable hash-chained audit log · builds isolated to your own repositories.

---

## 📬 Contact

Questions, commercial licensing, or partnership?

**📧 devaikaga@gmail.com**

If AppTrack is useful to you, please ⭐ **star the repo** — it genuinely helps.

---

## 📜 License

AppTrack is released under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

You may **use, modify, and share** it freely for **any noncommercial purpose** — personal projects, research, education, evaluation. **Commercial use is not permitted** without a separate commercial license. To obtain one, contact **devaikaga@gmail.com**.

<div align="center">
<br/>
<sub>Built for mobile teams who'd rather ship than fight their toolchain.</sub>
</div>
