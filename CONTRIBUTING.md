# Contributing

Thanks for taking a look at this project. A note on context first, then the how-to.

## Project status

This is currently a **solo-maintained portfolio project**. It's structured the way a
genuinely open-source project should be — clear docs, tests, a real contribution process —
but there isn't an active contributor community behind it yet, and issue/PR response times
may be slow. If you send a PR, it will be read and taken seriously; just don't expect
Slack-speed turnaround. If that changes, this section will be updated to say so.

That said, everything below reflects how the project is actually meant to be worked on,
solo or not — it's not aspirational boilerplate.

## Before you start

1. Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — most "why is it built this way"
   questions are answered there, including a few decisions that look like they could be
   simplified but are deliberate.
2. Read [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for how to actually run and test the
   thing.
3. For anything beyond a small fix, open an issue describing what you want to change and
   why *before* writing code. This project has a fairly specific, already-validated design
   for its hardest piece (the multi-load scheduler) — see
   [Touching the scheduler](#touching-the-scheduler) — and a heads-up avoids wasted work on
   both sides.

## Ways to contribute

- **Bug reports** — use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).
  Include what you expected, what happened, and how to reproduce it (ideally: the exact
  `loads` payload you sent to `/api/schedule`, and whether the backend or frontend is
  involved).
- **Feature requests** — use the
  [feature request template](.github/ISSUE_TEMPLATE/feature_request.md). See
  [Known gaps](#known-gaps) below for what's already planned vs. what would be new scope.
- **Documentation fixes** — typos, unclear explanations, missing setup steps. These are
  always welcome and don't need an issue first.
- **Code contributions** — see the workflow below.

## Development workflow

1. Fork the repo and create a branch off `main`: `git checkout -b fix/short-description`.
2. Make your change. Match the existing style in the file you're editing rather than
   introducing a new convention — this codebase doesn't use a formatter/linter config
   beyond `oxlint` on the frontend, so consistency is by eye.
3. Add or update tests for any behavior change. See
   [`docs/DEVELOPMENT.md#tests`](docs/DEVELOPMENT.md#tests) for how to run the suite.
   - Backend: a behavior change to `scheduler.py` or `price_fetcher.py` without a test
     covering it will be asked to add one before merge — both files have a history of real
     bugs (float drift, a staleness-flagging bug) that were caught specifically *because*
     the tests were adversarial, not just happy-path.
   - Frontend: see [Known gaps](#known-gaps) — there's no test suite yet, so verify with
     `tsc`/lint plus manual browser testing and describe what you checked in the PR.
4. If you touched `backend/app/scheduler.py`'s multi-load logic, re-run the MILP validation
   script (`python analysis/validate_optimum.py --scenarios 200`) and mention the result in
   your PR. A scheduler change that isn't re-validated against the true optimum is exactly
   the kind of silent regression this script exists to catch.
5. Open a PR using the [PR template](.github/PULL_REQUEST_TEMPLATE.md). Describe *why*, not
   just *what* — the "why" is what reviewers (and future readers of `git log`) actually
   need.

## Touching the scheduler

`backend/app/scheduler.py`'s `multi_load_schedule` is the most carefully-reasoned piece of
this codebase — read its docstring and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#why-the-multi-load-scheduler-is-a-hand-written-backtracking-search-instead-of-calling-a-solver-directly-in-the-request-path)
before changing its algorithm. In particular:

- It's an **exact** search, not a heuristic — that claim is load-bearing (it's what makes
  the savings numbers trustworthy) and is backed by `analysis/validate_optimum.py`, not
  just the unit tests. A change that trades exactness for speed needs to say so explicitly
  and update the README's framing, not just pass the existing tests.
- It's worst-case exponential in load count. This is a documented, accepted limitation at
  household scale — "this could time out with 50 loads" is not a bug report against this
  project's stated scope, though a PR that adds an explicit guard/error for absurdly large
  inputs would be welcome.

## When to touch the API contract

`Load`/`ScheduledRun` (`backend/app/models.py`), the FastAPI request/response models
(`backend/app/main.py`), `frontend/src/types.ts`, and [`docs/API.md`](docs/API.md) all
describe the same shapes and must be updated together. There's exactly one consumer of this
API (this repo's own frontend), so a breaking change is acceptable, but a PR that changes
the wire format on one side without the other three will not build/type-check and won't be
merged.

## Adding a dependency

Ask "does the problem actually require this" before reaching for a library — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#why-the-frontend-has-no-state-management-library)
and the Gantt-chart note in `local-doc`'s history for two cases where the answer was no. A
dependency is a maintenance cost and an attack surface, not a free win. If you do add one,
say in the PR what problem it solves that hand-rolling wouldn't.

## Known gaps

Listed here so they're not mistaken for oversights, and so a PR targeting one of them isn't
duplicated effort:

- **No frontend test suite.** Intended direction: Vitest + React Testing Library, starting
  with `ApplianceForm` (validation/preset logic) and `ScheduleSummary` (the
  stale/infeasible warning branches — real conditional logic, worth locking down).
- **No historical savings analysis.** `analysis/` currently only has the MILP validation
  script; a pandas-based analysis of savings across real past aWATTar days (median/IQR
  distribution) is planned but not started.
- **No persisted appliance configuration.** Loads are entered fresh each session; simple
  `localStorage` persistence would be a reasonable, low-risk addition.
- **No CI pipeline configured yet** (no GitHub Actions workflow in `.github/workflows/`) —
  the test suites above are run locally, not automatically on PRs. A CI workflow running
  `pytest` and `tsc --noEmit` would be a good first contribution.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating,
you're expected to uphold it.

## License

By contributing, you agree your contributions will be licensed under the project's
[MIT License](LICENSE).
