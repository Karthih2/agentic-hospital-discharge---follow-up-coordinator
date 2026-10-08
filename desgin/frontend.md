# frontend.md — UI Components & Screen Flow
## Agentic Hospital Discharge & Follow-up Coordinator

---

## Screen 1: Login / Sign Up

**Tabs:** Sign In | Sign Up

### Sign In Tab
- Email input field
- Password input field
- Sign In button
- Forgot password link

### Sign Up Tab (Family Members only)
- Name input field
- Email input field
- Password input field
- Sign Up button

---

## Screen 2: Language Selection

Shown immediately after login, before anything else.

- 6 language cards in a 2x3 grid
- Each card: language name in its own script + English label below
  - தமிழ் — Tamil
  - తెలుగు — Telugu
  - ಕನ್ನಡ — Kannada
  - മലയാളം — Malayalam
  - हिन्दी — Hindi
  - English — English
- English pre-selected by default (highlighted border)
- Continue button (enabled only after one card is selected)
- Style: large, tappable cards similar to district app

---

## Screen 3: Patient Code Entry (Family Members only)

Shown only if role = family member after sign up.

- Heading: "Enter Patient Code"
- Input field: patient code (e.g., PAT-2845)
- Submit button
- After submit → "Waiting for patient approval" state with a spinner/message

---

## Screen 4: Patient Approval Notification (Patient side)

Shown to the patient when a family member submits their code.

- Message: "[Name] wants to join as a family member"
- Approve button (green)
- Deny button (red)
- On approve → family member gets access
- On deny → family member sees "Access denied" message

---

## Screen 5: Patient Dashboard / Upload Screen

Landing screen for the patient after login.

### Upload Section
- Two tabs: **Paste Text** | **Upload File**

**Paste Text tab:**
- Large multiline text area
- Analyse button

**Upload File tab:**
- Drag and drop zone
- Browse button (PDF or text files only)
- Analyse button

- Invalid/blank/non-medical input → red error message + "Enter manually" link
- Manual entry link opens Screen 12 (Manual Entry Form)

### Previous Summaries Section (below upload)
- List of previously uploaded summaries
- Each item shows: date uploaded, status summary (e.g., 3 Pending, 1 Needs Review)
- Tap to open existing plan

---

## Screen 6: Extraction Results — Card View (Default)

Shown after Analyse is clicked. Default view is Card View.

### Top Bar
- Toggle: **Card View** (default) | **Two-Panel View**
- Progress indicator: "3 of 8 tasks"

### Task Card
- Task type badge (Appointment / Medicine / Test / Referral / Warning / Care Instruction / Date)
- Status badge — color coded:
  - 🔵 Pending
  - 🟢 Completed
  - 🟠 Needs Review
- Simple language text in chosen language (large, readable)
- "Show original" — tap to expand source line from summary
- Date chip + "Set reminder" toggle
- Provider suggestion card (if applicable) — labeled "Suggestion only, not a guarantee of availability or suitability"
- Listen button — bottom left (prominent for elderly)
- Request Callback button — bottom right (prominent for elderly)
- Swipe left/right OR prev/next arrows to navigate cards

### Needs Review Card State
- Grayed out
- Lock icon
- Text: "Waiting for doctor review"
- Listen and Callback buttons hidden

### Medicine Card (fixed template only — no free rewrite)
- Medicine name
- Dose
- Timing
- Duration
- Special instructions

### Two-Panel View (accessible via toggle, default for family members)
- Left panel: original summary text with color-coded highlights
  - 🔵 Blue — Appointments
  - 🟡 Yellow — Medicines
  - 🔴 Red — Warnings
- Right panel: generated task list

### Permanent Footer (every screen)
> "This tool organizes your discharge instructions. It does not give medical advice. Ask your doctor about anything unclear."

---

## Screen 7: Provider Map

Opens when a task has a referral or follow-up need.

### Top Section — Location Input
- "Use my location" button (GPS auto-detect)
- OR manual drill-down:
  - State dropdown (e.g., Tamil Nadu)
  - District dropdown (e.g., Chennai)
  - Area dropdown (e.g., Perambur)
- Specialty auto-filled from task (e.g., Orthopedics) — not editable by user

### Map Section (Leaflet.js + OpenStreetMap)
- Full width interactive map
- 🔵 Blue pins — Hospitals
- 🟢 Green pins — Local clinics / doctors
- Tap a pin → provider bottom sheet appears

### Provider Bottom Sheet (on pin tap)
- Provider name
- Specialty
- Facility name
- Distance (synthetic)
- Synthetic contact number
- "Select this provider" button
- Label: "Suggestion only — not a guarantee of availability or suitability"

### After Selecting a Provider
- Provider linked to the task
- User returns to card view
- Task card now shows selected provider

---

## Screen 8: Doctor Reviewer Queue

Landing screen for Doctor Reviewer after login.

### Top Section
- Total pending reviews count
- Filter tabs: All | Medicines | Appointments | Warnings | Other
- Sort by: Date flagged / Priority

### Queue List (each item)
- Patient name (synthetic)
- Task type badge
- Reason flagged (e.g., "Missing dose", "Ambiguous timing", "Symptom described")
- Date flagged
- Tap to open review detail

---

## Screen 8b: Review Detail

Opens when doctor taps a queue item.

- Original source line from summary
- Extracted item as-is
- Reason flagged (from safety gate)
- Simple language version (if generated)
- **Confirm** button ✅ — approves item, moves to Pending
- **Correct** button ✏️ — doctor edits wording, then confirms
- After action → item removed from queue, task unlocks for patient
- Audit log entry created on every confirm or correct

**Hard UI rules:**
- No "Auto-approve all" button
- No bulk actions
- Every item resolved one at a time

---

## Screens 9–13
*(To be completed — Management Dashboard, Family Member View, Notification Screen, Manual Entry Form, Settings)*

---

## Global UI Rules

- Permanent footer on every screen: *"This tool organizes your discharge instructions. It does not give medical advice. Ask your doctor about anything unclear."*
- Large, tappable elements for elderly users
- Callback and Listen buttons always prominent on task cards
- Provider suggestions always labeled: *"Suggestion only — not a guarantee of availability or suitability"*
- Medicine content never freely rewritten — fixed template only
- Fonts: Noto Sans variants for Tamil, Hindi, Telugu, Kannada, Malayalam
- Role-based routing: each role lands on their own screen after login
