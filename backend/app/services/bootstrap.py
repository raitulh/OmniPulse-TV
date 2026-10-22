import logging
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SportsEvent
from app.services.sample_data import SAMPLE_EVENT
from app.services.sports_provider import ApiFootballProvider

logger = logging.getLogger(__name__)


def seed_sample_data(db: Session) -> None:
    if not db.get(SportsEvent, SAMPLE_EVENT["id"]):
        db.add(SportsEvent(**SAMPLE_EVENT))
        db.commit()


def sync_live_sports_events(db: Session, max_items: int = 6) -> int:
    """Fetches live/today football matches from API-Football and syncs into DB."""
    settings = get_settings()
    if settings.sports_provider.lower() not in ("api-football", "apifootball") or not settings.sports_provider_api_key:
        return 0

    try:
        provider = ApiFootballProvider(api_key=settings.sports_provider_api_key)
        raw_fixtures = provider.fetch_live_or_today_fixtures(max_items=max_items)
        synced_count = 0

        for item in raw_fixtures:
            event_dict = provider.transform_fixture_to_event(item)
            event_id = event_dict["id"]
            existing = db.get(SportsEvent, event_id)
            if existing:
                existing.score_home = event_dict["score_home"]
                existing.score_away = event_dict["score_away"]
                existing.status = event_dict["status"]
                existing.timeline = event_dict["timeline"]
                existing.tactical = event_dict["tactical"]
            else:
                db.add(SportsEvent(**event_dict))
            synced_count += 1

        db.commit()
        logger.info("api_football_sync_success count=%s", synced_count)
        return synced_count
    except Exception as exc:
        logger.error("api_football_sync_error error=%s", exc, exc_info=True)
        db.rollback()
        return 0
