# EchoInsight Architecture Diagram Index

This document catalogues the architecture diagrams produced for the EchoInsight platform, explaining what each answers and recommending a reading order.

## Recommended Reading Order

1. **[D0 Master Poster](file:///docs/architecture/diagrams/D0_master_poster.svg)**: Start here for the 60-second summary. Shows the entire system on one page (components, data flow, trust/safety, observability).
2. **[D1 System Context](file:///docs/architecture/diagrams/D1_system_context.svg)**: Understand the system boundaries, users, and external dependencies.
3. **[D4 Analysis Pipeline](file:///docs/architecture/diagrams/D4_analysis_pipeline.svg)**: Deep dive into the core engine—how turns become final analyses, what is deterministic, and where the LLM is used.
4. **[D7 QA Scoring Flow](file:///docs/architecture/diagrams/D7_qa_scoring.svg)**: Understand the QA mechanisms, the evidence gate, and how partial scores and critical violations work.
5. **[D10 Security & Trust Boundaries](file:///docs/architecture/diagrams/D10_security.svg)**: Review how PII is redacted and how prompt injection is mitigated before any LLM call.

## Complete Diagram List

### 1. High-Level Overviews
* **[D0 Master Architecture Poster](file:///docs/architecture/diagrams/D0_master_poster.svg)**
  * *Answers:* What is EchoInsight? What are its parts? How does data move through it?
  * *Audience:* Everyone (Leadership, Engineers, Reviewers)
* **[D1 System Context](file:///docs/architecture/diagrams/D1_system_context.svg)**
  * *Answers:* Who uses the system? What external services does it talk to?
  * *Audience:* Product, Engineering
* **[D2 Runtime Containers](file:///docs/architecture/diagrams/D2_runtime_containers.svg)**
  * *Answers:* What processes are running? What databases and files are accessed at runtime?
  * *Audience:* DevOps, Engineering

### 2. Core Backend & Data
* **[D3 Backend Components & Dependencies](file:///docs/architecture/diagrams/D3_backend_components.svg)**
  * *Answers:* What are the Python packages? How do they depend on each other?
  * *Audience:* Backend Engineers
* **[D9 Data Model (ER Diagram)](file:///docs/architecture/diagrams/D9_data_model.svg)**
  * *Answers:* What tables exist? How do they relate? Which ones are seeded?
  * *Audience:* Data Engineers, Backend Engineers

### 3. Pipeline & Logic Deep Dives
* **[D4 Analysis Pipeline Data Flow](file:///docs/architecture/diagrams/D4_analysis_pipeline.svg)**
  * *Answers:* What happens when a turn is appended vs when a call ends? Which steps are deterministic vs LLM-driven?
  * *Audience:* AI Engineers, Backend Engineers
* **[D5 Conversation Lifecycle State Machine](file:///docs/architecture/diagrams/D5_state_machine.svg)**
  * *Answers:* How does a conversation move from created to closed? How does the idle sweep work?
  * *Audience:* Product, Engineering
* **[D6 Commitment Ledger Transitions](file:///docs/architecture/diagrams/D6_commitment_ledger.svg)**
  * *Answers:* What are the states of a commitment? What causes a transition?
  * *Audience:* Product, Engineering
* **[D7 QA Scoring Flow](file:///docs/architecture/diagrams/D7_qa_scoring.svg)**
  * *Answers:* How are QA scores calculated? How does selective verification work?
  * *Audience:* Product, Data Science

### 4. Interactions & Sequence
* **[D8 Sequence Diagrams](file:///docs/architecture/diagrams/D8_sequence_diagrams.svg)**
  * *Answers:* In what order do operations happen across the browser, API, worker, and LLM?
  * *Audience:* Full-stack Engineers

### 5. Non-Functional & Operations
* **[D10 Security & Trust Boundaries](file:///docs/architecture/diagrams/D10_security.svg)**
  * *Answers:* How is PII protected? How is access scoped? Where does the LLM fit securely?
  * *Audience:* Security, DevOps
* **[D11 Deployment Topology](file:///docs/architecture/diagrams/D11_deployment.svg)**
  * *Answers:* How is the app deployed? Where do Vercel and Render fit? How does the boot sequence work?
  * *Audience:* DevOps
* **[D12 Observability, Evaluation & CI](file:///docs/architecture/diagrams/D12_observability.svg)**
  * *Answers:* How do we know the system is healthy? What tests run?
  * *Audience:* DevOps, QA, Data Science
* **[D15 Scale-Out Target](file:///docs/architecture/diagrams/D15_scale_out.svg)** (Design only)
  * *Answers:* How would this system scale for production? What current limits does it address?
  * *Audience:* Architecture, Engineering Leadership

### 6. Sub-Systems
* **[D13 Frontend Architecture](file:///docs/architecture/diagrams/D13_frontend.svg)**
  * *Answers:* How is the React app structured? How is state managed?
  * *Audience:* Frontend Engineers
* **[D14 Optional & Add-on Layers](file:///docs/architecture/diagrams/D14_optional_layers.svg)**
  * *Answers:* What is feature-flagged off? How do the Action Layer and Assistant integrate?
  * *Audience:* Product, Engineering
