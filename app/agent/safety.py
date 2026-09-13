import re
from dataclasses import dataclass

@dataclass(frozen=True)
class SafetyDecision:
    category: str
    blocked: bool
    message: str

# Policy-first lexical screening. This is intentionally conservative for high-risk
# requests; ordinary appointment language is kept outside these patterns.
PROMPT_INJECTION = re.compile(
    r"(?:ignore|disregard|forget|override|bypass|disable|break).{0,120}"
    r"(?:system|developer|previous|safety|instruction|rule|policy)|"
    r"(?:reveal|show|print|dump|repeat|leak).{0,120}"
    r"(?:system prompt|hidden prompt|hidden instruction|api key|secret|password|token|credential|database|sql)|"
    r"(?:act as|pretend to be|you are now|roleplay as).{0,60}"
    r"(?:admin|developer|system|root|doctor)"
    r"|(?:پچھلی ہدایات|سسٹم ہدایات|چھپی ہدایات|قواعد نظر انداز|ہدایات نظر انداز|ڈاکٹر بنو)",
    re.I | re.S,
)

SECRET_REQUEST = re.compile(
    r"(?:api\s*key|secret|password|token|credential|private\s+(?:phone|contact)|"
    r"database\s*(?:url|password|credential|connection)|system\s*prompt|hidden\s*(?:prompt|instruction)|"
    r"sql\s*(?:query|statement)|patient\s+(?:records?|data|history)|medical\s+records?|"
    r"other\s+patients?|internal\s+(?:data|details|notes)|staff\s+only|developer\s+notes|"
    r"ذاتی\s*(?:معلومات|ریکارڈ)|مریضوں?\s*(?:کا\s*)?(?:ریکارڈ|ڈیٹا)|پاس ورڈ|خفیہ\s*ہدایات)",
    re.I,
)

MALICIOUS_TOOL = re.compile(
    r"(?:run|execute|write|delete|drop|update|insert|select|query|alter|truncate).{0,80}"
    r"(?:sql|database|table|record|appointment|patient)|"
    r"(?:database|sql).{0,40}(?:update|insert|delete|drop|alter|truncate)|"
    r"(?:delete|drop|alter|truncate).{0,50}(?:database|table|record)|"
    r"(?:mark|force|override|manually).{0,60}(?:confirmed|booked|available)|"
    r"(?:call|invoke|use).{0,50}(?:tool|function).{0,80}(?:without|ignore|skip).{0,50}(?:validation|availability|permission)",
    re.I | re.S,
)

# Emergency red flags.
#
# This layer exists because a patient describing a serious symptom while asking
# for an appointment is not asking for medical advice, so the MEDICAL pattern
# above does not fire - they get a routine booking form for something that may
# need care today. That is the wrong answer even though nothing false is said.
#
# Two rules govern what may go in here:
#   1. Only descriptions a lay person would recognise as urgent. It is a
#      keyword list, not a triage system.
#   2. The response never names a condition, never assesses severity, and never
#      suggests a specialty or doctor. Routing a symptom to a department is
#      clinical triage, which this assistant must not perform.
EMERGENCY = re.compile(
    r"\b(?:chest\s*pain|heart\s*attack|stroke|unconscious|not\s*breathing|"
    r"can'?t\s*breathe|cannot\s*breathe|difficulty\s*breathing|trouble\s*breathing|"
    r"severe\s*bleeding|heavy\s*bleeding|bleeding\s*a\s*lot|"
    r"seizure|fits|convulsion|poison|overdose|"
    r"suicidal|severe\s*allergic|anaphyla|"
    r"collapsed|fainted|unresponsive)\b"
    r"|\b(?:seenay?\s*(?:me|mein|main)?\s*dard|dil\s*ka\s*daura|"
    r"saans\s*(?:nahi|nhi|band)|behosh|dora\s*pa|zyada\s*khoon|khoon\s*beh)\b"
    r"|سینے\s*میں\s*درد|دل\s*کا\s*دورہ|سانس\s*(?:نہیں|بند)|بیہوش|دورہ\s*پڑ|شدید\s*خون",
    re.I,
)

SAFE_EMERGENCY = (
    "What you're describing may need urgent attention. Please contact local emergency "
    "services or go to the nearest emergency facility now — don't wait for an appointment. "
    "I'm an administrative assistant and can't assess symptoms. Once you've been seen, "
    "I'm here to help with clinic information and appointments."
)

MEDICAL = re.compile(
    r"(?:\b(?:diagnos(?:e|is|ing)|treatment|treat|medicine|medication|prescription|prescribe|"
    r"dosage|dose|symptom|symptoms|what disease|should i take|is this serious|what should i do for)\b|"
    r"مرض|علاج|دوائی|دوا|خوراک|تشخیص|نسخہ|علامات|بیماری|کیا دوا|علاج بتائیں|تشخیص کریں|"
    r"bemari|bemaari|ilaj|ilaaj|dawai|dawa|nuskha|khurak|alamat|marz)",
    re.I,
)

SAFE_INJECTION = (
    "I can help with clinic information and appointments, but I can't follow instructions "
    "that override my safety rules or expose internal instructions, secrets, or system details."
)
SAFE_MEDICAL = (
    "I can help with clinic information and appointments, but I can't diagnose conditions or "
    "provide treatment, prescription, or dosage advice. Please contact a qualified clinician. "
    "If this is an emergency, contact local emergency services or go to the nearest appropriate emergency facility."
)
SAFE_UNSUPPORTED = (
    "The requested information or operation is unavailable through this administrative assistant. "
    "Please contact clinic staff for help."
)

# Output-side defense: never echo privileged material even if a faulty retriever, tool,
# or future LLM response attempts to place it into the final answer.
OUTPUT_SECRET = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|api[_ -]?key\s*[:=]|password\s*[:=]|token\s*[:=]|"
    r"database\s*(?:url|connection)\s*[:=]|system\s*prompt\s*[:=])",
    re.I,
)
OUTPUT_INSTRUCTION = re.compile(
    r"(?:ignore|disregard|override)\s+(?:all\s+)?(?:previous|system|developer|safety)\s+(?:instructions|rules|policy)|"
    r"(?:assistant|system|developer)\s*:\s*(?:ignore|execute|reveal)",
    re.I,
)


def inspect_user_message(text: str) -> SafetyDecision:
    if not isinstance(text, str) or not text.strip():
        return SafetyDecision("security", True, SAFE_UNSUPPORTED)
    if PROMPT_INJECTION.search(text) or SECRET_REQUEST.search(text) or MALICIOUS_TOOL.search(text):
        return SafetyDecision("security", True, SAFE_INJECTION)
    # MEDICAL is checked first: "diagnose my chest pain" is a request for
    # clinical advice, and its refusal already points to emergency services.
    # EMERGENCY is for someone *describing* an urgent symptom without asking
    # for advice - "mujhe chest pain hai, appointment chahiye" - who would
    # otherwise be handed a routine booking form.
    if MEDICAL.search(text):
        return SafetyDecision("medical_safety", True, SAFE_MEDICAL)
    if EMERGENCY.search(text):
        return SafetyDecision("emergency", True, SAFE_EMERGENCY)
    return SafetyDecision("allowed", False, "")


def sanitize_retrieved_text(text: str) -> str:
    """Treat retrieved text as untrusted data, never as executable instructions."""
    if not text:
        return ""
    kept = []
    for line in str(text).splitlines():
        if PROMPT_INJECTION.search(line) or SECRET_REQUEST.search(line) or MALICIOUS_TOOL.search(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def sanitize_output(text: str, fallback: str = SAFE_UNSUPPORTED) -> str:
    """Fail closed if a downstream component leaks secrets or control instructions."""
    if not text or OUTPUT_SECRET.search(text) or OUTPUT_INSTRUCTION.search(text):
        return fallback
    return text.strip()