"""Reconcile durable queued documents with actual Celery deliveries. No document content is logged."""
import base64,json
from datetime import datetime,timezone
from sqlalchemy import select
from .db import Record,now
from .processing import client,Progress


def known_deliveries(celery):
    pending=set()
    # This deployment uses the default celery queue and no task priorities.
    queue=celery.conf.task_default_queue or 'celery'
    for raw in client().lrange(queue,0,-1):
        message=json.loads(raw)
        if message.get('headers',{}).get('task')=='context.ingest':
            args=json.loads(base64.b64decode(message['body']))[0]
            if args:pending.add(args[0])
    inspector=celery.control.inspect(timeout=2)
    reserved=inspector.reserved()
    active=inspector.active()
    if reserved is None or active is None:
        raise RuntimeError('Cannot verify worker deliveries')
    for states in (reserved,active):
        for tasks in states.values():
            for task in tasks:
                if task.get('name')=='context.ingest' and task.get('args'):
                    pending.add(task['args'][0])
    return pending


def recover(db,pending,enqueue,grace_seconds=120):
    recovered=[]
    ids=list(db.scalars(select(Record.id).where(Record.kind=='context',Record.data['status'].as_string()=='queued')))
    for id in ids:
        # Actual ingestion holds this row lock through extraction and indexing.
        doc=db.scalar(select(Record).where(Record.id==id).with_for_update(skip_locked=True).execution_options(populate_existing=True))
        if not doc:continue
        d=doc.data
        if d.get('status')!='queued' or not d.get('object_key') or id in pending:
            db.rollback();continue
        if d.get('expires_at') and d['expires_at']<=now().isoformat():
            db.rollback();continue
        since=datetime.fromisoformat(d['ingest_dispatch_requested_at']) if d.get('ingest_dispatch_requested_at') else doc.created_at
        if since.tzinfo is None:since=since.replace(tzinfo=timezone.utc)
        if (now()-since).total_seconds()<grace_seconds:
            db.rollback();continue
        # Commit the dispatch lease BEFORE publication: never race the worker's ready commit.
        doc.data={**d,'ingest_dispatch_requested_at':now().isoformat(),'ingest_recovery_count':d.get('ingest_recovery_count',0)+1}
        db.commit()
        Progress(id)('waiting')
        try:enqueue(id)
        except Exception:continue  # Durable queued state will be reconciled on the next eligible pass.
        recovered.append(id)
    return recovered
