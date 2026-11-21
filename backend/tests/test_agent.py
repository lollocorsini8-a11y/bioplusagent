from types import SimpleNamespace

import app.agent as agent_module


def test_agent_run_disables_agno_telemetry(monkeypatch):
    captured = {}

    class FakeGroq:
        def __init__(self, id):
            captured["model_id"] = id

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self, prompt):
            return SimpleNamespace(content="Risposta")

    monkeypatch.setattr("agno.agent.Agent", FakeAgent)
    monkeypatch.setattr("agno.models.groq.Groq", FakeGroq)
    monkeypatch.setattr(
        agent_module,
        "get_settings",
        lambda: SimpleNamespace(groq_api_key="test-key", groq_model="test-model"),
    )
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    assert agent_module._run_agent("prompt sintetico", []) == "Risposta"
    assert captured["telemetry"] is False
