"""Input checks for skill names, file paths and SKILL.md front matter."""

import re

import yaml

NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
# One path segment: no leading dot (no hidden files, no "." or ".."), safe characters only.
SEGMENT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")
MAX_TOTAL_BYTES = 200 * 1024
MAX_FILES = 100
MAX_PATH_LENGTH = 200
ENTRY_FILE = "SKILL.md"


class SkillError(ValueError):
    """A request the caller can fix; the message is safe to show to the model."""


def validate_name(name: object) -> str:
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise SkillError(
            "Skill name must be 1-64 characters: lowercase letters, digits and '-', "
            "starting with a letter or digit"
        )
    return name


def validate_path(path: object) -> str:
    if not isinstance(path, str) or not path:
        raise SkillError("File path must be a non-empty string")
    if len(path) > MAX_PATH_LENGTH:
        raise SkillError(f"File path is longer than {MAX_PATH_LENGTH} characters: {path!r}")
    if "\\" in path or ":" in path or path.startswith("/"):
        raise SkillError(f"File path must be relative and use '/': {path!r}")
    if not path.endswith(".md"):
        raise SkillError(f"Only .md files are allowed: {path!r}")
    for segment in path.split("/"):
        if segment in {"", ".", ".."} or not SEGMENT_RE.fullmatch(segment):
            raise SkillError(f"Invalid file path segment in {path!r}")
    return path


def parse_front_matter(text: str) -> dict:
    """Return the YAML front matter of SKILL.md with non-empty name and description."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillError("SKILL.md must start with YAML front matter ('---')")
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        raise SkillError("SKILL.md front matter is not closed with '---'") from None
    try:
        meta = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise SkillError(f"SKILL.md front matter is not valid YAML: {exc}") from None
    if not isinstance(meta, dict):
        raise SkillError("SKILL.md front matter must be a mapping")
    for key in ("name", "description"):
        value = meta.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SkillError(f"SKILL.md front matter needs a non-empty '{key}'")
    meta["name"] = meta["name"].strip()
    meta["description"] = " ".join(meta["description"].split())
    return meta


def validate_files(name: str, files: object) -> dict[str, str]:
    """Check a whole registration and return the files to store."""
    validate_name(name)
    if not isinstance(files, dict) or not files:
        raise SkillError("'files' must map file paths to their text")
    if len(files) > MAX_FILES:
        raise SkillError(f"A skill can have at most {MAX_FILES} files")
    total = 0
    clean: dict[str, str] = {}
    folded: set[str] = set()
    for path, text in files.items():
        validate_path(path)
        if not isinstance(text, str):
            raise SkillError(f"Content of {path!r} must be text")
        if path.lower() in folded:
            raise SkillError(f"Duplicate file path (case-insensitive): {path!r}")
        folded.add(path.lower())
        total += len(text.encode("utf-8"))
        clean[path] = text
    if total > MAX_TOTAL_BYTES:
        raise SkillError(f"Skill is {total} bytes; the limit is {MAX_TOTAL_BYTES}")
    if ENTRY_FILE not in clean:
        raise SkillError("'files' must contain SKILL.md")
    meta = parse_front_matter(clean[ENTRY_FILE])
    if meta["name"] != name:
        raise SkillError(f"SKILL.md name {meta['name']!r} does not match {name!r}")
    return clean
