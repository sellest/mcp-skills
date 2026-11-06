"""Two MCP endpoints over one store: /ro/mcp (read tools) and /rw/mcp (read + register)."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.lifespan import combine_lifespans
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from . import __version__
from .storage import SkillStore
from .validation import ENTRY_FILE, MAX_TOTAL_BYTES, SkillError

INSTRUCTIONS = (
    "This server holds skills: written instructions for specific kinds of tasks. "
    "Before you start a task, call list_skills and check whether a skill's description "
    "matches it. If one does, call get_skill for it and follow its text as your instructions. "
    "When SKILL.md links to another .md file of the skill, fetch it with get_skill(name, path)."
)

LIST_DESCRIPTION = (
    "List the registered skills with their name, description and current version. "
    "Call this before starting any task, and again whenever the topic changes: if a skill's "
    "description fits the task, load it with get_skill and follow it instead of improvising."
)

GET_DESCRIPTION = (
    "Return the text of a skill. With only a name it returns SKILL.md, the skill's main "
    "instructions: read them fully and follow them for the task. SKILL.md may link to other "
    ".md files of the same skill (for example references/index.md); pass that relative path "
    "as 'path' to read one. The result also lists all files of the skill."
)

REGISTER_DESCRIPTION = (
    "Admin only. Add a new skill, or publish a new version of an existing one. 'files' maps "
    "relative .md paths to their full text and must contain SKILL.md, which starts with YAML "
    "front matter holding 'name' (equal to 'name') and 'description'. Paths use '/', with no "
    f"'..' and no absolute paths; the total size is at most {MAX_TOTAL_BYTES // 1024} KB. "
    "Each call creates version N+1 and keeps the older versions. Only register a skill when "
    "the user explicitly asks and has given you its exact content."
)

SkillName = Annotated[str, Field(description="Skill name as shown by list_skills")]


def _fail(exc: SkillError) -> ToolError:
    return ToolError(str(exc))


def build_server(store: SkillStore, *, admin: bool) -> FastMCP:
    mcp = FastMCP("skills-admin" if admin else "skills", instructions=INSTRUCTIONS)
    read_only = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

    @mcp.tool(description=LIST_DESCRIPTION, annotations=read_only)
    def list_skills() -> dict:
        skills = [
            {"name": s.name, "description": s.description, "version": s.version}
            for s in store.skills()
        ]
        return {"skills": skills}

    @mcp.tool(description=GET_DESCRIPTION, annotations=read_only)
    def get_skill(
        name: SkillName,
        path: Annotated[str, Field(description="Relative .md path inside the skill")] = ENTRY_FILE,
    ) -> dict:
        try:
            version, text = store.read(name, path)
            _, files = store.files(name)
        except SkillError as exc:
            raise _fail(exc) from None
        return {"name": name, "version": version, "path": path, "files": files, "text": text}

    if admin:

        @mcp.tool(
            description=REGISTER_DESCRIPTION,
            annotations=ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=False,
                idempotentHint=False,
                openWorldHint=False,
            ),
        )
        def register_skill(
            name: Annotated[str, Field(description="Skill name (slug), equal to SKILL.md name")],
            files: Annotated[
                dict[str, str], Field(description="Map of relative .md path to file text")
            ],
        ) -> dict:
            try:
                version = store.register(name, files)
            except SkillError as exc:
                raise _fail(exc) from None
            return {"name": name, "version": version, "files": sorted(files)}

    return mcp


def create_app(store: SkillStore) -> Starlette:
    ro = build_server(store, admin=False).http_app(
        path="/mcp", stateless_http=True, json_response=True
    )
    rw = build_server(store, admin=True).http_app(
        path="/mcp", stateless_http=True, json_response=True
    )

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    return Starlette(
        routes=[Route("/health", health), Mount("/ro", app=ro), Mount("/rw", app=rw)],
        lifespan=combine_lifespans(ro.lifespan, rw.lifespan),
    )
