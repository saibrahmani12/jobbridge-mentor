# JobBridge Mentor — Submission Writeup

## Problem Statement

Underrepresented job seekers — including warehouse workers, caregivers, veterans, immigrants, people re-entering the workforce after incarceration, and single parents — face a compound disadvantage in the job market:

- They often lack access to professional resume writers ($200–$500 per session).
- They don't know which free or low-cost training programs exist for their skill gaps.
- They have no one to practice interviews with and feel unprepared.
- Generic AI tools give generic advice — not advice sensitive to real barriers like limited time, childcare constraints, or a criminal record.

**JobBridge Mentor** is an AI career assistant that closes this gap: it gathers each seeker's unique profile, drafts an ATS-optimised resume, recommends curated free/low-cost training programs, and runs a personalised mock interview — all in a single, secure session.

---

## Solution Architecture

```
User Message
     │
     ▼
┌─────────────────────────┐
│   Security Checkpoint   │  ← PII scrub · injection detect · fraud filter · rate limit
└────────────┬────────────┘
       CLEAR │              SECURITY_EVENT
             │              └──────────────────────────────► [Security Blocked Output]
             ▼
┌────────────────────────────────────────────────────────────────────┐
│                        Orchestrator Agent                          │
│  Delegates via AgentTool ──►  profile_collector                    │
│                          ──►  resume_writer  ◄── MCP Toolset A     │
│                          ──►  training_matcher ◄─ MCP Toolset B    │
│                          ──►  interview_coach                      │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
                   ┌──────────────────┐
                   │   Human Review ✋ │  ← HITL pause
                   └──────┬───────────┘
              APPROVED ───┘      REVISION
                   │                 └──► [Handle Revision]
                   ▼
          ┌────────────────┐
          │  Final Output  │
          └────────────────┘

MCP Server (stdio)
  ├── analyze_resume_keywords   → resume_writer
  ├── estimate_salary_range     → resume_writer
  ├── search_job_listings       → resume_writer
  ├── get_training_programs     → training_matcher
  └── find_career_resources     → training_matcher
```

---

## Concepts Used

| ADK Concept | Where Used | File |
|---|---|---|
| **ADK Workflow** | `jobbridge_workflow` Workflow graph with typed edges and route strings | `app/agent.py` L428–L447 |
| **LlmAgent** | `orchestrator_agent`, `profile_collector_agent`, `resume_writer_agent`, `training_matcher_agent`, `interview_coach_agent` — 5 specialised agents | `app/agent.py` L151–L268 |
| **AgentTool** | Orchestrator wraps all 4 sub-agents as callable tools | `app/agent.py` L262–L267 |
| **McpToolset** | Two filtered toolsets (resume tools, training tools) connect to the MCP stdio server | `app/agent.py` L38–L47 |
| **ctx.state** | Session state passed between nodes (`safe_input`, `orchestrator_result`, `security_blocked_msg`, `request_count`) | `app/agent.py` L283–L416 |
| **HITL / request_confirmation** | `human_review` node pauses for user confirmation before final delivery | `app/agent.py` L369–L383 |
| **Security Checkpoint Node** | `security_checkpoint()` sits between START and the orchestrator | `app/agent.py` L275–L358 |
| **Agents CLI scaffold** | Project scaffolded with `agents-cli scaffold create jobbridge-mentor --deployment-target agent_runtime` | `agents-cli-manifest.yaml` |
| **MCP Python SDK** | FastMCP stdio server with 5 domain-specific tools | `app/mcp_server.py` |

---

## Security Design

Every user message passes through `security_checkpoint()` before any LLM call is made. This node:

### 1. Rate Limiting
- **Control:** Max 10 requests per session (`_MAX_REQUESTS_PER_SESSION = 10`)
- **Why:** Prevents quota exhaustion from runaway sessions or automated abuse. Important for a free-tier public service.
- **Outcome on trigger:** `SECURITY_EVENT` → `security_blocked_output`, no LLM call.

### 2. PII Scrubbing
- **Control:** Regex redaction of SSN, US phone, email, credit card, passport number, date of birth.
- **Why:** Career assistants routinely receive sensitive personal data. Users should not have raw PII forwarded to external LLM APIs — it violates privacy expectations and can cause compliance issues.
- **Outcome on trigger:** PII replaced with `[REDACTED_TYPE]`, audit log at WARNING severity. Processing **continues** (non-blocking).

### 3. Prompt Injection Detection
- **Control:** 12 keyword patterns (e.g. "ignore previous instructions", "jailbreak", "you are now").
- **Why:** Prevents adversarial users from hijacking the agent's system prompt or extracting internal instructions.
- **Outcome on trigger:** `SECURITY_EVENT` → blocked, CRITICAL audit log entry.

### 4. Domain-Specific Fraud Filter
- **Control:** 20 career-fraud patterns (e.g. "fake degree", "lie on my resume", "fabricate experience").
- **Why:** The agent is explicitly for legitimate career support. Assisting with credential fraud would cause real harm to employers and undermine trust in the tool.
- **Outcome on trigger:** `SECURITY_EVENT` → blocked, CRITICAL audit log with `policy: career_fraud_filter`.

### Audit Log Format
Every security decision emits a structured JSON entry:
```json
{
  "event": "PII_DETECTED",
  "severity": "WARNING",
  "timestamp": "2026-06-28T07:30:00Z",
  "pii_types": ["ssn"],
  "redacted_count": 1,
  "node": "security_checkpoint"
}
```

---

## MCP Server Design

**File:** `app/mcp_server.py` — FastMCP stdio transport, 5 tools.

| Tool | Agent(s) | Purpose |
|---|---|---|
| `analyze_resume_keywords` | `resume_writer` | Compares a resume draft against role-specific ATS keyword lists; returns present/missing keywords and an ATS score estimate (0–100%). |
| `estimate_salary_range` | `resume_writer` | Benchmarks salary for a role + location + years of experience using aggregated BLS/Glassdoor data. Helps the resume writer add a salary expectation note. |
| `search_job_listings` | `resume_writer` | Returns 1–5 simulated job postings for the target role and location so the resume can be tailored to real-sounding openings. |
| `get_training_programs` | `training_matcher` | Looks up curated free/low-cost training programs by skill or role (Coursera, edX, Harvard CS50, LinkedIn Learning, etc.). |
| `find_career_resources` | `training_matcher` | Returns non-profit organisations and government programs matched to the seeker's barrier (disability, criminal record, veteran, single parent, immigrant, youth, general). |

All tool data is currently simulated/curated. In production, each tool would call a real API (Indeed, BLS, Coursera catalog, CareerOneStop, etc.).

---

## Human-in-the-Loop (HITL) Flow

After the orchestrator collects the full career support package (resume + training + interview prep), the workflow pauses at the `human_review` node before delivering output:

1. **Pause:** `ctx.request_confirmation(hint=...)` is called — the UI shows a confirmation prompt.
2. **User replies "yes":** Workflow routes to `final_output`, which delivers the full package.
3. **User replies with revision request:** Workflow routes to `handle_revision`, which acknowledges the feedback and instructs the user to re-send with changes.

**Why HITL here?** The career package can be long and the user may want to steer it (e.g., "focus only on the resume, skip interview prep"). Pausing before delivery respects the user's time and avoids overwhelming them with unrequested content.

---

## Demo Walkthrough

See the three test cases in `README.md`:

1. **Full Career Support Session** — Happy path: warehouse worker → data analytics transition. Tests all 5 agents + MCP tools + HITL confirmation.
2. **Security Block (Fraud Filter)** — Input contains "fake degree". Security checkpoint fires, no LLM is called, user gets the rejection message.
3. **PII Scrubbing** — Input contains a real SSN. Checkpoint scrubs it, logs it, then passes the sanitised message to the orchestrator for normal processing.

---

## Impact / Value Statement

**Who benefits:**
- Warehouse workers, retail employees, and other blue-collar workers seeking a career pivot
- Single parents with limited time who can't afford career counselling
- Immigrants and refugees whose credentials may not transfer directly
- Veterans transitioning out of service
- People with criminal records navigating fair-chance hiring
- Youth (16–24) who lack professional networks

**Why it matters:**
Professional resume writing costs $200–$500. Career counselling is $75–$200/session. Most underrepresented job seekers can afford neither. JobBridge Mentor delivers the equivalent of a resume writer, a career advisor, and an interview coach — in a single free session — while protecting user privacy through PII scrubbing and ensuring ethical use through the fraud filter.

The multi-agent architecture means each specialist (resume, training, interview) is optimised for its domain rather than relying on a single generalist prompt. The MCP server makes the career data layer independently testable and extensible — adding a real job board API or a live scholarship database requires changing only one tool function.
