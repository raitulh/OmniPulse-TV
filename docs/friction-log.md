# Friction Log Template

Record only issues observed while developing/testing. Do not fabricate friction logs or claim an Amazon review bonus.

For each issue, record:

- **Environment:** device/simulator, OS/version, browser/WebView version, resolution.
- **Reproduction:** exact steps and remote key sequence.
- **Expected behavior:** one clear sentence.
- **Actual behavior:** one clear sentence.
- **Impact:** blocked flow, focus loss, visible jank, or recoverable inconvenience.
- **Evidence:** safe screenshot/short screen recording, sanitized log lines, request ID.
- **Root cause:** confirmed or still unknown.
- **Fix:** commit/PR, with tests.
- **Retest:** environment and result after the fix.

Potential areas to test (not yet asserted as observed): directional focus trapping in overlays; Back behavior/history restoration; focus visibility during API loading; pose canvas frame rate; memory use after repeated screen transitions; camera permission denial; speech API unavailable; sample-vs-provider provenance visibility.
