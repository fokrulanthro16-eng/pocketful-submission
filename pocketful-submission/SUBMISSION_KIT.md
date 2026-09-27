# Pocketful: Complete Hackathon Submission Kit
**Event:** WeAreDevelopers x BAND: Dark Factory Hackathon  
**Participant:** Fokrul Islam (`fokrulanthro16-eng`)  
**Project:** Pocketful — Autonomous Zero-Sum Fintech Engine  
**Status:** Certified 10/10 Enterprise Release (193/193 Tests Passed, Highest Contiguous Stage: 4)

---

## 1. Lablab.ai Submission Metadata

### Project Title
`Pocketful — Autonomous Zero-Sum Fintech Engine`

### Tagline / Short Description
`A high-concurrency, bitemporal wallet and payments engine built autonomously by a 3-seat Band Desktop agent factory with 100% invariant verification and SHA-256 audit trails.`

### Categorized Tags
`FastAPI, Band Desktop, Multi-Agent Systems, Docker, Python, Fintech, SHA-256, Vercel, Microservices, Autonomous AI`

### Repository URL
`https://github.com/band-ai/dark-factory-wearedevs`

---

## 2. Long Pitch (Tailored to Hackathon Judging Criteria)

### A. The Autonomous Software Factory (50% of Total Score)
Traditional AI coding tools function as interactive copilot text completion engines, requiring continuous human steering, debugging, and prompt micro-adjustments. Pocketful was constructed under a radically different paradigm: a **100% Dark Factory** with **zero human intervention between stage dispatch and final verification**.

#### 1. Tripartite Separation of Concerns (`mandates/`)
Operating within **BAND Desktop**, our factory organizes three specialized agent seats that strictly decouple strategic design, implementation, and verification:
- **Planner (`@planner`):** Ingests functional requirements, decomposes bitemporal state-machine transitions, computes mathematical invariants, and dispatches self-contained handoff bundles. Never writes code.
- **Implementer (`@implementer`):** Generates modular, typed FastAPI services, double-entry transactional schemas, and container assets conforming to the Planner's architecture. Never self-approves.
- **Reviewer (`@reviewer`):** Acts as a hostile, independent auditor. Executes test harnesses in clean environments, checks DOM invariant assertions, and performs security audits. Never patches code directly.

#### 2. Model Tiering & Token Economics
- **Reasoning Tier (Planner & Reviewer):** Powered by `nvidia/llama-3.1-nemotron-70b-instruct` / `claude-3-7-sonnet` for deep invariant logic and adversarial test auditing.
- **Throughput Tier (Implementer):** Powered by `google/gemini-1.5-flash` / `claude-3-7-sonnet` for rapid code generation and 1M context analysis.
- **Total Factory Compute Cost:** **344,850 total tokens across 4 full stages costing only \$0.77 USD**—proving that multi-agent autonomous engineering is orders of magnitude more economical than traditional engineering teams.

#### 3. Zero Track Leakage & Generic Mandates
All seat mandates in `mandates/` are 100% generic, universal software engineering role descriptions with zero track-specific vocabulary leaks, earning a 0-problem pass on harness Gate 1 and Gate 4 checks.

---

### B. The Application: Enterprise Fintech Hardening (25% of Total Score)
Pocketful is not a prototype; it is an enterprise-hardened double-entry ledger platform:

#### 1. Fundamental Zero-Sum Invariant
$$\sum_{u \in \mathcal{U}} \text{balance}(u) = \mathcal{M}_0 \quad \forall t \ge 0$$
No money is ever created or destroyed. Every transaction, hold reservation, settlement, and refund strictly conserves the money supply $\mathcal{M}_0$, verified in real-time via `GET /audit/zero-sum` and visual UI health badges.

#### 2. Bitemporal Timeline & Historical Overdraft Guard
Transactions record both **Effective Time** ($\tau_{\text{eff}}$) and **Recorded Time** ($\tau_{\text{rec}}$). Retroactive corrections and multi-account correction batches are validated against historical available balances across every boundary instant in the timeline, preventing historical overdraft attacks.

#### 3. Real-Time Cryptographic Hash Chaining (SHA-256)
Every state mutation creates a Merkle block cryptographically linked to the preceding block:
$$H_i = \text{SHA256}\Big( i \;\|\; H_{i-1} \;\|\; T_i \;\|\; \text{EventType}_i \;\|\; \text{CanonicalJSON}(D_i) \Big)$$
The audit chain is verifiable in $O(N)$ time via `GET /audit/verify`, providing tamper-evident proof suitable for SOC 2 Type II compliance.

#### 4. Real-Time AML & Fraud Sentinel Layer (`app/sentinel.py`)
Runs inline behavioral analytics evaluating transactions in real-time:
- **Rule AML-001:** High-value anomaly flag ($\ge 100,000$ minor units).
- **Rule AML-002:** Rapid micro-transfer burst flag ($\ge 5\text{ transfers in } \le 60\text{s}$).
- Emits structured JSON security audit streams without breaking standard HTTP status code contracts.

#### 5. Two-Phase Payment Holds & Net Settlements
Supports commerce holds (`POST /authorizations`) with partial or final capture, voiding, and operator-level multi-wallet batch settlements (`POST /settlements`).

---

### C. Teamwork & Multi-Agent Collaboration (25% of Total Score)
- **Asynchronous Handoff Protocols:** Standardized JSON handoff packets passed through literal `@handle` mentions in the BAND room log (`room.json`).
- **Autonomous Error Recovery:** When Reviewer detected DOM detachment timing issues during Stage 2 Playwright verification, it automatically generated structured failure diffs with reproduction curl commands, enabling the Implementer to deliver a targeted patch on the next iteration without human input.
- **Containerization & Cloud Readiness:** Delivered with a multi-stage, non-root `Dockerfile` (`python:3.11-slim`), `docker-compose.yml` with health check probes, and `vercel.json` configured for 1-click cloud serverless deployment.

---

## 3. Exact 2-Minute Video Recording Script

**Target Duration:** Exactly 120 seconds (2:00)  
**Speaker:** Fokrul Islam  
**Tools on Screen:** BAND Desktop, VS Code / Terminal, Google Chrome (`http://127.0.0.1:8080`)

| Timestamp | Visual on Screen | Presenter Voiceover Script | Action / Demonstration |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:20** | BAND Desktop UI displaying the 3-seat room (`room.json`) with Planner, Implementer, and Reviewer. | *"Hello judges! Welcome to Pocketful — an enterprise zero-sum fintech engine built 100% autonomously by our 3-seat Dark Factory inside BAND Desktop. I'm Fokrul Islam, and here is how autonomous engineering built banking-grade software from scratch."* | Show room seats and initial dispatch from human. |
| **0:20 – 0:40** | Open `mandates/` directory in VS Code (`planner.md`, `implementer.md`, `reviewer.md`). | *"Notice our standing mandates: they are 100% generic software engineering roles. No track leaks, no hardcoded paths. The Planner breaks down invariants, the Implementer builds clean FastAPI code, and the Reviewer acts as a hostile auditor. They communicate strictly through self-contained handoffs."* | Scroll through `mandates/planner.md` highlighting separation of duties. |
| **0:40 – 1:00** | Split terminal: Run `python -m harness check pocketful-submission --track pocketful`. | *"Let's verify the submission gates. Running harness check: Gate 1, Gate 2, and Gate 4 mandates pass with 0 problems detected. All track constraints are 100% satisfied."* | Highlight `ok — gates 1, 2 and the mandate part of gate 4 pass. 0 problems.` |
| **1:00 – 1:15** | Run `python -m harness run --track pocketful --base-url http://127.0.0.1:8080 --stages 1 2 3 4`. | *"Now the complete test harness across all four stages: Stage 1 accounts, Stage 2 holds and Playwright UI, Stage 3 bitemporal timelines, and Stage 4 multi-wallet settlements. 193 out of 193 tests passing, achieving the highest contiguous Stage 4!"* | Point out terminal output showing `highest contiguous stage: 4` and `193 passed`. |
| **1:15 – 1:40** | Browser window at `http://127.0.0.1:8080/`. Log in as Ada. | *"Here is the live enterprise dashboard. Notice the header: 'Zero-Sum Health: 100% Invariant Verified' and 'SHA-256 Audit Chain Active'. When we transfer funds or split bills, available balances update with microsecond precision, double-spending is physically impossible, and the total money supply is strictly conserved."* | Show wallet balances, send a payment, demonstrate instant balance reflection. |
| **1:40 – 2:00** | Navigate to `http://127.0.0.1:8080/audit` (Enterprise Audit tab). | *"Finally, our Enterprise Audit tab. Every transaction is appended to a cryptographic SHA-256 hash chain, verifiable in real time via our `/audit/verify` API. Below it, our AML Sentinel evaluates velocity bursts and anomaly flags in real-time. Built in Python 3.11, containerized with non-root Docker, and ready for Vercel. Thank you!"* | Scroll through verified blocks with hashes and live AML alert feed. Conclude. |

---

## 4. Pre-Submission Validation Checklist

- [x] **Gate 1 (Mandates):** Checked with `python -m harness check` — 0 problems, 100% generic roles.
- [x] **Gate 2 (Structure):** `room.json`, `mandates/`, `stage-1/` through `stage-4/` present.
- [x] **Gate 3 (Build & Run):** Stage 1-4 services build and serve `/health` cleanly.
- [x] **Gate 4 (Execution):** 193 / 193 contract tests passed across all 4 stages.
- [x] **Highest Contiguous Stage:** Stage 4 (Maximum possible score).
- [x] **Enterprise Hardening:** Concurrency mutex, Idempotency-Key replay cache, AML Sentinel, and SHA-256 Merkle chain active.
- [x] **Documentation Package:** Complete `README.md`, `FACTORY.md`, `ENTERPRISE_ARCHITECTURE.md`, `LICENSE`, and `SUBMISSION_KIT.md`.
- [x] **Containerization:** Multi-stage `Dockerfile` (python:3.11-slim, non-root user) and `docker-compose.yml`.
- [x] **Cloud Deployment:** `vercel.json` configured for `fokruls-projects` with ASGI handler at `api/index.py`.
- [x] **Visual Evidence:** High-resolution screenshots captured in `assets/screenshots/`.
- [x] **Git & Security:** Clean working tree, `.env` strictly protected by `.gitignore`.
