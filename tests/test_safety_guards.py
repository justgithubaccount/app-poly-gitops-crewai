from auto_k8s_pilot.tools.cloudflare_dns_tool import CloudflareDNSTool
from auto_k8s_pilot.tools.mcp_k8s_tool import MCPK8sTool


def test_cloudflare_upsert_is_blocked_when_mutations_are_disabled(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "test-zone")
    monkeypatch.setenv("ALLOW_MUTATING", "false")

    result = CloudflareDNSTool()._run(
        op="upsert", name="api.example.com", type="A", content="192.0.2.1"
    )

    assert result == "ERROR: Mutating ops disabled (ALLOW_MUTATING=false)"


def test_mcp_config_snippet_uses_current_settings(monkeypatch):
    monkeypatch.setenv("MCP_K8S_SERVER_URL", "wss://mcp.example.test")
    monkeypatch.setenv("MCP_K8S_API_KEY", "test-key")

    result = MCPK8sTool()._run(op="config_snippet")

    assert '"url": "wss://mcp.example.test"' in result
    assert '"Authorization": "Bearer test-key"' in result
