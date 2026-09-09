import pytest
from tender_lens.config import Settings
from tender_lens.portfolio import PortfolioRateGate


def test_public_demo_rejects_local_live_models():
    with pytest.raises(ValueError, match="fake or MWS"):
        Settings(portfolio_demo=True, ai_mode="live", portfolio_secret="x" * 48)


def test_public_demo_requires_signing_secret():
    with pytest.raises(ValueError, match="signing secret"):
        Settings(portfolio_demo=True, ai_mode="fake", portfolio_secret="")


def test_public_demo_accepts_mws_with_credentials():
    settings = Settings(
        portfolio_demo=True,
        portfolio_secret="x" * 48,
        ai_mode="mws",
        mws_project="tenderlens-demo",
        mws_api_key="secret",
        mws_generation_model="generation-deployment",
    )
    assert settings.active_embedding_model == "bge-m3"
    assert settings.mws_openai_base_url.endswith("/projects/tenderlens-demo/openai/v1")


@pytest.mark.parametrize("field", ["mws_project", "mws_api_key"])
def test_mws_requires_project_and_key(field):
    values = {"mws_project": "tenderlens-demo", "mws_api_key": "secret"}
    values[field] = ""
    with pytest.raises(ValueError, match="MWS_"):
        Settings(ai_mode="mws", **values)


@pytest.mark.asyncio
async def test_portfolio_global_rate_gate_resets_each_minute():
    current = [125.0]
    gate = PortfolioRateGate(2, clock=lambda: current[0])

    assert await gate.consume() is None
    assert await gate.consume() is None
    assert await gate.consume() == 55

    current[0] = 180.0
    assert await gate.consume() is None
