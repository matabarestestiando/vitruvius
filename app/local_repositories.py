"""Session-scoped, expiring code snapshots. No filesystem access or execution on server."""
from datetime import timedelta
import hashlib
import re
from pathlib import PurePosixPath
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from .db import Record, now

MAX_FILES = 500
MAX_TEXT = 2_000_000
DENIED = {'node_modules','vendor','dist','build','coverage','__pycache__','venv','env','target','site-packages'}
EXTENSIONS = {'.py','.ts','.tsx','.js','.jsx','.mjs','.cjs','.vue','.svelte','.md','.txt','.json','.toml','.yaml','.yml','.sql','.go','.rs','.java','.kt','.kts','.cs','.c','.h','.cpp','.hpp','.rb','.php','.swift','.html','.css','.scss','.sh','.r','.ex','.exs','.scala','.dart','.xml','.gradle','.graphql','.proto'}
SECRET = re.compile(r'-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----|\b(?:sk-or-v1-[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})|(?:api[_-]?key|access[_-]?token|password|secret[_-]?key)\s*["\']?\s*[:=]\s*["\'][A-Za-z0-9_+/.=-]{12,}["\']', re.I)


def allowed_path(path):
    if not isinstance(path,str) or len(path)>240 or any(c in path for c in ('\\',':','\x00','\n','\r')):
        return False
    parts=path.split('/')
    if any(not p or p in ('.','..') or p.startswith('.') or p.lower() in DENIED or re.search(r'credential|(?:^|[._-])secrets?(?:[._-]|$)|^id_(?:rsa|ed25519)',p,re.I) for p in parts):
        return False
    p=PurePosixPath(path)
    return p.suffix.lower() in EXTENSIONS or p.name.lower() in ('readme','dockerfile','makefile','cmakelists.txt','license')


class CodeFile(BaseModel):
    path: str = Field(min_length=1,max_length=240)
    text: str = Field(max_length=200_000)


class LocalRepositoryIn(BaseModel):
    name: str = Field(min_length=1,max_length=120,pattern=r'^[^/\\\x00\n\r]+$')
    files: list[CodeFile] = Field(min_length=1,max_length=MAX_FILES)
    consent: bool = False
    partial: bool = False
    retention_hours: int = Field(default=24,ge=1,le=24)

    @model_validator(mode='after')
    def bounds(self):
        if sum(len(f.text) for f in self.files)>MAX_TEXT:
            raise ValueError('La copia supera el presupuesto de código compartido')
        return self


def session_record(db,id):
    row=db.get(Record,id)
    if not row or row.kind!='session': raise HTTPException(404,'Conversación no encontrada')
    return row


def metadata(row):
    d=row.data
    return {'id':row.id,'session_id':d['session_id'],'name':d['name'],'expires_at':d['expires_at'],'partial':d['partial'],'file_count':len(d['files']),'characters':sum(len(f['text']) for f in d['files']), 'files':[{'path':f['path'],'sha256':f['sha256'],'lines':len(f['text'].splitlines())} for f in d['files']]}


def store(db,session_id,data):
    session_record(db,session_id)
    if not data.consent: raise HTTPException(422,'Autorice compartir esta copia temporal de código')
    existing=active(db,session_id)
    replacing=[r for r in existing if r.data['name']==data.name]
    if len(existing)-len(replacing)>=3: raise HTTPException(409,'Desconecte una copia anterior antes de compartir otra')
    seen=set()
    files=[]
    for f in data.files:
        if not allowed_path(f.path) or f.path in seen:
            raise HTTPException(422,'La copia contiene rutas excluidas o duplicadas; revise su selección')
        if '\x00' in f.text or SECRET.search(f.text):
            raise HTTPException(422,'Se omitió la carga porque un archivo parece contener claves o contenido binario. Revise su copia; no se guardó el código.')
        seen.add(f.path)
        files.append({'path':f.path,'text':f.text,'sha256':hashlib.sha256(f.text.encode()).hexdigest()})
    row=Record(kind='local_repository',data={'session_id':session_id,'name':data.name,'files':files,'partial':data.partial,'expires_at':(now()+timedelta(hours=data.retention_hours)).isoformat()})
    for old in replacing: db.delete(old)
    db.add(row);db.commit()
    return metadata(row)


def active(db,session_id):
    return [r for r in db.scalars(select(Record).where(Record.kind=='local_repository')) if r.data['session_id']==session_id and r.data['expires_at']>now().isoformat()]


def get(db,session_id,repository_id):
    session_record(db,session_id)
    row=db.get(Record,repository_id)
    if not row or row.kind!='local_repository' or row.data['session_id']!=session_id: raise HTTPException(404,'Copia no disponible en esta conversación')
    if row.data['expires_at']<=now().isoformat(): raise HTTPException(410,'La copia temporal ha expirado; vuelva a compartirla')
    return row


def read(db,session_id,repository_id,path,start_line=1,line_count=80):
    row=get(db,session_id,repository_id)
    if not allowed_path(path): raise HTTPException(403,'Ruta excluida')
    if type(start_line)!=int or start_line<1 or type(line_count)!=int or not 1<=line_count<=150: raise HTTPException(422,'Rango de líneas inválido')
    f=next((f for f in row.data['files'] if f['path']==path),None)
    if not f: raise HTTPException(404,'Archivo no incluido en la copia compartida')
    lines=f['text'].splitlines()
    block=lines[start_line-1:start_line-1+line_count]
    # At most 6000 characters without silently claiming complete lines.
    content='\n'.join(block)
    truncated=len(content)>6000
    text=content[:6000]
    return {'repository_id':row.id,'repository':row.data['name'],'path':path,'sha256':f['sha256'],'start_line':start_line,'end_line':start_line+len(text.splitlines())-1,'text':text,'truncated':truncated or start_line-1+len(block)<len(lines),'expires_at':row.data['expires_at']}


def search(db,session_id,query,repository_id=None,limit=6):
    session_record(db,session_id)
    if len(query)>4000: raise HTTPException(422,'Consulta demasiado larga')
    rows=[get(db,session_id,repository_id)] if repository_id else active(db,session_id)
    terms=set(re.findall(r'[\w.-]{3,}',query.lower()))-{'para','como','quiero','puede','sobre','este','esta','repo','repositorio','código','codigo','the','and','with'}
    candidates=[]
    for row in rows:
        for f in row.data['files']:
            path=f['path'];lines=f['text'].splitlines()
            scores=[sum(t in line.lower() for t in terms) for line in lines]
            best=max(range(len(scores)),key=scores.__getitem__) if scores else 0
            score=sum(4 for t in terms if t in path.lower())+(scores[best] if scores else 0)
            if PurePosixPath(path).name.lower().startswith('readme'):score+=0.5
            candidates.append((score,row,f,max(1,best-8)))
    candidates.sort(key=lambda x:(-x[0],x[2]['path']))
    return [read(db,session_id,row.id,f['path'],line,60) for _,row,f,line in candidates[:limit]]


def evidence(db,session_id,query):
    result=[]
    for hit in search(db,session_id,query,limit=4):
        if not hit['text'].strip():continue
        result.append({'chunk_id':f"local:{hit['repository_id']}:{hit['sha256']}:{hit['start_line']}",'document_id':hit['repository_id'],'title':f"{hit['repository']} / {hit['path']} · líneas {hit['start_line']}–{hit['end_line']}",'text':hit['text'],'source':{'author':'Código aportado por el propietario','kind':'other','medium':'text'},'library_role':'provided_context','has_original':False,'path':hit['path'],'sha256':hit['sha256'],'start_line':hit['start_line'],'end_line':hit['end_line'],'truncated':hit['truncated']})
    return result


def cleanup(db,session_id=None):
    count=0
    for row in list(db.scalars(select(Record).where(Record.kind=='local_repository'))):
        if (session_id is not None and row.data['session_id']==session_id) or row.data['expires_at']<=now().isoformat():
            db.delete(row);count+=1
    if count:db.commit()
    return count
