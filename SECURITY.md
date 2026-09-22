# Security Policy

## Scope and intended deployment

This project is built and verified as a **local/portfolio deployment** (`docker compose up`
on a developer machine). It does not implement authentication, per-user accounts, rate
limiting, or TLS termination — those are deliberately out of scope for the current version,
not overlooked. If you deploy this somewhere network-reachable, you are responsible for
adding them (a reverse proxy with TLS + auth in front of it is the minimum). See
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for the intended local setup.

## Data handled

- No user accounts, no personal data, no payment data.
- The only persisted state is the aWATTar price cache (`PriceCache`, a single JSON file) —
  public market price data, nothing sensitive.
- `capacity_kw` and appliance `loads` submitted to `/api/schedule` are not persisted server
  side at all; they exist only for the duration of the request.

## Reporting a vulnerability

If you find a security issue (e.g., a way to crash the backend with a malformed request, an
injection vector, or a CORS misconfiguration beyond what's documented above), please report
it privately rather than opening a public issue:

- Email **chovatiajaimin@gmail.com** with a description and, if possible, reproduction
  steps.
- You should get an acknowledgment within a few days. As noted in
  [`CONTRIBUTING.md`](CONTRIBUTING.md#project-status), this is currently a solo-maintained
  project, so please be patient — but security reports are prioritized over feature work.

Please don't test for vulnerabilities against any deployment of this project you don't
control (e.g., don't probe a live demo instance beyond confirming a suspected issue).

## Known, accepted limitations (not vulnerabilities)

- No rate limiting on `/api/schedule` — a request with a very large number of `loads` could
  be slow, since `multi_load_schedule` is worst-case exponential in load count (documented,
  intentional tradeoff — see
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#why-the-multi-load-scheduler-is-a-hand-written-backtracking-search-instead-of-calling-a-solver-directly-in-the-request-path)).
  If you deploy this publicly, put a reasonable cap on the number of loads per request at
  your reverse proxy or in `main.py`.
- `CORS_ORIGINS` defaults to `http://localhost:5173` and must be explicitly set to your
  real frontend origin in any other deployment — it is intentionally not wildcarded.
