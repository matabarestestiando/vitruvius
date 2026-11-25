import json
from contextlib import contextmanager
import pytest
from fastapi import HTTPException
from app import main
from app import conversation_memory as cm
from app.db import Record,Message
from app.schemas import SessionIn


def session_without_project(client,headers,workspace):
    board=workspace[2]['board'][0]['id']
    r=client.post('/api/sessions',headers=headers,json={'board_id':board,'title':'Exploración suelta'})
    assert r.status_code==200
    return r.json()


def test_no_project_requirement_and_isolated_compatibility_scope(client,headers,workspace,db):
    before=len(client.get('/api/catalog',headers=headers).json()['project'])
    a=session_without_project(client,headers,workspace);b=session_without_project(client,headers,workspace)
    assert a['project_id']!=b['project_id']
    assert db.get(Record,a['project_id']).data['internal_context'] is True
    assert len(client.get('/api/catalog',headers=headers).json()['project'])==before
    assert not db.query(Record).filter_by(kind='artifact').count()


def test_start_conversation_and_library_are_not_owner_projects(client,headers,workspace,db,monkeypatch):
    @contextmanager
    def factory():yield db
    monkeypatch.setattr(main.database,'Session',factory)
    result=main.start_conversation(title='Una idea sin entrega')
    assert 'project_id' not in result
    assert result['session_id'] and result['board_id']
    board=result['board_id']
    a=client.post('/api/library-session',headers=headers,params={'board_id':board}).json()
    b=client.post('/api/library-session',headers=headers,params={'board_id':board}).json()
    assert a['id']==b['id'] and a['session_kind']=='library'
    assert not any(s['id']==a['id'] for s in main.list_sessions())
    assert not any(p.get('internal_context') for p in main.list_projects())


def test_optional_spec_export_is_conversation_scoped(client,headers,workspace):
    a=session_without_project(client,headers,workspace);b=session_without_project(client,headers,workspace)
    assert client.get('/api/sessions/'+a['id']+'/export',headers=headers).status_code==409
    def artifact(s,title):
        return client.post('/api/artifacts',headers=headers,json={'project_id':s['project_id'],'session_id':s['id'],'kind':'specification','title':title,'content':'Synthetic implementation scope','acceptance_criteria':['An explicit criterion']}).json()
    one=artifact(a,'Approved specification A');two=artifact(b,'Unapproved unrelated B')
    assert client.get('/api/sessions/'+a['id']+'/export',headers=headers).status_code==409
    client.post('/api/artifacts/'+one['id']+'/approve',headers=headers,json={})
    r=client.get('/api/sessions/'+a['id']+'/export',headers=headers)
    assert r.status_code==200 and one['title'] in r.json()['prompt'] and two['title'] not in r.json()['prompt']


@pytest.mark.asyncio
async def test_review_proposes_but_never_saves_and_checks_owner_quotes(db,client,headers,workspace):
    s=session_without_project(client,headers,workspace);session=db.get(Record,s['id'])
    owner=Message(session_id=session.id,speaker='Propietario',content='Prefiero validar los requisitos antes de elegir herramientas.',citations=[])
    expert=Message(session_id=session.id,speaker='Experto',content='Never turn this opinion into an owner fact.',citations=[])
    db.add_all([owner,expert]);db.commit()
    proposal={'text':owner.content,'reason':'Preferencia reutilizable del propietario','category':'preference','scope':'personal','evidence':[{'message_id':owner.id,'quote':owner.content}]}
    async def model(system,transcript,**kw):
        assert expert.content not in json.dumps(transcript)
        return json.dumps({'candidates':[proposal]})
    result=await cm.review(db,session,model)
    assert len(result)==1 and result[0]['status']=='proposed'
    assert not db.query(Record).filter_by(kind='memory_event').count()
    assert await cm.review(db,session,model)==[]
    proposal['evidence']=[{'message_id':expert.id,'quote':expert.content}]
    proposal['text']='Fabricated owner statement not supported by owner'
    assert await cm.review(db,session,model)==[]


@pytest.mark.asyncio
async def test_no_durable_content_and_quoted_command_are_not_memory(db,client,headers,workspace):
    s=session_without_project(client,headers,workspace);session=db.get(Record,s['id'])
    owner=Message(session_id=session.id,speaker='Propietario',content='¿Qué alternativas podríamos explorar para un agente?',citations=[]);db.add(owner);db.commit()
    async def model(*args,**kw):return json.dumps({'candidates':[]})
    assert await cm.review(db,session,model)==[]
    assert cm.explicit_command('Guarda en memoria de largo plazo: Prefiero requisitos explícitos.')=='Prefiero requisitos explícitos.'
    assert cm.explicit_command('No guarda en memoria de largo plazo: esta hipótesis') is None
    assert cm.explicit_command('El documento dice: "Guarda en memoria de largo plazo: algo"') is None
    assert cm.explicit_command('Guarda esto') is None


@pytest.mark.asyncio
async def test_explicit_save_and_candidate_approval_require_consent_and_survive_failure(db,client,headers,workspace,monkeypatch):
    s=session_without_project(client,headers,workspace);calls=[]
    async def save(data,db):
        calls.append(data)
        row=Record(kind='memory_event',data={'scope':data.scope,'target_id':data.target_id,'status':'approved'})
        db.add(row);db.commit();return {'record_id':row.id,'episode_id':'synthetic-memory'}
    monkeypatch.setattr(main,'memories',save)
    body=cm.RememberIn(text='Prefiero primero requisitos explícitos.')
    with pytest.raises(HTTPException):await cm.remember(db,s['id'],body)
    assert calls==[]
    body.owner_requested=True
    out=await cm.remember(db,s['id'],body);assert out['saved']
    again=await cm.remember(db,s['id'],body);assert again['already_saved'] and len(calls)==1
    row=Record(kind='memory_candidate',data={'session_id':s['id'],'status':'proposed','text':'Usar una revisión antes de exportar.','scope':'conversation','evidence':[],'digest':'synthetic'});db.add(row);db.commit()
    with pytest.raises(HTTPException):await cm.approve(db,row.id,False)
    async def fail(*args,**kw):raise HTTPException(503,'Memory offline')
    monkeypatch.setattr(main,'memories',fail)
    with pytest.raises(HTTPException):await cm.approve(db,row.id,True)
    assert row.data['status']=='proposed'
    monkeypatch.setattr(main,'memories',save)
    out=await cm.approve(db,row.id,True)
    assert out['status']=='saved' and calls[-1].scope=='project' and calls[-1].target_id==s['project_id']
    assert db.get(Record,out['event_id']).data['origin']=='approved_memory_candidate'


def test_candidate_dismiss_and_secret_rejection(client,headers,workspace,db):
    s=session_without_project(client,headers,workspace)
    row=Record(kind='memory_candidate',data={'session_id':s['id'],'status':'proposed','text':'A proposed lesson','reason':'Useful later','evidence':[]});db.add(row);db.commit()
    assert client.post('/api/memory-candidates/'+row.id+'/dismiss',headers=headers,json={}).status_code==200
    assert client.post('/api/memory-candidates/'+row.id+'/approve',headers=headers,json={'approved':True}).status_code==409
    assert client.post('/api/sessions/'+s['id']+'/remember',headers=headers,json={'text':'key=ghp_'+'a'*30,'owner_requested':True}).status_code==422
    assert client.post('/api/sessions/'+s['id']+'/remember',json={'text':'No auth'}).status_code==401


@pytest.mark.asyncio
async def test_mcp_exposes_conversation_workflow_not_project_setup():
    names={t.name for t in await main.mcp.list_tools()}
    assert {'start_conversation','discuss','list_memory_candidates','remember_memory','approve_memory_candidate','propose_specification','export_conversation_specification'}<=names
    assert not {'create_project','list_projects','export_development_prompt'}&names


def test_canonical_approved_memory_is_recalled_without_graph_relations(db):
    from app.memory_recall import ledger_facts
    group='vitruvius:personal:owner'
    db.add_all([Record(kind='memory_event',data={'group_id':group,'status':'approved','text':'Prefiero requisitos antes de herramientas.'}),Record(kind='memory_event',data={'group_id':group,'status':'proposed','text':'Never recall unapproved'}),Record(kind='memory_event',data={'group_id':'vitruvius:board:other','status':'approved','text':'Not this group'}),Record(kind='memory_candidate',data={'group_id':group,'status':'proposed','text':'Only a candidate'})]);db.commit()
    facts=ledger_facts(db,group,'herramientas')
    assert len(facts)==1 and facts[0]['source']=='approved_owner_record' and facts[0]['owner_approved']
    assert facts[0]['fact']=='Prefiero requisitos antes de herramientas.'
