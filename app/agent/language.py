import re

URDU_RE = re.compile(r"[\u0600-\u06FF]")
ROMAN_MARKERS = set("mujhe hai hain he hoon chahiye batao btao kitna kitni kab kahan kya ka ki ke meri mera appointment lena book karna available fee paisay waqt subah shaam kal aj clinic mein mein aur nahi kis hoti hai".split())

# Informal spellings people actually type. Chat Roman Urdu is not standardised:
# the same word appears as mujhe / mujay / mujy, and hai / hay / hy. Every token
# here is unambiguously non-English - words such as "to", "he", "do" and "is"
# are deliberately excluded even though they are also Roman Urdu, because they
# would misclassify ordinary English sentences.
ROMAN_VARIANTS = set(
    "mujay mujy mujhy mujhay mjhe mere apna apni apne aap aapko aapki aapka "
    "hay hy hoon hun hon hein "
    "krna krwana karwana krwani karwani karana karwane krwna kro karo "
    "chahta chahti chata chahye chaiye "
    "dikhana dikhani dikhane dekhana milna milne "
    "nhi nahin nahe bta btana bataye batana "
    "jana jaana aana parchi token "
    "kitne kaise kaisay konsa kaunsa koi thoda zyada bohat bahut "
    "sahab bhai baji".split()
)
ROMAN_MARKERS |= ROMAN_VARIANTS
ENGLISH_MARKERS = set("the is are am to of for in on at do does did what which how can could would should you your we our i me my please tell give have has had this that and or with from about when where who available availability services service fees fee payment card cash book booking appointment appointments clinic timings hours doctor doctors system prompt previous instructions ignore confirm university telemedicine parking treatment symptoms prescription diagnosis safety disable reveal".split())

def detect_language(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "english"
    has_urdu = bool(URDU_RE.search(text))
    tokens = set(re.findall(r"[A-Za-z]+", text.lower()))
    if has_urdu:
        return "mixed" if tokens else "urdu"
    roman_hits = len(tokens & ROMAN_MARKERS)
    english_hits = len(tokens & ENGLISH_MARKERS)
    roman_specific = tokens & ({"mujhe","hai","hain","hoon","chahiye","batao","btao","kitna","kitni","kab","kahan","kya","meri","mera","ka","ki","ke","paisa","paisay","waqt","subah","shaam","kal","aj","aaj","kis","hoti","mein","nahi","aur","karo","karna","lena"} | ROMAN_VARIANTS)
    # Strong English code-switching + even one Roman-Urdu marker is mixed.
    if roman_specific and english_hits >= 3:
        return "mixed"
    # Predominantly Roman Urdu with a few shared English clinic words.
    if roman_specific:
        return "roman_urdu"
    return "english"