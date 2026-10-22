# Data Provenance Policy

## Current fixture

`demo-football-001` is an invented sample football event. Player names, locations, speeds, score and timeline exist only to exercise the experience end-to-end. `source_type=sample` must remain visible in the UI/API and must never be changed to `provider` unless records genuinely originate from an approved data provider.

## Production provider adapter requirements

Before connecting live data, document:

- Provider name and account/contract owner.
- Rights to display team/player identifiers, scores, event timestamps and tracking data.
- Attribution and freshness requirements.
- Rate limits, cache rules and allowed derived works.
- Provider record ID and `observed_at` timestamp for each update.
- Normalized coordinate convention and player identity mapping.
- Data retention and correction handling.

The current repo does not include licensed live sports data, streaming playback rights, tracking-grade coordinates or provider credentials.
