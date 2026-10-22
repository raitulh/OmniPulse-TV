from datetime import datetime, timezone

SAMPLE_EVENT = {
    "id": "demo-football-001",
    "sport": "football",
    "league": "OmniPulse Sample League",
    "title": "North City vs Harbor United",
    "home_team": "North City",
    "away_team": "Harbor United",
    "status": "sample",
    "source_type": "sample",
    "score_home": 2,
    "score_away": 1,
    "starts_at": datetime.now(timezone.utc),
    "timeline": [
        {"id": "evt-001", "clock_seconds": 210, "minute": 4, "type": "pass", "team": "North City", "player_id": "player-07", "target_player_id": "player-12", "label": "Progressive pass", "source_type": "sample"},
        {"id": "evt-002", "clock_seconds": 1425, "minute": 24, "type": "shot", "team": "North City", "player_id": "player-12", "label": "Shot on target", "source_type": "sample"},
        {"id": "evt-003", "clock_seconds": 2680, "minute": 45, "type": "pass", "team": "Harbor United", "player_id": "player-09", "target_player_id": "player-04", "label": "Switch of play", "source_type": "sample"},
    ],
    "tactical": {
        "field": {"width": 100, "height": 100, "coordinate_system": "normalized-0-100", "source_type": "sample"},
        "players": [
            {"id": "player-07", "name": "A. Rivera", "team": "North City", "role": "Midfielder", "x": 33, "y": 42, "speed_kph": 21.4, "source_type": "sample"},
            {"id": "player-12", "name": "M. Chen", "team": "North City", "role": "Forward", "x": 58, "y": 34, "speed_kph": 26.1, "source_type": "sample"},
            {"id": "player-04", "name": "J. Okafor", "team": "Harbor United", "role": "Defender", "x": 67, "y": 58, "speed_kph": 19.2, "source_type": "sample"},
            {"id": "player-09", "name": "S. Rahman", "team": "Harbor United", "role": "Midfielder", "x": 42, "y": 68, "speed_kph": 23.0, "source_type": "sample"},
            {"id": "player-18", "name": "T. Brooks", "team": "North City", "role": "Winger", "x": 72, "y": 24, "speed_kph": 28.3, "source_type": "sample"},
            {"id": "player-03", "name": "L. Silva", "team": "Harbor United", "role": "Goalkeeper", "x": 91, "y": 50, "speed_kph": 0.0, "source_type": "sample"},
        ],
        "connections": [
            {"from": "player-07", "to": "player-12", "label": "pass", "source_type": "sample"},
            {"from": "player-12", "to": "player-18", "label": "run option", "source_type": "sample"},
        ],
    },
}
