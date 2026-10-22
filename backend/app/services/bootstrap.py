from sqlalchemy.orm import Session

from app.models import SportsEvent
from app.services.sample_data import SAMPLE_EVENT


def seed_sample_data(db: Session) -> None:
    if db.get(SportsEvent, SAMPLE_EVENT["id"]):
        return
    db.add(SportsEvent(**SAMPLE_EVENT))
    db.commit()
