# Phase 2 Launch — Onboarding Parents

> Cutover from the teacher-only pilot (Phase 1, `CONSENT_GATE_DISABLED=true`)
> to a pilot where parents receive magic links, sign consent, and access
> the Parent Portal.
>
> Companion to `PILOT_NOTES.md` (operational runbook) and `DIRECTOR_GUIDE.md`
> (end-user help). This file is the **launch checklist** — read top to bottom
> and tick each item.

---

## Readiness snapshot (from the codebase audit)

| Surface | Status | Notes |
|---|---|---|
| Consent gate switch + audit log | ✅ | `backend/utils/consent_gate.py`, audited to `consent_gate_audit` |
| `children_with_active_consent` view | ✅ | `alembic/versions/c2f8d35a9e4b_add_consent_view.py` — verify it's applied in prod |
| Magic-link token + email | ✅ | 7-day TTL, Resend API, falls back to log if `RESEND_API_KEY` unset |
| Consent form UI | ✅ | `frontend/console/src/portals/ConsentPortal/ConsentPage.jsx` |
| Child auto-activates on consent | ✅ | `backend/routers/consent.py:121` |
| Director adds parent contact → auto-triggers magic link | ✅ | Only when gate is enabled (`CONSENT_GATE_DISABLED=false`) |
| PII scrubbing in logs / Sentry | ✅ | `backend/utils/safe_logging.py` |
| **Pending-consent queue replay** | ❌ | TODO at `consent.py:123`. Events queued during the gap stay queued. |
| **WhatsApp parent push** | ❌ | Issue #12. Parents only see events if they open the portal. |
| **Resend consent link** endpoint | ❌ | No way to re-send a magic link once contact is created. |
| **Per-center feature flag** | ❌ | `CONSENT_GATE_DISABLED` is global; flips all centers at once. |

---

## Critical thing to understand before flipping the switch

During Phase 1 the director added kids and parent contacts with
`CONSENT_GATE_DISABLED=true`. Two side effects:

1. **Every kid is marked `ACTIVE` already** (the override in
   `onboarding_handlers.py:189` enrolls them straight to `ACTIVE` instead of
   `PENDING_CONSENT`).
2. **No `parental_consent` rows exist**, because the magic-link trigger in
   `create_parent_contact` is suppressed when the gate is disabled.

The production gate queries the `children_with_active_consent` view, which
INNER-JOINs `children` to `parental_consent`. **The moment you flip the
switch, every existing kid stops passing the gate** even though their
status is `ACTIVE` — because no consent record exists.

**Conclusion:** you must reset the existing pilot kids to `PENDING_CONSENT`
and route their parents through the magic-link flow BEFORE flipping the
switch. The wipe approach in `PILOT_NOTES.md §"Phase 1 → Phase 2 data
wipe"` is the cleanest way; the steps below assume you take it.

---

## Pre-launch — to build / confirm

### Must-have (block launch)
- [ ] **`RESEND_API_KEY` set in Railway** for the backend service. If
      missing, magic-link emails silently fall back to log lines.
- [ ] **`FRONTEND_BASE_URL` env var** points at the production console
      (e.g. `https://console.raina-pilot.com`) — the consent email's link
      uses this for the `/consent/<token>` URL.
- [ ] **Smoke-test the consent flow end-to-end on staging.** Add a child →
      add primary parent contact → check the email arrives → open the
      link in incognito → submit → confirm the child's status flips to
      `ACTIVE` and a `parental_consent` row appears.
- [ ] **Test event delivery for an ACTIVE-with-consent kid.** Send a
      WhatsApp voice memo, verify the event lands in `events` (not
      `pending_consent_queue`).
- [ ] **Test event blocking for a PENDING_CONSENT kid.** Same flow,
      different child without consent — verify it lands in
      `pending_consent_queue` and writes a `consent_gate_audit` row.

### Should-have (small builds — recommended before launch)
- [ ] **Add a "resend consent link" endpoint + button.** Today the only
      way to issue a magic link is to delete the parent contact and
      re-add it. Add `POST /api/parents/{contact_id}/consent-link/resend`
      that re-runs the token+email block from `onboarding_handlers.py:307-341`.
      Surface it as a "Resend" button on the ChildProfile panel.
- [ ] **Implement pending-consent queue replay.** Replace the TODO at
      `consent.py:123` with: when a parent submits consent, look up
      `pending_consent_queue` rows for that `child_id` where
      `resolved_at IS NULL`, replay each through `extract_events` or
      directly into `events` if the raw payload is already structured,
      mark `resolved_at = now()`. Without this, any event captured
      between switch-flip and parent-consent will be lost to parents.

### Nice-to-have (can ship after parents are onboarded)
- [ ] **WhatsApp push to parents on new event / EOD narrative.**
      Issue #12. Parents will rely on email + portal until this lands.
      Worth telling parents in the welcome email that this is coming.
- [ ] **Audit parent magic-link opens + submissions** to `activity_logs`.
      Today only the immutable `parental_consent` row + the `used_at` on
      the token are stamped; helpful for compliance trails.

---

## Cutover runbook

Run in this order. **Estimated wall clock: ~2 hours of director work + a
day for parents to respond.** Block off the day; don't accept Phase 1
voice memos during the wipe.

### T-3 days — communicate
1. Director emails parents: "Starting <date> we're moving you into our
   real-time portal. You'll receive a one-time consent link from
   `noreply@<your-domain>` — please click within 7 days." Include a
   one-sentence privacy summary and the legal-team contact for questions.
2. Director confirms every primary parent contact in the console has an
   email address (the magic link is email-only today, not SMS).

### T-1 day — confirm staging
3. Re-run the staging smoke test (Pre-launch §1). Don't skip.
4. Confirm `RESEND_API_KEY`, `FRONTEND_BASE_URL`, and `CONSENT_GATE_DISABLED=true`
   are still set in Railway (you haven't accidentally flipped yet).
5. Snapshot the Railway Postgres (Railway → Postgres → "Create backup").
   Phase 1 pilot data is non-binding but capture it for compliance just
   in case.

### T-0 morning — stop intake & wipe Phase 1 data
6. Set `EXTRACTION_DISABLED=true` in Railway to pause inbound voice
   memos (teachers get "Recording received — pending review" replies).
7. Run the Phase-1→Phase-2 wipe SQL from `PILOT_NOTES.md §289`. This
   clears events, photos, narratives, pending queues, audit logs, and AI
   API logs while preserving the structural data (center, rooms,
   teachers, admins, children, parent contacts).
8. Run a `UPDATE children SET status = 'PENDING_CONSENT'` (scoped to the
   pilot center) so the magic-link auto-trigger fires when contacts are
   re-touched.

### T-0 mid-day — flip the switch
9. In Railway, set `CONSENT_GATE_DISABLED=false`. Restart the backend
   service (Railway redeploys on env-var change).
10. Tail logs for ~5 minutes. You should NOT see
    `CONSENT_GATE_DISABLED is set` anymore. You should still see normal
    request logs.
11. Verify with a one-off: hit the consent-gate codepath from the Railway
    shell or a script that calls `get_child_for_processing` for a known
    child — confirm it returns `None`.

### T-0 afternoon — invite parents
12. For each parent contact already in the DB: the magic-link trigger
    only fires on contact *creation*, not on contact existence. You have
    two choices:
    - **(A) If the "Resend" endpoint shipped** in Pre-launch §2: click
      Resend on each child in the console. Each parent gets a fresh email.
    - **(B) If you deferred the Resend endpoint**: delete each primary
      parent contact and re-add it via the console. The auto-trigger fires
      on add. Less elegant; works.
13. Watch the Resend dashboard for delivery confirmation. Bounces almost
    always mean the director typo'd the email — fix in the console and
    retry that contact.

### T-0 evening — resume intake
14. Set `EXTRACTION_DISABLED=false`. Restart the backend.
15. Send one teacher voice memo (any kid in the pilot center). Confirm
    it lands in `pending_consent_queue` for kids without consent, and in
    `events` for any kid whose parent already consented during step 12.

### T+1 through T+7 — monitor the queue
16. Each morning, run:
    ```sql
    SELECT count(*) FROM pending_consent_queue WHERE resolved_at IS NULL;
    SELECT count(*) FROM parental_consent WHERE is_active = TRUE;
    ```
    The first number should be trending down as parents consent. If a
    kid is "stuck" (queue rows piling up, no consent submitted), the
    director should call the parent directly.
17. After day 7 the consent tokens expire. For any unresponsive parents,
    use the Resend mechanism (step 12) to issue a fresh 7-day token.

---

## Rollback

If something goes wrong (mass email bounce, parents flooding the
director, gate blocking too aggressively):

1. Set `CONSENT_GATE_DISABLED=true` in Railway and restart. The gate
   reverts to Phase 1 behaviour immediately.
2. Set `EXTRACTION_DISABLED=true` if events are being processed wrong.
3. Restore from the snapshot taken at T-1 §5 if data needs to come back.
4. Open an incident note in `PILOT_NOTES.md §"Incidents"`.

The flip is a single env var — rollback is fast.

---

## Verification — definition of "Phase 2 is live"

- [ ] `CONSENT_GATE_DISABLED=false` confirmed in Railway.
- [ ] At least one parent has submitted consent (row in `parental_consent`
      with `is_active=TRUE`).
- [ ] That kid's next teacher-submitted event lands in `events` (not the
      pending queue) AND surfaces in the Parent Portal for that parent.
- [ ] No `CONSENT_GATE_DISABLED is set — bypassing consent` warnings in
      Sentry/Railway logs.
- [ ] `consent_gate_audit` is recording blocks for the kids who haven't
      consented yet (proves the gate is doing real work, not silently
      passing everything).

---

## Open questions for the team before launch

1. **Email-only consent**: today the magic link only goes by email. Some
   parents may not check email reliably. Do we need an SMS path before
   launch? (Nice-to-have, not blocking.)
2. **EOD narrative delivery**: parents only see narratives if they open
   the portal. Do we want a push (email or WhatsApp) to nudge them at 5
   PM? Recommend yes — even a plain Resend email with "your daily report
   is ready" + a deep link.
3. **Per-center rollout**: if a second pilot center comes online before
   Phase 2 stabilises here, we'll need a per-center flag. Not blocking
   if Tilly's Tots is the only center.
