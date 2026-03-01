<!--
# AI AGENT INSTRUCTION (META-PROMPT)
# Role: System Architect
# Goal: Interview the user to populate the "Tech Stack" structure below.
# Protocol:
# 1. BE SPECIFIC. No generic "Python". We need "Python 3.12, chosen for asyncio maturity."
# 2. ASK WHY. Challenge every technology choice — what alternative was considered?
# 3. VERIFY COMPATIBILITY across all listed components.
# 4. USE THE 'EXPECTATION' HINTS to judge completeness.
# 5. USE [UNKNOWN: reason] for anything the user cannot yet answer. Never guess.

# EXAMPLES (Gold Standard vs Bad):

# --- Web App Examples ---
# BAD: "Database: Postgres"
# GOOD: "Database: PostgreSQL 16 (AWS RDS), chosen for JSONB support and existing team expertise."
# BAD: "Auth: Uses tokens."
# GOOD: "Auth: JWT (RS256) issued by Auth0, validated via API gateway middleware."

# --- Library / CLI Examples ---
# BAD: "Language: Rust"
# GOOD: "Language: Rust 1.75 (stable), chosen for zero-cost abstractions and no runtime dependency."
# BAD: "Distribution: Published somewhere."
# GOOD: "Distribution: Published to crates.io via GitHub Actions on tag push. MSRV policy: current stable minus 2."

# SELF-CORRECTION CHECKLIST (Do not stop until specific):
# - [ ] Did I identify the system type (web app, library, CLI, mobile, etc.)?
# - [ ] Did I pin versions for all core technologies?
# - [ ] Did I explain the *why* behind each major technology choice?
# - [ ] Did I describe how the system reaches its users (deployment, publishing, distribution)?
# - [ ] Did I mark unknowns with [UNKNOWN: reason] instead of guessing?
# - [ ] Did I complete the Metadata section?
# - [ ] Is every component's role and connections described?
-->

# Tech Stack: [Project Name]

## 0. Metadata
| Key | Value |
| :--- | :--- |
| **Project Name** | [Name] |
| **Version** | 0.1 (Draft) |
| **Status** | [Draft/Review/Approved] |
| **Date** | [YYYY-MM-DD] |

## 1. About This Document
**Purpose**: This document serves as the **System Architecture Specification**. It maps the product requirements (defined in `seed_overview.md`) into concrete engineering decisions: what technologies are used, how the system is structured, and how it is delivered to users.

**Expectations**:
1.  **System Completeness**: Define every component required to build, run, and deliver the system. Nothing "magically" happens — if it is needed, it must be listed.
2.  **Pinned Authority**: Technology choices must be explicit. No "We might use Rust". Instead: "Rust 1.75 (stable), chosen for memory safety without GC." This reduces downstream decision fatigue.
3.  **Integration Logic**: Explicitly define the "glue". How does A talk to B? What protocol? What format?
4.  **Honesty Over Completeness**: Use `[UNKNOWN: reason]` for decisions not yet made. An honest unknown is better than a wrong guess.

## 2. System Type & Core Technology

### 2.1 System Type
- **Expectation**: What kind of software is this? Be specific about the category and its implications.
<!--
DEEP DIVE QUESTIONS:
- "Is this a web application, library, CLI tool, mobile app, desktop app, framework, embedded system, API service, or something else?"
- "Is it a standalone system or a component consumed by other systems?"
- "Does it have a user interface, or is it purely programmatic?"
-->
- **System Type**: [e.g. "Web application", "Python library", "CLI tool", "iOS app", "REST API service", "Embedded firmware"]
- **Deployment Model**: [e.g. "Long-running server", "Invoked on demand", "Imported as dependency", "Installed on device"]

### 2.2 Core Technology Decisions
- **Expectation**: Specific versions for every core technology. Must include rationale. **NO "LATEST" TAGS.** Use `[UNKNOWN: reason]` for undecided choices.
<!--
DEEP DIVE QUESTIONS:
- "What exact version? (e.g. Node 20.10.0, Rust 1.75, Swift 5.9)"
- "Why that version? (LTS policy? Required feature? Team expertise?)"
- "What alternatives were considered and rejected?"
-->
| Technology | Version | Rationale |
| :--- | :--- | :--- |
| **Language** | [e.g. Python 3.12] | [Why this language and version?] |
| **Runtime / Platform** | [e.g. CPython, Node, JVM 21, .NET 8, bare metal] | [Why?] |
| **Build System** | [e.g. Cargo, pip + setuptools, Gradle, CMake] | [Why?] |
| **Primary Framework** | [e.g. FastAPI, React 18, SwiftUI, none] | [Why? Or "N/A" if not applicable] |
| [Add rows as needed] | | |

### 2.3 Architecture Overview
- **Expectation**: Describe the major parts of the system and how they relate. The structure depends on the system type — there is no fixed set of layers. Identify what matters for *your* system.
<!--
DEEP DIVE QUESTIONS:
- "What are the 2-5 major parts of this system?"
- "How do they communicate? (function calls, HTTP, message queue, shared memory, IPC)"
- "What are the hard constraints? (e.g. 'Must run on Raspberry Pi', 'Must work offline', 'Must be a single binary')"

EXAMPLES BY SYSTEM TYPE:
- Web app: "API server | Database | Background worker | CDN-served frontend"
- Library: "Core module | Public API surface | Plugin system"
- CLI tool: "Argument parser | Core engine | Output formatters"
- Mobile app: "UI layer | Local storage | API client | Push notification handler"
- Embedded: "Hardware abstraction | Sensor drivers | Communication protocol | OTA updater"
-->
| Part | Technologies | Role & Constraints |
| :--- | :--- | :--- |
| [Part 1] | [Tech] | [What it does and why it is structured this way] |
| [Part 2] | [Tech] | [What it does and why] |
| [Add rows as needed] | | |

---

## 3. Components

- **Expectation**: Deep detail on each major part identified in 2.3. For each component, describe its role, what it connects to, and how it is configured. The number and nature of components depends on your system type.
<!--
GUIDANCE BY SYSTEM TYPE:
- Web app: services, databases, queues, caches
- Library: public modules, internal modules, extension points
- CLI tool: subcommands, input parsers, output handlers
- Mobile app: screens, services, data stores, platform integrations
- Embedded: drivers, protocols, state machines

DEEP DIVE QUESTIONS:
- "What is its specific role?"
- "How does it connect to other components?"
- "Where is the configuration stored?"
-->

### 3.1 [Component Name]
- **Technologies**: [Tech list with versions]
- **Role**: [What it does]
- **Connections**: [What it talks to and how — protocol, format, auth]
- **Configuration**: [Key config patterns, environment variables, config files]

### 3.2 [Component Name]
- **Technologies**: [Tech list with versions]
- **Role**: [What it does]
- **Connections**: [What it talks to and how]
- **Configuration**: [Key config patterns]

<!-- Add more components as needed. Every part from §2.3 should have a component entry. -->

---

## 4. Constraints & Boundaries

### 4.1 Security Boundary
- **Expectation**: What needs protecting and from what? The answer depends on the system type. Be specific about the threat model that matters for *your* system.
<!--
DEEP DIVE QUESTIONS:
- "What is the most sensitive thing in the system? (User data? API keys? Privileged operations?)"
- "Who or what could misuse it? (Untrusted users? Malicious input? Supply chain?)"
- "What is the trust boundary? (Network perimeter? Process sandbox? Package signature?)"

EXAMPLES BY SYSTEM TYPE:
- Web app: "Authentication via OAuth2, API rate limiting, secrets in Vault, WAF at edge."
- Library: "Input validation on all public functions, no network calls, no filesystem writes outside specified paths."
- CLI tool: "Runs with user-level permissions, no elevated privileges required, credentials stored in OS keychain."
- Mobile app: "Biometric auth, certificate pinning, encrypted local storage, no PII in logs."
-->
- **Threat Model**: [What needs protecting and from what]
- **Trust Boundary**: [Where trusted meets untrusted]
- **Access Control**: [Authentication/authorization approach, or "N/A" for a library with no auth concept]
- **Secrets Management**: [How secrets are stored and accessed, or "N/A"]

### 4.2 Distribution & Delivery
- **Expectation**: How does this system reach its users? Be specific about the mechanism, not just the destination.
<!--
DEEP DIVE QUESTIONS:
- "How do users get it? (Visit a URL? pip install? Download an installer? App store? Pre-installed on hardware?)"
- "What environments does it target? (Dev/Staging/Prod? Or: Linux/macOS/Windows?)"
- "What triggers a release? (Git tag? Manual approval? Continuous deployment?)"

EXAMPLES BY SYSTEM TYPE:
- Web app: "Deployed to AWS ECS via GitHub Actions on merge to main. Staging auto-deploys, prod requires manual approval."
- Library: "Published to PyPI via GitHub Actions on tag push. Supports Python 3.10+."
- CLI tool: "Distributed as a single binary via GitHub Releases. Homebrew tap for macOS. Scoop for Windows."
- Mobile app: "Submitted to App Store Connect via Fastlane. TestFlight for beta. 2-week review cycle."
- Embedded: "Firmware flashed at factory. OTA updates via MQTT channel."
-->
- **Distribution Channel**: [How it reaches users]
- **Target Environments**: [Where it must run]
- **Release Mechanism**: [What triggers a release and how it flows]

### 4.3 Resilience
- **Expectation**: What happens when things fail? The answer varies dramatically by system type. Some systems need disaster recovery plans; others just need graceful error messages. State what applies.
<!--
DEEP DIVE QUESTIONS:
- "What is the worst thing that can happen? (Data loss? Downtime? Corrupted output? Crash?)"
- "How does the system recover? (Auto-restart? Retry? Manual intervention? User re-runs?)"
- "Is there data that must survive failures? (Database backups? Local state? Nothing?)"

EXAMPLES BY SYSTEM TYPE:
- Web app: "Database: daily automated backups to S3, 15-min RPO. App: auto-restart via container orchestrator. RTO: 30 minutes."
- Library: "No persistent state. Errors surfaced as typed exceptions with actionable messages. No silent failures."
- CLI tool: "Interrupted operations leave no partial output. Atomic file writes. Exit codes follow POSIX conventions."
- Mobile app: "Offline queue syncs on reconnect. Local SQLite survives app restart. Crash reports via Sentry."
-->
- **Failure Mode**: [What can go wrong and how severe is it]
- **Recovery Strategy**: [How the system recovers, or "N/A — stateless, user re-runs"]
- **Data Durability**: [Backup strategy, or "No persistent state"]

---

## 5. Dependencies

- **Expectation**: Complete list of external dependencies required to build and run the system from scratch.
<!--
DEEP DIVE QUESTIONS:
- "System-level dependencies? (ffmpeg? libc? CUDA? Xcode?)"
- "Build tools? (gcc? make? protoc?)"
- "Runtime dependencies? (requirements.txt? package.json? Cargo.toml?)"
- "Are there version constraints or known incompatibilities?"
-->

### 5.1 System Requirements (OS / Platform Level)
*   **[Dependency]**: [Version constraint and purpose]

### 5.2 Application Requirements (Runtime Level)
*   **[Dependency]**: [Version constraint and purpose]

---

## 6. Stack Summary

- **Expectation**: A concise summary of the full technology stack. This is the "at a glance" reference for anyone joining the project.

| Aspect | Decision |
| :--- | :--- |
| **System Type** | [e.g. Web application, Python library, CLI tool] |
| **Language** | [e.g. Python 3.12] |
| **Runtime** | [e.g. CPython on Linux, Node 20 LTS] |
| **Framework** | [e.g. FastAPI, none] |
| **Data Storage** | [e.g. PostgreSQL 16, SQLite, none] |
| **Distribution** | [e.g. PyPI, Docker Hub, GitHub Releases, App Store] |
| **Key Constraints** | [e.g. Must run on Raspberry Pi, must work offline, single binary] |
