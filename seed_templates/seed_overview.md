# Product Brief: [Project Name]

> **AI Coach Instructions**
> You are a **Product Coach**. Your goal is to guide the user to define a clear, complete Product Intent Brief for ANY type of software (web app, library, CLI tool, mobile app, desktop app, framework, embedded system, SDK, data pipeline, etc.).
>
> **Protocol:**
> 1. NO JARGON. Use plain English questions.
> 2. DEMAND SPECIFICITY. Vague answers get follow-up questions.
> 3. FILL EVERY SECTION with real content or an `[UNKNOWN: reason]` marker.
> 4. USE THE 'Expectation' hints to calibrate depth.
> 5. DO NOT GUESS. If the user does not know something, mark it `[UNKNOWN: reason]` and move on. This is a sanctioned marker, not a gap.
> 6. DO NOT STRAY into technical decisions (languages, frameworks, hosting, monitoring). Those belong in `seed_tech_stack.md`.
>
> **Quality Calibration (Gold Standard vs Bad):**
> - BAD: "Target User: Everyone who likes food."
> - GOOD: "Target User: 'The Exhausted Parent' - 30-40s, works full time, values speed over price, looking for healthy meal prep."
> - BAD: "Success: Make a lot of money."
> - GOOD: "Success: 100 Paying Users ($10/mo) within 90 days. Retention > 40%."
>
> **Self-Correction Checklist (do not stop until all are satisfied):**
> - [ ] Did I mark unknowns with `[UNKNOWN: reason]` instead of guessing?
> - [ ] Did I enforce a metric for every success criterion?
> - [ ] Did I distinguish between "Must Have" and "Nice to Have"?
> - [ ] Is the language simple enough for a non-technical reader?
> - [ ] Did I complete the Metadata section?
> - [ ] Does every section stay within product intent (no tech stack leakage)?
> - [ ] Are capabilities described as behaviors, not implementation details?

## 0. Metadata
| Key | Value |
| :--- | :--- |
| **Project Name** | [Name] |
| **Version** | 0.3 (Draft) |
| **Status** | [Draft / Review / Approved] |
| **Date** | [YYYY-MM-DD] |
| **Software Type** | [Web App / CLI Tool / Library / Mobile App / Desktop App / Framework / Embedded / SDK / Data Pipeline / Other] |

## 1. About This Document
**Purpose**: This document captures the **product intent** for the project. It describes the problem, the people affected, what success looks like, and the boundaries of the first deliverable. It is written in plain language so that anyone on the team -- technical or not -- can understand what we are building and why.

**What this document is NOT**: This is not an exhaustive system specification. It does not prescribe technologies, architectures, or deployment strategies. Those decisions are made later in the pipeline, informed by this brief. Its job is to give downstream steps enough context to ask smart clarifying questions.

**How to fill this out**: Work through each section in order. The AI coach will ask follow-up questions when your answers are too vague. If you genuinely don't know something, write `[UNKNOWN: reason]` -- this is an accepted marker, not a defect. A completed seed with honest unknowns is better than one with guesses.

**Markers**: Use `[UNKNOWN: reason]` when you genuinely don't know the answer. In the companion `seed_tech_stack.md`, you'll also see `[AUTO-DERIVE: context]` — use that when you want the pipeline to make a technical decision for you based on your requirements.

**Expectations**:
1. **Problem-first**: Lead with the pain point. Every feature traces back to a real user need.
2. **Specific but not exhaustive**: Provide enough detail to unblock discovery, not enough to skip it.
3. **No gaps, unknowns are OK**: Every section must have content. If something is genuinely unknown, write `[UNKNOWN: reason]`.
4. **Plain language authority**: Use accessible language, but be precise. This document acts as the contract between Product and Engineering.

## 2. Problem & Users

### 2.1 Problem Statement
<!--
DEEP DIVE QUESTIONS:
- "What is the specific pain point? Tell me a story about it. What is broken TODAY?"
- "Who feels this pain and how often?"
- "What is the measurable cost of this problem? (Time wasted? Money lost? Errors made?)"
-->
- **Expectation**: Clear, punchy description of the pain point. Who feels it and when?
- **Content**: [The specific pain point we are solving]

### 2.2 Target Users / Personas
<!--
DEEP DIVE QUESTIONS:
- "Whose life is being improved? Give me a job title and a mood." (e.g. 'Overwhelmed Student')
- "What distinguishes one user group from another? (Role? Technical skill? Frequency of use?)"
- "Which user group matters MOST for the first version?"
- "What frustrates each user group today? What does success look like for them?"
-->
- **Expectation**: Specific segments, not "everyone". For each user group, describe who they are, what frustrates them today, and what success looks like for them.

**User Group 1**: [Name / Role — e.g., "The Exhausted Parent"]
- **Who they are**: [Role, context, primary motivation]
- **What frustrates them today**: [Current pain points — e.g., "Spends 2 hours/week planning meals manually"]
- **What success looks like**: [Desired outcome — e.g., "Meal plan generated in under 5 minutes with ingredients they already have"]

**User Group 2**: [Name / Role]
- **Who they are**: [Role, context, primary motivation]
- **What frustrates them today**: [Current pain points]
- **What success looks like**: [Desired outcome]

### 2.3 Core Scenarios (Jobs-to-be-Done)
<!--
DEEP DIVE QUESTIONS:
- "Walk me through the 3 most important things a user needs to accomplish."
- "What does the 'happy path' look like step by step?"
- "What goes wrong? What happens when a payment fails, a file is corrupted, the network drops, or two people edit the same thing?"
- "What happens at the extremes? (Zero items? 10,000 items? First-time user? Power user?)"
-->
- **Expectation**: 3-5 bullet points describing the primary things users need to accomplish. Include at least one error/edge case scenario.
- **Content**:
  - [Scenario 1: The main 'Happy Path' — what does the user do most often?]
  - [Scenario 2: Another key workflow]
  - [Scenario 3: What happens when something goes wrong? (e.g., invalid input, failed payment, network error)]

### 2.4 Success Metrics (KPIs)
<!--
DEEP DIVE QUESTIONS:
- "How do we measure if we won? (Time saved? Money made? Errors eliminated?)"
- "What is the current baseline for each metric? If you do not have real measured data, say UNKNOWN. Do not use industry averages or estimates."
- "How will we measure this? (Dashboard? Manual count? Survey?)"
-->
- **Expectation**: Quantifiable outcomes. For each metric, state what you're measuring, the target, how you'll measure it, and the current baseline (or `[UNKNOWN]` if no baseline exists).
- **Content**:
  - [Metric Name] | Target: [Value] [Unit] | How measured: [Tool, dashboard, manual count, or UNKNOWN] | Baseline: [Current value or UNKNOWN]
  - (e.g. Task Completion Time | Target: < 30 seconds | How measured: In-app timer analytics | Baseline: UNKNOWN — no analytics yet)

## 3. Scope (MVP Definition)
<!--
DEEP DIVE QUESTIONS:
- Must-Haves: "If you had 2 weeks, what specific capabilities make the cut?"
- Non-Goals: "What are we explicitly NOT building yet?"
- Constraints: "Any hard limits? (Cost? Hardware? Legal? Team size?)"
-->
### 3.1 In-Scope Goals (Must-Haves)
- **Expectation**: The concrete outcomes this project will deliver. These are the results, not the behaviors (behaviors belong in the Functional Requirements section). Think "what will exist when we're done" not "what the system does."
- **Content**:
  <!-- Must list at least 3 specific goals -->
  - [Goal 1 — e.g., "Secure, personalized access for all team members" or "Automated daily sales report delivered by 9am"]
  - [Goal 2]
  - [Goal 3]

### 3.2 Out-of-Scope (Non-Goals)
- **Expectation**: Explicit list of "Phase 2" items to prevent scope creep. Must list at
  least 3 specific non-goals. Step 00 charter schema requires `out_of_scope minItems:3`;
  the `seed-lint` gate (W555) will warn if fewer than 3 substantive items are supplied
  across all seeds routed to step 00.
- **Content**:
  - [Non-goal 1]
  - [Non-goal 2]
  - [Non-goal 3]

### 3.3 Assumptions & Constraints
<!--
DEEP DIVE QUESTIONS:
- Budget/Resources: "What is the budget? How many people? What is the timeline?"
- Regulatory: "Are there compliance requirements? (GDPR, HIPAA, SOC2, PCI-DSS, accessibility?)"
- Platform: "Must it run on specific devices, browsers, or operating systems?"
- Legacy: "Are there existing systems it must work with or replace?"
-->
- **Expectation**: Hard limits that constrain what is possible. Separate by category.
- **Budget / Resources**:
  - [e.g., "Solo developer", "$0 infrastructure budget", "Must launch within 3 months"]
- **Regulatory / Compliance** (only list requirements the user explicitly confirms — do not assume applicability):
  - [e.g., "GDPR — users in EU", "HIPAA — handles patient data", "None known"]
- **Platform / Environment**:
  - [e.g., "Must work on iOS 15+", "Must support Chrome, Firefox, Safari", "Must work offline"]
- **Legacy / Integration**:
  - [e.g., "Must integrate with existing Salesforce instance", "Replacing legacy PHP system"]

## 4. Expected Capabilities
<!--
NOTE: Section 3.1 captures WHAT you will deliver (the goals/outcomes).
This section captures HOW the system behaves — the specific actions and responses
users will experience. Think of 3.1 as the destination and this section as the journey.

DEEP DIVE QUESTIONS:
- "What must the product DO from the user's perspective?"
- "Describe each capability as a behavior: when X happens, the system should Y."
- "Which of these are must-haves vs nice-to-haves?"
- "How do users solve this problem today? (Spreadsheets? Manual process? Competitor product? Nothing?)"

QUALITY CALIBRATION:
- BAD: "Manage users" (too vague — manage how? create? delete? search?)
- GOOD: "When a new employee joins, an admin can create their account with name, email, and role. The employee receives a welcome email with a temporary password."
- BAD: "Support payments" (what kind? one-time? recurring? refunds?)
- GOOD: "A customer can pay for their order using a credit card. If the payment fails, they see a clear error message and can retry."
-->
- **Expectation**: High-level behavioral expectations written in plain language. Describe what the product does, not how it does it internally. Group by must-have vs nice-to-have.

**Current Solution**: [How do users solve this problem today? e.g., "Manual spreadsheets", "Competitor X but too expensive", "No solution exists"]

- **Must-Have** (each capability = one distinct behavior; if it contains "and," consider splitting):
  - [Capability 1 — describe the behavior in plain language]
  - [Capability 2]
- **Nice-to-Have**:
  - [Capability 3]
- **Future** (acknowledged but not for this phase):
  - [Capability 4]

## 5. Domain Model (Data & Concepts)
<!--
DEEP DIVE QUESTIONS:
- Data Sources: "Where does the information come from? (User input? Files? External feeds? Sensors?)"
- Concepts: "What are the 'things' in the system? (Posts? Users? Orders? Configs? Readings?)"
- Relationships: "How do these things relate to each other? (A User places many Orders. Each Order has Line Items.)"
- Lifecycle: "Do any of these things go through stages? (An Order goes from Pending to Shipped to Delivered.)"
- Freshness: "How does data stay current? (Real-time? Nightly batch? Manual? On-demand?)"
-->
### 5.1 Data Sources
- **Expectation**: List of all inputs the system consumes (user entry, files, APIs, hardware signals, etc.).
- **Content**:
  - [Source 1]

### 5.2 Key Entities & Relationships
- **Expectation**: The nouns of your system and how they relate to each other.
- **Content**:
  - [Entity 1] — [brief description]
  - [Entity 2] — [brief description]
  - **Relationships** (only document relationships the user explicitly describes — do not infer database structure): [e.g., "A User has many Orders. Each Order contains Line Items."]
  - **Lifecycle stages** (if any): [e.g., "Order: Draft -> Submitted -> Paid -> Shipped -> Delivered -> Returned"]

### 5.3 Update Strategy
- **Expectation**: How does data stay fresh? (Real-time? Nightly batch? Manual trigger? Event-driven?)
- **Content**: [Strategy]

## 6. Timeline & Milestones
<!--
DEEP DIVE QUESTIONS:
- "What is the very first version (alpha)? When do we want it?"
- "What are the big risks? (e.g. 'We don't know how to do X', 'Key dependency is unstable')"
-->
### 6.1 Milestones
- **Expectation**: Phased delivery plan. (e.g., "Prototype -> MVP -> V1" for an app, or "v0.1 core API -> v0.2 plugins -> v1.0 stable" for a library)
- **Content**:
  - [Milestone 1]

### 6.2 Risks & Mitigations
- **Expectation**: What could go wrong? How do we reduce the likelihood or impact?
- **Content**:
  - [Risk 1] -> [Mitigation]

## 7. Team & Process
<!--
DEEP DIVE QUESTIONS:
- "Who owns the product decisions?"
- "How do we approve changes?"
- "Who are the key stakeholders that need to be consulted?"
-->
### 7.1 Owners
- **Expectation**: Who is responsible? List key stakeholders. Format: `[Role]: [Need]`.
- **Content**:
  - Owner: [Name] (Team: api/ui/system/ops/data/product/business)
  - Stakeholder: [Role] needs [Requirement] (e.g. Compliance: Audit trail required)

### 7.2 Process
- **Expectation**: How changes are proposed, reviewed, and approved. Release cadence if known.
- **Content**: [Change management]
