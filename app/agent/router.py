import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Route:
    intent: str
    confidence: float

MEDICAL = re.compile(r"\b(diagnos|treatment|treat|medicine|medication|dose|dosage|prescription|symptom|symptoms|what disease|مرض|علاج|دوائی|دوا|خوراک|تشخیص)\b", re.I)
BOOKING = re.compile(r"\b(book|booking|appointment|appointments|apointment|mulaqat|mulaaqaat|mulaqaat|schedule|reserve|appoint|بک|اپائنٹمنٹ|وقت لے|ملاقات)\b", re.I)

# How people actually ask for an appointment in Pakistan. Patients rarely say
# "book an appointment" - they say they want a checkup, want to be seen by a
# doctor, or want to come in. Every alternative below is a high-signal phrase;
# bare verbs such as "karna" are deliberately excluded because they attach to
# any request ("fee check karna hai") and would swallow other intents.
VISIT = re.compile(
    r"\bcheck[\s\-]?up\b|\bcheckup\b|\bchekup\b"
    r"|\bdikhana\b|\bdikhani\b|\bdikhane\b|\bdikhaana\b|\bdekhana\b"
    r"|\bparchi\b|\bparchee\b"
    r"|\b(?:milna|milne|milni)\s+(?:hai|hay|he|chahta|chahti|chahiye)\b"
    r"|\b(?:aana|ana|anaa|aanaa)\s+(?:hai|hay|he|chahta|chahti|chahiye)\b"
    r"|\b(?:waqt|time|token|number)\s+(?:lena|leni|lene|chahiye|lagwana|lagwani)\b"
    r"|چیک\s*اپ|دکھانا|دکھانی|دکھانے|پرچی|ملنا\s*ہے|آنا\s*ہے",
    re.I,
)
AVAIL = re.compile(r"\b(available|availability|slot|free time|open slot|when can|خالی|دستیاب|وقت|slot)\b", re.I)
CANCEL = re.compile(r"\b(cancel|cancellation|لغو|منسوخ)\b", re.I)
RESCHEDULE = re.compile(
    r"\b(reschedule|rescheduling|rescheduled|change.*appointment|move.*appointment"
    r"|dobara\s*schedule|waqt\s*badal|time\s*badal)\b"
    r"|دوبارہ\s*وقت|دوبارہ\s*شیڈول|شیڈول\s*تبدیل|وقت\s*تبدیل|اپائنٹمنٹ\s*تبدیل|تبدیل\s*کرنا",
    re.I,
)

# Asking what the cancellation/rescheduling rules are is an information question
# answered from the knowledge base. Asking to actually cancel or reschedule is a
# human handoff. Kept deliberately narrow: "can you cancel my appointment?" is a
# request, not a policy question, and must still reach a human.
POLICY_QUESTION = re.compile(
    r"\b(policy|policies|notice\s*period|how\s*(?:much|long|many)\s*(?:notice|before|in\s*advance)"
    r"|kitna\s*pehle|kitni\s*pehle|kitne\s*din\s*pehle|kitne\s*ghante\s*pehle)\b"
    r"|پالیسی|کتنا\s*پہلے|کتنی\s*دیر\s*پہلے|کتنے\s*گھنٹے\s*پہلے",
    re.I,
)
DOCTOR = re.compile(r"\b(doctor|doctors|specialist|physician|cardiologist|dermatologist|pediatrician|ڈاکٹر|معالج|ماہر)\b", re.I)
SERVICE = re.compile(r"\b(service|services|fee|fees|cost|price|charges|consultation|خدمت|سروس|فیس|قیمت|مشاورت)\b", re.I)
INFO = re.compile(r"\b(hours?|timings?|timing|auqat|auqaat|zabaan|zaban|open|close|address|location|phone|email|payment|cash|card|policy|policies|where|when|how|کب|کہاں|پتہ|فون|ای میل|اوقات|کھلا|کھلی|بند|اتوار|ہفتہ|فیس|ادائیگی|پالیسی)\b", re.I)


UNSUPPORTED_ATTR = re.compile(r'\b(university|education|degree|qualification|experience|private|personal|direct contact|home address|insurance|telemedicine|parking|wifi|wi-fi|pharmacy|laboratory|lab|waiting time|wait time|پارکنگ|ٹیلی.?میڈیسن|انشورنس|فارمیسی|لیبارٹری)\b', re.I)

def classify(text: str) -> Route:
    if MEDICAL.search(text): return Route("medical_safety", .99)
    if (RESCHEDULE.search(text) or CANCEL.search(text)) and POLICY_QUESTION.search(text):
        return Route("information", .95)
    if RESCHEDULE.search(text): return Route("rescheduling", .98)
    if CANCEL.search(text): return Route("cancellation", .98)
    if BOOKING.search(text) or VISIT.search(text): return Route("booking", .97)
    if UNSUPPORTED_ATTR.search(text): return Route("information", .90)
    if DOCTOR.search(text) and SERVICE.search(text) and re.search(r"\b(fee|fees|cost|price|charges|فیس|قیمت)\b", text, re.I): return Route("service_lookup", .94)
    if DOCTOR.search(text) and not SERVICE.search(text): return Route("doctor_lookup", .93)
    if AVAIL.search(text):
        # 'parking available', 'wifi available', etc. are clinic-information questions,
        # not live appointment availability.
        if re.search(r'\b(parking|wifi|wi-fi|pharmacy|insurance|telemedicine|lab|laboratory)\b', text, re.I):
            return Route("information", .90)
        if re.search(r'(DR-\d+|SERVICE-\d+|\bappointment\b|\bslot\b|\bbook\b|\btime\b|\bوقت\b|\bدستیاب\b)', text, re.I):
            return Route("availability", .94)
        return Route("information", .80)
    if SERVICE.search(text) and not DOCTOR.search(text): return Route("service_lookup", .93)
    if DOCTOR.search(text) or SERVICE.search(text): return Route("directory_lookup", .88)
    if INFO.search(text): return Route("information", .82)
    return Route("unknown", .45)