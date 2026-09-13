from __future__ import annotations
import os, sys, uuid
from pathlib import Path
import streamlit as st
from sqlalchemy import select
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)
from app.agent.agent import ClinicReceptionistAgent
from app.database.connection import get_engine,get_session_factory,initialize_database
from app.database.models import Appointment,Clinic,Doctor,Service
from app.rag.pipeline import RAGPipeline
from app.tools import TOOL_REGISTRY
CLINIC_ID=os.getenv('DEFAULT_CLINIC_ID','CLINIC-001')
st.set_page_config(page_title='Maple Crescent | AI Receptionist',page_icon='🏥',layout='wide',initial_sidebar_state='expanded')
def css():
 st.markdown('''<style>.stApp{background:linear-gradient(180deg,#f6fbfa,#fff 42%)}[data-testid="stSidebar"]{background:#f6fbfa;border-right:1px solid #dce9e7}.brand{padding:6px 0 18px}.mark{width:48px;height:48px;border-radius:14px;background:#0f766e;color:white;display:flex;align-items:center;justify-content:center;font-size:25px;font-weight:800}.title{font-size:1.35rem;font-weight:800;color:#16302f;margin-top:10px}.sub{color:#64748b;font-size:.82rem}.hero{background:linear-gradient(135deg,#ecfdf5,#f0fdfa,#fff);border:1px solid #d7efeb;border-radius:22px;padding:25px 28px;margin-bottom:18px}.hero h1{margin:0;color:#16302f;font-size:2rem}.hero p{margin:.5rem 0 0;color:#526766;max-width:850px}.pill{display:inline-block;padding:5px 10px;border-radius:999px;background:#dff7f2;color:#0f766e;font-size:.75rem;font-weight:700;margin-right:5px}.workflow{border:1px solid #e2eceb;border-radius:14px;padding:10px 13px;background:#fff;color:#48615f;font-size:.8rem;margin:8px 0}.source{background:#f8fafc;border:1px solid #e8eef2;border-radius:9px;padding:7px 9px;margin:4px 0;font-size:.76rem}.footer{color:#94a3b8;text-align:center;font-size:.74rem;padding:20px}</style>''',unsafe_allow_html=True)
@st.cache_resource(show_spinner=False)
def rag():
 # ensure_index rebuilds only when the corpus, chunking or embedding backend
 # changed, so a stale index can never silently answer from old documents.
 r=RAGPipeline();r.ensure_index(ROOT/'data/production/knowledge/documents',CLINIC_ID)
 return r
@st.cache_resource(show_spinner=False)
def agent():return ClinicReceptionistAgent(CLINIC_ID,rag(),tools=TOOL_REGISTRY)
def ensure_db():
 initialize_database(get_engine());S=get_session_factory()
 with S() as s:exists=s.scalar(select(Clinic).where(Clinic.clinic_id==CLINIC_ID))
 if not exists:
  from scripts.seed_database import seed;seed()
def clinic():
 S=get_session_factory()
 with S() as s:return s.scalar(select(Clinic).where(Clinic.clinic_id==CLINIC_ID))
def appointments():
 S=get_session_factory()
 with S() as s:rows=s.execute(select(Appointment,Doctor.full_name,Service.name).join(Doctor,Doctor.doctor_id==Appointment.doctor_id).join(Service,Service.service_id==Appointment.service_id).where(Appointment.clinic_id==CLINIC_ID).order_by(Appointment.starts_at.desc())).all()
 return [{'Appointment':a.appointment_id,'Date / Time':a.starts_at.strftime('%Y-%m-%d %H:%M'),'Doctor':d,'Service':sv,'Patient':a.patient_id,'Status':a.status} for a,d,sv in rows]
def reset():
 sid=st.session_state.get('sid');a=agent()
 if sid:a.sessions.pop(sid,None)
 st.session_state.sid=str(uuid.uuid4());st.session_state.messages=[]
def sidebar(c):
 with st.sidebar:
  st.markdown('<div class="brand"><div class="mark">✚</div><div class="title">Maple Crescent</div><div class="sub">AI Clinic Receptionist</div></div>',unsafe_allow_html=True)
  if c:st.caption(c.address);st.caption(f'☎ {c.phone}');st.caption(f'✉ {c.email}')
  st.divider();st.markdown('**Demo controls**')
  if st.button('↻ Reset conversation',width="stretch"):reset();st.rerun()
  st.markdown('**Try a demo prompt**')
  for i,x in enumerate(['What are your Saturday timings?','Mujhe available doctors ke naam bata dein.','What payment methods do you accept?','Dr. Bilal ke liye cardiology appointment chahiye.']):
   if st.button(x,key=f'ex{i}',width="stretch"):st.session_state.pending=x;st.rerun()
  st.divider();st.markdown('**Safety**');st.caption('Administrative healthcare assistant — not a doctor.');st.caption('Live slots are checked from the appointment database.')
def trace(r):
 if r.tool_calls:st.markdown('<div class="workflow"><b>Workflow:</b> User → Agent → <b>'+' → '.join(c['tool'] for c in r.tool_calls)+'</b> → Database → Response</div>',unsafe_allow_html=True)
 elif r.sources:st.markdown('<div class="workflow"><b>Workflow:</b> User → Agent → <b>RAG</b> → Knowledge Base → Response</div>',unsafe_allow_html=True)
 if r.sources:
  with st.expander(f'Sources & grounding ({len(r.sources)})'):
   seen=set()
   for s in r.sources:
    k=(s.get('source'),s.get('document_type'),s.get('language'))
    if k in seen:continue
    seen.add(k);score=s.get('score');sc=f' · score {score:.2f}' if isinstance(score,(int,float)) else ''
    st.markdown(f'<div class="source"><b>{s.get("source") or "Clinic knowledge"}</b> · {s.get("document_type") or "document"} · {s.get("language") or "unknown"}{sc}</div>',unsafe_allow_html=True)
def main():
 css();ensure_db();st.session_state.setdefault('sid',str(uuid.uuid4()));st.session_state.setdefault('messages',[]);st.session_state.setdefault('pending',None)
 c=clinic();sidebar(c)
 st.markdown('<div class="hero"><span class="pill">Multilingual</span><span class="pill">RAG + Tools</span><span class="pill">Safe by design</span><h1>AI Clinic Receptionist & Appointment Assistant</h1><p>Your front-desk assistant for clinic information, doctor and service discovery, live appointment availability, and booking — in English, Urdu, Roman Urdu, or mixed language.</p></div>',unsafe_allow_html=True)
 chat,admin=st.columns([1.7,1],gap='large')
 with chat:
  if not st.session_state.messages:st.info('👋 Welcome! Ask about timings, doctors, services, fees, availability, or booking.')
  for m in st.session_state.messages:
   with st.chat_message(m['role'],avatar='🏥' if m['role']=='assistant' else '🙂'):
    st.markdown(m['content']);r=m.get('response')
    if r:trace(r)
  prompt=st.chat_input('Ask the receptionist… English / اردو / Roman Urdu')
  if st.session_state.pending:prompt=st.session_state.pending;st.session_state.pending=None
  if prompt:
   st.session_state.messages.append({'role':'user','content':prompt})
   with st.spinner('Checking clinic information and appointment data…'):r=agent().handle(prompt,st.session_state.sid)
   st.session_state.messages.append({'role':'assistant','content':r.text,'response':r});st.rerun()
 with admin:
  st.subheader('Front Desk Overview');data=appointments();active=sum(x['Status'] in {'scheduled','confirmed'} for x in data);cancelled=sum(x['Status']=='cancelled' for x in data)
  a,b=st.columns(2);a.metric('Active',active);b.metric('Cancelled',cancelled)
  with st.expander('Appointment / admin view',expanded=True):st.dataframe(data,width="stretch",hide_index=True,height=410)
  st.caption('Demo data is synthetic. Production admin access should require authentication and role-based authorization.')
 st.markdown('<div class="footer">Maple Crescent Family Clinic · AI receptionist demo · Administrative support only</div>',unsafe_allow_html=True)
if __name__=='__main__':main()
