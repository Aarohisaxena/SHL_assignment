from __future__ import annotations

import re

REFUSAL_TRIGGERS = (
    re.compile(r"\b(gdpr|hipaa|legal advice|employment law|visa|immigration|salary benchmark)\b", re.I),
    re.compile(r"\b(write|draft|create)\s+(?:a\s+)?job description\b", re.I),
    re.compile(r"\b(hiring decision|who should i hire|best candidate)\b", re.I),
)

INJECTION_TRIGGERS = (
    re.compile(r"ignore (?:all )?(?:previous|prior|above) instructions", re.I),
    re.compile(r"you are now (?:a|an) ", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"reveal (?:your )?instructions", re.I),
    re.compile(r"jailbreak", re.I),
)


def off_topic_reason(text: str) -> str | None:
    for pattern in REFUSAL_TRIGGERS:
        if pattern.search(text):
            return "I can only help you choose SHL assessments from our product catalog."
    for pattern in INJECTION_TRIGGERS:
        if pattern.search(text):
            return "I can only discuss SHL assessments. Tell me about the role or skills you need to measure."
    return None
