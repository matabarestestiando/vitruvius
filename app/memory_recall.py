"""Recall canonical owner-approved text even when graph extraction yields no relations."""
import re
from sqlalchemy import select
from .db import Record


def ledger_facts(db,group_id,query,limit=3):
    terms=set(re.findall(r'[\w-]{3,}',query.lower()))
    rows=[r for r in db.scalars(select(Record).where(Record.kind=='memory_event').order_by(Record.created_at.desc())) if r.data.get('status')=='approved' and r.data.get('group_id')==group_id and r.data.get('text')]
    scored=[(sum(t in r.data['text'].lower() for t in terms),r) for r in rows]
    scored.sort(key=lambda pair:-pair[0])
    return [{'id':r.id,'fact':r.data['text'][:3000],'truncated':len(r.data['text'])>3000,'source':'approved_owner_record','owner_approved':True,'match':'text' if score else 'recent_in_scope','session_id':r.data.get('session_id'),'valid_at':r.created_at.isoformat()} for score,r in scored[:limit]]
