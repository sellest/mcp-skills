import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from mcp_skills.server import build_server, create_app

from .conftest import skill_md

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


async def tool_names(server):
    async with Client(server) as client:
        return {tool.name for tool in await client.list_tools()}


async def test_read_only_server_hides_register(store):
    assert await tool_names(build_server(store, admin=False)) == {"list_skills", "get_skill"}
    assert await tool_names(build_server(store, admin=True)) == {
        "list_skills",
        "get_skill",
        "register_skill",
    }


async def test_descriptions_tell_the_model_to_check_skills(store):
    async with Client(build_server(store, admin=False)) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    assert "before starting any task" in tools["list_skills"].description.lower()
    assert "follow" in tools["get_skill"].description.lower()
    assert tools["list_skills"].annotations.readOnlyHint is True


async def test_register_then_read_through_mcp(store):
    files = {"SKILL.md": skill_md("demo"), "references/a.md": "# A"}
    async with Client(build_server(store, admin=True)) as admin:
        result = await admin.call_tool("register_skill", {"name": "demo", "files": files})
        assert result.data["version"] == 1
    async with Client(build_server(store, admin=False)) as reader:
        listed = await reader.call_tool("list_skills", {})
        assert listed.data["skills"] == [
            {"name": "demo", "description": "Does a thing. Use when the user asks.", "version": 1}
        ]
        main = await reader.call_tool("get_skill", {"name": "demo"})
        assert main.data["text"] == files["SKILL.md"]
        assert main.data["files"] == ["SKILL.md", "references/a.md"]
        ref = await reader.call_tool("get_skill", {"name": "demo", "path": "references/a.md"})
        assert ref.data["text"] == "# A"


async def test_errors_are_readable(store):
    async with Client(build_server(store, admin=True)) as admin:
        with pytest.raises(ToolError, match="does not match"):
            await admin.call_tool(
                "register_skill", {"name": "demo", "files": {"SKILL.md": skill_md("x")}}
            )
        with pytest.raises(ToolError, match="not registered"):
            await admin.call_tool("get_skill", {"name": "missing"})


def _rpc(client, url, method, params=None, id_=1):
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    response = client.post(url, json=body, headers=MCP_HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def _initialize(client, url):
    return _rpc(
        client,
        url,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    )


def test_http_endpoints(store):
    store.register("demo", {"SKILL.md": skill_md("demo")})
    with TestClient(create_app(store)) as client:
        assert client.get("/health").json()["status"] == "ok"
        for prefix, expected in (
            ("/ro", {"list_skills", "get_skill"}),
            ("/rw", {"list_skills", "get_skill", "register_skill"}),
        ):
            url = f"{prefix}/mcp"
            assert "serverInfo" in _initialize(client, url)["result"]
            tools = _rpc(client, url, "tools/list", id_=2)["result"]["tools"]
            assert {tool["name"] for tool in tools} == expected
        called = _rpc(
            client,
            "/ro/mcp",
            "tools/call",
            {"name": "register_skill", "arguments": {"name": "x", "files": {}}},
            id_=3,
        )
        assert "error" in called or called["result"].get("isError")
        assert [s.name for s in store.skills()] == ["demo"]
