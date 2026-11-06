# mcp-skills: shared AI skills over MCP

These are notes for a new session. Nothing has been built yet; this folder holds only this file.
The user (sellest) already created the GitHub repo `sellest/mcp-skills`; it is private. Run `git init`
here and add that remote.

## Goal

This is a small, generic MCP server that shares **Markdown-only skills** with ChatGPT users through
our mcp-gateway. German (a 1C developer and the first client) asked for it. The end users are his
family and friends, who have no technical knowledge: they only talk to ChatGPT. So nothing is
installed on their computers. ChatGPT reads a skill's text online and follows it.

The project has to stay generic, with nothing about 1C or German in it, because other clients will
reuse it.

A skill uses the Codex/ChatGPT skill format: a folder with `SKILL.md`, whose YAML front matter has
`name:` and `description:`, plus optional Markdown files that `SKILL.md` links to, such as
`references/index.md`. One real example is
`C:\Users\selle\.codex\skills\cinematic-fantasy-characters`. Its images are out of scope.

## The tools (the user decided these; don't redesign them)

| Tool | Behaviour | Who |
|---|---|---|
| `list_skills` | Returns each registered skill's name, description and current version | readers |
| `get_skill(name, path="SKILL.md")` | Returns the text of `SKILL.md`, or of another `.md` file in that skill | readers |
| `register_skill(name, files)` | `files` maps a path to its text and must contain `SKILL.md`. It adds a new skill, or a new version of an existing one | admins only (German and the user at first) |

The user explicitly rejected exposing **one tool per skill**. Keep exactly these three tools.

Rules:
- `register_skill` validates its input:
  - `SKILL.md` has front matter, and its `name:` and `description:` are not empty;
  - the front-matter `name` equals `name`;
  - the name matches a slug, for example `[a-z0-9][a-z0-9-]{0,63}`;
  - every path is relative and ends in `.md`, with no `..`, no backslashes and no absolute paths;
  - the total size is about 200 KB at most.
- Versions: every registration becomes `v<N+1>`. Keep the previous versions so we can roll back,
  and a later admin tool can do the rollback.
- The descriptions of `list_skills` and `get_skill` must tell the model to check the skill list
  before a task and then follow the skill's text. This is what helps it find skills.

Out of scope for now:
- images and binary files;
- installing skills locally (zips, download links, Codex `~/.codex/skills`);
- running scripts that come with skills;
- per-skill permissions.

## Permissions: the gateway constraints decide the design

Users connect to `sellest/mcp-gateway` (at `D:\Python\Projects\mcp-gateway`, FastMCP 3.x). The
gateway reaches this server as a backend. What we know about the gateway, version 0.1.1:
- It uses a ProxyProvider with an **operator token**. It does **not** pass on the end user's
  identity, so this server cannot know who is calling.
- Access is checked **per backend server**, through `allowed_groups` (Pocket ID OIDC groups).
- Backend URLs cannot contain a query string.
- Server IDs must match `[a-z][a-z0-9-]{0,31}`.
- Tools are exposed as `<server>_<tool>`.
- ChatGPT sees only `search_tools`, `call_tool` and `gateway_status`, through a RegexSearchTransform.
- The user does **not** want client-specific code in mcp-gateway. Integration must be config only.

So the server serves two MCP endpoints from one process, sharing the same storage:
- `/ro/mcp` exposes `list_skills` and `get_skill`. Gateway backend `skills`, with readers' groups.
- `/rw/mcp` exposes all three tools. Gateway backend `skills-admin`, with admin groups only.

Auth (checked in the german-1c-dev session and the mcp-german-1c deploy config):
- End users log in to the user's Pocket ID (`https://static.123.204.243.132.clients.console.lat`)
  through ChatGPT, using client `mcp-german-chatgpt`. Tokens are for the resource
  `https://131401.ip-ns.net/mcp` with scope `gateway:use`. The gateway checks the token and the
  `groups` claim, then applies `allowed_groups` per backend.
- Backends have **no auth of their own**. The gateway reaches the toolkit with no `token_file`, over
  the internal Docker network `backend` (`internal: true`), and mcp-skills works the same way: no
  auth code and no published port, only that internal network.
- Adding the skills backends changes nothing in Pocket ID: same API, scope and client. Later, family
  users need Pocket ID accounts and a group.
- The gateway also needs a `tools` allowlist per backend: `skills` gets `[list_skills, get_skill]`,
  and `skills-admin` gets all three.

## Stack and conventions (follow the sibling repos)

- Python 3.12. The MCP SDK is FastMCP, as in `mcp-gateway` (`fastmcp==3.4.11`). `mcp-german-1c` uses
  the plain `mcp>=1.26`. Choose one and pin it.
- `pyproject.toml` and `ruff` as in mcp-gateway. Tests with pytest, using temporary storage.
- A Dockerfile based on `python:3.12-slim`. Storage goes on a volume such as `/data/skills/<name>/v<N>/...`,
  with atomic writes: write to a temp dir, then rename.
- A GitHub Actions workflow that builds and pushes `ghcr.io/sellest/mcp-skills`. See
  `mcp-german-1c/.github/workflows/https-image.yml` for reference. Clients pin the image by
  `@sha256` digest.
- Keep it small. The first host, German's VPS, has 1 GB of RAM and about 1.6 GB of free disk.
  Aim for under 128 MB of memory.

## Integration after the server works (lives in `D:\Python\Projects\mcp-german-1c`, not here)

- Add a pin to `deploy/images.env`.
- Add a `skills` service to `deploy/de/compose.yaml`. That stack runs in rootless Docker as user
  `mcp-german` on 193.163.85.27 (`https://131401.ip-ns.net`).
- Add two backends, `skills` and `skills-admin`, to the gateway config that
  `deploy/msk/render-gateway.py --pilot-env deploy/de/pilot.env` renders. Groups (the user decided):
  `skills` → `onec-test-operators`, `onec-prod-users`; `skills-admin` → `onec-test-operators` only.
  The user will create a family Pocket ID group later and add it to `skills`.
- `mcp-german-1c/skills/` already contains two skills (`calling-1c-rest-api-via-curl`,
  `composing-1c-queries`). They are good test material. Ask before registering them.

## Working rules from the user

- Merge PRs only after the user explicitly says "merge". Work on branches, one PR per change.
- Never put secrets in chat or in Git. The user types tokens and passwords on servers themselves.
- Deploy only code that is committed and pushed. Server changes go through committed scripts.
- On German's DE host, leave his VPN alone (sing-box, nginx, warp, system Docker).
- The user writes in English or Russian. Skills and tool texts for end users can be Russian.

## First steps

1. `git init`, add the remote, and open an issue with this spec in `sellest/mcp-skills`.
2. Write the server, its storage and its tests. Create a PR.
3. Add the image workflow. Merge only after the user says so, and record the image digest.
4. Integrate in mcp-german-1c with a separate PR. Then deploy through the `deploy-pilot` workflow
   (target `de`), or by hand following `deploy/de/README.md`.
5. Test in ChatGPT: list, get, register. Check that a user without the admin group can't see
   `register_skill`.
