# SnapClass UI: Human–Computer Interaction (HCI) decisions

SnapClass is used by people with very different comfort levels with technology: teachers who
may rarely use web apps, students on phones, and a technical administrator. This note maps the
interface to standard HCI principles, so every design choice can be explained.

## 1. Users and their goals

| User | Typical device | Main goal | Constraints we design for |
|---|---|---|---|
| Teacher | Phone or laptop, in class | Take attendance in under a minute | Little time, may not be tech-savvy, large classes (60–120) |
| Student | Phone | Set up face once, check own attendance | First-time use from a QR code, privacy worries |
| Administrator | Laptop | Add teachers, keep the system healthy | Technical, but must not change risky settings by accident |

## 2. Nielsen's 10 usability heuristics

| # | Heuristic | Where it shows in SnapClass |
|---|---|---|
| 1 | Visibility of system status | 4-step progress tracker on every attendance; "What to do now" box; "Checking the photos…" screen that updates itself; toast messages after every action ("Attendance saved: 52 present, 8 absent") |
| 2 | Match between system and real world | Everyday words: "Not sure" instead of UNCERTAIN, "Save attendance" instead of Finalize, "Face setup" instead of Biometrics, "Lecture period", dates with weekday ("Wed, 7 Oct 2026") |
| 3 | User control and freedom | Remove any photo before upload; Present/Absent can be changed until saving; after saving, "Change" with a reason; Cancel on every dialog; "Undo changes" in settings |
| 4 | Consistency and standards | Same status badge (word + icon + colour) everywhere; same button styles (one purple primary action per screen); same layout on every page |
| 5 | Error prevention | Save is disabled until every "Not sure" student is decided; confirmation dialogs for saving, removing a student and deleting data; Caps Lock warning; photo limit enforced before upload; technical thresholds hidden under "Advanced" with a warning |
| 6 | Recognition rather than recall | Class name in the attendance title; face crops next to names; numbered steps; filters show counts ("Needs check 3") |
| 7 | Flexibility and efficiency | Search by name/roll number and filters for large classes; drag-and-drop for laptop users, camera for phone users; one button uploads and starts checking |
| 8 | Aesthetic and minimalist design | Match scores hidden behind "Show match details"; optional voice recording and unmatched faces folded away; one primary button per step |
| 9 | Help users recover from errors | Plain error messages that say what to do ("Cannot reach SnapClass. Check your internet connection"); Retry buttons; "Try again" for failed processing; per-photo reasons ("Photo 2: move closer to the camera") |
| 10 | Help and documentation | Help button with a role-specific quick guide and FAQ; "What does Not sure mean?" tips next to the feature; first-time "Getting started" checklist for teachers |

## 3. Norman's design principles

- **Affordances and signifiers:** buttons look pressable (filled or outlined); the drop area has a dashed border and an upload icon; the camera has a round shutter button like a phone camera.
- **Feedback:** white flash and "2 photos taken" counter when a photo is taken; toasts; buttons change text while working ("Uploading…").
- **Mapping:** the step tracker order matches the real task order (photos → checking → review → saved).
- **Constraints:** at most 4 class photos, 3–5 face photos, exactly 3 voice clips; Save disabled until decisions are complete.

## 4. Laws of interaction

- **Fitts's law:** all buttons are at least 44 px tall (WCAG 2.5.5); Present/Absent are large, side-by-side targets; the Save button stays at the bottom of the screen (sticky action bar) so it is always within reach.
- **Hick's law:** one clear next action per step; teachers see three filters, not a complex table; advanced options are hidden until requested.
- **Miller's law / chunking:** the review list is split into "Needs check", "Present", "Absent"; long forms are grouped into short sections.

## 5. Accessibility (different abilities)

- **Text size** (Normal / Large / Extra large) and **high contrast** mode, chosen by each user and remembered on the device; also available on the sign-in page.
- Status never relies on colour alone: every badge has an icon and a word (colour-blind users).
- Keyboard: "Skip to main content" link, visible focus ring, native `<dialog>` (Escape closes, focus is trapped).
- Screen readers: labels on every input, `aria-live` toasts, `aria-pressed` on toggles, `aria-current` on the active step and page.
- Respects "reduce motion" in the operating system.
- Responsive from 375 px phones to desktops.

## 6. Evaluate it (do this before claiming it works)

Usability claims need evidence, just like accuracy claims. Suggested study:
1. **Think-aloud test** with 3–5 teachers of different ages: give them the task "Take today's attendance for period 2", observe without helping, and note where they hesitate.
2. Measure **task success**, **time on task** and **errors** for: take attendance, correct one student, invite students (students: set up face).
3. Ask the **System Usability Scale (SUS)** questionnaire after the tasks (10 questions; a score above about 68 is above average).
4. Fix the top problems, then test again with new participants.

No usability results have been measured yet.
