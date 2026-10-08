# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + Tailwind CSS, react-router, motion, React Bits text and scroll components (copied source), self-hosted fonts. Decided in docs/TECH_STACK.md and confirmed by the user. Backend is the FastAPI service in `backend/`.

## Users

- Patients after a hospital stay, including elderly patients whose family member operates the account. They need to know what to do next and when.
- Family members who view the plan within the access the patient granted, and receive reminders.
- Doctor reviewers who resolve the items the system could not settle.
- Hospital management who assign reviewers and handle callback requests, without seeing clinical text.

## Product Purpose

Turns a synthetic discharge summary into a trackable follow-up plan: tasks, dates, reminders, timeline, each explained in simple language and in the patient's language, each tied to the exact source line. It organizes and explains. It never diagnoses, changes medicine, or recommends treatment. Success: nothing in the discharge papers is missed, and anything unclear reaches a human doctor.

## Positioning

A fixed-rule safety gate decides what is safe, not a model. Only two of nine agents call an AI model. Every item keeps its evidence line, and only a doctor can close a Needs Review item. A chatbot cannot truthfully claim this.

## Operating Context

Input is a pasted or uploaded synthetic discharge summary. Six languages: English, Tamil, Hindi, Telugu, Kannada, Malayalam. Footer disclaimer on every screen: "This tool organizes your discharge instructions. It does not give medical advice. Ask your doctor about anything unclear." Provider matches are always labelled "Suggestion only, not a guarantee of availability or suitability".

## Capabilities and Constraints

- Seven item types: appointment, test, referral, medicine, care instruction, date, warning sign.
- Statuses: Pending (blue), Completed (green), Needs Review (orange, locked).
- Medicine cards use a fixed template, never reworded.
- Synthetic data only. No real patient, provider or clinical data.
- Backend endpoints exist for auth, family, summaries, tasks, providers, review, management, notifications.

## Brand Commitments

- The user's icon sheet `desgin/Healthcare App Icon Library.png` is the visual source: hand-illustrated icons with navy outlines and flat fills. Landing page and app use icons from it only.
- User bans, binding: harsh gradients, lucide icons, pure white backgrounds, rainbow colouring, drop shadows, rows of feature cards, emoji, liquid glass, em dashes, Inter / Geist / Space Grotesk, terminal windows, fake testimonials, bento grids, neon, "it's not X, it's Y" phrasing, checkmark bullets, three pricing tiers, soft corner radius, purple and black, radial orbs, dot grids, sparkle icons, animated arrows, hover animations, coloured left stripes, basic pastels.
- User requires: a real product demo, skeleton loaders, Terms of Service and Privacy Policy pages.

## Evidence on Hand

- Working backend with 79 passing tests, live Groq model extraction on the PRD sample.
- Synthetic sample summaries in `backend/sample_data/`.
- No customers, testimonials, benchmarks or pricing exist. None may be invented.

## Product Principles

1. Fail visibly. An unclear item is shown as waiting for a doctor, never guessed.
2. Evidence beside every output.
3. The patient owns the account and the consent.
4. Plain language first, the patient's own language second, the original line always one tap away.
5. Synthetic and prototype status stays stated.

## Accessibility & Inclusion

Elderly and family-operated use is a core case: large text, 48px minimum controls, high contrast, keyboard focus visible, six scripts with proper fonts, motion that respects reduced-motion.
