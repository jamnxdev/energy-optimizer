## What and why

<!-- What does this change, and why -- the motivation matters more than a restatement of the diff. -->

## Related issue

<!-- Closes #... , or "none -- small fix" -->

## Testing

- [ ] `pytest -q` passes (backend), if backend code changed
- [ ] `npx tsc -b --noEmit` and `npm run lint` pass (frontend), if frontend code changed
- [ ] If `backend/app/scheduler.py`'s multi-load logic changed: re-ran
      `python analysis/validate_optimum.py --scenarios 200` — result:
- [ ] Manually verified in a real browser (for UI changes) — describe what you checked:

## Checklist

- [ ] Updated `docs/API.md` if the request/response shape of an endpoint changed
- [ ] Updated `docs/ARCHITECTURE.md` if this changes a documented design decision
- [ ] Added/updated tests for the behavior change
- [ ] Added an entry to `CHANGELOG.md` under `[Unreleased]`
