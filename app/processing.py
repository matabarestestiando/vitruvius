"""Content-free progress, outside the atomic document transaction."""
import json,time
from datetime import datetime,timezone
from redis import Redis
from .config import settings

LABELS={'waiting':'Esperando turno','downloading':'Leyendo el archivo','extracting':'Leyendo las páginas','layout':'Analizando el diseño del PDF','indexing':'Preparando búsquedas','ready':'Listo para revisar','failed':'El procesamiento necesita atención'}


def client():return Redis.from_url(settings.redis_url,socket_connect_timeout=.3,socket_timeout=.3)


def read_many(ids):
    if not ids:return {}
    try:
        values=client().mget(['vitruvius:document-progress:'+i for i in ids])
        return {i:json.loads(v) for i,v in zip(ids,values) if v}
    except Exception:return {}


class Progress:
    def __init__(self,id):self.id=id;self.state={};self.last=0
    def __call__(self,stage,**values):
        changed=self.state.get('stage')!=stage
        self.state.update(stage=stage,label=LABELS[stage],**values)
        if not changed and time.monotonic()-self.last<1:return
        self.last=time.monotonic()
        self.state['updated_at']=datetime.now(timezone.utc).isoformat()
        try:client().setex('vitruvius:document-progress:'+self.id,7200,json.dumps(self.state))
        except Exception:pass


def extract_for_ingestion(path,content_type,progress,fallback=None):
    from .knowledge import extract
    fallback=fallback or extract
    if content_type=='application/pdf':
        from pypdf import PdfReader
        import os
        reader=None;probe=[]
        if os.getenv('PDF_EXTRACTION_MODE','auto')!='layout':
            try:
                reader=PdfReader(path)
                probe=[reader.pages[i].extract_text() or '' for i in range(min(3,len(reader.pages)))]
            except Exception:reader=None
        if reader is not None and any(t.strip() for t in probe):
            total=len(reader.pages);empty=0
            progress('extracting',pages_done=0,pages_total=total,method='pdf_text',pages_without_text=0)
            for i,page in enumerate(reader.pages):
                value=probe[i] if i<len(probe) else (page.extract_text() or '')
                empty+=not bool(value.strip())
                progress('extracting',pages_done=i+1,pages_total=total,method='pdf_text',pages_without_text=empty)
                yield i+1,value
            return
        progress('layout',method='docling_cpu')
    else:progress('extracting',method='text')
    for page,value in fallback(path,content_type):yield page,value
