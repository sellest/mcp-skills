"""Versioned skill storage on disk: <root>/<name>/v<N>/<path>.

A registration is written to a temporary folder next to the versions and then renamed to
v<N+1>, so readers never see a half-written version. Old versions are kept for rollback.
"""

import logging
import os
import re
import shutil
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from .validation import (
    ENTRY_FILE,
    NAME_RE,
    SkillError,
    parse_front_matter,
    validate_files,
    validate_name,
    validate_path,
)

log = logging.getLogger(__name__)
VERSION_RE = re.compile(r"v([1-9][0-9]*)")


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    version: int


class SkillStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _versions(self, name: str) -> list[int]:
        skill_dir = self.root / name
        if not skill_dir.is_dir():
            return []
        found = []
        for entry in skill_dir.iterdir():
            match = VERSION_RE.fullmatch(entry.name)
            if match and entry.is_dir():
                found.append(int(match.group(1)))
        return sorted(found)

    def _current_dir(self, name: str) -> tuple[int, Path]:
        versions = self._versions(validate_name(name))
        if not versions:
            raise SkillError(f"Skill {name!r} is not registered; call list_skills to see skills")
        return versions[-1], self.root / name / f"v{versions[-1]}"

    def list(self) -> list[SkillInfo]:
        skills = []
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir() or not NAME_RE.fullmatch(entry.name):
                continue
            try:
                version, folder = self._current_dir(entry.name)
                meta = parse_front_matter((folder / ENTRY_FILE).read_text(encoding="utf-8"))
            except (OSError, SkillError):
                log.warning("Skipping unreadable skill %s", entry.name, exc_info=True)
                continue
            skills.append(SkillInfo(entry.name, meta["description"], version))
        return skills

    def files(self, name: str) -> tuple[int, list[str]]:
        version, folder = self._current_dir(name)
        paths = sorted(
            p.relative_to(folder).as_posix() for p in folder.rglob("*.md") if p.is_file()
        )
        return version, paths

    def read(self, name: str, path: str = ENTRY_FILE) -> tuple[int, str]:
        validate_path(path)
        version, folder = self._current_dir(name)
        target = folder / path
        if not target.is_file():
            raise SkillError(f"Skill {name!r} has no file {path!r}")
        with open(target, encoding="utf-8", newline="") as fh:
            return version, fh.read()

    def register(self, name: str, files: dict[str, str]) -> int:
        clean = validate_files(name, files)
        skill_dir = self.root / name
        with self._lock:
            skill_dir.mkdir(exist_ok=True)
            tmp = skill_dir / f".tmp-{uuid.uuid4().hex}"
            try:
                for path, text in clean.items():
                    target = tmp / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with open(target, "w", encoding="utf-8", newline="") as fh:
                        fh.write(text)
                        fh.flush()
                        os.fsync(fh.fileno())
                versions = self._versions(name)
                version = (versions[-1] if versions else 0) + 1
                os.rename(tmp, skill_dir / f"v{version}")
            except BaseException:
                shutil.rmtree(tmp, ignore_errors=True)
                raise
        log.info("Registered skill %s v%d (%d files)", name, version, len(clean))
        return version
