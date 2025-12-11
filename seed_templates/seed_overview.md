<!--
# AI AGENT INSTRUCTION (META-PROMPT)
# Role: Product Coach & Startup Mentor
# Goal: Guide a non-technical founder to define a COMPLETE, EXHAUSTIVE Product Brief.
# Protocol:
# 1. NO JARGON. Use plain English questions.
# 2. DEMAND SPECIFICITY.
# 3. FILL EVERY SECTION.
# 4. USE THE 'EXPECTATION' HINTS.

# EXAMPLES (Gold Standard vs Bad):
# BAD: "Target User: Everyone who likes food."
# GOOD: "Target User: 'The Exhausted Parent' - 30-40s, works full time, values speed over price, looking for healthy meal prep."
# BAD: "Success: Make a lot of money."
# GOOD: "Success: 100 Paying Users ($10/mo) within 90 days. Retention > 40%."

# SELF-CORRECTION CHECKLIST (Do not stop until specific):
# - [ ] Did I remove all "TBDs"?
# - [ ] Did I enforce a metric for Success?
# - [ ] Did I distinguish between "Must Have" and "Nice to Have"?
# - [ ] Is the language simple enough for a 5th grader?
# - [ ] Did I complete the Metadata section?
-->

# Project Brief: [Project Name]

## 0. Metadata
| Key | Value |
| :--- | :--- |
| **Project Name** | [Name] |
| **Version** | 0.1 (Draft) |
| **Status** | [Draft/Review/Approved] |
| **Date** | [YYYY-MM-DD] |

## 1. About This Document
**Purpose**: This document serves as the **End-to-End Product Definition** for the MVP. It orchestrates the entire user value chain, from the initial problem statement to the final measure of success. It is not just a high-level summary; it is the **authoritative product requirement specification** that drives all engineering decisions.

**Expectations**:
1.  **End-to-End Flow**: You must describe the complete product journey. Do not stop at "It's a website". Explain *what happens* from the moment a user arrives to the moment they leave.
2.  **Product Expectations**: Explicitly define what "Good" looks like. What are the quality bars? What are the "Must-Haves" that make the product viable?
3.  **No Gaps**: If a feature is mentioned in "Scope", its logic must be detailed in "Requirements". If a user persona is mentioned, their specific journey must be mapped in "Core Scenarios".
4.  **Plain Language Authority**: Use accessible language, but be precise. This document effectively acts as the "Contract" between Product and Engineering.

## 2. Problem & Users
<!-- 
DEEP DIVE QUESTIONS:
- Problem: "What is the specific pain point? Tell me a story about it. What is broken TODAY?"
- User: "Whose life is being improved? Give me a job title and a mood." (e.g. 'Overwhelmed Student')
- Success: "How do we measure if we won? (Time saved? Money made?)"
-->
### 2.1 Problem Statement
- **Expectation**: Clear, punchy description of the pain logic.
- **Content**: [The specific pain point we are solving]

### 2.2 Target Users / Personas
- **Expectation**: Specific segments, not "everyone".
- **Content**: [Who exactly is this for]

### 2.3 Core Scenarios (Jobs-to-be-Done)
- **Expectation**: 3-5 bullet points describing the primary user flows.
- **Content**:
  - [Scenario 1: The 'Happy Path']
  - [Scenario 2: The Edge Case]

### 2.4 Success Metrics (KPIs)
- **Expectation**: Quantifiable or clearly observable outcomes.
- **Content**:
  - [Metric 1]

## 3. Scope (MVP Definition)
<!-- 
DEEP DIVE QUESTIONS:
- Must-Haves: "If you had 2 weeks, what specific features make the cut?"
- Non-Goals: "What are we explicitly NOT building yet? (e.g. 'No mobile app', 'No login')"
- Constraints: "Any hard limits? (Cost? Hardware? Legal?)"
-->
### 3.1 In-Scope Goals (Must-Haves)
- **Expectation**: The absolute minimum feature set to ship value Day 1.
- **Content**:
  - [Goal 1]

### 3.2 Out-of-Scope (Non-Goals)
- **Expectation**: explicit list of "Phase 2" items to prevent scope creep.
- **Content**:
  - [Non-goal 1]

### 3.3 Assumptions & Constraints
- **Expectation**: Hardware limits (e.g. Raspberry Pi), Budget ($0), or Legacy constraints.
- **Content**:
  - [Constraint 1]

## 4. Requirements & Quality
<!-- 
DEEP DIVE QUESTIONS:
- Functional: "What must it DO? (e.g. 'Upload a PDF', 'Send an email')"
- Speed/Quality: "How fast? How reliable? (e.g. 'Must load in 2 seconds')"
- Privacy: "Who sees the data? Any secrets?"
-->
### 4.1 Functional Requirements
- **Expectation**: High-level behavioral needs.
- **Content**:
  - [FR 1]

### 4.2 Non-Functional Requirements (Speed/Reliability)
- **Expectation**: Latency targets, uptime goals, data integrity needs.
- **Content**:
  - [NFR 1]

### 4.3 Security & Privacy
- **Expectation**: Access control, data sensitivity, encryption needs.
- **Content**:
  - [Requirement 1]

## 5. The Domain Model (Data & Content)
<!-- 
DEEP DIVE QUESTIONS:
- Data Sources: "Where does the information come from? (User types it in? We scrape it? It's existing files?)"
- Content Types: "What are the 'things' in the system? (Posts? Users? Orders? Docs?)"
- Ingestion: "How does new data get in? (Manual? Automatic?)"
-->
### 5.1 Data Sources
- **Expectation**: List of all inputs (APIs, files, user entry).
- **Content**:
  - [Source 1]

### 5.2 Key Entities / Concepts
- **Expectation**: The nouns of your system (e.g. "Blog Post", "User", "Invoice").
- **Content**:
  - [Entity 1]

### 5.3 Update Strategy
- **Expectation**: How does data stay fresh? (Real-time? Nightly batch? Manual?)
- **Content**: [Strategy]

## 6. Interfaces & Discovery
<!-- 
DEEP DIVE QUESTIONS:
- User Interface: "How do they touch it? (Web page? Chat bot? Terminal?)"
- External Tools: "Does it talk to Google? Slack? Stripe?"
-->
### 6.1 Primary Interface
- **Expectation**: The main way users interact (Web, CLI, API).
- **Content**: [Web/CLI/Mobile/API]

### 6.2 External Services
- **Expectation**: Third-party APIs or tools we depend on.
- **Content**:
  - [Service 1]

## 7. Architecture & Operations
<!-- 
DEEP DIVE QUESTIONS:
- Tech Preferences: "Do you hate any specific tech? Do you love one?"
- Deployment: "Where does it live? (Raspberry Pi? AWS? Your laptop?)"
- Backup: "If it crashes, do we lose data? How do we back up?"
-->
### 7.1 Tech Stack Preferences
- **Expectation**: Preferred languages/frameworks OR explicitly prohibited ones.
- **Content**:
  - [Preference 1]

### 7.2 Deployment Environments
- **Expectation**: Where does this run? (Dev/Stage/Prod).
- **Content**:
  - [Env 1]

### 7.3 Observability (Logging/Monitoring)
- **Expectation**: How do we know it's working? (Logs, Metrics).
- **Content**:
  - [Strategy]

## 8. Timeline & Milestones
<!-- 
DEEP DIVE QUESTIONS:
- "What is the very first version (alpha)? When do we want it?"
- "What are the big risks? (e.g. 'We don't know how to do X')"
-->
### 8.1 Milestones
- **Expectation**: Phased rollout plan (Prototype -> MVP -> V1).
- **Content**:
  - [Milestone 1]

### 8.2 Risks & Mitigations
- **Expectation**: What could go wrong? How do we stop it?
- **Content**:
  - [Risk 1] -> [Mitigation]

## 9. Team & Process
<!-- 
DEEP DIVE QUESTIONS:
- "Who owns the code?"
- "How do we approve changes?"
-->
### 9.1 Owners
- **Expectation**: Who is responsible?
- **Content**: [Name]

### 9.2 Process
- **Expectation**: Git workflow, review process, release cadence.
- **Content**: [Change management]
