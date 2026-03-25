# System Design: [Project Name]

> **AI Coach Instructions**
> You are a **System Architect Coach**. Your goal is to help the user define the system design for the product described in `seed_overview.md`. Adapt your coaching depth based on the user's technical proficiency (§0 Metadata).
>
> **Protocol by Proficiency:**
> - **Non-technical**: Ask about constraints and preferences in plain language. Recommend specific technologies based on requirements, explaining your reasoning. Mark recommendations as `[RECOMMENDED: reason]` so the user can accept or override. If a section depends on earlier answers the user couldn't provide, proactively suggest `[AUTO-DERIVE]`.
> - **Some technical experience**: Ask clarifying questions before recommending. Present 2-3 options with trade-offs instead of a single recommendation. Use `[RECOMMENDED: reason]` for areas outside their expertise.
> - **Software engineer / Architect**: Demand specificity. Challenge every technology choice — what alternative was considered? Verify compatibility across all listed components. For SWE users, also surface API design and interface style questions (REST vs gRPC vs GraphQL, versioning strategy).
>
> **For all proficiency levels:**
> 1. FILL EVERY SECTION with real content, `[UNKNOWN: reason]`, or `[AUTO-DERIVE: based on requirements]`.
> 2. DO NOT GUESS. An honest unknown is better than a wrong guess.
> 3. VERIFY that choices here are consistent with constraints in `seed_overview.md`.
>
> **Quality Calibration (Gold Standard vs Bad):**
> - BAD: "Database: Postgres"
> - GOOD: "Database: PostgreSQL 16, chosen for JSONB support and existing team expertise."
> - BAD (for non-technical user): Leaving blank because they don't know.
> - GOOD (for non-technical user): "[AUTO-DERIVE: We need to store user data and orders. Team has no database preference.]"
>
> **Self-Correction Checklist:**
> - [ ] Did I identify the system type and deployment model?
> - [ ] Are technology choices specific (or marked for auto-derivation)?
> - [ ] Did I describe how the major parts of the system connect?
> - [ ] Did I capture hard constraints that limit what is possible?
> - [ ] Did I capture scale expectations?
> - [ ] Did I mark unknowns with `[UNKNOWN: reason]` instead of guessing?

## 0. Metadata
| Key | Value |
| :--- | :--- |
| **Project Name** | [Name] |
| **Version** | 0.3 (Draft) |
| **Status** | [Draft / Review / Approved] |
| **Date** | [YYYY-MM-DD] |
| **Technical Proficiency** | [Non-technical / Some technical experience / Software engineer or architect] |

## 1. About This Document
**Purpose**: This document captures the **system design** for the product defined in `seed_overview.md`. It maps product requirements into engineering decisions: what kind of system this is, how it is structured, what technologies are used, and what constraints bound the design.

**How to fill this out**: If you are non-technical, focus on what you know — your team's skills, your existing tools, your constraints. Mark anything you're unsure about as `[AUTO-DERIVE: brief context]` and the pipeline will resolve it based on your requirements. If you are technical, be as specific as possible — pinned versions with rationale reduce downstream decision fatigue.

**How AUTO-DERIVE works**: When you mark a decision as `[AUTO-DERIVE: context]`, the pipeline's architecture step (Step 02) will resolve it by matching your constraints (team expertise, scale, budget, system type) to appropriate technologies. Include as much context as you can — `[AUTO-DERIVE: need fast reads, team knows SQL]` is much better than `[AUTO-DERIVE]` alone.

**Important**: If you mark most of this document as `[AUTO-DERIVE]`, the pipeline will make technology decisions on your behalf. You will review these decisions at the architecture step (Step 02) — pay close attention during that review, and consult a technical advisor if available.

**Expectations**:
1. **System Completeness**: Define every major part required to build and run the system.
2. **Honesty Over Completeness**: Use `[UNKNOWN: reason]` for decisions not yet made, `[AUTO-DERIVE: context]` for decisions you want the pipeline to resolve.
3. **Consistency**: Choices here must not contradict constraints in `seed_overview.md`.

---

## 2. System Type & Core Technology

### 2.1 System Type
<!--
DEEP DIVE QUESTIONS:
- "Is this a web application, library, CLI tool, mobile app, desktop app, framework, embedded system, API service, or something else?"
- "Is it a standalone system or a component consumed by other systems?"
- "Does it have a user interface, or is it purely programmatic?"
-->
- **Expectation**: What kind of software is this? Be specific about the category and its implications.
- **System Type**: [e.g. "Web application", "Python library", "CLI tool", "iOS app", "REST API service", "Embedded firmware"]
- **Deployment Model**: [e.g. "Long-running server", "Invoked on demand", "Imported as dependency", "Installed on device"]

### 2.2 Core Technology Decisions
<!--
FOR TECHNICAL USERS:
- "What exact version? (e.g. Node 20.10.0, Rust 1.75, Swift 5.9)"
- "Why that version? (LTS policy? Required feature? Team expertise?)"
- "What alternatives were considered and rejected?"

FOR NON-TECHNICAL USERS:
- "Do you or your team have experience with any programming languages or tools?"
- "Do you have any strong preferences? (e.g., 'I want it built in Python' or 'I have no preference')"
- "If you don't have preferences, write [AUTO-DERIVE: brief context] and we'll recommend based on your requirements."
-->
- **Expectation**: Technology choices with rationale. Non-technical users: state preferences or mark `[AUTO-DERIVE]` with context.

| Technology | Decision | Rationale |
| :--- | :--- | :--- |
| **Language** | [e.g. "Python 3.12" or "[AUTO-DERIVE: team knows Python basics]"] | [Why, or context for auto-derivation] |
| **Primary Framework** | [e.g. "FastAPI" or "[AUTO-DERIVE: need a web API]"] | [Why, or "N/A" if not applicable] |
| **Data Storage** | [e.g. "PostgreSQL 16" or "[AUTO-DERIVE: need to store user accounts and orders]"] | [Why?] |
| **Interface Style** (SWE users) | [e.g. "REST with JSON", "gRPC", "GraphQL", "CLI flags + stdout" or "N/A"] | [Why? Or skip if non-technical] |
| [Add rows as needed — consider: cache, message broker, search, CDN if applicable] | | |

### 2.3 Architecture Overview
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
- **Expectation**: Describe the major parts of the system and how they relate.

| Part | Technology | Role & Constraints |
| :--- | :--- | :--- |
| [Part 1] | [Tech or AUTO-DERIVE] | [What it does and why it is structured this way] |
| [Part 2] | [Tech or AUTO-DERIVE] | [What it does and why] |
| [Add rows as needed] | | |

---

## 3. Components & External Systems

<!--
GUIDANCE BY SYSTEM TYPE:
- Web app: services, databases, queues, caches, external APIs
- Library: public modules, internal modules, extension points
- CLI tool: subcommands, input parsers, output handlers
- Mobile app: screens, services, data stores, platform integrations
- Embedded: drivers, protocols, state machines

DEEP DIVE QUESTIONS:
- "What is its specific role?"
- "How does it connect to other components? (HTTP, database wire protocol, message queue, function call)"
- "Are there any external systems this must talk to? (Payment processors, identity providers, analytics, email services?)"
-->
- **Expectation**: Detail on each major part from §2.3. Focus on role and connections. Include any third-party services the system depends on.
- **If you marked §2.3 as AUTO-DERIVE**: Mark this section as `[AUTO-DERIVE: see §2.3]` and skip to §3.3 (External Systems). The pipeline will derive components from your requirements and constraints.

### 3.1 [Component Name]
- **Role**: [What it does]
- **Connections**: [What it talks to and how — protocol, format, auth]

### 3.2 [Component Name]
- **Role**: [What it does]
- **Connections**: [What it talks to and how]

### 3.3 External Systems & Integrations
- **Expectation**: Third-party services the system depends on (payment processors, identity providers, email services, analytics, cloud APIs, etc.).
- **Content**:
  - [External system 1]: [What it provides, how it connects]
  - [External system 2]: [What it provides, how it connects]

<!-- Add more components as needed. Every part from §2.3 should have an entry. -->

---

## 4. Constraints & Boundaries

### 4.1 Security & Access
<!--
DEEP DIVE QUESTIONS:
- "What is the most sensitive thing in the system? (User data? API keys? Privileged operations? Nothing?)"
- "Who are the different types of users? (Admin, regular user, guest, API consumer?)"
- "Where does trusted meet untrusted? (Public internet? Partner API? Internal only?)"

EXAMPLES BY SYSTEM TYPE:
- Web app: "Authentication via OAuth2, admin and regular user roles, secrets in Vault."
- Library: "Input validation on all public functions, no network calls."
- CLI tool: "Runs with user-level permissions, credentials stored in OS keychain."
- Mobile app: "Biometric auth, certificate pinning, encrypted local storage."
-->
- **User Roles**: [e.g. "Admin (full access), Regular User (own data only), Guest (read-only)" or "Single-user CLI" or "Library consumers (trusted callers)" or "N/A"]
- **Sensitive Data**: [What needs protecting — e.g. "User PII, payment info" or "API keys in config" or "Sensor calibration data" or "None"]
- **Trust Boundary**: [Where trusted meets untrusted — e.g. "Public internet to API" or "Untrusted file input to parser" or "Bluetooth peripheral to firmware" or "N/A — trusted environment only"]
- **Auth Approach** (state the approach, not specific vendors unless you have a preference): [e.g. "JWT tokens", "OAuth2 (provider TBD)", "API key", "OS-level file permissions", "Package signing" or "[AUTO-DERIVE: need user login]" or "N/A"]

### 4.2 Distribution & Target Environments
<!--
DEEP DIVE QUESTIONS:
- "How do users get it? (Visit a URL? pip install? App store? Download an installer?)"
- "What environments does it target? (Linux/macOS/Windows? Dev/Staging/Prod? Specific devices?)"
-->
- **Distribution Channel**: [e.g. "Web URL", "PyPI", "npm", "crates.io", "App Store", "GitHub Releases", "Docker Hub", "OTA firmware update", "Pre-installed on device"]
- **Target Environments**: [e.g. "AWS us-east-1, dev/staging/prod" or "macOS and Linux" or "iOS 15+" or "ARM Cortex-M4" or "Any platform with Python 3.10+"]

### 4.3 Resilience & Data Sensitivity
<!--
DEEP DIVE QUESTIONS:
- "What is the worst thing that can happen? (Data loss? Downtime? Corrupted output? Crash?)"
- "Is data loss acceptable? (Ephemeral data vs critical records)"
- "How important is uptime? (24/7 critical vs best-effort vs runs-when-invoked)"
-->
- **Expectation**: What matters for YOUR system — not every system needs a disaster recovery plan.
- **Data Loss Tolerance**: [e.g. "Data loss is unacceptable — user financial records" or "Ephemeral — can be regenerated" or "Output is deterministic — re-run to recover" or "N/A — stateless tool"]
- **Availability Expectation**: [e.g. "24/7, <1hr downtime/month" or "Best effort, occasional downtime OK" or "Runs on demand — no uptime concept" or "Must respond within hardware interrupt deadline"]

### 4.4 Build, Test & Deploy
<!--
DEEP DIVE QUESTIONS:
- "How do you build and test today? (CI service? Manual? Nothing yet?)"
- "What quality checks should block a release? (Tests pass? Linting? Security scan?)"
- "What secrets or credentials does the system need to run? (Database passwords? API keys? Signing certificates?)"
- "Are there compliance standards the infrastructure must meet? (SOC2, GDPR, HIPAA, PCI-DSS?)"
-->
- **Expectation**: How the system is built, tested, and released. Non-technical users: describe what you know or mark `[AUTO-DERIVE]`.
- **CI/CD**: [e.g. "GitHub Actions", "Jenkins", "None yet — greenfield" or "[AUTO-DERIVE]"]
- **Quality Gates**: [e.g. "Tests must pass, linting required" or "[AUTO-DERIVE: standard quality checks]"]
- **Secrets / Credentials**: [e.g. "DATABASE_URL, STRIPE_API_KEY, JWT_SECRET" or "None" or "[UNKNOWN]"]
- **Compliance Standards**: [e.g. "SOC2, GDPR" or "None" or "Same as overview §3.3"]

---

## 5. Scale & Team Context

### 5.1 Scale Expectations
<!--
DEEP DIVE QUESTIONS:
- "How many users do you expect? (10? 1,000? 1,000,000?)"
- "How much data? (Megabytes? Gigabytes? Terabytes?)"
- "What does growth look like? (Steady? Spiky? Seasonal?)"
- "What is the expected request volume? (10 req/s? 1,000 req/s? Bursty?)"
-->
- **Expected Users / Consumers**: [e.g. "~100 internal users" or "10,000 app users, growing 20%/month" or "~500 library installs/week" or "1 device per deployment" or "[UNKNOWN: new market]"]
- **Expected Data Volume**: [e.g. "~10GB database" or "Terabytes of sensor data/day" or "Small config files only" or "[UNKNOWN]"]
- **Usage Pattern**: [e.g. "Steady low traffic" or "Bursty — spikes during business hours" or "Batch — runs nightly" or "Continuous sensor stream" or "On-demand CLI invocation"]

### 5.2 Team & Existing Infrastructure
<!--
DEEP DIVE QUESTIONS:
- "What languages/tools does your team know well?"
- "What cloud provider or hosting do you already use?"
- "Are there existing systems, databases, or services this must integrate with?"
- "What CI/CD or deployment tools do you already have?"
-->
- **Team Expertise**: [e.g. "Team knows Python and JavaScript well, some Go experience" or "Non-technical founder, will hire" or "[UNKNOWN]"]
- **Existing Infrastructure**: [e.g. "AWS account with RDS and ECS", "Heroku", "Nothing — greenfield" or "[UNKNOWN]"]
- **Existing Systems to Integrate**: [e.g. "Must connect to existing Salesforce and Stripe accounts" or "None"]
