# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project does not yet cut
versioned releases, so entries are grouped under `[Unreleased]` until the first tag.

## [Unreleased]

### Added
- Full documentation set: architecture guide, API reference, development guide,
  contribution guidelines, code of conduct, security policy (this pass).
- Per-appliance schedule timeline (`ScheduleTimeline`) and per-hour capacity-usage chart
  (`CapacityChart`) in the frontend.
- React + TypeScript frontend: live price chart with schedule overlays, appliance
  configuration form, savings summary.
- FastAPI `/api/prices` and `/api/schedule` endpoints; PuLP MILP validation confirming the
  backtracking scheduler matches the true optimum across 150+ generated scenarios with zero
  mismatches.
- Multi-load shared-capacity scheduler: exact branch-and-bound backtracking search.
- aWATTar day-ahead price fetcher with disk cache, graceful degradation (stale-flagged
  fallback) on API failure, and a hard 48h staleness ceiling.

### Known gaps
See [`CONTRIBUTING.md#known-gaps`](CONTRIBUTING.md#known-gaps) — no frontend test suite,
no historical savings analysis, no persisted appliance config, no CI pipeline yet.
