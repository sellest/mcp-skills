import pytest

from mcp_skills.storage import SkillStore
from mcp_skills.validation import SkillError

from .conftest import skill_md


def test_register_and_read(store):
    files = {"SKILL.md": skill_md("demo"), "references/a.md": "# A\n"}
    assert store.register("demo", files) == 1
    assert store.read("demo") == (1, files["SKILL.md"])
    assert store.read("demo", "references/a.md") == (1, "# A\n")
    assert store.files("demo") == (1, ["SKILL.md", "references/a.md"])
    [info] = store.skills()
    assert (info.name, info.version) == ("demo", 1)
    assert info.description.startswith("Does a thing")


def test_new_version_keeps_old_ones(store):
    store.register("demo", {"SKILL.md": skill_md("demo", "first"), "old.md": "x"})
    assert store.register("demo", {"SKILL.md": skill_md("demo", "second")}) == 2
    assert store.skills()[0].description == "second"
    assert store.files("demo") == (2, ["SKILL.md"])
    with pytest.raises(SkillError, match="no file"):
        store.read("demo", "old.md")
    assert (store.root / "demo" / "v1" / "old.md").read_text(encoding="utf-8") == "x"


def test_version_numbers_sort_numerically(store):
    for _ in range(11):
        store.register("demo", {"SKILL.md": skill_md("demo")})
    assert store.read("demo")[0] == 11
    assert store.register("demo", {"SKILL.md": skill_md("demo")}) == 12


def test_text_is_stored_byte_for_byte(store):
    text = skill_md("demo") + "Строка\r\nwith CRLF\n"
    store.register("demo", {"SKILL.md": text})
    assert store.read("demo")[1] == text


def test_failed_registration_leaves_nothing(store):
    with pytest.raises(SkillError):
        store.register("demo", {"SKILL.md": "no front matter"})
    assert store.skills() == []
    assert not (store.root / "demo").exists()


def test_no_temp_dirs_left(store):
    store.register("demo", {"SKILL.md": skill_md("demo")})
    assert [p.name for p in (store.root / "demo").iterdir()] == ["v1"]


def test_unknown_skill_and_bad_input(store):
    with pytest.raises(SkillError, match="not registered"):
        store.read("missing")
    with pytest.raises(SkillError):
        store.read("../etc")
    store.register("demo", {"SKILL.md": skill_md("demo")})
    for path in ("../demo/v1/SKILL.md", "/etc/passwd", "v1/SKILL.md", "x.txt"):
        with pytest.raises(SkillError):
            store.read("demo", path)


def test_list_ignores_junk(store):
    store.register("demo", {"SKILL.md": skill_md("demo")})
    (store.root / "Bad_Name").mkdir()
    (store.root / "empty").mkdir()
    (store.root / "broken" / "v1").mkdir(parents=True)
    (store.root / "broken" / "v1" / "SKILL.md").write_text("garbage", encoding="utf-8")
    (store.root / "demo" / ".tmp-abc").mkdir()
    (store.root / "notes.txt").write_text("x", encoding="utf-8")
    assert [s.name for s in store.skills()] == ["demo"]
    assert store.read("demo")[0] == 1


def test_store_persists_across_instances(tmp_path):
    SkillStore(tmp_path).register("demo", {"SKILL.md": skill_md("demo")})
    assert SkillStore(tmp_path).read("demo")[0] == 1
