# Sync Service — Review Notes

Tracking non-blocking observations raised during wave reviews.

## Wave 1

- **No shared lock on read**: `SnapshotReader` doesn't acquire `LOCK_SH` — consistent with `JsonStateManager` pattern. Atomic write + small JSON makes torn reads unlikely in practice.
- **No test for `wait_for_first_sync`**: Trivial poll loop, will be exercised in Wave 4 integration.
- **Type style**: `SyftBgConfig.syftbox_root` is `str | None`, service configs use `Optional[Path]`. Pre-existing pattern across all services.
- **No explicit `sync:` YAML in test fixture**: Tests only cover default-merge path. YAML parsing is Pydantic `model_validate`, already tested across other services.
