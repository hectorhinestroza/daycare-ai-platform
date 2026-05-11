# Daycare Director Guide

Welcome! This guide walks you through everything you need to run the
daycare pilot — from your first login through the two onboarding phases,
how teachers use WhatsApp, and what every part of the app does.

Read it once end-to-end before pilot day. Then keep it open as a
reference during the first week.

> 📸 *[Screenshot: home screen of the director portal — shows tabs at the bottom and today's event count]*

---

## What this app does, in one minute

Teachers record short voice notes during the day — "Annie ate lunch
at noon," "Carlos napped from 1 to 2:30," "the whole class went outside."
The app converts those notes into structured records, you review them,
and parents see the approved updates in real time on their own phone.

The teachers' tool is **WhatsApp**. That's it for them — they don't
install a separate app, just send voice notes to a number we set up.
You and parents use a web app that looks and feels like a regular phone
app (you'll "Add to Home Screen" so it lives next to your other apps).

Three roles, three views of the same data:

| Role | Tool | What they do |
|---|---|---|
| **Teacher** | WhatsApp on their phone | Records voice notes throughout the day, optionally adds photos |
| **You (director)** | "Daycare Portal" web app on your phone or tablet | Approves what teachers report, manages enrollment, sees everything |
| **Parent** | Same "Daycare Portal" web app, different home-screen icon | Reads approved updates and the end-of-day summary |

---

## The pilot has two phases

You agreed to a careful rollout — **2 days of teachers-only operation
before any parent gets access**. Here's why and what to expect.

### Phase 1: Teachers + you (Days 1–2)

- Teachers send voice notes via WhatsApp
- You review everything in the director portal and use the **Preview parent view** button to see what each parent would see
- Parents don't have the app yet
- We turn ON a "monitoring override" so events flow normally even without each parent's signed consent on file

**Why bother with this phase:** real activity in the system reveals the rough spots (teacher voice habits, AI misses, classroom routines) before any parent watches their child's first day filtered through new software.

### Between phases: data wipe

After Day 2, all activity from Phase 1 is **deleted**. The director profile, teacher profiles, room layout, and child enrollments stay. We start with a clean event log going into Phase 2.

### Phase 2: Parents join (Day 3 onward)

- Each parent signs a paper consent form (you'll handle distribution and collection)
- You enter the signed consents into the system
- You generate each parent a unique app link
- Parents open the link on their phone, "Add to Home Screen," and start seeing their child's day in real time

The monitoring override turns OFF before any parent receives a link.

---

## Setting up WhatsApp on each teacher's phone

Teachers talk to a Twilio "Sandbox" number — a shared testing number we use during the pilot. The rules are slightly different from a regular WhatsApp contact:

### Step 1: Save the number

Have each teacher save this contact in their phone:

> **Daycare Bot**  
> +1 415 523 8886

### Step 2: Send the join message

Each teacher must send this **exact message** to that number from WhatsApp:

```
join ___________________________
```

> 📝 *Fill in the join code here before printing or sharing this guide:*
>
> **Code: `____________________`**

Twilio replies with "Sandbox: You are all set!" — that confirms it worked.

### ⚠ Important: re-join every 72 hours

The Twilio Sandbox automatically expires each teacher's connection **72 hours after their last message**. If a teacher hasn't sent a voice note or text in three days, their next message won't go through.

**Fix:** ask them to send the `join ___________` message again. Re-joining only takes a second.

Mondays after a long weekend are the most common time to need a re-join.

> 📸 *[Screenshot: teacher's WhatsApp showing the "you are all set" reply]*

---

## How teachers use WhatsApp

Once joined, teachers do everything by sending messages to the Daycare Bot number. Three things they'll do all day:

### 1. Set context for the next voice note

```
/child Annie
```

This tells the bot "the next voice note is about Annie." If a teacher records a voice note without setting context first, the AI usually figures out who they meant — but `/child` is a safe fallback for when the name is hard to pronounce or sounds like another kid's.

Similar command for room context (less common):

```
/classroom Butterflies
```

> 📸 *[Screenshot: teacher's WhatsApp showing /child Annie message + bot's "context set" reply]*

### 2. Send a voice note

Hold the microphone button in WhatsApp, speak, release. That's it. The teacher can speak naturally:

> "Annie ate all her pasta for lunch and she also had some fruit. Then she napped from 1 to 2:30. She had a great day."

The bot replies within a few seconds with a confirmation like:

> ✅ Got it! Parsed 3 events for Annie (1 food, 1 nap, 1 kudos).

If the bot can't match the name to a child in your roster, it will say so:

> ⚠️ I couldn't match 'Annie' to your roster. Reply with their enrolled name, or type 'ignore'.

Then the teacher just types the correct enrolled name (e.g. `Anika`) and the bot replays the same events under that name.

> 📸 *[Screenshot: teacher's WhatsApp showing a voice note + bot's parsed confirmation]*

### 3. Send a photo

The teacher can attach a photo to a WhatsApp message:

- If they've already done `/child Annie`, the photo gets attached to Annie's day
- If they haven't, the bot will ask: "📷 Photo received! Please assign it to a child with /child [name]". Send `/child Annie` next and the photo gets attached.

Photos get the date stripped from metadata (privacy), saved to secure storage, and shown to the parent.

> 📸 *[Screenshot: teacher's WhatsApp photo upload + bot's "photo saved" reply]*

### What teachers should know

| Do | Don't |
|---|---|
| Speak naturally — full sentences | Worry about exact phrasing or keywords |
| Mention the child's name in the audio | Say last names or birthdays in voice notes |
| Re-send the `join` message if WhatsApp seems stuck | Forward voice notes from another chat |
| Type `ignore` if a name match is wrong | Try to "fix" past events from WhatsApp — that's the director's job |

---

## The Director Console — your view

You'll add the director app to your home screen on Day 0. Once that's done, tap the icon any time to open it.

> 📸 *[Screenshot: home screen with the "Daycare" icon highlighted]*

The director console has four sections, accessed via the row of icons at the bottom of the screen.

### Today's Queue (default home)

> 📸 *[Screenshot: Today's Queue showing several pending event cards]*

The big landing screen. Shows every event submitted **today that hasn't been approved yet** — the AI thinks each event is real and confident, but you decide whether it goes to the parent.

Each event card shows:
- The child's name and event type (food, nap, potty, kudos, etc.)
- The detail line the AI extracted
- A confidence score (high = AI is sure, low = please double-check)
- Two big buttons: **Approve** and **Reject**

**Things flagged for closer review** appear with a yellow stripe. Common reasons: low confidence, an incident, or a medication event. These need your judgment.

> 📸 *[Screenshot: a flagged incident event with the yellow stripe]*

**Tip:** if you have 30 events to clear and they're all routine, scroll through and tap Approve fast. The parent only sees an event after you've approved it.

### History

> 📸 *[Screenshot: History tab with calendar strip and past events]*

A calendar strip across the top. Tap any past day to see every event from that day, including the approved/rejected status. Useful for:
- "What did Annie eat last Tuesday?"
- "When was the last potty incident?"
- Reviewing patterns before a parent-teacher conversation
- End-of-week exports for compliance

### Center

> 📸 *[Screenshot: Center tab showing three sub-tabs — Children / Rooms / Teachers]*

The administrative section. Three sub-tabs:

#### Children sub-tab
- List of every enrolled child
- Tap a child to expand their profile
- Edit name, date of birth, classroom, allergies
- Add/remove parent contacts
- **"Preview parent view" link** on each child — opens that child's parent portal in a new tab, so you can see what their family will see

> 📸 *[Screenshot: expanded child profile showing the Preview parent view link]*

#### Rooms sub-tab
- Add or rename classrooms (Toddlers, Butterflies, Pre-K, etc.)
- Assign which classroom a kid belongs to

#### Teachers sub-tab
- List of teachers with their phone numbers and assigned classrooms
- **A pre-generated "Teacher app link" panel** on each teacher row — copy and send to the teacher so they can install the director-companion view (less commonly used than WhatsApp)
- A **Remove** button to take a teacher off the roster (they'll no longer be able to submit via WhatsApp)

> 📸 *[Screenshot: Teachers sub-tab with bootstrap link panels visible]*

### Activity

> 📸 *[Screenshot: Activity log with timestamped audit entries]*

Audit trail. Every approval, rejection, edit, and admin action is recorded here with who did it and when. You probably won't look at this daily — it's there for compliance and when you need to reconstruct what happened.

---

## The Parent Portal — what they see

Each parent who's been given a link installs the app on their phone exactly the way you do. The look is different — calmer, fewer buttons, more focused on their child specifically.

### Live feed

> 📸 *[Screenshot: parent's live feed showing today's events as cards]*

Real-time event cards from today. As soon as you approve an event in your queue, it appears here for the parent within seconds. Photos appear inline.

### End-of-day summary

> 📸 *[Screenshot: parent's end-of-day narrative paragraph]*

At 5 PM, the app generates a warm, personalized paragraph summarizing the child's day — "Annie had a wonderful day! She ate a great lunch of pasta and fruit, took a long nap, and showed kindness when she shared her toys with Carlos. We're so glad you sent her in today." This appears at the top of the parent's feed in the evening.

### History

> 📸 *[Screenshot: parent's history view — past days listed as a calendar strip]*

Parents can scroll back through past days. Useful for pediatrician visits, recapping a tough morning, or just nostalgia.

### Privacy policy footer

Every page of the parent app has a small "Privacy Policy" link at the bottom. Tapping it opens the policy that explains exactly what data is collected and how it's used. (This is a legal requirement.)

---

## Phase 1 monitoring playbook

For Days 1 and 2, your job is **observation + course-correction**, not yet "communication with parents." Here's what to do:

### Morning of Day 1

1. Confirm all teachers have completed the WhatsApp `join` step (ask each one to send a test voice note that says "Hello, this is [their name]")
2. Confirm you see test events appear in your Today's Queue
3. Approve the test events — they'll be invisible to parents (no parents have access yet)
4. Tap **Preview parent view** on each child to see the live feed populates correctly

### Throughout each day

- Check your Today's Queue every couple of hours — approve routine events, scrutinize flagged ones (yellow stripe)
- For any event that the AI got wrong (wrong child, wrong event type, made-up detail), tap **Edit** to correct it before approving, OR tap **Reject** to drop it entirely
- Note any patterns of misses in a notebook — you'll review these with me after Day 2

### What to specifically watch for

- **Wrong child names**: AI might say "Annie" for "Ani" or "Carlos" for "Carlos Jr." Both kids enrolled? The AI should flag for review. Single kid with unusual nickname? Add the nickname to their profile or just teach the teachers to use the exact roster name.
- **Made-up details**: AI is told to "stick to what was said." If you see "and she said she loved it" but the teacher never said that, mark it as a hallucination and let me know — those are bugs we want to fix.
- **Wrong event categorization**: "Annie cried for 10 minutes" might come through as `observation` when it should be `incident`. Edit the event type or reject + ask the teacher to mention "incident" explicitly next time.
- **Missing photos**: If the teacher sent a photo but it doesn't appear on the child's profile, it's probably stuck in the "pending photos" queue waiting for a `/child [name]` command from the teacher.

### End of each day

- Confirm the **end-of-day summary** appears for each child in the Preview parent view (around 5 PM)
- If a summary looks wrong, you can regenerate it from the child's profile in the Center tab
- Make notes for the next morning's stand-up

---

## Phase 2 transition: onboarding parents

After Day 2's work is done, we do the following, in this order. **Do not skip steps**.

### Step 1: Wipe Phase 1 data

We delete all the events, photos, and narratives from Phase 1 so parents see a clean start. Your director profile, the teachers, the room layout, and the children stay enrolled. **Important: I (the engineer) run this step.** Don't worry about it.

### Step 2: Turn off the monitoring override

I flip the consent gate back on. From now on, no event can be created for a child whose parent hasn't signed a consent form recorded in the system.

### Step 3: Collect signed paper consent forms

You'll have a printed consent form (we'll provide). Each parent reads, signs, and returns it. The form includes:
- What data is collected
- Who sees it
- How they can withdraw consent
- A link to the privacy policy

Keep the signed paper forms in a folder — these are your legal record.

### Step 4: Enter parent contacts in the system

For each child:

1. Open **Center → Children → [child's profile]**
2. In the **Contacts** section, add a contact for each parent
3. Fill in their name, phone, and email
4. Mark one as **Primary** (the main person who gets the app)
5. Set **Can pick up** correctly for everyone (parents, grandparents, etc.)

> 📸 *[Screenshot: child profile contact-add form]*

### Step 5: Record the consent

This is the legal step that lets you generate a parent app link.

> Note for the engineer (Hector): we need a small "record paper consent" admin UI for this step. For now, you'll insert a row into `parental_consent` per child via the Railway query tab. I'll add the UI shortly — see deferred work in `pilot_deferred_bugs.md`.

### Step 6: Generate each parent's app link

1. Open the child's profile
2. Each parent contact has its own panel labeled "Parent portal link"
3. Click **Copy** to copy the link to your clipboard
4. Send the link to the parent — text it, email it, or print and hand it over (whichever they prefer)

### Step 7: Walk parents through installation

If a parent is in person, walk them through it. If not, send written instructions:

1. Open the link on your phone in Safari (iPhone) or Chrome (Android)
2. The app loads showing today's updates for your child
3. Tap the Share button (square with up arrow on iOS; three-dot menu on Android)
4. Tap "Add to Home Screen"
5. From now on, tap the new icon to open the app directly

### Step 8: Confirm the first parent can see their child's day

Have one of the more app-savvy parents test the link first. Once you confirm it works end-to-end, send the rest.

---

## Common situations and how to handle them

### "A teacher's WhatsApp isn't working anymore"

Most likely cause: their Sandbox connection expired. Have them send the `join ___________` message again. If that doesn't fix it, message me.

### "Events aren't showing up after a teacher sends a voice note"

Check the Activity tab — was the event received and rejected? Was the teacher's phone number recognized? Was there an extraction failure (sometimes an AI hiccup, usually transient)? Ask the teacher to resend; if it fails twice in a row, message me.

### "A teacher submitted an event for the wrong kid"

In the Today's Queue, tap the event → **Edit** → change the child name → save. Or **Reject** and ask the teacher to redo.

### "A parent says they can't open the app"

- Confirm their bootstrap URL is still valid (each is good for 90 days)
- If expired or revoked, generate a fresh one from the child's profile
- For iOS users specifically: if they tap the home-screen icon and see "Access link expired," have them open the new bootstrap URL again — it'll restore access

### "A parent wants their child's data deleted"

Contact me directly — this is a COPPA deletion request and needs to be handled carefully (legal record, billing exceptions, etc.). For now, just collect the parent's request in writing and I'll process it.

### "The AI keeps misnaming a kid"

If a child has a nickname or unusual name, edit their profile and add the nickname into the **Name** field (e.g. "Annika (Anika)") so it appears on the AI's roster.

### "An event sounds like the AI made something up"

Tap **Reject** in the queue. Note which event and which teacher. If a teacher's events have a pattern of hallucinations, message me — it could indicate the AI's confidence is misaligned and we need to retune.

---

## Emergency procedures

### Stop AI extraction in case of a problem

If something is clearly wrong with AI output across the board (e.g., the AI is hallucinating things or sending wrong data to parents), tell me immediately. I can flip a kill switch that **pauses extraction** — voice notes still arrive, teachers get a "Recording received — pending review" reply, but nothing goes to the queue until I turn it back on.

### Rolling back a bad change

I handle this. If you notice something is broken after a recent deploy, just message me and don't try to fix it yourself.

### Reaching me

| Severity | How to reach me |
|---|---|
| Data leak suspected, privacy concern, parent complaint | Text + call immediately (24/7) |
| AI hallucinating, wrong events flowing to parents | Text (during waking hours), message in the morning if overnight |
| Annoying UX bug, request for a feature, "this would be nicer if…" | Email or text whenever |

My contact: `__________________________________`

---

## Reference cards

Pages to print and put up near the daycare's central station, if helpful:

### Teacher quick reference (1 page)

```
DAYCARE BOT — Quick Reference

WhatsApp number: +1 415 523 8886
First-time join: send "join ___________" (only needed once, or after 3 days idle)

Set context (which child the next note is about):
  /child Annie

Send a voice note: hold the mic, speak naturally, release.
  Examples:
    "Annie had pasta for lunch"
    "Carlos napped from 1 to 2:30"
    "All the kids went to the park this morning"

Send a photo: attach photo → optional caption.
  If the bot asks who it's for, reply: /child Annie

If the bot says it can't match a name: reply with the
  correct enrolled name (or type 'ignore' to discard).

If WhatsApp seems stuck: send "join ___________" again.
```

### Director quick reference

```
DAILY ROUTINE

  Morning:   Check Today's Queue, clear test events
  Hourly:    Quick pass through the queue
  4–5 PM:    Final approval sweep before EOD summaries
  Evening:   Spot-check 1–2 children via Preview parent view

WHEN TO LOOK CLOSER
  - Yellow-striped events (incidents, medication, low confidence)
  - Anything attributing speech to a child ("she said she loved it")
  - Photos in the wrong child's profile

WHEN TO MESSAGE ME
  - Anything privacy-related (parent complaint, possible leak)
  - Hallucinated events
  - Backend errors you can see in the UI
```
