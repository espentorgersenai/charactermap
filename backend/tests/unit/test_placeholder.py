def test_settings_load():
    from app.config import settings
    assert settings.daily_cost_limit_usd == 5.00
