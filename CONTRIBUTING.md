# Contributing

1. Keep API and UI contracts explicit and versioned.
2. Never label sample data as real provider data.
3. Add backend tests for new endpoint behavior and household authorization.
4. Add frontend tests for new interaction/state transitions.
5. Verify D-pad focus and Back behavior with both keyboard preview and target hardware.
6. Do not add secrets, raw media, transcripts, or personal household data to fixtures or logs.
7. Run `python -m pytest` in `backend/`, then `npm test` and `npm run build` in `frontend/`.
8. Document any untested platform assumptions or external providers in `docs/`.
