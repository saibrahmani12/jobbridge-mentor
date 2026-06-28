# ruff: noqa
# JobBridge Mentor — ADK 2.0 Multi-Agent Workflow
# Career assistant: resume drafting, training matching, interview practice

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

from mcp import StdioServerParameters

from google.adk import Workflow
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.workflow import Edge, START, node

from .config import config

# ─────────────────────────────────────────────────────────
# MCP Toolset — connects to local mcp_server.py via stdio
# ─────────────────────────────────────────────────────────

_MCP_SERVER_COMMAND = StdioConnectionParams(
    server_params=StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
    )
)

# Resume-focused MCP toolset (keyword analysis + salary benchmarking)
resume_mcp_toolset = McpToolset(
    connection_params=_MCP_SERVER_COMMAND,
    tool_filter=["analyze_resume_keywords", "estimate_salary_range", "search_job_listings"],
)

# Training-focused MCP toolset (program finder + career resources)
training_mcp_toolset = McpToolset(
    connection_params=_MCP_SERVER_COMMAND,
    tool_filter=["get_training_programs", "find_career_resources"],
)

logger = logging.getLogger("jobbridge_mentor")

# ─────────────────────────────────────────────────────────
# Security helpers — Phase 4
# ─────────────────────────────────────────────────────────

# PII patterns relevant to resume/career domain
_PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "passport": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    "date_of_birth": re.compile(
        r"\b(0?[1-9]|1[0-2])[/\-](0?[1-9]|[12]\d|3[01])[/\-](19|20)\d{2}\b"
    ),
}

# Prompt injection keywords — generic
_INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "disregard your instructions",
    "forget everything",
    "bypass security",
    "jailbreak",
    "act as dan",
    "pretend you are",
    "override your programming",
    "system prompt",
    "you are now",
    "new instructions",
    "ignore all rules",
]

# Domain-specific harmful content filter (career fraud / fake credentials)
_HARMFUL_CAREER_PATTERNS = [
    "fake degree",
    "fake diploma",
    "forged certificate",
    "fake employment history",
    "lie on resume",
    "lie on my resume",
    "lies on resume",
    "fake reference",
    "fake references",
    "counterfeit credential",
    "buy fake",
    "purchase diploma",
    "falsify work experience",
    "fabricate education",
    "ghost employee",
    "identity theft",
    "work illegally",
    "undocumented work without authorization",
    "fake work history",
    "fabricate experience",
    "forge diploma",
]

# Per-session request cap (domain-specific rate limit to protect quota)
_MAX_REQUESTS_PER_SESSION = 10


def scrub_pii(text: str) -> tuple[str, list[str]]:
    """Redact PII and return cleaned text + list of what was found."""
    found: list[str] = []
    for label, pattern in _PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            found.append(label)
            text = pattern.sub(f"[REDACTED_{label.upper()}]", text)
    return text, found


def detect_injection(text: str) -> list[str]:
    """Return any matched prompt-injection keywords."""
    lowered = text.lower()
    return [kw for kw in _INJECTION_KEYWORDS if kw in lowered]


def detect_harmful_content(text: str) -> list[str]:
    """Career-domain harmful content filter — detects requests for fraudulent credentials."""
    lowered = text.lower()
    return [pattern for pattern in _HARMFUL_CAREER_PATTERNS if pattern in lowered]


def audit_log(event: str, severity: str, details: dict[str, Any]) -> None:
    """Emit a structured JSON audit log entry (severity: INFO | WARNING | CRITICAL)."""
    import datetime
    entry = {
        "event": event,
        "severity": severity,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        **details,
    }
    logger.warning("AUDIT: %s", json.dumps(entry))


# ─────────────────────────────────────────────────────────
# Sub-agents
# ─────────────────────────────────────────────────────────

profile_collector_agent = LlmAgent(
    name="profile_collector",
    model=config.model,
    instruction="""You are a warm, supportive career counselor. Your job is to gather
the job seeker's background information. Ask for:
1. Their current or most recent job title / field
2. Key skills they have (technical or soft)
3. Highest level of education
4. What type of work they are looking for
5. Any barriers or challenges they face in their job search

Respond in a concise, friendly manner. When you have gathered enough information,
summarise the profile as a JSON block wrapped in triple backticks like:
```json
{"current_role":"...", "skills":["..."], "education":"...", "target_role":"...", "barriers":"..."}
```
""",
)

resume_writer_agent = LlmAgent(
    name="resume_writer",
    model=config.model,
    instruction="""You are a professional resume writer who specialises in helping
underrepresented job seekers. Given a job seeker's profile (current role, skills,
education, target role), craft a clean, ATS-friendly resume in markdown format.

You have access to career tools:
- Use `analyze_resume_keywords` to check ATS keyword gaps before writing.
- Use `estimate_salary_range` to include a salary expectation note.
- Use `search_job_listings` to find 1-2 matching job postings to tailor the resume toward.

Include:
- Contact block (use placeholder values)
- Professional Summary (3 sentences, tailored to target role)
- Skills section (grouped: Technical / Soft) — enriched with missing ATS keywords
- Work Experience (use provided or assumed relevant experience)
- Education
- A final "Action Tips" section with 2 personalised tips

Keep tone professional and empowering. Output the full resume in markdown.
""",
    tools=[resume_mcp_toolset],
)

training_matcher_agent = LlmAgent(
    name="training_matcher",
    model=config.model,
    instruction="""You are a career development advisor who specialises in local
training and upskilling programs. Given a job seeker's profile, recommend:

You have access to career tools:
- Use `get_training_programs` to find specific training programs for the seeker's skill gaps.
- Use `find_career_resources` to locate non-profit organisations relevant to their barriers.

1. Three specific training programs, courses, or certifications relevant to their
   target role and skill gaps. For each include:
   - Name of program / course
   - Provider (e.g. Coursera, edX, local community college, government program)
   - Estimated cost (free / low-cost preferred)
   - Duration
   - Why it's relevant to this seeker

2. Two job-search resources (job boards, networking groups, non-profit career centres)
   relevant to their situation or barriers — use find_career_resources to personalise these.

Format output as a structured markdown list.
""",
    tools=[training_mcp_toolset],
)

interview_coach_agent = LlmAgent(
    name="interview_coach",
    model=config.model,
    instruction="""You are a supportive interview coach. Given a job seeker's profile
and target role, provide:

1. Five likely interview questions for their target role
2. For each question: a model answer using the STAR method (Situation, Task, Action, Result)
   tailored to the seeker's background
3. Three confidence tips specific to the barriers they mentioned

Format as a numbered list with clear STAR breakdowns.
""",
)

# ─────────────────────────────────────────────────────────
# Orchestrator — uses AgentTool to delegate
# ─────────────────────────────────────────────────────────

orchestrator_agent = LlmAgent(
    name="orchestrator",
    model=config.model,
    instruction="""You are the JobBridge Mentor orchestrator. You help underrepresented
job seekers by coordinating a team of specialist agents.

ALWAYS start by using the profile_collector tool to gather the user's information.

After collecting the profile, determine what the user needs and call the appropriate
specialist tools in order:
- resume_writer: to draft a tailored resume
- training_matcher: to recommend training programs
- interview_coach: to prepare for interviews

You may call multiple tools in one session if the user wants comprehensive help.

After all tools have completed, provide a brief, encouraging summary paragraph that
ties together all the help provided. End with a motivational closing line.

IMPORTANT: Always be warm, empowering, and non-judgmental. Many users face real
barriers and deserve respectful, practical support.
""",
    tools=[
        AgentTool(agent=profile_collector_agent),
        AgentTool(agent=resume_writer_agent),
        AgentTool(agent=training_matcher_agent),
        AgentTool(agent=interview_coach_agent),
    ],
)

# ─────────────────────────────────────────────────────────
# Workflow nodes
# ─────────────────────────────────────────────────────────


@node
async def security_checkpoint(ctx: Context) -> str:
    """Phase 4 Security node — PII scrub + injection detect + domain fraud filter + rate limit.

    Returns:
        'CLEAR'          — input passed all checks, proceed to orchestrator.
        'SECURITY_EVENT' — input blocked; short-circuit to security_blocked_output.
    """
    raw = ""
    if ctx.user_content and ctx.user_content.parts:
        raw = " ".join(
            p.text for p in ctx.user_content.parts if hasattr(p, "text") and p.text
        )

    # ── Rate limit check (domain-specific: max requests per session) ──
    request_count = ctx.state.get("request_count", 0) + 1
    ctx.state["request_count"] = request_count
    if request_count > _MAX_REQUESTS_PER_SESSION:
        audit_log(
            "RATE_LIMIT_EXCEEDED",
            "WARNING",
            {"request_count": request_count, "limit": _MAX_REQUESTS_PER_SESSION,
             "node": "security_checkpoint"},
        )
        ctx.state["security_blocked_msg"] = (
            "⚠️ You have reached the maximum number of requests for this session. "
            "Please start a new session to continue."
        )
        ctx.state["security_blocked"] = True
        return "SECURITY_EVENT"

    # ── PII scrubbing (SSN, phone, email, credit card, passport, DOB) ──
    cleaned, pii_found = scrub_pii(raw)
    if pii_found:
        audit_log(
            "PII_DETECTED",
            "WARNING",
            {"pii_types": pii_found, "redacted_count": len(pii_found),
             "node": "security_checkpoint"},
        )
    ctx.state["safe_input"] = cleaned

    # ── Prompt injection detection ──
    injections = detect_injection(raw)
    if injections and config.injection_detection_enabled:
        audit_log(
            "INJECTION_DETECTED",
            "CRITICAL",
            {"keywords": injections, "node": "security_checkpoint"},
        )
        ctx.state["security_blocked_msg"] = (
            "⚠️ Your message was flagged for potentially unsafe content and could "
            "not be processed. Please rephrase your request."
        )
        ctx.state["security_blocked"] = True
        return "SECURITY_EVENT"

    # ── Domain-specific: career fraud / fake credentials filter ──
    harmful = detect_harmful_content(raw)
    if harmful:
        audit_log(
            "HARMFUL_CONTENT_DETECTED",
            "CRITICAL",
            {"patterns": harmful, "node": "security_checkpoint",
             "policy": "career_fraud_filter"},
        )
        ctx.state["security_blocked_msg"] = (
            "❌ JobBridge Mentor cannot assist with requests involving fraudulent "
            "credentials, fake work history, or other deceptive practices. "
            "We're here to help you succeed through legitimate means. "
            "Please rephrase your request."
        )
        ctx.state["security_blocked"] = True
        return "SECURITY_EVENT"

    # ── All clear ──
    audit_log(
        "INPUT_ACCEPTED",
        "INFO",
        {"pii_redacted": bool(pii_found), "request_count": request_count,
         "node": "security_checkpoint"},
    )
    ctx.state["security_blocked"] = False
    return "CLEAR"


@node
async def run_orchestrator(ctx: Context) -> None:
    """Delegate to the LlmAgent orchestrator using ctx.run_node."""
    safe_input = ctx.state.get("safe_input", "")
    result = await ctx.run_node(orchestrator_agent, node_input=safe_input)
    ctx.state["orchestrator_result"] = result.output if result else ""


@node
async def human_review(ctx: Context) -> str:
    """Ask the user to confirm before delivering the final output package."""
    await ctx.request_confirmation(
        hint=(
            "✅ JobBridge Mentor has prepared your career support package (resume, "
            "training recommendations, and/or interview prep). "
            "Reply **yes** to receive it, or tell me what you'd like to change."
        )
    )
    confirmed = ctx.resume_inputs
    if confirmed and str(confirmed).strip().lower() in ("yes", "y", "ok", "sure", "confirm"):
        return "APPROVED"
    ctx.state["revision_request"] = str(confirmed)
    return "REVISION"


@node
async def final_output(ctx: Context) -> None:
    """Emit the career support package to the user."""
    result = ctx.state.get("orchestrator_result", "")
    if result:
        ctx.output = result
    else:
        ctx.output = (
            "Your JobBridge Mentor session is complete. "
            "Please start a new message to begin your career support journey."
        )
    audit_log(
        "SESSION_COMPLETE",
        "INFO",
        {"delivered": bool(result), "node": "final_output"},
    )


@node
async def security_blocked_output(ctx: Context) -> None:
    """Return the security rejection message."""
    ctx.output = ctx.state.get(
        "security_blocked_msg",
        "⚠️ Your request was blocked for security reasons. Please rephrase and try again.",
    )


@node
async def handle_revision(ctx: Context) -> None:
    """Store revision request and loop back gracefully."""
    revision = ctx.state.get("revision_request", "")
    ctx.output = (
        f"Understood! I'll take note of your feedback: \"{revision}\". "
        "Please start a new message with your updated request and I'll regenerate "
        "your career support package."
    )


# ─────────────────────────────────────────────────────────
# Workflow graph
# ─────────────────────────────────────────────────────────

jobbridge_workflow = Workflow(
    name="jobbridge_mentor_workflow",
    description=(
        "End-to-end career support workflow: security check → profile collection "
        "→ resume writing / training matching / interview coaching → human review "
        "→ final delivery."
    ),
    edges=[
        # Entrypoint
        Edge(from_node=START, to_node=security_checkpoint),
        # Security routing
        Edge(from_node=security_checkpoint, to_node=run_orchestrator, route="CLEAR"),
        Edge(from_node=security_checkpoint, to_node=security_blocked_output, route="SECURITY_EVENT"),
        # Orchestrator → human review
        Edge(from_node=run_orchestrator, to_node=human_review),
        # Human review routing
        Edge(from_node=human_review, to_node=final_output, route="APPROVED"),
        Edge(from_node=human_review, to_node=handle_revision, route="REVISION"),
    ],
)

# ─────────────────────────────────────────────────────────
# App entry point
# ─────────────────────────────────────────────────────────

root_agent = jobbridge_workflow

app = App(
    root_agent=root_agent,
    name="app",  # Must match the directory name used by `adk web app`
)
