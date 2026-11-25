from sqlalchemy import select
from .db import Record

NAMES = [
    ("Antonio Gulli", "Arquitectura y patrones de agentes"),
    ("Harrison Chase", "LangGraph y orquestación"),
    ("Chip Huyen", "Ingeniería y evaluación de IA"),
    ("Daniel Chalef", "Memoria de agentes"),
    ("Martin Kleppmann", "Sistemas distribuidos"),
    ("Cathy Pearl", "Diseño conversacional"),
    ("Micheal Lanham", "Implementación de agentes"),
]


def seed(db):
    if db.scalar(select(Record).where(Record.kind == "board")):
        return
    experts = []
    for name, specialty in NAMES:
        e = Record(
            kind="expert",
            data={
                "name": name,
                "specialty": specialty,
                "principles": "",
                "skill_ids": [],
                "model": None,
                "identity_notice": "Panelista virtual inspirado en su especialidad; no representa al autor. Biblioteca aún no incorporada.",
            },
        )
        db.add(e)
        db.flush()
        experts.append(e.id)
    db.add(
        Record(
            kind="board",
            data={
                "name": "Conversational AI & Agent Architecture Board",
                "expert_ids": experts,
                "mission": "Discutir, cuestionar y diseñar agentes conversacionales; entregar especificaciones aprobadas para desarrollo.",
            },
        )
    )
    db.commit()
