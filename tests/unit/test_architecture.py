from app.agent import root_agent
from app.mcp_server import handle_request


def test_root_agent_has_specialist_sub_agents() -> None:
    names = {agent.name for agent in root_agent.sub_agents}

    assert {
        "source_intake_agent",
        "reconciliation_agent",
        "github_pr_agent",
        "connector_draft_agent",
        "security_approval_agent",
    }.issubset(names)


def test_mcp_server_lists_and_calls_tools(tmp_path, monkeypatch) -> None:
    from app import ledger

    monkeypatch.setattr(ledger, "LEDGER_ROOT", tmp_path / "ledger")

    listed = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tool_names = {tool["name"] for tool in listed["result"]["tools"]}
    assert "ingest_source" in tool_names
    assert "request_approval" in tool_names
    assert "execute_approved_action" in tool_names

    called = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "ingest_source",
                "arguments": {
                    "content": "Action: create the MCP bridge.",
                    "source_type": "freeform",
                    "metadata_json": "{}",
                },
            },
        }
    )

    assert called["result"]["content"][0]["type"] == "text"
    assert "SRC-001" in called["result"]["content"][0]["text"]
