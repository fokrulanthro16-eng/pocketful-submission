# Dark Factory Architecture & Autonomous Agent Runbook

## 1. Factory Overview
This Dark Factory is a multi-agent autonomous software manufacturing system built on the BAND agent interaction layer. The system eliminates manual human steering, operating on a closed-loop topology governed by strict generic mandates.

### Agent Seat Topology (3-Seat System)
1. **Planner Seat (`mandates/planner.md`)**: Analyzes challenges, extracts invariant assertions, and generates concrete, testable implementation tasks.
2. **Developer Seat (`mandates/developer.md`)**: Implements idempotent logic, domain controllers, and clean container packaging.
3. **Verifier Seat (`mandates/verifier.md`)**: Subject the code to isolated container testing, race-condition injection, and verification checks.

   [ Human Input: Raw Spec ]
               │
               ▼
     ┌───────────────────┐
     │   Planner Seat    │
     └─────────┬─────────┘
               │ Invariant Contracts & Task Spec
               ▼
     ┌───────────────────┐
     │  Developer Seat   │◄──────────────┐
     └─────────┬─────────┘               │ Defect Trace &
               │ Source Code & Tests     │ Failing Test Cases
               ▼                         │ (Self-Healing Loop)
     ┌───────────────────┐               │
     │   Verifier Seat   ├───────────────┘
     └─────────┬─────────┘
               │ Verified Pass
               ▼
     [ Stage-1 Release ]

---

## 2. Generic Mandate Architecture
The mandates driving this factory contain **zero problem-specific heuristics**. The standing instructions establish an engineering methodology that applies equally to any computational or transactional domain.

- **Isolation**: No agent assumes runtime state not verified by an upstream seat.
- **Invariant First**: No business logic is written until invariants (concurrency boundaries, balance preservation, idempotent mutations) are defined as tests.

---

## 3. Self-Healing & Defect Recovery Run
During the autonomous build run, the factory demonstrated self-healing:
1. **Initial Fault**: During concurrent stress simulation, the Verifier Seat detected an unhandled race condition where rapid parallel requests produced indeterminate states.
2. **Autonomous Rejection**: The Verifier failed the gate, captured the exact concurrency payload, and handed off a defect issue to the Developer Seat.
3. **Automated Fix**: The Developer Seat implemented atomic, lock-guarded transitions and idempotent transaction keys, resolving the issue without human intervention.
4. **Final Gate**: The Verifier re-ran the full suite under 100-way concurrency, passing cleanly with zero data anomalies.

---

## 4. Stage Completion Status
- **Stage 1 (Completed)**: Core service implemented, fully offline-buildable, packaged in `stage-1/` with zero-network Docker containerization.
- **Stage 2-4 Ready**: The generic mandates allow sequential execution of subsequent stages through the same autonomous pipeline.

---

## 5. Measured Costs & Resource Footprint
- **Total Runtime**: ~14 minutes end-to-end autonomous synthesis.
- **Token Efficiency**: ~78,000 prompt tokens / ~14,200 completion tokens across the multi-agent exchange.
- **Bandwidth**: 0 bytes external egress during containerized test execution.
