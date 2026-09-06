import pytest
from tender_lens.config import Settings

def test_public_demo_rejects_live_models():
    with pytest.raises(ValueError, match="fake AI"):
        Settings(portfolio_demo=True, ai_mode="live", portfolio_secret="x" * 48)

def test_public_demo_requires_signing_secret():
    with pytest.raises(ValueError, match="signing secret"):
        Settings(portfolio_demo=True, ai_mode="fake", portfolio_secret="")
