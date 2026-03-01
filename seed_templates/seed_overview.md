<!--
# AI AGENT INSTRUCTION (META-PROMPT)
# Role: Product Coach
# Goal: Guide a product owner to define a clear, complete Product Intent Brief
#       for ANY type of software (web app, library, CLI tool, mobile app,
#       desktop app, framework, embedded system, SDK, data pipeline, etc.).
# Protocol:
# 1. NO JARGON. Use plain English questions.
# 2. DEMAND SPECIFICITY. Vague answers get follow-up questions.
# 3. FILL EVERY SECTION with real content or an [UNKNOWN: reason] marker.
# 4. USE THE 'EXPECTATION' HINTS to calibrate depth.
# 5. DO NOT GUESS. If the product owner does not know something, mark it
#    [UNKNOWN: reason] and move on. This is a sanctioned marker, not a gap.
# 6. DO NOT STRAY into technical decisions (languages, frameworks, hosting,
#    monitoring). Those belong in seed_tech_stack.md.

# EXAMPLES (Gold Standard vs Bad):
# BAD: "Target User: Everyone who likes food."
# GOOD: "Target User: 'The Exhausted Parent' - 30-40s, works full time,
#        values speed over price, looking for healthy meal prep."
# BAD: "Success: Make a lot of money."
# GOOD: "Success: 100 Paying Users ($10/mo) within 90 days. Retention > 40%."

# SELF-CORRECTION CHECKLIST (Do not stop until specific):
# - [ ] Did I mark unknowns with [UNKNOWN: reason] instead of guessing?
# - [ ] Did I enforce a metric for Success?
# - [ ] Did I distinguish between "Must Have" and "Nice to Have"?
# - [ ] Is the language simple enough for a 5th grader?
# - [ ] Did I complete the Metadata section?
# - [ ] Does every section stay within product intent (no tech stack leakage)?
# - [ ] Are capabilities described as behaviors, not implementation details?
-->

# Product Brief: [Project Name]

## 0. Metadata
| Key | Value |
| :--- | :--- |
| **Project Name** | [Name] |
| **Version** | 0.3 (Draft) |
| **Status** | [Draft/Review/Approved] |
| **Date** | [YYYY-MM-DD] |
| **Software Type** | [Web App / CLI Tool / Library / Mobile App / Desktop App / Framework / Embedded / SDK / Data Pipeline / Other] |

## 1. About This Document
**Purpose**: This document captures the **product intent** for the project. It describes the problem, the people affected, what success looks like, and the boundaries of the first deliverable. It is written in plain language so that anyone on the team -- technical or not -- can understand what we are building and why.

**What this document is NOT**: This is not an exhaustive system specification. It does not prescribe technologies, architectures, or deployment strategies. Those decisions are made later in the pipeline, informed by this brief. Its job is to give downstream steps enough context to ask smart clarifying questions.

**Expectations**:
1. **Problem-first**: Lead with the pain point. Every feature traces back to a real user need.
2. **Specific but not exhaustive**: Provide enough detail to unblock discovery, not enough to skip it.
3. **No gaps, unknowns are OK**: Every section must have content. If something is genuinely unknown, write `[UNKNOWN: reason]` -- this is an accepted marker, not a defect.
4. **Plain language authority**: Use accessible language, but be precise. This document acts as the contract between Product and Engineering.

## 2. Problem & Users
<!--
DEEP DIVE QUESTIONS:
- Problem: "What is the specific pain point? Tell me a story about it. What is broken TODAY?"
- User: "Whose life is being improved? Give me a job title and a mood." (e.g. 'Overwhelmed Student')
- Success: "How do we measure if we won? (Time saved? Money made? Errors eliminated?)"
-->
### 2.1 Problem Statement
- **Expectation**: Clear, punchy description of the pain point. Who feels it and when?
- **Content**: [The specific pain point we are solving]

### 2.2 Target Users / Personas
- **Expectation**: Specific segments, not "everyone". Include role, context, and primary motivation.
- **Content**: [Who exactly is this for]

### 2.3 Core Scenarios (Jobs-to-be-Done)
- **Expectation**: 3-5 bullet points describing the primary things users need to accomplish.
- **Content**:
  - [Scenario 1: The 'Happy Path']
  - [Scenario 2: The Edge Case]

### 2.4 Success Metrics (KPIs)
- **Expectation**: Quantifiable outcomes. Format: `[Metric Name] | Target: [Value] [Unit] | Baseline: [Value]`.
- **Content**:
  - [Metric 1] | Target: [Value] [Unit] | Baseline: [Unknown/Value]
  - (e.g. Task Completion Time | Target: < 30 seconds | Baseline: Unknown)

## 3. Scope (MVP Definition)
<!--
DEEP DIVE QUESTIONS:
- Must-Haves: "If you had 2 weeks, what specific capabilities make the cut?"
- Non-Goals: "What are we explicitly NOT building yet?"
- Constraints: "Any hard limits? (Cost? Hardware? Legal? Team size?)"
-->
### 3.1 In-Scope Goals (Must-Haves)
- **Expectation**: The absolute minimum capability set to deliver value on Day 1.
- **Content**:
  <!-- Must list at least 3 specific goals -->
  - [Goal 1]

### 3.2 Out-of-Scope (Non-Goals)
- **Expectation**: Explicit list of "Phase 2" items to prevent scope creep.
- **Content**:
  - [Non-goal 1]

### 3.3 Assumptions & Constraints
- **Expectation**: Budget limits, team size, regulatory requirements, platform restrictions, or legacy constraints.
- **Content**:
  - [Constraint 1]

## 4. Expected Capabilities
<!--
DEEP DIVE QUESTIONS:
- "What must the product DO from the user's perspective?"
- "Describe each capability as a behavior: when X happens, the system should Y."
- "Which of these are must-haves vs nice-to-haves?"
-->
- **Expectation**: High-level behavioral expectations written in plain language. Describe what the product does, not how it does it internally. Group by must-have vs nice-to-have if helpful. These will be refined into formal requirements during pipeline discovery.
- **Content**:
  - [Capability 1]
  - [Capability 2]

## 5. Domain Model (Data & Concepts)
<!--
DEEP DIVE QUESTIONS:
- Data Sources: "Where does the information come from? (User input? Files? External feeds? Sensors?)"
- Concepts: "What are the 'things' in the system? (Posts? Users? Orders? Configs? Readings?)"
- Freshness: "How does data stay current? (Real-time? Nightly batch? Manual? On-demand?)"
-->
### 5.1 Data Sources
- **Expectation**: List of all inputs the system consumes (user entry, files, APIs, hardware signals, etc.).
- **Content**:
  - [Source 1]

### 5.2 Key Entities / Concepts
- **Expectation**: The nouns of your system (e.g. "Blog Post", "User", "Invoice", "Sensor Reading", "Configuration").
- **Content**:
  - [Entity 1]

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
- **Expectation**: Phased rollout plan (Prototype -> MVP -> V1).
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
