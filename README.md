# mcp-skills

A small MCP server that shares **Markdown-only skills** with AI assistants such as ChatGPT. A skill
is a folder in the Codex/ChatGPT format: `SKILL.md` with YAML front matter (`name`, `description`)
plus optional `.md` files it links to, such as `references/index.md`. The assistant reads the text
online and follows it. Nothing is installed on the user's computer.

## Tools

| Tool | What it does |
|---|---|
| `list_skills()` | Name, description and current version of every skill |
| `get_skill(name, path="SKILL.md")` | Text of `SKILL.md` or another `.md` file of the skill, plus the skill's file list |
| `register_skill(name, files)` | Adds a skill, or a new version of one. `files` maps relative `.md` paths to text and must include `SKILL.md` |

`register_skill` rejects:
- a name that isn't a slug `[a-z0-9][a-z0-9-]{0,63}`;
- a `SKILL.md` without front matter, without a non-empty `name` or `description`, or whose `name`
  differs from `name`;
- paths that aren't relative `.md` paths using `/` (no `..`, no backslashes, no absolute or hidden
  paths);
- more than 200 KB of UTF-8 text, or more than 100 files.

## Endpoints

One process serves two MCP endpoints (streamable HTTP, stateless) over the same storage:

| Path | Tools | Intended for |
|---|---|---|
| `/ro/mcp` | `list_skills`, `get_skill` | readers |
| `/rw/mcp` | all three | admins |
| `/health` | – | container health checks |

The server has **no authentication of its own**. Run it behind an MCP gateway that authenticates
users and grants backends per group, on a network only the gateway can reach. With
[mcp-gateway](https://github.com/sellest/mcp-gateway), register two backends:

```json
"servers": {
  "skills": {
    "url": "http://skills:6004/ro/mcp",
    "allowed_groups": ["readers", "admins"],
    "tools": ["list_skills", "get_skill"]
  },
  "skills-admin": {
    "url": "http://skills:6004/rw/mcp",
    "allowed_groups": ["admins"],
    "tools": ["list_skills", "get_skill", "register_skill"]
  }
}
```

## Storage

Skills live in `SKILLS_DATA_DIR` (default `/data/skills`) as `<name>/v<N>/<path>`. Each
registration is written to a temporary folder and renamed to `v<N+1>`, so readers never see a
partial version. Older versions are kept, so a skill can be rolled back.

## Running

```sh
docker run -d --name skills -v skills-data:/data/skills ghcr.io/sellest/mcp-skills@sha256:<digest>
```

Settings come from environment variables: `SKILLS_DATA_DIR`, `SKILLS_HOST` (default `0.0.0.0`) and
`SKILLS_PORT` (default `6004`).

## Development

```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```
