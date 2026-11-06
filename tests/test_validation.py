import pytest

from mcp_skills.validation import (
    MAX_TOTAL_BYTES,
    SkillError,
    parse_front_matter,
    validate_files,
    validate_name,
    validate_path,
)

from .conftest import skill_md


@pytest.mark.parametrize("name", ["a", "demo", "my-skill-2", "0abc", "a" * 64])
def test_good_names(name):
    assert validate_name(name) == name


@pytest.mark.parametrize("name", ["", "-a", "A", "a_b", "a b", "a" * 65, "ä", None, "../x"])
def test_bad_names(name):
    with pytest.raises(SkillError):
        validate_name(name)


@pytest.mark.parametrize("path", ["SKILL.md", "references/index.md", "a/b-c/d_e.v2.md"])
def test_good_paths(path):
    assert validate_path(path) == path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/etc/x.md",
        "../x.md",
        "a/../b.md",
        "a\\b.md",
        "C:/x.md",
        "x.txt",
        "a//b.md",
        "./a.md",
        ".hidden.md",
        "a/.b.md",
        "SKILL.MD",
        "a b.md",
        "x" * 300 + ".md",
    ],
)
def test_bad_paths(path):
    with pytest.raises(SkillError):
        validate_path(path)


def test_front_matter_folded_description():
    text = "---\nname: demo\ndescription: >\n  First line\n  second line.\n---\nbody"
    meta = parse_front_matter(text)
    assert meta == {"name": "demo", "description": "First line second line."}


def test_front_matter_with_bom_and_crlf():
    meta = parse_front_matter("\ufeff---\r\nname: demo\r\ndescription: x\r\n---\r\n")
    assert meta["name"] == "demo"


@pytest.mark.parametrize(
    "text",
    [
        "no front matter",
        "---\nname: demo\ndescription: x\n",
        "---\n- a\n- b\n---\n",
        "---\nname: demo\n---\n",
        "---\nname: demo\ndescription: '  '\n---\n",
        "---\nname: ''\ndescription: x\n---\n",
        "---\nname: [demo\ndescription: x\n---\n",
        "---\nname: 5\ndescription: x\n---\n",
    ],
)
def test_bad_front_matter(text):
    with pytest.raises(SkillError):
        parse_front_matter(text)


def test_files_ok():
    files = {"SKILL.md": skill_md("demo"), "references/a.md": "# A"}
    assert validate_files("demo", files) == files


@pytest.mark.parametrize(
    "files, message",
    [
        ({}, "must map"),
        ([], "must map"),
        ({"references/a.md": "x"}, "must contain SKILL.md"),
        ({"SKILL.md": skill_md("other")}, "does not match"),
        ({"SKILL.md": skill_md("demo"), "a.md": 5}, "must be text"),
        ({"SKILL.md": skill_md("demo"), "a.md": "x", "A.md": "y"}, "Duplicate"),
        ({"SKILL.md": skill_md("demo"), "big.md": "x" * MAX_TOTAL_BYTES}, "limit"),
        ({"SKILL.md": skill_md("demo"), "../a.md": "x"}, "Invalid"),
    ],
)
def test_files_rejected(files, message):
    with pytest.raises(SkillError, match=message):
        validate_files("demo", files)


def test_size_counts_utf8_bytes():
    # Cyrillic letters are two bytes each in UTF-8.
    body = "я" * (MAX_TOTAL_BYTES // 2)
    with pytest.raises(SkillError, match="limit"):
        validate_files("demo", {"SKILL.md": skill_md("demo"), "ru.md": body})
