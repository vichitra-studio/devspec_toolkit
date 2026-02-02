<!--
# AI AGENT INSTRUCTION (META-PROMPT)
# Role: Senior Site Reliability Engineer & System Architect
# Goal: Interview the user to populate the "Tech Stack" structure below.
# Protocol:
# 1. BE SPECIFIC. No generic "Python". We need "Python 3.11 via Docker".
# 2. ASK WHY. Challenge every choice.
# 3. VERIFY COMPATIBILITY.
# 4. USE THE 'EXPECTATION' HINTS.

# EXAMPLES (Gold Standard vs Bad):
# BAD: "Database: Postgres"
# GOOD: "Database: PostgreSQL 16 (AWS RDS), chosen for JSONB support and existing team expertise."
# BAD: "Auth: Uses tokens."
# GOOD: "Auth: JWT (RS256) issued by Auth0, validated via Nginx middleware."

# SELF-CORRECTION CHECKLIST:
# - [ ] Did I pin versions (e.g. Node 20, not just Node)?
# - [ ] Did I explain the *why* for the database?
# - [ ] Is the backup strategy specific (frequency/SLA)?
# - [ ] Is there a list of system dependencies?
# - [ ] Did I complete the Metadata section?
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
**Purpose**: This document serves as the **End-to-End System Architecture** specification. It maps the product requirements into concrete engineering decisions, defining the **High-Level Design (HLD)** and **Low-Level Design (LLD)** constraints simultaneously.

**Expectations**:
1.  **System Completeness**: You must define every component required to run the system. From the browser hitting the CDN, to the API, the Database, and the Backup bucket. Nothing "magically" happens.
2.  **Pinned Authority**: Logic must be explicit. No "We might use AWS". Instead: "We utilize AWS Lambda running Python 3.12". This reduces downstream decision fatigue.
3.  **Operational Viability**: A system is not just code. It is logs, alerts, security headers, and recovery plans. This document must define *how it survives in production*.
4.  **Integration Logic**: Explicitly define the "glue". How does A talk to B? What protocol? What auth?

## 2. High-Level Stack Overview

### 2.1 Pinned Core Versions
- **Expectation**: Specific versions for OS, Runtime, and Language. Must include the "Source" (where it comes from) and "Rationale" (Why this specific version?). **NO "LATEST" TAGS.**
<!-- 
DEEP DIVE QUESTIONS:
- "What exact version of the runtime? (e.g. Node 20.10.0)"
- "Why that version? (Legacy support? New feature?)"
- "Source? (Docker Hub? Apt? Official Installer?)"
-->
| Component | Version | Source | Rationale |
| :--- | :--- | :--- | :--- |
| **OS** | [Version (e.g. Ubuntu 22.04)] | [Source] | [Why?] |
| **Runtime** | [Version (e.g. Python 3.11)] | [Source] | [Why?] |
| **Language** | [Version] | [Source] | [Why?] |

### 2.2 Layer Summary
- **Expectation**: A breakdown of the stack layers. "Logic & Constraints" MUST explain *why* these choices were made (e.g. "Chosen for SEO", "Legacy constraints").
<!-- 
DEEP DIVE QUESTIONS:
- "Walk me through the stack bottom-up."
- "What are the hard constraints? (e.g. 'Must run on Pi 4')"
-->
| Layer | Primary Technologies | Logic & Constraints |
| :--- | :--- | :--- |
| **Frontend** | [Tech] | [Constraint] |
| **Backend** | [Tech] | [Constraint] |
| **Database** | [Tech] | [Constraint] |
| **Infrastructure** | [Tech] | [Constraint] |
| **CI/CD** | [Tech] | [Constraint] |

---

## 3. Detailed Technical Components

### 3.1 [Component A]
- **Expectation**: Deep operational detail. Not just "What it is", but "How it runs", "What it talks to", and "How it is configured".
<!-- 
DEEP DIVE QUESTIONS:
- "What is its specific role?"
- "How does it connect to other parts?"
- "Where is the config stored?"
-->
- **Technologies**: [Tech list]
- **Role**: [What it does]
- **Connections**: [What it talks to]
- **Configuration**: [Key config patterns]

### 3.2 [Component B]
- **Technologies**: [Tech list]
- **Role**: [What it does]

## 4. Operations & Security

### 4.1 Security Stack
- **Expectation**: Defense-in-depth strategy. Auth, Network, Secrets, and Privacy.
<!-- 
DEEP DIVE QUESTIONS:
- "How do we handle Auth? (JWT? OAuth?)"
- "Where do secrets live? (Dotenv? Vault?)"
- "Network security? (WAF? Firewall? Tunnel?)"
-->
- **Authentication**: [Auth method]
- **Firewall/WAF**: [Defense layer]
- **Secrets Management**: [Strategy]

### 4.2 Observability & Logs
- **Expectation**: How we debug production. Log formats, metric stores, and retention policies.
<!-- 
DEEP DIVE QUESTIONS:
- "How do we debug production?"
- "Log format? (JSON? Text?)"
- "Metrics? (Prometheus? Cloudwatch?)"
-->
- **Logging Format**: [JSON/Text]
- **Metrics**: [Tooling]
- **Retention**: [Policy]

### 4.3 Backups & DR
- **Expectation**: Recovery strategy. Mechanism, Frequency, and SLA (Recovery Time Objective).
<!-- 
DEEP DIVE QUESTIONS:
- "If the DB vanishes, what do we do?"
- "Backup frequency? Retention?"
- "Recovery Time Objective?"
-->
- **Mechanism**: [Tool]
- **Frequency**: [Schedule]
- **Recovery SLA**: [Target]

## 5. Dependencies Strategy
- **Expectation**: Complete list of packages required to bootstrap the system from scratch.
<!-- 
DEEP DIVE QUESTIONS:
- "System level deps? (ffmpeg? libc?)"
- "Build tools? (gcc? make?)"
- "Application deps? (requirements.txt? package.json?)"
-->

### 5.1 System Requirements (OS Level)
*   **Package 1**: [Description]

### 5.2 Application Requirements (Runtime Level)
*   **Dependency 1**: [Version]

---

## 6. Stack Index
- **Expectation**: A YAML block defining the component graph. This is consumed by automation tools.
<!-- 
INSTRUCTION: Generate this YAML block automatically based on the components identified above. 
-->

```yaml
stack_index:
  # IDs must be kebab-case (e.g. aws-rds-postgres)
  - id: [component_id]
    name: [Component Name]
    category: [hardware|runtime|database|service]
    role: [Role description]
    runs_on: [environment_id]
    depends_on: [other_component_id]
    critical: true
```
