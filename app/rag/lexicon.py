"""Shared multilingual vocabulary for retrieval and grounding.

The retriever and the grounding layer both tokenise text, and they previously
kept two drifting copies of the same stop-word and synonym tables. This module
holds the additions they share so Roman Urdu and Urdu queries normalise the
same way on both sides.

Two rules govern what may go in here:

1. Only function words go in ``EXTRA_STOPWORDS``. Dropping a grammatical
   particle ("ke", "liye", "karna") sharpens the query; dropping a content
   word would hide a real gap and let the system answer a question the
   knowledge base does not cover.
2. ``EXTRA_SYNONYMS`` may only map words to concepts the knowledge base
   actually contains. It is a translation table, not a relevance booster.
"""

# --------------------------------------------------------------------------
# Roman Urdu / Urdu grammatical particles and question scaffolding.
# These carry no retrieval signal and otherwise dominate short queries.
# --------------------------------------------------------------------------

EXTRA_STOPWORDS = set(
    """
    ka ki kay kaa kii ko se par pe pr mein men me mai
    hai hay hain hein he ho hota hoti hote hon hoon
    tha thi thay gaya gayi gaye hua huwa hui huye
    تھا تھی تھے گیا گئی گئے
    kia kiya kya kyaa kaise kaisay kesay kesa kaisa
    kis kaun kon konsa kaunsa kitna kitni kitne
    karna karne karni karein karo karta karti kar
    bata batao btao bataye bataen batana batadein dein den de do
    chahiye chahye chaiye liye lye
    mujhe mujhy mujy meri mera mere
    aap apka apki aapka aapki
    koi kuch bhi bhee to tou
    ek aik
    ye yeh wo woh is us
    nahi nahin
    hi hee
    ہے ہیں ہوں ہو ہوتا ہوتی ہوتے سکتا سکتی سکتے
    کا کی کو کے سے پر میں
    کیا کیسے کون کونسا کتنا کتنی
    کرنا کرنے کریں کر
    بتائیں بتائے بتا دیں
    مجھے میرا میری
    اور یا ہی بھی تو کوئی کچھ
    نہیں
    یہ وہ اس
    """.split()
)


# --------------------------------------------------------------------------
# Translations and spelling variants.
# Every target token below occurs in data/production/knowledge/documents/.
# --------------------------------------------------------------------------

EXTRA_SYNONYMS = {
    # --- timings -------------------------------------------------------
    "timing": "timings",
    "time": "timings",
    "times": "timings",
    "opens": "timings",
    "opened": "timings",
    "closes": "timings",
    "waqt": "timings",
    "auqat": "timings",
    "auqaat": "timings",
    "khula": "open",
    "khuli": "open",
    "khulta": "open",
    "khulti": "open",
    "band": "closed",
    "وقت": "timings",
    "کھلتا": "open",
    "کھلتی": "open",
    # --- fees ----------------------------------------------------------
    "fee": "fees",
    "charges": "fees",
    "paisay": "fees",
    "paise": "fees",
    "kharcha": "fees",
    "qeemat": "fees",
    "قیمت": "fees",
    # --- doctors -------------------------------------------------------
    "dr": "doctors",
    "doktor": "doctors",
    "daktar": "doctors",
    "physician": "doctors",
    "ڈاکٹرز": "doctors",
    "معالج": "doctors",
    # --- specialties (the KB names the specialty, not the body part) ----
    "skin": "dermatology",
    "chamri": "dermatology",
    "جلد": "dermatology",
    "dermatologist": "dermatology",
    "heart": "cardiology",
    "dil": "cardiology",
    "دل": "cardiology",
    "cardiologist": "cardiology",
    "child": "pediatrics",
    "children": "pediatrics",
    "bachon": "pediatrics",
    "bachay": "pediatrics",
    "بچوں": "pediatrics",
    "pediatrician": "pediatrics",
    "pediatric": "pediatrics",
    # --- appointments --------------------------------------------------
    "appointments": "appointment",
    "apointment": "appointment",
    "apointments": "appointment",
    "اپائنٹمنٹ": "appointment",
    "ملاقات": "appointment",
    # --- cancellation / rescheduling ------------------------------------
    "cancelled": "cancellation",
    "cancellations": "cancellation",
    "منسوخ": "cancellation",
    "منسوخی": "cancellation",
    "reschedule": "rescheduling",
    "rescheduled": "rescheduling",
    "reschedules": "rescheduling",
    "dobara": "rescheduling",
    "دوبارہ": "rescheduling",
    "شیڈول": "rescheduling",
    "تبدیل": "rescheduling",
    # --- contact / human support ----------------------------------------
    "call": "contact",
    "baat": "contact",
    "rabta": "contact",
    "raabta": "contact",
    "numbers": "contact",
    "نمبر": "contact",
    "عملہ": "staff",
    "istaff": "staff",
    # --- languages -------------------------------------------------------
    "languages": "language",
    "multilingual": "language",
    "communication": "language",
    "zaban": "language",
    "zubaan": "language",
    "zabaan": "language",
    "زبان": "language",
    # --- payment ---------------------------------------------------------
    "payments": "payment",
    "pays": "payment",
    "paying": "payment",
    "adaigi": "payment",
    "naqd": "cash",
    # --- services ---------------------------------------------------------
    "sarvis": "services",
    "khidmat": "services",
    "خدمات": "services",
    "consultations": "consultation",
    # --- misc -------------------------------------------------------------
    "supported": "supports",
    "support": "supports",
    "available": "availability",
    "dastyab": "availability",
    "دستیاب": "availability",
    # "address" appears nowhere in the knowledge base; contact_information.md
    # says "Clinic contact: ... support@maplecrescent.example". Synonym lookup is
    # single-pass, so every address word must map straight to "contact" - mapping
    # "pata" to "address" would leave a token the corpus can never cover.
    "address": "contact",
    "emails": "contact",
    "pata": "contact",
    "پتہ": "contact",
}