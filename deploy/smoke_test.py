"""Disposable synthetic verification. No source is attributed to a real person."""
import asyncio,json,uuid
import httpx
from sqlalchemy import select,delete
from app.config import settings
from app.db import Session,Record,Message,Chunk,Approval
PREFIX='SYNTHETIC GROUNDING VERIFICATION '
SOURCE='SYNTHETIC TEST MATERIAL, not real literature. Professional method: establish requirements before choosing tools. Require explicit owner approval before exporting development specifications. Use PostgreSQL for durable project decisions. Treat unverified links as references, not evidence.'

async def main():
    created=[];session_id=None;project_id=None;expert_id=None;board_id=None
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',headers={'Authorization':'Bearer '+settings.owner_token},timeout=240) as api:
        async def request(method,path,body=None,expected=200):
            r=await api.request(method,'/api'+path,json=body)
            if r.status_code!=expected: raise AssertionError(path+' HTTP '+str(r.status_code))
            return r.json()
        try:
            name='Synthetic Verification Author '+str(uuid.uuid4())[:8]
            expert=await request('POST','/experts',{'name':name,'specialty':'Synthetic evidence verification only'});expert_id=expert['id']
            board=await request('POST','/boards',{'name':PREFIX+str(uuid.uuid4())[:8],'expert_ids':[expert_id]});board_id=board['id']
            project=await request('POST','/projects',{'name':PREFIX+str(uuid.uuid4())[:8]});project_id=project['id']
            session=await request('POST','/sessions',{'board_id':board_id,'project_id':project_id});session_id=session['id']
            empty=await request('POST','/sessions/'+session_id+'/turns',{'text':'Give an opinion about agent architecture','max_turns':1})
            assert not any(m['speaker']==name for m in empty)
            assert 'No se emitieron opiniones técnicas' in empty[-1]['content']
            print('No primary library => no technical opinion: PASS',flush=True)
            ref=await request('POST','/experts/'+expert_id+'/references',{'title':'SYNTHETIC VIDEO LINK — NO CONTENT FETCHED','author':name,'kind':'youtube','url':'https://www.youtube.com/watch?v=synthetic-only'})
            created.append(ref['id'])
            r=await request('POST','/references/'+ref['id']+'/import',{'session_id':session_id,'permanent_consent':True})
            assert r['status']=='requires_content' and r.get('document_id') is None
            print('Registered YouTube URL is not counted as evidence: PASS',flush=True)
            ref2=await request('POST','/experts/'+expert_id+'/references',{'title':'SYNTHETIC SOURCE, NOT REAL LITERATURE','author':name,'kind':'article','url':'https://example.invalid/synthetic-test'})
            created.append(ref2['id'])
            content=await request('POST','/references/'+ref2['id']+'/text',{'session_id':session_id,'permanent_consent':True,'text':SOURCE})
            doc_id=content['document_id'];created.append(doc_id)
            await request('POST','/contexts/'+doc_id+'/source',{'author':name,'source_url':'https://example.invalid/synthetic-test','kind':'author_work','reviewed_by_owner':True})
            await request('POST','/experts/'+expert_id+'/sources',{'document_ids':[doc_id],'role':'primary','approved':True})
            # Ensure actual pgvector index completion, independently of queue timing.
            await request('POST','/contexts/'+doc_id+'/index',{})
            print('Reference text incorporated, reviewed, indexed and assigned as primary: PASS',flush=True)
            history=await request('POST','/sessions/'+session_id+'/turns',{'text':'Según el material sintético proporcionado, ¿qué debe ocurrir antes de elegir herramientas? Responda solo con una afirmación sustentada en un fragmento literal. No atribuya nada a una persona real.','max_turns':1})
            replies=[m for m in history if m['speaker']==name]
            assert replies and replies[-1]['grounding_status']=='supported','No supported technical response produced'
            assert replies[-1]['citations']
            for c in replies[-1]['citations']:
                assert c['quote'] in SOURCE and c['source']['author']==name
            print('Real model response => exact quoted primary evidence + independent review: PASS',flush=True)
            profile=await request('POST','/experts/'+expert_id+'/profile/draft',{'session_id':session_id});created.append(profile['id'])
            assert profile['status']=='draft' and profile['citations']
            await request('POST','/expert-profiles/'+profile['id']+'/approve',{'approved':True})
            print('Documented professional profile drafted and explicitly approved: PASS',flush=True)
            # An unsupported foreign author cannot become this expert's primary author.
            other=await request('POST','/contexts',{'session_id':session_id,'title':'SYNTHETIC OTHER AUTHOR','text':SOURCE,'scope':'EXPERT','expert_ids':[expert_id],'permanent_consent':True,'source':{'author':'Different Synthetic Author','reviewed_by_owner':True}})
            created.append(other['id'])
            await request('POST','/experts/'+expert_id+'/sources',{'document_ids':[other['id']],'approved':True},expected=422)
            print('Other-author material cannot replace the primary author: PASS',flush=True)
        finally:
            if session_id:
                await api.delete('/api/sessions/'+session_id)
            with Session() as db:
                from app.knowledge import remove_document
                for id in reversed(created):
                    r=db.get(Record,id)
                    if not r: continue
                    if r.kind=='context': remove_document(db,r)
                    else: db.delete(r);db.commit()
                for r in list(db.scalars(select(Record).where(Record.kind=='expert_library_audit'))):
                    if r.data.get('expert_id')==expert_id:db.delete(r)
                for id in (project_id,board_id,expert_id):
                    r=db.get(Record,id) if id else None
                    if r: db.delete(r)
                db.commit()
            print('Synthetic expert, sources, profile, board, project and history cleanup: complete',flush=True)
if __name__ == "__main__":
    asyncio.run(main())
