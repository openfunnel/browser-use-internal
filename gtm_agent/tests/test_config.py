from gtm_agent.config import AgentConfig


def test_default_agent_config():
    config = AgentConfig()
    assert config.max_steps == 24
    assert config.extraction_fields == ["name", "context"]
