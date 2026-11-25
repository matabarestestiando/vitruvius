from types import SimpleNamespace
from app.db import Record
from app import main


def test_plain_text_reference_needs_no_placeholder_url(client,headers,workspace):
    expert=workspace[2]['expert'][0]
    r=client.post('/api/experts/'+expert['id']+'/references',headers=headers,json={'title':'Owner supplied text','author':'Actual named author','kind':'text'})
    assert r.status_code==200 and r.json()['url'] is None


def test_resume_pdf_reuses_object_key_and_cannot_replace_reviewed_source(client,headers,workspace,db,monkeypatch):
    _,s,c=workspace;expert=c['expert'][0];signed=[]
    class Spaces:
        def generate_presigned_post(self,**kw):signed.append(kw);return {'url':'https://private-upload.invalid','fields':{'key':kw['Key']}}
    monkeypatch.setattr(main,'spaces',lambda:Spaces())
    r=client.post('/api/experts/'+expert['id']+'/references',headers=headers,json={'title':'Pending PDF','author':expert['name'],'kind':'pdf'}).json()
    original=client.post('/api/references/'+r['id']+'/upload',headers=headers,json={'session_id':s['id'],'permanent_consent':True}).json()
    d=db.get(Record,original['document_id']);key=d.data['object_key']
    assert client.post('/api/references/'+r['id']+'/resume-upload',headers=headers,json={'session_id':s['id']}).status_code==422
    resumed=client.post('/api/references/'+r['id']+'/resume-upload',headers=headers,json={'session_id':s['id'],'permanent_consent':True})
    assert resumed.status_code==200 and signed[-1]['Key']==key and signed[-1]['ExpiresIn']==300
    assert signed[-1]['Conditions']==[{'Content-Type':'application/pdf'}]
    d.data={**d.data,'source':{**d.data['source'],'reviewed_by_owner':True}};db.commit()
    assert client.post('/api/references/'+r['id']+'/resume-upload',headers=headers,json={'session_id':s['id'],'permanent_consent':True}).status_code==409
