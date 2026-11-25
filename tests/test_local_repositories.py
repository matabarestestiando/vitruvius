from datetime import timedelta
from app.db import Record,now
from app import local_repositories as local
from app import main
import pytest


def upload(client,headers,session,files=None,**kw):
    return client.post('/api/sessions/'+session['id']+'/local-repositories',headers=headers,json={'name':'private-project','files':files or [{'path':'app/main.py','text':'def unique_dispatch():\n    return "actual local code"\n'}],'consent':True,**kw})


def test_auth_consent_and_no_catalog_code(client,headers,workspace):
    _,s,_=workspace
    assert upload(client,{},s).status_code==401
    assert upload(client,headers,s,consent=False).status_code==422
    r=upload(client,headers,s);assert r.status_code==200
    assert r.json()['file_count']==1 and 'actual local code' not in r.text
    catalog=client.get('/api/catalog',headers=headers).text
    assert 'actual local code' not in catalog and 'private-project' not in catalog


@pytest.mark.parametrize('path',['../escape.py','/absolute.py','app/../../file.py','.env','config/.env.py','node_modules/index.js','x/credentials.json','secrets.py','id_rsa','app\\hidden.py','app//main.py','key.pem'])
def test_excluded_paths(client,headers,workspace,path):
    _,s,_=workspace
    r=upload(client,headers,s,files=[{'path':path,'text':'should not be stored'}]);assert r.status_code==422


def test_content_secret_filter_atomic_and_redacted_errors(client,headers,workspace,db):
    _,s,_=workspace
    key='ghp_'+'a'*30
    r=upload(client,headers,s,files=[{'path':'safe.py','text':'safe content'},{'path':'config.py','text':f'key="{key}"'}])
    assert r.status_code==422 and key not in r.text
    assert not local.active(db,s['id'])
    r=upload(client,headers,s,files=[{'path':'app.py','text':'x'*200001}]);assert r.status_code==422
    assert len(r.content)<500


def test_scope_search_read_expiry_disconnect(client,headers,workspace,db):
    _,s,catalog=workspace
    row=upload(client,headers,s).json();rid=row['id']
    hit=local.search(db,s['id'],'unique_dispatch')[0]
    assert hit['path']=='app/main.py' and 'actual local code' in hit['text']
    assert len(hit['sha256'])==64 and hit['start_line']==1
    source=local.evidence(db,s['id'],'unique_dispatch')[0]
    assert source['library_role']=='provided_context' and source['document_id']==rid
    other=Record(kind='session',data={'project_id':s['project_id'],'board_id':s['board_id']});db.add(other);db.commit()
    assert local.active(db,other.id)==[]
    with pytest.raises(Exception) as e:local.read(db,other.id,rid,'app/main.py')
    assert e.value.status_code==404
    assert client.get(f"/api/sessions/{s['id']}/local-repositories/{rid}/read",headers=headers,params={'path':'app/main.py'}).status_code==200
    assert client.delete(f"/api/sessions/{s['id']}/local-repositories/{rid}",headers=headers).status_code==200
    assert local.active(db,s['id'])==[]
    rid=upload(client,headers,s).json()['id'];r=db.get(Record,rid);r.data={**r.data,'expires_at':(now()-timedelta(seconds=1)).isoformat()};db.commit()
    assert local.active(db,s['id'])==[]
    with pytest.raises(Exception) as e:local.read(db,s['id'],rid,'app/main.py')
    assert e.value.status_code==410
    from app.knowledge import cleanup
    assert cleanup(db)==1 and db.get(Record,rid) is None


def test_read_ranges_no_arbitrary_path_and_session_delete(client,headers,workspace,db):
    _,s,_=workspace
    text='\n'.join('line '+str(i) for i in range(1,201))
    rid=upload(client,headers,s,files=[{'path':'src/code.py','text':text}]).json()['id']
    block=local.read(db,s['id'],rid,'src/code.py',120,10)
    assert block['start_line']==120 and block['end_line']==129 and block['text'].startswith('line 120')
    with pytest.raises(Exception):local.read(db,s['id'],rid,'/etc/passwd')
    assert client.delete('/api/sessions/'+s['id'],headers=headers).status_code==200
    assert db.get(Record,rid) is None


def test_mcp_portal_link_and_same_snapshot(monkeypatch,db,client,headers,workspace):
    _,s,_=workspace
    class Scope:
        def __enter__(self):return db
        def __exit__(self,*args):pass
    monkeypatch.setattr(main.database,'Session',lambda:Scope())
    link=main.prepare_local_repository(s['id'])
    assert link['url']=='https://vitruvius.work/?local_repository_session='+s['id']
    assert 'token' not in link['url'] and link['live_access'] is False
    rid=upload(client,headers,s).json()['id']
    assert main.list_local_repositories(s['id'])[0]['id']==rid
    assert main.search_local_repository(s['id'],'unique_dispatch')['results'][0]['path']=='app/main.py'
    assert 'actual local code' in main.read_local_repository(s['id'],rid,'app/main.py')['text']


@pytest.mark.asyncio
async def test_council_receives_real_local_code_as_case_evidence(db,workspace,client,headers):
    import json
    from app.board import BoardRunner
    from test_grounding import source,answer
    _,s,catalog=workspace
    expert=db.get(Record,catalog['expert'][0]['id']);session=db.get(Record,s['id'])
    doc,chunk=source(db,expert,session)
    expert.data={**expert.data,'primary_source_ids':[doc.id]};db.commit()
    upload(client,headers,s)
    runner=BoardRunner(db,session,[expert],client=object());seen=[]
    async def complete(system,messages,model=None,structured=False):
        if system.startswith('Eres el moderador'):return json.dumps({'done':False,'next_speaker':expert.id})
        if system.startswith('Verifica'):return json.dumps({'accepted_claim_indices':[0]})
        seen.append(system)
        assert 'actual local code' in system and 'app/main.py' in system
        assert 'provided_context' in system
        return json.dumps(answer(chunk.id))
    runner.complete=complete
    await runner.graph(1).ainvoke({'transcript':[{'speaker':'Propietario','content':'unique_dispatch'}],'turns':0,'next_speaker':'','done':False,'summary':''})
    assert seen



def test_refresh_replaces_same_folder_only_after_validation(client,headers,workspace,db):
    _,s,_=workspace
    old=upload(client,headers,s).json()['id']
    bad=upload(client,headers,s,files=[{'path':'.env','text':'excluded'}])
    assert bad.status_code==422 and local.active(db,s['id'])[0].id==old
    new=upload(client,headers,s,files=[{'path':'src/new.py','text':'updated code version'}]).json()['id']
    assert new!=old and db.get(Record,old) is None
    assert len(local.active(db,s['id']))==1
    assert 'updated code version' in local.search(db,s['id'],'updated')[0]['text']
