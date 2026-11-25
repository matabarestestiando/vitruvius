"""Control-plane recovery never supplies technical expert claims."""
import json
import re
import unicodedata
from fastapi import HTTPException
from sqlalchemy import select
from .db import Message


def routing_decision(raw, identities):
    value=json.loads(raw)
    if not isinstance(value,dict) or type(value.get('done')) is not bool:raise ValueError('Invalid moderator decision')
    if value['done']:return {'done':True,'next_speaker':''}
    speaker=value.get('next_speaker')
    if not isinstance(speaker,str):raise ValueError('Invalid moderator decision')
    if speaker not in identities:
        matches=[id for id,identity in identities.items() if identity['name'].casefold()==speaker.strip().casefold()]
        if len(matches)!=1:raise ValueError('Invalid moderator decision')
        speaker=matches[0]
    return {'done':False,'next_speaker':speaker}


def social_reply(text):
    normalized=unicodedata.normalize('NFKD',text.casefold())
    normalized=''.join(c for c in normalized if not unicodedata.combining(c))
    normalized=re.sub(r'[^a-z ]','',normalized).strip()
    if normalized in {'hola','hola a todos','buenos dias','buenas tardes','buenas noches','hello','hi','buenas'}:
        return 'Hola. ¿Qué quiere explorar con el consejo? Puede contarme su idea, plantear una pregunta o adjuntar un documento. Las respuestas técnicas se apoyarán en los libros habilitados y mostrarán sus citas.'
    if normalized in {'gracias','muchas gracias','thanks','thank you'}:
        return 'Con gusto. Podemos profundizar en lo anterior o explorar otra pregunta.'
    return None


def retry_owner_message(db,session_id,data):
    if not data.retry_message_id:return None
    owner=db.get(Message,data.retry_message_id)
    latest=db.scalar(select(Message).where(Message.session_id==session_id).order_by(Message.created_at.desc(),Message.id.desc()).limit(1))
    if not owner or owner.session_id!=session_id or owner.speaker!='Propietario':raise HTTPException(404,'La pregunta no pertenece a esta conversación')
    if not latest or latest.id!=owner.id:raise HTTPException(409,'Esta pregunta ya recibió intervenciones o hay una pregunta posterior. Continúe la conversación con un nuevo mensaje.')
    if data.text!=owner.content or set(data.attachment_ids)!={c['attachment_id'] for c in owner.citations if c.get('attachment_id')}:raise HTTPException(409,'Para reintentar conserve la pregunta y sus adjuntos originales')
    return owner
