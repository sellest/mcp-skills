import pytest

from mcp_skills.storage import SkillStore


def skill_md(name: str, description: str = "Does a thing. Use when the user asks.") -> str:
    return (
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\nSee references/a.md\n"
    )


@pytest.fixture
def store(tmp_path):
    return SkillStore(tmp_path / "skills")
