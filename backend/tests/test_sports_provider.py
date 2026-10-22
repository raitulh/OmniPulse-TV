from datetime import datetime, timedelta, timezone
from app.services.sports_provider import (
    OptaSportsProvider,
    SportradarProvider,
    SampleSportsProvider,
    get_sports_provider,
    clamp,
)


def test_clamp_function():
    assert clamp(-5.0) == 0.0
    assert clamp(105.4) == 100.0
    assert clamp(55.234) == 55.23


def test_opta_provider():
    provider = OptaSportsProvider()
    assert provider.provider_id() == "opta"
    assert "Opta Sports" in provider.get_attribution()
    
    # Coordinate normalization
    x, y = provider.normalize_coordinates(45.5, 92.1)
    assert x == 45.5
    assert y == 92.1

    # Freshness
    now = datetime.now(timezone.utc)
    fresh, delay = provider.verify_freshness(now - timedelta(seconds=5), max_delay_seconds=30)
    assert fresh is True
    assert 4.0 <= delay <= 7.0

    stale, delay = provider.verify_freshness(now - timedelta(seconds=45), max_delay_seconds=30)
    assert stale is False
    assert delay >= 45.0


def test_sportradar_provider():
    provider = SportradarProvider()
    assert provider.provider_id() == "sportradar"
    assert "Sportradar" in provider.get_attribution()

    # Coordinates: 105m length, 68m width
    # 52.5m is exactly halfway length (50%)
    # 34m is exactly halfway width (50%)
    x, y = provider.normalize_coordinates(52.5, 34.0)
    assert round(x, 1) == 50.0
    assert round(y, 1) == 50.0


def test_sample_provider_default():
    provider = get_sports_provider()
    assert isinstance(provider, (SampleSportsProvider, OptaSportsProvider, SportradarProvider))
    assert provider.provider_id() == "sample"
    assert "SAMPLE DATA" in provider.get_attribution()
