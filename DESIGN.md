---
name: Follow-up Coordinator
description: Flat mint ground, navy 2px outlines and sticker tiles that turn discharge papers into a plan a patient can follow.
colors:
  teal: "#0e7c7b"
  teal-deep: "#0a5c5c"
  mint: "#5ed6c3"
  ground: "#eafbf6"
  ground-deep: "#d3f1e8"
  tile: "#f4fdf9"
  ink: "#14304f"
  ink-soft: "#3d5671"
  line: "#a9d9cd"
  pending: "#2f6fde"
  done: "#1f7a43"
  review: "#a8530c"
  error-ink: "#8c1d18"
  error-line: "#b3261e"
typography:
  display:
    fontFamily: "Bricolage Grotesque Variable, Noto Sans Tamil, Noto Sans Devanagari, Noto Sans Telugu, Noto Sans Kannada, Noto Sans Malayalam, sans-serif"
    fontSize: "clamp(2.4rem, 5.2vw, 4.4rem)"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "clamp(1.9rem, 3.6vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Atkinson Hyperlegible, Noto Sans Tamil, Noto Sans Devanagari, Noto Sans Telugu, Noto Sans Kannada, Noto Sans Malayalam, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 600
rounded:
  tile: "4px"
  skeleton: "2px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  section: "64px"
components:
  button-primary:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.ground}"
    rounded: "{rounded.tile}"
    padding: "8.8px 22.4px"
    height: "48px"
  button-primary-active:
    backgroundColor: "{colors.teal-deep}"
  button-plain:
    backgroundColor: "{colors.tile}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tile}"
    padding: "8.8px 22.4px"
    height: "48px"
  button-plain-active:
    backgroundColor: "{colors.ground-deep}"
  tile:
    backgroundColor: "{colors.tile}"
    rounded: "{rounded.tile}"
  field:
    backgroundColor: "{colors.tile}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tile}"
    padding: "8.8px 14.4px"
    height: "48px"
  status-pending:
    backgroundColor: "{colors.pending}"
    textColor: "#ffffff"
    rounded: "{rounded.tile}"
  status-done:
    backgroundColor: "{colors.done}"
    textColor: "#ffffff"
    rounded: "{rounded.tile}"
  status-review:
    backgroundColor: "{colors.review}"
    textColor: "#ffffff"
    rounded: "{rounded.tile}"
---

# Design System: Follow-up Coordinator

## Overview

**Creative North Star: "The Sticker Sheet"**

The whole product is drawn the way its icon sheet is drawn: flat mint paper, objects outlined in navy ink at 2px, small square corners, status carried by a colour square. Nothing floats, glows or leans. A patient or family member reading a plan in a hospital corridor should find the page calm, legible and plain about what is done, what is pending and what a doctor must review.

The landing page (Persuade) and the signed-in screens (Operate) share one vocabulary. Landing alternates bands of mint ground, deeper mint and committed teal; app screens stay on the mint ground with tiles. Real content leads: a synthetic discharge sheet, the plan generated from it, six translations of one task. Six scripts are first-class, so type and line height flex for Indic text.

**Key Characteristics:**
- Flat everywhere: no shadows, no gradients, depth from outline weight and tonal bands.
- One ink (navy) for text and every outline; teal is the action and committed-band colour.
- 4px corners on every tile, button, field and status chip.
- Status is a solid colour square plus a word, never colour alone.
- The 58 sliced icons from the user's sheet are the only icons.
- Motion is one calm entrance rise; no hover animation.

## Colors

A mint-and-teal paper palette joined to a navy ink and three status hues, taken from the user's colour card and the icon sheet.

### Primary
- **Clinic Teal** (#0e7c7b): primary buttons, committed safety band, selected toggles and selection borders, scrollbar thumb, caret.
- **Deep Teal** (#0a5c5c): pressed primary button, the closing call-to-action band.
- **Fresh Mint** (#5ed6c3): text selection and small bullet squares on teal bands. A highlight, not a surface.

### Neutral
- **Mint Paper** (#eafbf6): page ground and text on teal and ink bands.
- **Deeper Mint** (#d3f1e8): alternating bands (how it works, languages, FAQ), locked or inactive cards, skeleton base, scrollbar track.
- **Tile Mint** (#f4fdf9): the lightest surface; tiles, fields, plain buttons. This is the system's "white".
- **Navy Ink** (#14304f): all body text, 2px outlines, focus ring, footer band.
- **Soft Ink** (#3d5671): secondary text, placeholders, locked-item text.
- **Quiet Line** (#a9d9cd): hairline borders, header rule, skeleton peak.

### Status
- **Pending Blue** (#2f6fde), **Completed Green** (#1f7a43), **Needs Review Orange** (#a8530c): status chips, timeline squares and the dashed outline on Needs Review items. White text on each.
- **Alert Red** (#b3261e border, #8c1d18 text): inline error alert only.

### Named Rules
**The No-White Rule.** The lightest surface is Tile Mint (#f4fdf9). Pure white appears only as text on a status chip.
**The One Ink Rule.** Text and outlines are Navy Ink. No black, no grey outlines on primary surfaces.
**The Status Trio Rule.** Blue, green and orange mean Pending, Completed, Needs Review and nothing else. Do not reuse them as decoration.

## Typography

**Display Font:** Bricolage Grotesque Variable (with Noto Sans for Tamil, Devanagari, Telugu, Kannada, Malayalam)
**Body Font:** Atkinson Hyperlegible (same Noto fallbacks)

**Character:** A characterful grotesque for headings and controls over a reading face built for low-vision legibility. Tabular numerals throughout so dates and times align.

### Hierarchy
- **Display** (700, clamp(2.4rem, 5.2vw, 4.4rem), 1.08, -0.02em): landing hero headline only.
- **Headline** (700, clamp(1.9rem, 3.6vw, 3rem), 1.08): section headings (2xl to 4xl steps appear on app screens).
- **Title** (700, 1.25rem): brand name, card and item titles.
- **Body** (400, 1.125rem, 1.6): all running text, max 68ch. Indic scripts: line height 1.75, headings 1.3 with no negative tracking.
- **Label** (600, 0.85 to 1.05rem, display face): buttons (1.05rem), status chips (0.85rem), nav links, selects. Sentence case.

### Named Rules
**The Script-Aware Rule.** Every text role must survive Tamil, Hindi, Telugu, Kannada and Malayalam: no negative tracking, no tight line height, no fixed-height text boxes.

## Layout

Single-column traditional flow in a 72rem container (`min(72rem, 100% - 2.5rem)`), bands full-bleed. Landing sections breathe at 4rem (py-16) rising to 6rem on large screens; the hero is two columns (headline left, plan preview tile right) collapsing to one. Gaps cluster on 8, 12 and 16px with 20 to 24px inside cards. The header is sticky, 4.5rem tall, with a quiet bottom rule; inline nav appears at xl and a menu below. Touch targets are at least 48px (3rem); role and level toggles 48 to 56px.

## Elevation & Depth

Flat, with no shadows and no gradients. Depth is conveyed by a 2px navy outline (prominent), a 1px Quiet Line outline (secondary), and tonal bands (Mint Paper, Deeper Mint, Teal, Navy). Pressed state is a tone step, never a lift.

### Named Rules
**The Flat Sticker Rule.** If a surface needs to stand out, thicken or darken its outline (2px ink, 3 to 4px teal when selected); never add a shadow.

## Shapes

Small, near-square corners: 4px on tiles, buttons, fields, chips and selects; 2px on skeleton bars. Selected cards switch to a 3 to 4px teal border. Placeholder and drop zones use a 2px dashed ink border; Needs Review items use a dashed orange border on Deeper Mint. Bullets are small solid squares, not circles.

## Components

### Buttons
- **Shape:** 4px corners, 2px ink outline, min-height 48px, padding about 9px by 22px, display face 600 at 1.05rem.
- **Primary:** Clinic Teal fill, Mint Paper text. Pressed: Deep Teal.
- **Plain:** Tile Mint fill, Navy Ink text. Pressed: Deeper Mint.
- **On teal bands:** Deep Teal fill with Mint Paper text and Mint Paper outline.
- **States:** no hover change. Focus is a 3px ink outline offset 3px. Disabled is 55% opacity.

### Tiles
- **`tile`:** Tile Mint, 2px ink border, 4px corners; holds icons, plan items, preview.
- **`tile-quiet`:** same with a 1px Quiet Line border for secondary groups.
- **Locked / Needs Review:** Deeper Mint with Soft Ink text and a dashed border.

### Inputs / Fields
- Tile Mint fill, 2px ink border, 4px corners, 48px min-height, Soft Ink placeholder; textareas 12rem. Focus uses the global ink ring; caret teal. Errors appear in a bordered Alert Red inline alert, not on the field.

### Status chip
- Solid status colour, white display-face 600 text at 0.85rem, 4px corners, paired with an icon or word.

### Toggles and selects
- Segmented toggles: 48px, 2px ink border, selected Clinic Teal (or Navy Ink for access level) with Mint Paper text, unselected Tile Mint.

### Skeleton
- Flat Deeper Mint bar stepping to Quiet Line and back over 1.4s; static under reduced motion. No sweep.

### Icons
- The 58 PNGs sliced from the user's icon sheet, shown at 30 to 38px (brand, language flags) and larger on tiles. Never replaced by an icon font or library.

### Motion
- One entrance: fade and 14 to 18px rise over 0.7s, once, skipped for reduced motion. A scroll-drawn 2px ink line in the how-it-works steps. Smooth anchor scrolling with 5rem offset.

## Do's and Don'ts

### Do:
- **Do** outline every raised object in 2px Navy Ink with 4px corners.
- **Do** pair every status colour with a word or icon.
- **Do** use Tile Mint (#f4fdf9) as the lightest surface and Mint Paper (#eafbf6) as the page.
- **Do** keep touch targets at 48px or more and body text at 18px.
- **Do** use only icons from the sliced sheet in `frontend/src/assets/icons`.
- **Do** show real content (synthetic sheet, real generated plan, real translations).
- **Do** use skeleton bars for loading, and honour `prefers-reduced-motion`.

### Don't:
- **Don't** use gradients, shadows, glows, orbs or dot grids.
- **Don't** add hover animation or animated arrows; state changes are tone steps.
- **Don't** use emoji, em dashes or lucide icons.
- **Don't** use kickers or eyebrow labels above headings.
- **Don't** build bento grids or rows of feature cards.
- **Don't** use pure white (#ffffff) as a surface, soft or large corner radii, or rainbow or pastel accents.
- **Don't** use Pending, Completed or Needs Review colours as decoration.
