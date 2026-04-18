# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `RedisSemaphore.attach()` to connect to an existing semaphore without passing `count`, polling metadata until the creator initializes the pool (optional `timeout`; raises `RedisSemaphoreTimeoutError`).
- `RedisSemaphore.get_count()` returning the configured permit count.
- `RedisSemaphoreCountMismatchError` when `create()` is called with a `count` that does not match the existing semaphore.
- Redis metadata key (`:meta`) storing `count` alongside the permit list; Lua init script reads/writes it and returns the stored count for validation.

### Changed

- **Breaking:** Replaced `SemaphoreInitStrategy.SETNX` with `SemaphoreInitStrategy.OPTIMISTIC_LOCKING`; non-Lua initialization now uses `WATCH` / `MULTI` / `EXEC` instead of `SETNX` plus a separate init key.
- **Breaking:** `RedisSemaphore` constructor now requires an explicit `count` (no default).
- `RedisSemaphore.create()` validates that an existing semaphore’s count matches the requested value (Lua and optimistic-locking paths).

## [1.0.0] - 2026-02-24

### Added

- Initial published release of `redsync`.
