import io,base64
from datetime import timedelta
import pytest
from fastapi import HTTPException
from app import chat_media as media
from app.db import Record,Message,now
from PIL import Image


def png():
    output=io.BytesIO();Image.new('RGB',(10,10),'blue').save(output,format='PNG');return output.getvalue()


def test_image_magic_and_limits():
    media.verify_image(png(),'image/png')
    for content,mime in [(png(),'image/jpeg'),(b'<svg/>','image/png'),(png(),'image/svg+xml'),(b'x'*(media.MAX_IMAGE_BYTES+1),'image/png')]:
        with pytest.raises(Exception):media.verify_image(content,mime)


def test_attachment_isolation_expiry_and_history(db,workspace):
    sid=workspace[1]['id'];doc=Record(kind='context',data={'session_id':sid,'title':'Private image','status':'ready','content_type':'image/png','expires_at':(now()+timedelta(hours=1)).isoformat()});db.add(doc);db.commit()
    with pytest.raises(HTTPException):media.attachment_citations(db,'another-session',[doc.id])
    refs=media.attachment_citations(db,sid,[doc.id,doc.id]);assert len(refs)==1
    message=Message(session_id=sid,speaker='Propietario',content='Look',citations=refs);db.add(message);db.commit()
    result=media.message_payload(db,message);assert result['attachments'][0]['available'];assert not result['citations'];assert 'object_key' not in str(result)
    doc.data={**doc.data,'expires_at':(now()-timedelta(seconds=1)).isoformat()};db.commit()
    assert not media.message_payload(db,message)['attachments'][0]['available']
    with pytest.raises(HTTPException) as error:media.attachment_citations(db,sid,[doc.id])
    assert error.value.status_code==410


def test_session_subset_and_auth(client,headers,workspace):
    board=workspace[2]['board'][0]
    assert client.post('/api/sessions',headers=headers,json={'board_id':board['id'],'expert_ids':['unknown']}).status_code==422
    assert client.post('/api/sessions',headers=headers,json={'board_id':board['id'],'expert_ids':[]}).status_code==422
    assert client.post('/api/sessions/'+workspace[1]['id']+'/images',json={'prompt':'hello'}).status_code==401
    assert client.post('/api/sessions/'+workspace[1]['id']+'/turns/stream',json={'text':'hello'}).status_code==401


@pytest.mark.asyncio
async def test_generated_image_real_bytes_and_failure_cleanup(db,workspace,monkeypatch):
    sid=workspace[1]['id'];objects={}
    class Storage:
        def put_object(self,**kw):objects[kw['Key']]=kw['Body']
        def delete_object(self,**kw):objects.pop(kw['Key'],None)
    monkeypatch.setattr(media,'spaces',lambda:Storage())
    from types import SimpleNamespace
    monkeypatch.setattr(media,'settings',SimpleNamespace(openrouter_key='private-test-key',spaces_ready=True,spaces_bucket='test'))
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'message':{'images':[{'image_url':{'url':'data:image/png;base64,'+base64.b64encode(png()).decode()}}]}}]}
    class Http:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kw):return Response()
    monkeypatch.setattr(media.httpx,'AsyncClient',Http)
    await media.generate(db,sid,'Synthetic blue square')
    generated=[d for d in db.query(Record).filter_by(kind='context') if d.data.get('generated_image')]
    assert len(generated)==1 and generated[0].data['scope']=='SESSION' and not generated[0].data['permanent_consent']
    assert list(objects.values())==[png()]
    message=db.query(Message).filter_by(speaker='Imagen generada').one();assert media.message_payload(db,message)['attachments'][0]['generated']
    monkeypatch.setattr(Response,'json',lambda self:{'choices':[{'message':{'images':[]}}]})
    with pytest.raises(HTTPException) as error:await media.generate(db,sid,'Provider failure test')
    assert error.value.status_code==502 and len(objects)==1
    assert db.query(Message).filter_by(speaker='Imagen generada').count()==1


def test_visual_cannot_be_promoted_even_after_metadata_change(client,headers,workspace,db):
    sid=workspace[1]['id'];doc=Record(kind='context',data={'session_id':sid,'title':'Visual','status':'ready','scope':'SESSION','content_type':'image/png','source':{'medium':'text','reviewed_by_owner':True,'author':'Synthetic'},'expert_ids':[]});db.add(doc);db.commit()
    assert client.post('/api/contexts/'+doc.id+'/promote?scope=GLOBAL',headers=headers,json={}).status_code==422
    expert=workspace[2]['expert'][0]['id']
    assert client.post('/api/experts/'+expert+'/sources',headers=headers,json={'document_ids':[doc.id],'role':'primary','approved':True}).status_code==422
