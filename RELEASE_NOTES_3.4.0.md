# Migraine Risk Card 3.4.0 — Quality / Reliability

This release keeps the v3 scoring model unchanged and focuses on hidden correctness and lifecycle edge cases.

## Standalone card

- Fixed Recorder history for `weather.*` pressure/temperature attributes by requesting non-significant updates and timestamping them with `last_updated`.
- Added pressure and weather-unit attributes to the render hash, so pressure-only updates repaint immediately.
- Normalised Fahrenheit forecast temperatures before tomorrow scoring.
- Made forecast day selection use the Home Assistant timezone.
- Replaced endless history loading with a clear unavailable state when Recorder data is insufficient.
- Hardened translation loading for multiple cards and transient failures.
- Switched the one-shot forecast fallback from admin-only `execute_script` to response-capable `call_service` (supported by the minimum HA 2024.6) and added long-term recovery retries.
- Cleaned old history/forecast subscriptions when editor source entities change.
- Removed stale forecast UI when a configured forecast entity disappears.
- Recognised `storm` / `thunderstorm` current weather conditions.
- Guarded duplicate custom-element/resource registration.
- Removed translated editor HTML injection.

## Optional compatibility sensor package

The package remains optional and is not used by the standalone v3.x card. For users who still rely on it:

- Replaced reset-based pressure/temperature tracking with true rolling Statistics windows.
- Added unit-aware °F/°C and kPa/mmHg/inHg/psi/hPa conversion.
- Added support for lower station pressure at altitude.
- Removed absolute pressure/temperature device classes from delta sensors.
- Normalised tomorrow forecast temperatures to °C before scoring, including legacy helper-sensor inputs.
- Propagated pressure/risk unavailability instead of presenting a false `Low` state when required pressure data is missing.

## Project quality

- Added Node regression tests for conversions, rolling calculations, forecast scoring, timezone handling and critical HA API invariants.
- Stopped ignoring new `dist/` files in `.gitignore`.
- Consolidated HACS validation into one pinned workflow.
- Updated README version and compatibility wording.
