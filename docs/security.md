# Security and Privacy Checklist

## Must be complete before public launch

- [ ] Cognito Hosted UI Authorization Code + PKCE configured with exact callback/logout URLs.
- [ ] Local `DEMO_MODE` disabled and local JWT secret removed from production configuration.
- [ ] PostgreSQL TLS, restricted security group, backups, restore test and migration job configured.
- [ ] CORS restricted to exact deployed frontend origin(s); no wildcard origin with credentials.
- [ ] API Gateway/WAF request throttles and abuse alarms configured.
- [ ] Secrets live in Secrets Manager/secure environment variables, never in Git or frontend bundle.
- [ ] CI dependency and secret scans run on pull requests.
- [ ] Logs are reviewed to ensure no token, raw audio, raw frames or unnecessary household behavior is recorded.
- [ ] Household data deletion, backup retention and external-provider retention policies documented.
- [ ] Data processing notice, consent UX, privacy contact and relevant legal review completed.
- [ ] Threat model and authorization tests cover cross-household access.

## Camera policy

- Raw camera frames are processed locally by the current UI implementation.
- The API has no raw-media upload endpoint.
- Derived movement metrics are sent only for a session with `consent_recorded=true`.
- A browser/device can still access the camera only after its own permission prompt and on a supported secure origin.
- Pose estimation values are approximate and are not medical advice or a validated athletic scoring system.
