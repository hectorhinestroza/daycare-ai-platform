# Phase 2 Director Guide — Onboarding Parents

> Companion to `DIRECTOR_GUIDE.md` — read that one first if you haven't.
> This file covers **what changes when parents join the pilot**: the new
> consent flow (entirely by email, no more paper forms), recent features
> teachers will use, and your daily routine once families have access.

---

## What's different in Phase 2

| | Phase 1 (teachers only) | Phase 2 (parents joined) |
|---|---|---|
| Who sees events | You + teachers | You + teachers + parents |
| Consent monitoring | Override ON (events flow without consent) | Override OFF (no event without a signed consent on file) |
| Parent onboarding | None | You add a parent contact, they get a consent email automatically |
| Parent portal access | "Preview parent view" only | Real links sent automatically after consent |
| Your daily focus | Spot AI misses, build comfort | Above PLUS replying to parent questions, chasing missing consents |

The big mental shift: **once a parent's consent is recorded, every event you approve goes to a real family in real time.** Approve carefully. Reject anything that doesn't represent the child accurately.

---

## How the parent gets onboarded — the email flow

Two emails, in order. Both are sent automatically; you don't copy any links by hand.

### Email 1: the consent link (sent the moment you save the parent contact)

When you add a child's primary parent contact in **Center → Children → [child] → Add contact** and check **Primary**, the system immediately sends them an email from `Raina <onboarding@raina-pilot.com>`:

> **Subject:** Tilly's Tots — Complete enrollment for Loie
>
> Hi Jane, we need your consent before we can start sharing Loie's daily updates with you.
>
> This takes about 30 seconds. You'll review three simple consent items covering daily reports, photos, and voice memo processing.
>
> **[Complete Enrollment →]**  *(button)*
>
> *This link expires in 7 days. If you didn't expect this email, you can safely ignore it.*

The button takes them to a private page where they tick each consent box, type their full name as a digital signature, and submit. The link is single-use and expires in 7 days.

> 📸 *[Screenshot: the consent form on a parent's phone — three checkboxes plus signature field]*

### Email 2: the portal welcome (sent the instant they submit consent)

The moment the parent finishes the consent form, two things happen:
1. Their child's status flips from `PENDING_CONSENT` to `ACTIVE` — events for that kid can now flow.
2. A second email goes out immediately:

> **Subject:** Tilly's Tots — Loie's daily updates are ready 🌿
>
> Hi Jane, Loie's enrollment is complete and the parent portal is now live for your family.
>
> Throughout the day you'll see real-time updates from Loie's teachers — meals, naps, photos, and a daily recap at the end of the day.
>
> **[Open Loie's Portal →]**  *(button)*
>
> *Tip: bookmark this link or add it to your phone's home screen so you can come back with one tap. The link is private to you — please don't share it.*

The portal link is signed and scoped to that one child, good for one year. The parent should **Add to Home Screen** on first open (Safari Share menu on iPhone, three-dot menu on Android) so the app sits next to their other apps.

### What parents see when they reply

Either email can be replied to. Replies route to the pilot operator's inbox (currently set to Hector's Gmail). You'll be looped in as needed — if you'd like parent replies to go to *your* email instead, ask Hector to update the `RESEND_REPLY_TO_EMAIL` setting.

---

## The new step-by-step: onboarding one parent

Replaces the old "Phase 2 transition" section in `DIRECTOR_GUIDE.md` (the manual-paper-form workflow is no longer the primary path).

### Step 1 — Open the child's profile

**Center tab → Children sub-tab → [child's name]** to expand their profile.

### Step 2 — Add the primary parent contact

Scroll to **Contacts** → **+ Add contact**. Fill in:
- **Name** — the parent's full name (used in the email greeting).
- **Email** — the address that will receive both emails. Triple-check the spelling.
- **Phone** — for your records; not currently used for outbound messaging.
- **Relationship** — parent, guardian, etc.
- **Primary** — toggle **ON** for one contact per child (the one who gets the app). Other contacts can be added later without sending another email.
- **Can pick up** — set per contact (parents, grandparents, approved sitters).

When you save, the consent email fires within seconds.

> 📸 *[Screenshot: child profile contact-add form with Primary toggle highlighted]*

### Step 3 — Confirm the email landed

Ask the parent (or check your reply inbox if it bounces). Common issues:

- **Went to spam.** Tell them to search for "Raina" and mark it as Not Spam.
- **Typo in email address.** Edit the contact, fix the email, re-save — but the original token still works. To send a fresh email you'll need to delete and re-add the contact (a "resend" button is on the roadmap).
- **Parent didn't act within 7 days.** Same fix — delete and re-add the contact, fresh email and 7-day window.

### Step 4 — Wait for them to consent

You'll see the child's status change from `PENDING_CONSENT` to `ACTIVE` on the child's profile. That's the signal the parent is now in and can start receiving events.

### Step 5 — Confirm the welcome email landed and works

Ask the parent to confirm the second email arrived and that the portal opens for them. If they get a "Link expired" page on the portal, the token didn't mint correctly — message the engineer immediately, that's a bug.

### Step 6 — Help them Add to Home Screen

This is the only step that often needs hand-holding. Walk them through it on day 1 if you can. Once it's on their home screen, daily use is a single tap.

---

## Features added since the original guide

These changed since `DIRECTOR_GUIDE.md` was written. Teachers don't need to relearn anything — the new behaviours just work — but you'll see new things in the queue.

### 1. Batch photo upload (one message → many photos)

Teachers can now select up to 10 photos from their gallery and send them in a single WhatsApp message. The bot replies once: *"📷 Got 5 photo(s). Reply (text or voice note) with who's in them and what's happening."*

Three ways the bot figures out who's in a photo, in order:
- **Caption with the upload**: "Clara and Emi reading" → photos get attached to both children.
- **Caption saying "everyone"**: photo gets attached to every kid in the teacher's classroom.
- **No caption**: bot parks the photos and waits for a follow-up message (text or voice note) naming the kids and describing the scene. The follow-up reply becomes the photo's caption that parents see.

The teacher's old `/child` command still works as a fallback. The new AI-driven flow is the default.

What you'll see in the parent portal: one photo can appear in multiple kids' galleries simultaneously (it's the same physical photo, just tagged to each child).

> 📸 *[Screenshot: parent portal showing a photo with the auto-generated caption "Clara and Emi building a tower"]*

### 2. Attendance events (check_in / check_out)

Two new event types capture arrivals and departures:

| Type | Captures | Example voice notes |
|---|---|---|
| **check_in** | Child arriving at daycare | *"Checking in Carl and Loie this morning"* · *"Annie was dropped off at 7:45"* |
| **check_out** | Child leaving daycare | *"Carlos was picked up at 5"* · *"Mom got Sofia early today"* |

Two important behaviours:
- **Multi-child check-in is supported.** *"Checking in Carl and Loie"* creates two separate events, one per kid. No need to repeat names.
- These auto-approve at high confidence, just like food/nap/potty. They'll show up in the parent feed with login/logout icons.

For the pilot, attendance lives in the same event stream as everything else. If parents start asking for a separate "who's here today" view, that's a follow-up build.

### 3. Welcome email after consent (already covered above)

This is the second email in the flow you just read. It removes the manual "copy bootstrap URL and paste into a text message" step from the old Phase 2 process.

### 4. Verbatim child names in the AI

The AI used to occasionally "autocorrect" unusual names — e.g. *"Loie"* spoken or typed could come out as *"Doie"* or *"Lola"*. That's now explicitly forbidden in the extraction prompt: names get copied byte-for-byte from what the teacher said. You should see far fewer name mismatches in the queue.

If you do see a name substitution still happening, screenshot it and send to the engineer — it means the prompt rule needs reinforcing.

### 5. Email replies route to a real inbox

The consent and welcome emails support a "Reply" button now. Replies go to the pilot operator's mailbox via a forwarder (Namecheap DNS + ImprovMX → Gmail). When you want replies to go to *your* inbox instead, ask Hector to flip the env var.

---

## Your daily routine in Phase 2

### Morning (before kids arrive)

1. Check your inbox for parent replies overnight (or the Hector-forwarded ones).
2. Glance at any pending parents who haven't consented yet — chase the ones blocking their kid's events.
3. Open the director portal, check overnight Activity for anything odd.

### Throughout the day

- **Approve aggressively** on routine events (food, nap, potty, check-in/out) so parents see updates in near-real-time.
- **Scrutinize the yellow-striped events** — incidents, medication, low confidence. These reach parents only after your explicit approval.
- **Spot-check Preview parent view** for one or two kids each day to confirm the feed reads naturally.

### When a parent asks "I didn't get an email"

Order of operations:
1. Confirm their email in the child's contacts is spelled correctly. Most "didn't get the email" reports are typos.
2. Ask them to check spam — search for "Raina."
3. If still nothing, delete + re-add the contact to fire a fresh email.
4. Still nothing → message Hector. It might be a Resend deliverability issue.

### When a parent says the portal won't open

1. Confirm they're using the link from the **welcome email** (Email 2), not the consent email (Email 1).
2. Ask them to open it in Safari (iPhone) or Chrome (Android) — some in-app browsers (Facebook, Instagram) block the auth flow.
3. If the page loads but says "Link expired" or "Link invalid," message Hector — the token likely didn't mint.

### End of day

- Make sure the end-of-day summary at 5 PM looks right for at least one kid before parents read it.
- Note any patterns you noticed during the day for the next morning's stand-up.

---

## What's intentionally manual still

These are pieces I deliberately *haven't* automated yet — happy to revisit after the pilot generates real signal:

- **Resending a consent or welcome email**: no "resend" button yet. Workaround is delete + re-add the contact. Worth building if you find yourself doing this often.
- **Per-center feature flags**: the consent gate flips for the whole platform at once. Fine while Tilly's Tots is the only center; first new center triggers this build.
- **WhatsApp push to parents on new event/EOD**: parents only see updates when they open the portal. The plan is a "your daily report is ready" WhatsApp message; not built yet.
- **Pending-consent queue replay**: if an event gets blocked because a kid's parent hasn't consented yet, the blocked event stays in a queue and isn't replayed automatically when consent later arrives. For now, ask the teacher to re-send the voice note after the parent consents.

---

## Quick reference card — Phase 2 specific

```
PARENT ONBOARDING — STEP BY STEP

  Center → Children → [kid] → + Add contact
    Name, Email, Phone, Relationship
    Primary: ON
    Save

  ↓ (consent email fires automatically)

  Parent clicks button → checks 3 boxes → signs → submits

  ↓ (kid flips to ACTIVE + welcome email fires automatically)

  Parent opens welcome email → taps "Open Portal"
    iPhone: Share button → Add to Home Screen
    Android: ⋮ menu → Add to Home Screen

  Done.


WHEN A PARENT IS STUCK

  No consent email?       Triple-check email spelling, then re-add contact
  Consent expired?        Delete + re-add contact (fresh 7-day window)
  No welcome email?       Confirm kid status flipped to ACTIVE first
  Portal won't open?      Ask them to open in Safari/Chrome (not Facebook)
  None of the above?      Message Hector with the parent's name + child


WHAT'S NEW SINCE PHASE 1

  • Batch photos: up to 10 per message, AI figures out captions
  • Check-in / check-out events for arrivals & pickups
  • Welcome email arrives instantly after consent — no manual link
  • Unusual child names are preserved exactly (no more Loie → Doie)
  • Email replies route to a real human inbox
```
