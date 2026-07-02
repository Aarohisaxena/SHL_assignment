from __future__ import annotations

import re

from app.catalog.search import HiringContext
from app.models import ChatMessage

ROLE_HINTS = (
    "developer",
    "engineer",
    "manager",
    "analyst",
    "consultant",
    "designer",
    "recruiter",
    "sales",
    "support",
    "accountant",
    "nurse",
    "driver",
    "administrator",
    "director",
    "graduate",
    "intern",
)

SKILL_HINTS = (
    "java",
    "python",
    "javascript",
    "sql",
    "react",
    "spring",
    "dotnet",
    ".net",
    "c++",
    "c#",
    "aws",
    "devops",
    "excel",
    "communication",
    "stakeholder",
    "leadership",
    "customer service",
    "negotiation",
)

SENIORITY_MAP = {
    "entry": "entry-level",
    "junior": "entry-level",
    "graduate": "graduate",
    "intern": "entry-level",
    "mid": "mid-professional",
    "senior": "senior",
    "lead": "manager",
    "manager": "manager",
    "director": "director",
    "executive": "executive",
}

COMPARE_RE = re.compile(
    r"(?:difference|compare|versus|vs\.?|better)\s+(?:between\s+)?(.+?)\s+(?:and|vs\.?|versus)\s+(.+?)(?:\?|$)",
    re.I,
)
JD_RE = re.compile(r"(?:job description|jd|description text|here is (?:a )?text)[:\s]+(.+)", re.I | re.S)
EXCLUDE_RE = re.compile(r"(?:not|without|exclude|avoid)\s+([a-z0-9+#.\s]{2,40})", re.I)


def _join_user_text(messages: list[ChatMessage]) -> str:
    return "\n".join(m.content for m in messages if m.role == "user")


def _last_user_message(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


def extract_context(messages: list[ChatMessage]) -> HiringContext:
    text = _join_user_text(messages)
    lower = text.lower()
    last = _last_user_message(messages).lower()

    ctx = HiringContext(raw_text=text)

    if JD_RE.search(text) or len(text.split()) > 35:
        ctx.pasted_jd = bool(JD_RE.search(text)) or len(text.split()) > 60

    for hint in ROLE_HINTS:
        if re.search(rf"\b{re.escape(hint)}\b", lower):
            ctx.role = hint if not ctx.role else ctx.role

    for hint in SKILL_HINTS:
        if hint.replace(".", "") in lower or hint in lower:
            if hint not in ctx.skills:
                ctx.skills.append(hint)

    for token, mapped in SENIORITY_MAP.items():
        if re.search(rf"\b{token}\b", lower):
            ctx.seniority = mapped
            break

    if re.search(r"\b\d+\s*(?:years?|yrs?)\b", lower):
        yrs = re.search(r"\b(\d+)\s*(?:years?|yrs?)\b", lower)
        if yrs:
            n = int(yrs.group(1))
            if n <= 2:
                ctx.seniority = ctx.seniority or "entry-level"
            elif n <= 5:
                ctx.seniority = ctx.seniority or "mid-professional"
            else:
                ctx.seniority = ctx.seniority or "senior"

    ctx.wants_personality = any(
        k in lower for k in ("personality", "opq", "behavior", "behaviour", "motivation", "culture fit")
    )
    ctx.wants_cognitive = any(
        k in lower for k in ("cognitive", "aptitude", "verify", "reasoning", "mental ability", "gsa", "g+")
    )
    ctx.wants_technical = any(
        k in lower for k in ("technical", "coding", "programming", "skill test", "java", "python", "sql")
    )
    ctx.wants_sjt = any(k in lower for k in ("situational", "sjt", "judgment", "judgement"))
    ctx.wants_simulation = "simulation" in lower

    if "add personality" in last or "include personality" in last:
        ctx.wants_personality = True
    if "add cognitive" in last or "include cognitive" in last:
        ctx.wants_cognitive = True
    if "add " in last or "also " in last or "include " in last:
        if "technical" in last or "skill" in last:
            ctx.wants_technical = True

    # Common trap: Java role should not pull JavaScript tests
    if "java" in ctx.skills and "javascript" not in lower:
        if "javascript" not in ctx.exclude_terms:
            ctx.exclude_terms.append("javascript")

    for m in EXCLUDE_RE.finditer(text):
        term = m.group(1).strip()
        if term and term not in ctx.exclude_terms:
            ctx.exclude_terms.append(term)

    cm = COMPARE_RE.search(_last_user_message(messages))
    if cm:
        ctx.compare_targets = [cm.group(1).strip(), cm.group(2).strip()]

    return ctx


def context_dimensions(ctx: HiringContext) -> int:
    dims = 0
    if ctx.role:
        dims += 1
    if ctx.seniority:
        dims += 1
    if ctx.skills:
        dims += 1
    if ctx.pasted_jd:
        dims += 1
    if any(
        [
            ctx.wants_personality,
            ctx.wants_cognitive,
            ctx.wants_technical,
            ctx.wants_sjt,
            ctx.wants_simulation,
        ]
    ):
        dims += 1
    return dims


def is_vague_opening(messages: list[ChatMessage]) -> bool:
    if len(messages) > 1:
        return False
    text = _last_user_message(messages).strip().lower()
    vague_patterns = (
        r"^i need an assessment\.?$",
        r"^recommend assessments?\.?$",
        r"^help me choose\.?$",
        r"^what should i use\??$",
    )
    if any(re.match(p, text) for p in vague_patterns):
        return True
    if len(text.split()) <= 4 and "assessment" in text:
        return True
    return False


def should_clarify(messages: list[ChatMessage], ctx: HiringContext) -> bool:
    if is_vague_opening(messages):
        return True

    if ctx.compare_targets:
        return False

    if ctx.pasted_jd:
        return False

    if not ctx.role:
        return True
    
    return context_dimensions(ctx) < 2
