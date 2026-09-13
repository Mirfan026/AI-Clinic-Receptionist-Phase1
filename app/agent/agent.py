from dataclasses import dataclass, field
import re
from typing import Any, Callable
import uuid

from datetime import date as _date, datetime as _datetime

from .language import detect_language
from .dates import parse_clock_time, resolve_relative_date
from .parsing import parse_date, parse_datetime, parse_patient_id, looks_like_bare_id_attempt
from .policies import SYSTEM_PROMPT, UNAVAILABLE, MEDICAL_HANDOFF, HUMAN_HANDOFF
from .safety import inspect_user_message, sanitize_output, SAFE_UNSUPPORTED
from .router import classify

@dataclass
class AgentResponse:
    text: str
    intent: str
    language: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

class ClinicReceptionistAgent:
    """Policy-first orchestrator. LLMs may synthesize grounded prose, but never execute SQL."""
    def __init__(self, clinic_id: str, rag: Any, tools: dict[str, Callable] | None = None, response_generator: Callable | None = None):
        self.clinic_id = clinic_id
        self.rag = rag
        from .tools import TOOL_REGISTRY
        candidate_tools = tools or TOOL_REGISTRY
        self.tools = {name: candidate_tools[name] for name in TOOL_REGISTRY if name in candidate_tools}
        self.allowed_tools = frozenset(TOOL_REGISTRY)
        self.response_generator = response_generator
        self.sessions: dict[str, Any] = {}

    def new_session(self, session_id: str | None = None):
        from .state import ConversationState
        sid = session_id or str(uuid.uuid4())
        state = ConversationState(sid, self.clinic_id)
        self.sessions[sid] = state
        return state

    def handle(self, message: str, session_id: str = "default") -> AgentResponse:
        state = self.sessions.get(session_id) or self.new_session(session_id)
        language = detect_language(message)
        state.language = language
        safety = inspect_user_message(message)
        state.add_turn("user", message)
        if safety.blocked:
            state.last_intent = safety.category
            text = self._localized_safety(safety.category, language)
            state.add_turn("assistant", text)
            return AgentResponse(text, safety.category, language, [], [], state.snapshot())
        route = classify(message)
        # Context carry-over: a short follow-up such as "schedule_id=101",
        # "Cardiology" or "kal" continues an unfinished booking rather than
        # becoming an unrelated directory or knowledge-base query.
        if self._continues_booking(message, route, state):
            route = type(route)("booking", .90)
        state.last_intent = route.intent
        calls = []
        rag_sources = []

        if route.intent == "medical_safety":
            text = MEDICAL_HANDOFF
        elif route.intent in {"cancellation", "rescheduling"}:
            text = HUMAN_HANDOFF
        elif route.intent == "doctor_lookup":
            result = self._tool("get_doctors", {"clinic_id": self.clinic_id}, calls)
            text = self._doctor_text(result, language)
        elif route.intent == "service_lookup":
            result = self._tool("get_services", {"clinic_id": self.clinic_id}, calls)
            text = self._service_text(result, language)
        elif route.intent == "directory_lookup":
            doctors = self._tool("get_doctors", {"clinic_id": self.clinic_id}, calls)
            services = self._tool("get_services", {"clinic_id": self.clinic_id}, calls)
            text = self._directory_text(doctors, services, language)
        elif route.intent == "availability":
            text = self._availability(message, state, calls, language)
        elif route.intent == "booking":
            text = self._booking(message, state, calls, language)
        elif route.intent == "information":
            text, rag_sources = self._rag_answer(message, calls, language)
        else:
            # Unknown general question: RAG first; if no grounded result, explicit unavailable.
            text, rag_sources = self._rag_answer(message, calls, language)

        state.add_turn("assistant", text)
        return AgentResponse(text, route.intent, language, calls, self._sources(calls) + rag_sources, state.snapshot())

    def _tool(self, name, payload, calls):
        # Hard boundary: only explicitly registered tools may execute, and every
        # operational payload is forced into this agent's clinic tenant.
        if name not in self.allowed_tools or name not in self.tools:
            result = {"success": False, "error": {"code": "TOOL_NOT_ALLOWED", "message": "The requested operation is not available.", "retryable": False}}
            calls.append({"tool": name, "input": {}, "result": result})
            return result
        safe_payload = dict(payload)
        requested_clinic = safe_payload.get("clinic_id", self.clinic_id)
        if requested_clinic != self.clinic_id:
            result = {"success": False, "error": {"code": "CLINIC_SCOPE_VIOLATION", "message": "The requested operation is not available.", "retryable": False}}
            calls.append({"tool": name, "input": safe_payload, "result": result})
            return result
        safe_payload["clinic_id"] = self.clinic_id
        try:
            result = self.tools[name](safe_payload)
        except Exception:
            result = {"success": False, "error": {"code": "TOOL_ERROR", "message": "The requested operation could not be completed.", "retryable": True}}
        calls.append({"tool": name, "input": safe_payload, "result": result})
        return result

    @staticmethod
    def _date_context(message, language):
        """Turn a relative expression into a concrete weekday before retrieval.

        The knowledge base stores clinic hours per weekday, so "kal" and
        "tomorrow" retrieve nothing on their own. Date arithmetic is done in
        Python; only the weekday is handed to RAG, which keeps the knowledge
        base the sole source of the hours themselves.
        """
        resolved = resolve_relative_date(message)
        if not resolved:
            return message, ""
        query = re.sub(
            re.escape(resolved.expression),
            resolved.weekday,
            message,
            count=1,
            flags=re.I,
        )
        pretty = resolved.date.strftime("%d %B %Y")
        note = {
            "urdu": f"{resolved.expression} {resolved.weekday} ہے ({pretty})۔",
            "roman_urdu": f"{resolved.expression.capitalize()} {resolved.weekday} hai ({pretty}).",
            "mixed": f"{resolved.expression.capitalize()} is {resolved.weekday} ({pretty}).",
        }.get(language, f"{resolved.expression.capitalize()} is {resolved.weekday} ({pretty}).")
        return query, note

    def _rag_answer(self, message, calls, language="english"):
        query, date_note = self._date_context(message, language)
        try:
            try:
                result = self.rag.answer(query, self.clinic_id, language=language)
            except TypeError:
                # Backward-compatible with lightweight test/dummy RAG adapters.
                result = self.rag.answer(query, self.clinic_id)
        except Exception:
            return UNAVAILABLE, []
        if not result.get("retrieval") or not result.get("answer") or result["answer"] == UNAVAILABLE:
            return UNAVAILABLE, []
        safe_answer=sanitize_output(result["answer"], UNAVAILABLE)
        # Abstention text stays byte-for-byte exact; a date note is only added to
        # an answer that is actually grounded in the knowledge base.
        if date_note and safe_answer != UNAVAILABLE:
            safe_answer = f"{date_note} {safe_answer}"
        sources=[]
        retrieval=result.get("retrieval")
        for item in getattr(retrieval, "results", []) or []:
            sources.append({"chunk_id":item.chunk_id,"source":item.metadata.get("source"),"document_type":item.metadata.get("document_type"),"language":item.metadata.get("language"),"score":item.score})
        return safe_answer, sources

    @staticmethod
    def _sources(calls):
        out=[]
        for c in calls:
            result=c.get("result", {})
            data = result.get("data") if isinstance(result, dict) else None
            if isinstance(data, dict) and data.get("sources"):
                out.extend(data["sources"])
        return out

    @staticmethod
    def _doctor_text(result, language):
        if not result.get("success"): return {"urdu":"ڈاکٹروں کی فہرست اس وقت دستیاب نہیں۔ براہِ کرم دوبارہ کوشش کریں۔","roman_urdu":"Doctors ki list is waqt available nahi. Meherbani karke dobara koshish karein.","mixed":"Doctor directory abhi available nahi hai. Please dobara try karein."}.get(language, "I couldn't retrieve the doctor directory right now. Please try again.")
        docs=result["data"]["doctors"]
        items="; ".join(f"{d['name']} — {d['specialty']}" for d in docs)
        return {"urdu":"دستیاب ڈاکٹر: "+items+".","roman_urdu":"Available doctors: "+items+".","mixed":"Available doctors ki list yeh hai: "+items+"."}.get(language, "Available doctors: " + items + ".")

    @staticmethod
    def _service_text(result, language):
        if not result.get("success"): return {"urdu":"سروسز کی فہرست اس وقت دستیاب نہیں۔ براہِ کرم دوبارہ کوشش کریں۔","roman_urdu":"Services ki list is waqt available nahi. Meherbani karke dobara koshish karein.","mixed":"Service directory abhi available nahi hai. Please dobara try karein."}.get(language, "I couldn't retrieve the service directory right now. Please try again.")
        ss=result["data"]["services"]
        items="; ".join(f"{s['name']} — PKR {s['fee_pkr']:g}" for s in ss)
        return {"urdu":"دستیاب سروسز: "+items+".","roman_urdu":"Available services: "+items+".","mixed":"Available services aur fees yeh hain: "+items+"."}.get(language, "Available services: " + items + ".")

    @staticmethod
    def _directory_text(doctors, services, language):
        if not doctors.get("success") or not services.get("success"):
            return "I couldn't retrieve the clinic directory right now. Please try again."
        return "I can help with the doctor or service list. Available doctors: " + "; ".join(d["name"] for d in doctors["data"]["doctors"]) + ". Available services include: " + "; ".join(s["name"] for s in services["data"]["services"]) + "."

    def _availability(self, message, state, calls, language):
        dt=self._absorb_datetime(message, state)
        doctor_id=self._extract_id(message, "DR-") or state.slots.get("doctor_id")
        service_id=self._extract_id(message, "SERVICE-") or state.slots.get("service_id")
        doctor_id, service_id = self._resolve_named_entities(message, doctor_id, service_id, calls)
        state.update(doctor_id=doctor_id, service_id=service_id)
        missing=[]
        if not doctor_id: missing.append("doctor")
        if not service_id: missing.append("service")
        if not dt and not state.slots.get("start_at"):
            missing.append("time" if state.slots.get("booking_date") else "date and time")
        if missing:
            return self._missing_fields_text(missing, state, language)
        payload={"clinic_id":self.clinic_id,"doctor_id":doctor_id,"service_id":service_id,"start_at":state.slots["start_at"]}
        result=self._tool("check_availability",payload,calls)
        if not result.get("success"):
            return self._tool_error_text(result)
        slots=result["data"]["slots"]
        if not slots: return "No available slot was returned for that request. I won't guess at availability."
        requested=state.slots["start_at"]
        exact=next((s for s in slots if s["start_at"] == requested), None)
        if not exact:
            items="; ".join(f"{s['schedule_id']}: {s['start_at']}" for s in slots[:10])
            prefix={"urdu":"درخواست کردہ وقت دستیاب نہیں ہے۔ متبادل اوقات: ","roman_urdu":"Requested time available nahi hai. Alternative slots: ","mixed":"Requested time available nahi hai. Alternative slots: "}.get(language, "The requested time is not available. Alternative slots: ")
            return prefix + items + "."
        text=exact["start_at"]
        return {"urdu":"یہ وقت دستیاب ہے: "+text+".","roman_urdu":"Yeh time available hai: "+text+".","mixed":"This time available hai: "+text+"."}.get(language, "This requested time is available: " + text + ".")

    def _booking(self, message, state, calls, language):
        state.update(booking_active=True)
        self._absorb_datetime(message, state)
        # A name in *this* message outranks whatever was stored earlier, so
        # "actually, Dr Sara" switches the doctor instead of being ignored.
        named_doctor, named_service = self._resolve_named_entities(message, None, None, calls)
        doctor_id=self._extract_id(message,"DR-") or named_doctor or state.slots.get("doctor_id")
        service_id=self._extract_id(message,"SERVICE-") or named_service or state.slots.get("service_id")
        if (doctor_id != state.slots.get("doctor_id") or service_id != state.slots.get("service_id")):
            # Previously offered slots belong to the old doctor/service.
            for stale in ("schedule_id", "awaiting_slot_choice", "offered_slots"):
                state.slots.pop(stale, None)
        patient_id=parse_patient_id(message) or state.slots.get("patient_id")
        schedule_id=(self._extract_int_after(message,"schedule_id")
                     or self._match_offered_slot(message, state)
                     or state.slots.get("schedule_id"))
        state.update(doctor_id=doctor_id,service_id=service_id,patient_id=patient_id,schedule_id=schedule_id)
        missing=[]
        for k,label in [(doctor_id,"doctor"),(service_id,"service"),(patient_id,"patient ID")]:
            if not k: missing.append(label)
        if not state.slots.get("start_at"):
            missing.append("time" if state.slots.get("booking_date") else "date and time")
        if missing:
            # A bare number is never silently accepted as a patient ID: an
            # unverified ID must not reach the booking transaction.
            hint = ""
            if not patient_id and looks_like_bare_id_attempt(message):
                hint = self._bare_id_hint(language)
            return hint + self._missing_fields_text(missing, state, language)
        avail_payload={"clinic_id":self.clinic_id,"doctor_id":doctor_id,"service_id":service_id,"start_at":state.slots["start_at"],"limit":10}
        availability=self._tool("check_availability",avail_payload,calls)
        if not availability.get("success"): return self._tool_error_text(availability)
        slots=availability["data"]["slots"]
        chosen=None
        if schedule_id:
            chosen=next((s for s in slots if s["schedule_id"]==schedule_id),None)
        if not chosen:
            if not slots: return "No available slot was returned for that request. I won't guess at availability."
            # Every alternative below comes from check_availability; none is inferred.
            requested=state.slots.get("start_at")
            lead=""
            if requested and not any(s["start_at"]==requested for s in slots):
                pretty=_datetime.fromisoformat(requested).strftime("%A %d %B %Y at %H:%M")
                lead={
                    "urdu": f"{pretty} دستیاب نہیں ہے۔ ",
                    "roman_urdu": f"{pretty} available nahi hai. ",
                    "mixed": f"{pretty} available nahi hai. ",
                }.get(language, f"{pretty} is not available. ")
            # Remember what was offered so the next turn can accept a bare
            # number ("121") or an ordinal ("2nd") instead of demanding the
            # exact "schedule_id=" syntax nobody types.
            offered=[s["schedule_id"] for s in slots[:10]]
            state.update(offered_slots=offered, awaiting_slot_choice=True)
            # If an exact schedule wasn't supplied, ask user to select one instead of silently booking.
            return lead + "I found these available slots: " + "; ".join(f"{s['schedule_id']}: {s['start_at']}" for s in slots[:10]) + ". Please choose a slot ID."
        state.update(schedule_id=chosen["schedule_id"])
        appointment_id="APT-" + uuid.uuid4().hex[:10].upper()
        payload={"appointment_id":appointment_id,"clinic_id":self.clinic_id,"doctor_id":doctor_id,"service_id":service_id,"patient_id":patient_id,"schedule_id":chosen["schedule_id"]}
        booked=self._tool("book_appointment",payload,calls)
        if not booked.get("success"): return self._tool_error_text(booked)
        aid=booked["data"]["appointment_id"]
        # The booking is complete: drop the collected details so a stale doctor,
        # patient or slot can never leak into the next request.
        for slot in ("booking_active","doctor_id","service_id","patient_id","start_at",
                     "booking_date","schedule_id","offered_slots","awaiting_slot_choice"):
            state.slots.pop(slot, None)
        return {"urdu":f"آپ کی اپائنٹمنٹ بک ہو گئی ہے۔ Appointment ID: {aid}.","roman_urdu":f"Aap ki appointment book ho gayi hai. Appointment ID: {aid}.","mixed":f"Your appointment book ho gayi hai. Appointment ID: {aid}."}.get(language, f"Your appointment is booked. Appointment ID: {aid}.")

    def _resolve_named_entities(self, message, doctor_id, service_id, calls):
        """Resolve human-readable doctor/service names through allowlisted directory tools.
        No medical inference is performed: a doctor name never implies a service.
        """
        if not doctor_id and re.search(r"\b(dr\.?\s+[A-Za-z][A-Za-z .'-]+)", message, re.I):
            result = self._tool("get_doctors", {"clinic_id": self.clinic_id}, calls)
            if result.get("success"):
                norm = re.sub(r"[^a-z0-9 ]", "", message.lower())
                matches=[]
                for d in result["data"]["doctors"]:
                    name_norm=re.sub(r"[^a-z0-9 ]", "", d["name"].lower()).replace("dr ", "").strip()
                    name_tokens=set(name_norm.split())
                    msg_tokens=set(norm.split())
                    # Match a distinctive first/last name token; do not infer specialty.
                    if len(name_tokens & msg_tokens) >= 1: matches.append(d["doctor_id"])
                if len(matches)==1: doctor_id=matches[0]
        if not service_id and re.search(r"\b(?:consultation|follow-up|follow up|cardiology|dermatology|pediatric|family medicine|general physician|preventive|screening|chronic care|سروس|مشاورت|فیس)\b", message, re.I):
            result = self._tool("get_services", {"clinic_id": self.clinic_id}, calls)
            if result.get("success"):
                norm = re.sub(r"[^a-z0-9 ]", "", message.lower())
                matches=[]
                for svc in result["data"]["services"]:
                    name_norm=re.sub(r"[^a-z0-9 ]", "", svc["name"].lower())
                    core=name_norm.replace("consultation", "").strip()
                    if len(core) >= 8 and core in norm: matches.append(svc["service_id"])
                if len(matches)==1: service_id=matches[0]
        return doctor_id, service_id

    @staticmethod
    def _localized_safety(category, language):
        if category == "emergency":
            # Deliberately names no condition, no severity and no specialty:
            # directing a symptom to a department would be clinical triage.
            if language == "urdu": return "آپ جو بتا رہے ہیں اس پر فوری توجہ کی ضرورت ہو سکتی ہے۔ براہِ کرم ابھی مقامی ایمرجنسی سروسز سے رابطہ کریں یا قریبی ایمرجنسی سینٹر جائیں — اپائنٹمنٹ کا انتظار نہ کریں۔ میں علامات کا جائزہ نہیں لے سکتا؛ چیک اپ کے بعد کلینک کی معلومات اور اپائنٹمنٹ میں مدد کر سکتا ہوں۔"
            if language == "roman_urdu": return "Aap jo bata rahe hain us par foran tawajjo ki zarurat ho sakti hai. Meherbani karke abhi local emergency services se rabta karein ya qareebi emergency facility jayein — appointment ka intezar na karein. Main symptoms ka jaiza nahi le sakta; baad mein clinic information aur appointment mein madad kar sakta hoon."
            if language == "mixed": return "What you're describing may need urgent attention. Please abhi local emergency services se rabta karein ya nearest emergency facility jayein — appointment ka wait na karein. Main symptoms assess nahi kar sakta."
            return ("What you're describing may need urgent attention. Please contact local emergency "
                    "services or go to the nearest emergency facility now — don't wait for an appointment. "
                    "I'm an administrative assistant and can't assess symptoms. Once you've been seen, "
                    "I'm here to help with clinic information and appointments.")
        if category == "medical_safety":
            if language == "urdu": return "میں تشخیص، علاج، نسخہ یا دوا کی خوراک کے بارے میں طبی مشورہ نہیں دے سکتا۔ براہِ کرم کسی مستند ڈاکٹر سے رابطہ کریں۔ ہنگامی صورت میں مقامی ایمرجنسی سروسز سے رابطہ کریں۔"
            if language == "roman_urdu": return "Main diagnosis, ilaj, prescription ya dawa ki dosage ka mashwara nahi de sakta. Meherbani karke qualified doctor se rabta karein. Emergency ho to local emergency services se rabta karein."
            if language == "mixed": return "I can help with clinic information and appointments, lekin diagnosis, treatment, prescription ya dosage advice nahi de sakta. Please qualified clinician se contact karein."
            return "I can help with clinic information and appointments, but I can't diagnose conditions or provide treatment, prescription, or dosage advice. Please contact a qualified clinician. If this is an emergency, contact local emergency services."
        if language == "urdu": return "میں صرف کلینک کی معلومات اور اپائنٹمنٹس میں مدد کر سکتا ہوں۔ میں اندرونی ہدایات یا خفیہ معلومات ظاہر نہیں کر سکتا۔"
        if language == "roman_urdu": return "Main sirf clinic information aur appointments mein madad kar sakta hoon. Main internal instructions ya secret information share nahi kar sakta."
        if language == "mixed": return "I can help with clinic information and appointments, lekin internal instructions ya secret information share nahi kar sakta."
        return "I can help with clinic information and appointments, but I can't follow instructions that override safety rules or expose internal information."

    # A reply that supplies a booking field rather than asking something new.
    _BOOKING_FILLABLE = re.compile(
        r"DR-\d+|SERVICE-\d+|(?:PATIENT|P)-\d+|schedule_id"
        r"|\bdr\.?\s+[A-Za-z]"
        r"|\b(?:consultation|cardiology|dermatology|pediatric|pediatrics|family medicine"
        r"|general physician|preventive|screening|chronic care|follow-?up)\b"
        r"|\b(?:today|tomorrow|yesterday|kal|aaj|parson|aglay|agle"
        r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
        r"|\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(?:am|pm)\b|\b(?:baje|bajay|subah|shaam|dopahar)\b"
        r"|20\d{2}-\d{2}-\d{2}|\b\d{3,12}\b"
        r"|کل|آج|پرسوں|صبح|شام|دوپہر",
        re.I,
    )

    # Markers of a genuinely new question, which must escape the booking flow.
    _FRESH_QUESTION = re.compile(
        r"\?|؟|\b(?:what|which|how|where|why|who|list|tell|show"
        r"|timings?|hours?|fees?|price|cost|payment|address|phone|email|policy|parking)\b"
        r"|\b(?:kya|kia|kaunsi|konsi|kaunsa|konsa|kitni|kitna|batao|btao|bataen)\b"
        r"|کیا|کون|کہاں|کتنی|کتنا|بتائیں",
        re.I,
    )

    _REQUIRED_BOOKING_SLOTS = ("doctor_id", "service_id", "patient_id", "start_at")

    @classmethod
    def _continues_booking(cls, message, route, state):
        """Decide whether this turn is still part of an unfinished booking.

        Tracked on an explicit `booking_active` flag rather than `last_intent`,
        so answering a clinic question mid-booking ("what are your Saturday
        timings?") does not silently discard the details already collected.

        The flag alone is not enough. Once every field was filled, an earlier
        version continued the booking for *any* unrecognised message, so a
        finished booking swallowed the rest of the conversation and re-ran
        availability forever. Continuation now requires something still to do -
        a missing field, or an offered slot awaiting choice - and any question
        escapes immediately.
        """
        if route.intent == "booking" or not state.slots.get("booking_active"):
            return False
        # Safety, medical and human-handoff routes always take precedence.
        if route.intent in {"medical_safety", "emergency", "security", "cancellation", "rescheduling"}:
            return False
        # A question is a question, even mid-booking. Collected fields stay in
        # state, so the booking resumes on the next slot-filling reply.
        if cls._FRESH_QUESTION.search(message):
            return False

        incomplete = any(
            not state.slots.get(slot) for slot in cls._REQUIRED_BOOKING_SLOTS
        )
        awaiting = bool(state.slots.get("awaiting_slot_choice"))
        if not incomplete and not awaiting:
            return False

        fillable = bool(cls._BOOKING_FILLABLE.search(message))
        if route.intent == "unknown":
            return fillable or awaiting
        return fillable

    @staticmethod
    def _absorb_datetime(message, state):
        """Accumulate date and time across turns without ever inventing either.

        "Tomorrow" on one turn and "2:30 pm" on the next must combine into a
        single instant. A date alone is remembered as `booking_date`; it only
        becomes a bookable `start_at` once a real clock time arrives.
        """
        dt = parse_datetime(message)
        if dt:
            state.update(start_at=dt.isoformat(), booking_date=dt.date().isoformat())
            return dt

        day = parse_date(message)
        if day:
            state.update(booking_date=day.isoformat())
            return None

        # A time supplied on its own completes a date captured earlier.
        pending = state.slots.get("booking_date")
        if pending and not state.slots.get("start_at"):
            clock = parse_clock_time(message)
            if clock:
                base = _date.fromisoformat(pending)
                dt = _datetime(base.year, base.month, base.day, clock[0], clock[1])
                state.update(start_at=dt.isoformat())
                return dt
        return None

    # Field names shown back to the user, per language.
    _FIELD_LABELS = {
        "urdu": {
            "doctor": "ڈاکٹر",
            "service": "سروس",
            "patient ID": "پیشنٹ آئی ڈی",
            "date and time": "تاریخ اور وقت",
            "time": "وقت",
        },
        "roman_urdu": {
            "doctor": "doctor",
            "service": "service",
            "patient ID": "patient ID",
            "date and time": "date aur time",
            "time": "time",
        },
    }
    _FIELD_LABELS["mixed"] = _FIELD_LABELS["roman_urdu"]

    @classmethod
    def _missing_fields_text(cls, missing, state, language):
        labels = cls._FIELD_LABELS.get(language, {})
        listed = ", ".join(labels.get(m, m) for m in missing)
        known = ""
        day = state.slots.get("booking_date")
        if day and "time" in missing:
            pretty = _date.fromisoformat(day).strftime("%A %d %B %Y")
            known = {
                "urdu": f"میرے پاس {pretty} کی تاریخ محفوظ ہے۔ ",
                "roman_urdu": f"Mere paas {pretty} ki date save hai. ",
                "mixed": f"I have {pretty} saved. ",
            }.get(language, f"I have {pretty} noted. ")
        example = {
            "urdu": "Dr. Bilal Hassan، Cardiology Consultation، P-001، کل 2:30 PM",
            "roman_urdu": "Dr. Bilal Hassan, Cardiology Consultation, P-001, kal 2:30 PM",
            "mixed": "Dr. Bilal Hassan, Cardiology Consultation, P-001, kal 2:30 PM",
        }.get(language, "Dr. Bilal Hassan, Cardiology Consultation, P-001, tomorrow at 2:30 PM")
        return {
            "urdu": f"{known}براہِ کرم {listed} فراہم کریں۔ مثال: {example}۔",
            "roman_urdu": f"{known}Meherbani karke {listed} bata dein. Misaal: {example}.",
            "mixed": f"{known}Please {listed} provide karein. Example: {example}.",
        }.get(language, f"{known}Before I can continue, please provide the {listed}. For example: {example}.")

    @staticmethod
    def _bare_id_hint(language):
        return {
            "urdu": "یہ نمبر کلینک کی پیشنٹ آئی ڈی کے فارمیٹ میں نہیں ہے (مثلاً P-001)۔ ",
            "roman_urdu": "Yeh number clinic ki patient ID format (jaise P-001) mein nahi hai. ",
            "mixed": "That number isn't in the clinic's patient ID format (jaise P-001). ",
        }.get(language, "That number isn't a clinic patient ID — they look like P-001. ")

    @staticmethod
    def _clarification(text, language):
        if language == "urdu":
            return "براہِ کرم مطلوبہ معلومات فراہم کریں تاکہ میں مدد کر سکوں۔"
        if language == "roman_urdu":
            return "Meherbani karke zaroori maloomat dein taa-ke main madad kar sakoon."
        if language == "mixed":
            return "Please zaroori information provide karein taa-ke main appointment mein help kar sakoon."
        return text

    @staticmethod
    def _match_offered_slot(message, state):
        """Select from the slots just offered, by number or ordinal.

        Identifiers are stripped first: "P-001" must never be read as slot 1.
        Only ids that were actually offered can be chosen, so a stray number
        cannot book an arbitrary slot.
        """
        offered = state.slots.get("offered_slots") or []
        if not offered:
            return None
        cleaned = re.sub(r"\b(?:PATIENT|P|DR|SERVICE)-\d+", " ", message or "", flags=re.I)

        ordinal = re.search(r"\b(\d{1,2})\s*(?:st|nd|rd|th)\b", cleaned, re.I)
        if ordinal:
            index = int(ordinal.group(1)) - 1
            if 0 <= index < len(offered):
                return offered[index]

        for token in re.findall(r"\b\d+\b", cleaned):
            if int(token) in offered:
                return int(token)
        return None

    @staticmethod
    def _extract_id(text,prefix):
        m=re.search(re.escape(prefix)+r"\d+",text,re.I)
        return m.group(0).upper() if m else None

    @staticmethod
    def _extract_int_after(text,key):
        m=re.search(re.escape(key)+r"\s*[:=]?\s*(\d+)",text,re.I)
        return int(m.group(1)) if m else None

    @staticmethod
    def _tool_error_text(result):
        err=result.get("error",{})
        code=err.get("code","TOOL_ERROR")
        if code in {"DOCTOR_SERVICE_MISMATCH","SERVICE_NOT_FOUND","DOCTOR_NOT_FOUND"}:
            return "That doctor/service combination is not available in this clinic. Please choose a valid doctor and service."
        if code in {"SLOT_UNAVAILABLE","BOOKING_CONFLICT"}:
            return "That slot is no longer available. Please choose another slot."
        if code == "PATIENT_NOT_FOUND":
            # The database is the authority on who is registered; the agent never
            # assumes an ID is valid just because it is well formed.
            return "That patient ID isn't registered at this clinic. Please check it and try again, or contact clinic staff to register."
        return "I couldn't complete that appointment operation. Please try again or contact clinic staff."