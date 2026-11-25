from io import BytesIO
from zipfile import ZipFile, BadZipFile
from fastapi import HTTPException


def import_skill(name, content):
    if len(content) > 1024 * 1024:
        raise HTTPException(422, "Skill mayor de 1 MB")
    if name.lower().endswith(".zip"):
        try:
            with ZipFile(BytesIO(content)) as archive:
                candidates = [
                    i
                    for i in archive.infolist()
                    if i.filename.split("/")[-1] == "SKILL.md" and not i.is_dir()
                ]
                if len(candidates) != 1 or candidates[0].file_size > 64000:
                    raise HTTPException(
                        422, "El ZIP debe contener un único SKILL.md de hasta 64 KB"
                    )
                # Read one member into memory; no archive paths are extracted or executed.
                content = archive.read(candidates[0])
        except BadZipFile:
            raise HTTPException(422, "ZIP inválido") from None
    elif not name.lower().endswith(".md"):
        raise HTTPException(422, "Formato esperado: Markdown o ZIP")
    try:
        value = content.decode("utf-8")
    except UnicodeError:
        raise HTTPException(422, "Use UTF-8") from None
    if not value.strip() or len(value) > 64000:
        raise HTTPException(422, "Contenido vacío o demasiado extenso")
    return value
