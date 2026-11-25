from pathlib import Path
import subprocess
from fastapi import HTTPException
from .config import settings

DENIED = {".git", ".env", "node_modules", ".venv", "vendor", "dist", "__pycache__"}
EXTENSIONS = {
    ".py",
    ".ts",
    ".js",
    ".vue",
    ".md",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".sql",
    ".go",
    ".rs",
    ".java",
    ".txt",
}


def repository(path):
    root = Path(settings.repo_root).resolve()
    p = Path(path).resolve()
    if not p.is_relative_to(root) or p == root or not (p / ".git").exists():
        raise HTTPException(422, "Repositorio no autorizado")
    return p


def safe_file(root, path):
    p = (root / path).resolve()
    if (
        not p.is_relative_to(root)
        or any(
            part in DENIED or part.startswith(".env")
            for part in p.relative_to(root).parts
        )
        or p.suffix not in EXTENSIONS
        or p.is_symlink()
    ):
        raise HTTPException(403, "Archivo excluido")
    if not p.is_file() or p.stat().st_size > 256000:
        raise HTTPException(422, "Archivo inexistente o demasiado grande")
    return p


def inspect(path, query="", file=None):
    p = repository(path)
    commit = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(p), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    from .observability import event

    event("repository_read", commit=commit)
    if file:
        return {
            "commit": commit,
            "path": file,
            "text": safe_file(p, file).read_text(errors="replace"),
        }
    # Only tracked files. No hooks, checkout, fetch, shell, build or repository commands are executed.
    tracked = (
        subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(p), "ls-files", "-z"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        .stdout.decode()
        .split("\0")
    )
    results = []
    for name in tracked[:20000]:
        if not name:
            continue
        try:
            f = safe_file(p, name)
        except HTTPException:
            continue
        if not query:
            results.append({"path": name})
        else:
            for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if query.lower() in line.lower():
                    results.append({"path": name, "line": n, "text": line[:500]})
                if len(results) >= 100:
                    break
        if len(results) >= 100:
            break
    return {"commit": commit, "results": results}
