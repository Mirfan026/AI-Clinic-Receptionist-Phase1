from app.agent.agent import ClinicReceptionistAgent
from app.agent.policies import UNAVAILABLE

class FakeRAG:
    def __init__(self, answer="Maple Crescent Family Clinic is open Monday to Friday from 9 AM to 7 PM."):
        self.answer_text=answer
    def answer(self, query, clinic_id):
        return {"answer": self.answer_text, "retrieval":[{"score":.9,"metadata":{"source":"clinic_timings"}}]}

class FakeRAGEmpty(FakeRAG):
    def answer(self, query, clinic_id):
        return {"answer":UNAVAILABLE,"retrieval":[]}

class Tools:
    def __init__(self): self.calls=[]
    def doctors(self,p): self.calls.append(("get_doctors",p)); return {"success":True,"data":{"doctors":[{"name":"Dr. Amina Rahman","specialty":"General Practice"}]}}
    def services(self,p): self.calls.append(("get_services",p)); return {"success":True,"data":{"services":[{"name":"General Physician Consultation","fee_pkr":2000}]}}
    def availability(self,p):
        self.calls.append(("check_availability",p)); return {"success":True,"data":{"slots":[{"schedule_id":101,"start_at":"2026-09-16T10:00:00","end_at":"2026-09-16T10:30:00"}]}}
    def booking(self,p): self.calls.append(("book_appointment",p)); return {"success":True,"data":{"appointment_id":p["appointment_id"]}}


def make_agent(t):
    return ClinicReceptionistAgent("CLINIC-001", FakeRAG(), {
        "get_doctors":t.doctors,"get_services":t.services,"check_availability":t.availability,"book_appointment":t.booking})

def test_english_information_routes_rag():
    a=ClinicReceptionistAgent("CLINIC-001", FakeRAG())
    r=a.handle("What are the clinic opening hours?", "s1")
    assert r.intent=="information" and "9 AM" in r.text

def test_urdu_language_detected():
    a=ClinicReceptionistAgent("CLINIC-001", FakeRAG())
    r=a.handle("کل کلینک کے اوقات کیا ہیں؟", "s2")
    assert r.language=="urdu"

def test_roman_urdu_language_detected():
    a=ClinicReceptionistAgent("CLINIC-001", FakeRAG())
    r=a.handle("clinic ke timings kya hain", "s3")
    assert r.language in {"roman_urdu","mixed"}

def test_mixed_language_detected():
    a=ClinicReceptionistAgent("CLINIC-001", FakeRAG())
    r=a.handle("Clinic ke timings کیا ہیں?", "s4")
    assert r.language=="mixed"

def test_doctor_lookup_uses_tool():
    t=Tools(); r=make_agent(t).handle("Which doctors are available?", "s5")
    assert r.intent=="doctor_lookup" and t.calls[0][0]=="get_doctors"

def test_availability_never_invented_when_missing_fields():
    t=Tools(); r=make_agent(t).handle("Is there an available slot?", "s6")
    assert "doctor" in r.text and not t.calls

def test_booking_checks_availability_before_booking():
    t=Tools(); a=make_agent(t)
    r=a.handle("Book DR-001 SERVICE-001 PATIENT-001 on 2026-09-16 at 10:00", "s7")
    assert "Please choose a slot ID" in r.text
    assert [x[0] for x in t.calls]==["check_availability"]

def test_booking_after_slot_selection():
    t=Tools(); a=make_agent(t)
    a.handle("Book DR-001 SERVICE-001 PATIENT-001 on 2026-09-16 at 10:00", "s8")
    r=a.handle("schedule_id=101", "s8")
    assert r.intent=="booking" and "booked" in r.text
    assert [x[0] for x in t.calls]==["check_availability","check_availability","book_appointment"]

def test_unsupported_question_abstains():
    a=ClinicReceptionistAgent("CLINIC-001", FakeRAGEmpty())
    r=a.handle("Does the clinic have free parking?", "s9")
    assert r.text==UNAVAILABLE

def test_medical_request_handoff():
    a=ClinicReceptionistAgent("CLINIC-001", FakeRAG())
    r=a.handle("What medicine should I take for my fever?", "s10")
    assert r.intent=="medical_safety" and "can't diagnose" in r.text

def test_tool_failure_is_not_success():
    t=Tools(); t.availability=lambda p: {"success":False,"error":{"code":"SLOT_UNAVAILABLE","retryable":True}}
    r=make_agent(t).handle("Is DR-001 SERVICE-001 available on 2026-09-16 at 10:00?", "s11")
    assert "no longer available" in r.text
