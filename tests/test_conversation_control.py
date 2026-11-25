import json
import pytest
from fastapi import HTTPException
from app.conversation_control import routing_decision,social_reply,retry_owner_message
from app.db import Message,Record
from app.schemas import TurnIn


def test_moderator_rejects_invalid_ids_and_boolean_strings():
 identities={'valid-id':{'name':'Expert Example'}}
 assert routing_decision('{"done":false,"next_speaker":"Expert Example"}',identities)['next_speaker']=='valid-id'
 for raw in ['{"done":false,"next_speaker":"Propietario"}','{"done":"false","next_speaker":"valid-id"}','[]','bad json']:
  with pytest.raises((ValueError,TypeError)):routing_decision(raw,identities)


def test_social_turns_do_not_bypass_grounding_for_technical_questions():
 assert social_reply('¡Hola!') and social_reply('Muchas gracias.')
 assert social_reply('Hola quiero saber si puedo tener un agente que se comunique con otro agente.') is None
 assert social_reply('¿Qué es MCP?') is None


def test_retry_only_unanswered_owner_message_in_same_session(db,workspace):
 sid=workspace[1]['id'];owner=Message(session_id=sid,speaker='Propietario',content='Exact question',citations=[]);db.add(owner);db.commit()
 data=TurnIn(text=owner.content,retry_message_id=owner.id)
 assert retry_owner_message(db,sid,data).id==owner.id
 for other_sid,body in [('other',data),(sid,TurnIn(text='Changed question',retry_message_id=owner.id))]:
  with pytest.raises(HTTPException):retry_owner_message(db,other_sid,body)
 db.add(Message(session_id=sid,speaker='Expert',content='A completed answer',citations=[]));db.commit()
 with pytest.raises(HTTPException):retry_owner_message(db,sid,data)


@pytest.mark.asyncio
async def test_invalid_moderator_recovers_routing_without_unverified_claims(db,workspace):
 from app.board import BoardRunner
 from test_grounding import source,answer
 _,s,cat=workspace;session=db.get(Record,s['id']);expert=db.get(Record,cat['expert'][0]['id']);doc,chunk=source(db,expert,session);expert.data={**expert.data,'primary_source_ids':[doc.id]};db.commit()
 runner=BoardRunner(db,session,[expert],client=object());routes=0
 async def complete(system,*args,**kwargs):
  nonlocal routes
  if system.startswith('Eres el moderador'):routes+=1;return json.dumps({'done':False,'next_speaker':'Propietario'})
  if system.startswith('Verifica'):return json.dumps({'accepted_claim_indices':[0]})
  return json.dumps(answer(chunk.id))
 runner.complete=complete
 result=await runner.graph(1).ainvoke({'transcript':[{'speaker':'Propietario','content':'Exact question'}],'turns':0,'done':False,'next_speaker':'','summary':''})
 assert routes==2 and result['turns']==1
 message=db.query(Message).filter(Message.speaker==expert.data['name']).one()
 assert len(message.citations)==1


@pytest.mark.asyncio
async def test_greeting_retry_reuses_owner_message(client,headers,workspace,db,monkeypatch):
 from app import main
 from types import SimpleNamespace
 sid=workspace[1]['id'];owner=Message(session_id=sid,speaker='Propietario',content='Hola',citations=[]);db.add(owner);db.commit()
 monkeypatch.setattr(main,'settings',SimpleNamespace(openrouter_key='test-key'))
 result=await main.run_turn(db,sid,TurnIn(text='Hola',retry_message_id=owner.id))
 assert db.query(Message).filter_by(session_id=sid,speaker='Propietario').count()==1
 assert result[-1]['speaker']=='Moderador' and '¿Qué quiere explorar' in result[-1]['content']


@pytest.mark.asyncio
async def test_stream_failure_reports_saved_question_and_safe_retry(db,workspace,monkeypatch,caplog):
 from contextlib import contextmanager
 from types import SimpleNamespace
 from app import main
 sid=workspace[1]['id']
 @contextmanager
 def factory():yield db
 async def failed_turn(active_db,id,data):
  active_db.add(Message(session_id=id,speaker='Propietario',content=data.text,citations=[]));active_db.commit()
  raise RuntimeError('SENSITIVE_DIAGNOSTIC_NOT_FOR_CLIENT')
 async def connected():return False
 monkeypatch.setattr(main.database,'Session',factory);monkeypatch.setattr(main,'run_turn',failed_turn)
 response=await main.stream_turn(sid,TurnIn(text='Question retained'),SimpleNamespace(is_disconnected=connected),db)
 body=''.join([part async for part in response.body_iterator])
 error_block=next(part for part in body.split('\n\n') if part.startswith('event: error'))
 error=json.loads(error_block.split('data: ',1)[1]);owner=db.query(Message).filter_by(session_id=sid,speaker='Propietario').one()
 assert error['retry_message_id']==owner.id and 'pregunta quedó guardada' in error['message']
 assert 'SENSITIVE_DIAGNOSTIC' not in body and 'SENSITIVE_DIAGNOSTIC' not in caplog.text
 assert 'intervenciones verificadas quedaron' not in body


@pytest.mark.asyncio
async def test_translation_changes_only_prose_not_evidence_or_claim_kind():
 from app.claim_language import localize_claims
 from app.grounding import GroundedAnswer
 from test_grounding import answer,QUOTE
 original=GroundedAnswer.model_validate(answer('verified-chunk'))
 async def translate(system,transcript,**kwargs):
  assert QUOTE not in json.dumps(transcript)
  return json.dumps({'texts':['El proyecto sintético utiliza PostgreSQL.']})
 translated=await localize_claims(translate,original,'¿Qué base de datos usa?')
 assert translated.claims[0].text=='El proyecto sintético utiliza PostgreSQL.'
 assert translated.claims[0].evidence==original.claims[0].evidence and translated.claims[0].kind==original.claims[0].kind
