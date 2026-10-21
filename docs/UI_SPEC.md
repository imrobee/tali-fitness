# UI Spec: web app (4 pages)

Stack: **React + Vite + TypeScript (strict)**, built to static files, calling the FastAPI JSON API (`ARCHITECTURE.md` section 11). Mobile-first for iPhone Safari ("Add to Home Screen" via Safari, no service worker or PWA features). Also usable on desktop.

All business rules (streak, freeze, qualifying day, calorie status, greeting, today) are computed **server-side**. The front end renders what the API returns and only does presentation math (formatting, ring geometry, chart scaling), in pure functions with unit tests.

Suggested libraries (add each with a one-line reason in DECISIONS): `react-router`, `@tanstack/react-query` (loading/error/caching), `react-icons` (verify icon names exist at build time; wrap them in `src/icons.ts`), Vitest + Testing Library, Playwright. Ring and bar chart are **hand-drawn SVG components** (no chart library; the visuals are specific and easy to explain). Styling: CSS variables for tokens plus CSS modules.

## 1. App shell and navigation

Four pages, one **bottom navigation bar** on every page:

| Tab | Route | Label | Icon |
|---|---|---|---|
| Dashboard | `/` | Dashboard | simplified bar chart |
| Activities | `/activities` | Activities | person running |
| Nutrition | `/nutrition` | Nutrition | apple |
| Me | `/me` | Me | person in a circle |

- Fixed to the bottom, ~56px high plus `env(safe-area-inset-bottom)`. Page content gets matching bottom padding so nothing hides behind it. Active tab: filled icon, accent color, bold label, `aria-current="page"`. Inactive: outline icon, secondary text color. Each tab shows icon **and** label.
- `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`, `apple-mobile-web-app-capable`, status-bar style meta, an apple-touch-icon, `theme-color`. No service worker.
- Desktop: content in a centered column (max width ~520px), nav aligned to the same column. Same layout, no separate desktop design.
- **`selectedDate`** is shared state synced to the URL (`?date=YYYY-MM-DD`). Default: `today` from the API. Cannot go past today or before `earliest_date`. Tab switches keep it. Dashboard and Nutrition show the day chooser; Activities scrolls to and highlights that day.
- First load without an API key shows a small gate screen asking for the key (stored in `localStorage`). A 401 returns to it.
- Dark-first. All reference images are dark.

## 2. Dashboard: order and click targets

Top to bottom. Every card responds to the **day chooser** (`selectedDate`) except the streak card, which always shows the current week.

| # | Element | Notes | Tap target |
|---|---|---|---|
| 1 | Greeting | `h1`, large bold, not in a card, no subtitle | none |
| 2 | Day chooser | Pill, not in a card | its own buttons |
| 3 | Streak card | Always the current Mon-Sun week and the real streak. The circle matching `selectedDate` gets an accent underline on its weekday letter | tapping a past or today circle sets `selectedDate` |
| 4 | Recovery day card | Always visible, constant height, shows the **freeze indicator** | its button |
| 5 | Logged exercises card | Collapsible. **Whole card opens Activities** for `selectedDate`; rows are **not** individually clickable | whole card, except the expand button |
| 6 | Calorie budget card | Ring | **whole card opens Nutrition** for `selectedDate` |
| 7 | Protein card | | whole card opens Nutrition |
| 8 | Weekly calorie budget card | Week containing `selectedDate` | whole card opens Nutrition; tapping a bar sets `selectedDate` instead |

Implement "whole card is a link" with the **stretched link pattern** (one `<a>` in the card title whose pseudo-element covers the card; the expand button and chart bars sit above it with `position: relative`). Do not nest buttons inside anchors.

Card style: radius 24px, padding 16px, gap 12px, page padding 16px, system font stack (`-apple-system, system-ui`).

## 3. Reference images (what to take, what to ignore)

Reference images live in `docs/design-reference/`. This text is authoritative where an image and the text disagree.

**Strava iOS streak widget to Streak card.** Take: dark rounded card; gray title "Your streak"; left block orange flame with the number inside (dark numeral) and the unit label **"Days"** in orange below; right block 7 circles Mon-Sun with the **day-of-month number inside** and single-letter weekday labels below. States: activity day = solid white circle with a black activity icon; past day without a qualifying day = dark filled circle (one step lighter than the card) with white date number; today (pending) = white outlined ring with date number; future = dim thin outline with dim number. Ignore the Strava logo. Add: one calorie marker per day (section 5.3).

**MyNetDiary to Day chooser, Calorie card, Protein card, Weekly chart.** Take: pill with calendar icon, "Today", and chevrons; dark card with three-column rhythm and a calorie ring that fills **green** (ours is a **plain circular ring, not an apple**); protein row (label, "21g, 109g left", percentage at right, thin green bar); weekly bars with a **dashed budget line**, green when under, **orange and rising above the line** when over, two-line labels (`Mo` over `19`), today's label in an accent color with an underline. Ignore: apple shape, `...` menu, Exercise/Steps/Water/Notes column, meal columns, "View All Meals", pencil icon.

**Concept mock (generated) is overall feel only. DO NOT COPY:** neon/teal glowing ring; orange-filled day circles with flame/heart icons and badges; three-dot markers; garbled copy; "Synced 2h ago"; five-tab nav with Home/Calendar/Trends/Log/Settings; teal protein bar with the percentage inside it; weekly chart without a dashed budget line. Take: card rhythm, dark palette, large bold greeting, "Eaten / Budget" pairing, the always-visible recovery card idea.

## 4. Rules the UI must reflect (source of truth: `ARCHITECTURE.md` section 8)

- A day **qualifies** with a workout AND logged calories. Over/under budget never matters.
- **One freeze.** A recovery day uses it. It resets on the next qualifying day. Two non-qualifying days in a row break the streak.
- Yesterday not logged = **at risk** (healable until midnight; count shown unchanged with a quiet message).
- Recovery days only for today or yesterday.

## 5. Components

### 5.1 Greeting
`"<greeting>, <nickname>"` from the API (no nickname: just the greeting). Large bold white, left aligned. Refetch the dashboard when the tab becomes visible so the greeting and "today" stay correct across boundaries.

### 5.2 Day chooser
Full-width pill: `‹`, calendar icon + label, `›`. Label: "Today", "Yesterday", or "Sat, Oct 17". `›` disabled on today; `‹` disabled at `earliest_date`. Tapping the label when not on today jumps back to today. Buttons ≥ 44px tall. Accessible names: "Previous day", "Next day", "Jump to today".

### 5.3 Streak card
Title "Your streak" top-left. Layout: flame+count block, then the 7-day row. No overflow menu (pause is not in v1).

| `state` | Circle |
|---|---|
| `qualifying` | Solid white circle, **one** black icon for `primary_activity_type` (longest-duration activity that day). No badges, "+N", or "x2". Fallback icon for unknown types |
| `today_pending` | White outlined ring with the date number; becomes a solid circle with icon when it qualifies |
| `missed` | Dark filled circle (one step lighter than the card) with white date number. No red |
| `at_risk` | Same as `missed` plus a small dashed outline (healable); never red |
| `recovery` | Soft-tinted circle with a **snowflake** glyph (the freeze) |
| `future` | Dim thin outline with a dim date number, no marker |

**Calorie marker** (directly under each circle for past days and today; live for today):

| `calorie_status` | Shape | Color |
|---|---|---|
| `not_logged` | hollow circle (>= 1.5px stroke) | neutral gray |
| `within` | filled circle | green |
| `over` | **filled square** | orange |
| `not_set` | filled circle | neutral gray (`--neutral`); calories logged but no budget in effect |

Marker 8-10px. **Shape carries the meaning, not color.** Hidden on `recovery` and `future` days unless calories were logged. Weekday letters sit below the marker; if crowded, move letters above the circles. Circles >= 32px; if 7 circles plus the flame block do not fit, put the flame+count in the title row and let circles span the width. At 200% zoom stack the flame block above the row.

Footer: one quiet line only when relevant (copy in section 9).

### 5.4 Recovery day card (always visible)
Same slot and roughly the same height in every state. Title and body left, button right, **freeze indicator** as a pill with a snowflake icon and text (never color alone). Acts on `selectedDate`. State comes from `recovery.state`:

| State | Meaning | Title / body | Pill | Button |
|---|---|---|---|---|
| `available` | day is today/yesterday, not qualifying, previous day qualified | "Taking a recovery day?" / "Rest counts. Your freeze keeps the streak on hold." | "1 freeze available" | **Log recovery** |
| `logged` | `selectedDate` is a valid recovery day | "Recovery day logged" / "Your streak is on hold. A workout and logged calories reset your freeze." | "Freeze used" | **Undo** |
| `no_freeze` | previous day was the recovery day | "No freezes left" / "Log a workout and calories to reset your freeze." | "0 freezes" | none |
| `blocked` | previous day did not qualify, so a freeze cannot hold the streak | "Fill in yesterday first" / "A freeze needs yesterday to be counted." | "0 freezes" | **Go to yesterday** |
| `counted` | `selectedDate` already qualifies | "This day counted" / "Nice work. No recovery needed." | "1 freeze available" | none |
| `locked` | older than yesterday | "Recovery day" / "Recovery days can only be set for today or yesterday." | none | none |

`POST /recovery` on success refetches the dashboard. Errors show inline text from the API message.

### 5.5 Logged exercises card
- Title "Logged exercises" with a small gray count. Shows the activities for `selectedDate`, **ordered most recent first by start time**.
- **Collapsed by default on launch: exactly 1 row** (`COLLAPSED_EXERCISE_COUNT = 1`). A **down chevron** button at the bottom center expands to all rows; the chevron rotates up to collapse (`aria-expanded`, label "Show 2 more exercises" / "Show fewer exercises"). Session-only state. Height animation off under reduced motion.
- 0 activities: "No exercises logged for this day." and no chevron. 1 activity: no chevron.
- **Row** (card-in-card on the elevated surface; **not clickable, no `>`**): icon in a circle (run, weightlifting, cycling, swim, walk, yoga, HIIT, generic fallback), **title** (Strava activity name), **duration as subtitle** (`32 min`, `1 h 05 min`, `1 h`).
- The whole card links to `/activities?date=<selectedDate>`.

### 5.6 Calorie budget card
- Title "Calorie budget". Three columns: **Eaten** (e.g. `654`), the ring, **Budget** (e.g. `1,853`), with small gray captions above the numbers.
- **Ring** (plain circle, SVG): ~180px, ~16px stroke, round caps, starts at 12 o'clock, clockwise, flat color, **no glow**. Track: elevated surface. Fill: **green** by `eaten / budget`. Center: large **remaining** number (green) with caption "kcal left".
- **Over budget:** ring full and **orange**, center shows the overage in orange with caption "kcal over". Non-color cues: the "over" caption, plus a dashed overflow arc inside the ring covering `(eaten - budget) / budget`, capped at 100%.
- Fill animates ~0.6s ease-out; none under reduced motion. No budget set: empty ring and a "Set your calorie budget" link to Me.

### 5.7 Protein card
Left "Protein" (bold) and "21g, 109g left" (gray); right the percentage (`16%`, nearest whole number). Thin (~8px) full-width rounded bar: elevated-surface track, **green** fill, capped at 100%. The percentage may exceed 100% in text. **Never turns orange.** The percentage is **outside** the bar. No goal set: "Set a protein goal" link to Me.

### 5.8 Weekly calorie budget card
Title "Weekly calorie budget". One bar per day, Mon-Sun, for the week containing `selectedDate`. **Dashed horizontal line at the budget** with a small label at its right end (step line if budgets differ across the week). Bar color from `status`: `within` green; `over` **orange and rising above the dashed line**; `not_set` **neutral gray** (`--neutral`; no budget line segment for that day); `not_logged` and `future` get **no bar**. Y max = `max(1.25 x budget, tallest bar x 1.1)`. Bars ~22px wide with rounded tops. Two-line x labels (`Mo` over `19`); the selected day's label uses the accent color with a 2px underline. Tapping a bar sets `selectedDate`. Today's bar is live.

## 6. Other pages (v1)

### 6.1 Activities
- Title "Activities". **Day-grouped list, newest first**, default last 30 days with a "Load older" button. Day header: "Mon, Oct 19" plus a "Today" or "Yesterday" chip. When arriving with `?date=`, scroll to that day and highlight it.
- Activity item (card): icon circle, title, time range, duration, and a type summary: run = `5.2 km · 5:41 /km · 29 min`; strength = `9 exercises · 22 sets · 3,491 kg`.
- Strength summary omits the volume when it is 0 (bodyweight, cardio, and timed sets only): `6 exercises · 12 sets`.
- **Tap an item to expand** (here items are interactive): lifting shows exercises and sets by kind: `Set 1  20 kg × 8`; sets entered in lb show `18.1 kg (40 lb) × 12`; bodyweight `Set 1  10 reps`; distance `Set 1  21 km · 1 h`; timed hold `Set 1  1 min 30 s`. Equipment appears as a muted suffix. An exercise note appears as one muted line under the exercise name. If `parse_status` is not `ok`, show a small "Couldn't read some sets" tag and the raw description in a collapsible monospace block.
- Empty, loading (skeleton), and error states. Week/month calendar and trends arrive in Slice 7.

### 6.2 Nutrition
Title "Nutrition", the day chooser, then the **calorie budget card, protein card, and weekly calorie budget card** (same components as the dashboard, not links here). Trends arrive in Slice 7.

### 6.3 Me
- **Profile and targets:** nickname, calorie budget (kcal), protein goal (g). Helper text: "Changes apply from today. Past days keep their old targets." Sanity limits (calories 800-6000, protein 0-400). Save button with inline errors.
- **Timezone:** shown read-only ("Asia/Manila") in v1.
- **Connection:** API key masked, with "Change".
- **Data and sync** panel (from `/pipeline/health`): per source (Strava, Apple Health) "Last successful sync" as relative time plus clock time, status shown as icon **and** text (OK / Delayed / Failed), failures in the last 7 days; "Quarantined records: N" expandable to a list (source, reason, raw snippet); "Data quality: N passed, N warnings, N failed" expandable to the check list.

## 7. Design tokens (`web/src/theme/tokens.css`; components must not use raw hex)

| Token | Intent | Starting value (verify contrast) |
|---|---|---|
| `--surface` | page background | near-black |
| `--card` | card background | ~#1C1C1E |
| `--card-elevated` | tracks, missed circles, exercise rows | one step lighter |
| `--text` / `--text-secondary` | text | white / gray |
| `--within-budget` | ring, bars, within marker, protein | green ~#66B33F |
| `--over-budget` | over ring, bars, marker | orange ~#E39A3B |
| `--flame` | flame and unit label | orange ~#E8622A; built as `#FC4C02`, Strava's orange (DECISIONS D62) |
| `--accent` | selected day, active tab | blue; built as `#409CFF` for 4.5:1 (D62) |
| `--neutral` | `not_logged` hollow marker, `not_set` marker and bar | neutral gray |

`--over-budget` is one token shared by ring, bars, and marker. **No red anywhere.** Light mode is a token swap, only if time allows.

## 8. Accessibility (required)

- Semantic HTML: `<main>`, `<nav aria-label="Primary">`, one `h1` per page, logical heading order, visible `:focus-visible`, touch targets >= 44px.
- **Contrast:** markers, bars, ring >= 3:1 non-text contrast; text >= 4.5:1. Check with a contrast tool. Verify markers and bars in grayscale and under a color-vision-deficiency simulation; they must stay distinguishable by **shape and bar position**.
- Each streak circle plus marker is **one** element: `"<Weekday>, <Month> <day>: <state>. <activity or none>. Calories: <not logged | within budget | over budget | logged, no budget set>."` Example: `"Tuesday, October 13: qualifying day. Workout. Calories within budget."`
- Streak summary: `"Streak: 12 days. Today: workout logged."` plus at-risk status.
- Ring: `"Calories: 654 eaten of 1,853, 1,199 left."` or `"... 320 over budget."` Protein: `"Protein: 21 of 130 grams, 16 percent."` Chart: summary (`"Weekly calories: 4 days within budget, 1 over, budget 1,853."`) plus per-bar labels.
- Freeze indicator and every status are text plus icon.
- Respect `prefers-reduced-motion` and `prefers-contrast`. Use rem units and verify at 200% zoom.

## 9. Copy (no red, no shame, no exclamation marks, no modals)

| Situation | Copy |
|---|---|
| Yesterday not logged (at risk) | "Yesterday isn't logged. Fill it in to keep your 12-day streak." (action: "Fill in" selects yesterday) |
| Streak broke at midnight | "Fresh start today. Your best was 12 days." |
| Today qualified | "Nice. Today's counted." |
| Over budget | No message; ring/marker/bar convey it; it never affects the streak |
| Recovery states | see 5.4 |
| Empty exercises | "No exercises logged for this day." |
| Stale data (Me panel) | "Last sync 9 hours ago" with status text |

The at-risk, fresh-start, and counted messages appear as one quiet line at the bottom of the streak card.

## 10. Loading, empty, and error states

Skeleton cards while loading (no layout jump). Per-card error with a "Retry" button rather than a full-page error. Offline or API down: banner "Can't reach the server" with retry; never show stale numbers without saying so. 401 goes to the key gate.

## 11. Visual verification loop (the agent must do this)

- API runs with `APP_ENV=test` and `NOW_OVERRIDE` so greeting and "today" are deterministic. `scripts/seed_demo.py --scenario <name>` loads data (including the Hevy sample as a Saturday session).
- `make screenshots` renders each scenario at **393x852** (iPhone) and **1280x800** (desktop), dark scheme, to `docs/screenshots/`. Compare with sections 3, 5, and 12; fix; repeat.
- **Staging:** M1 (Slice 6a) renders only `midweek`, `at_risk`, and `edge_empty` at 393x852. The full set below, at both sizes, is due by M2 (Slice 6b).

Scenarios:
1. **midweek**: now Sat 2026-10-17 14:00. Mon Q (run), Tue Q over budget (strength), Wed recovery, Thu Q, Fri Q, Sat pending with 654 of 1,853 kcal and 21/130 g protein, Sun future. Greeting "Good afternoon, Rob". Saturday has 3 activities.
2. **fresh_monday**: now Mon 2026-10-19 15:55. Nothing logged today; prior week healthy; recovery card `available`.
3. **over_budget**: 2,173 of 1,853.
4. **at_risk**: yesterday not logged; streak shows the unchanged count and the quiet message; recovery card `blocked`.
5. **freeze_used**: yesterday was the recovery day; today pending; recovery card `no_freeze`.
6. **recovery_logged** (today is a valid recovery day) and **counted** (today already qualifies).
7. **past_day**: `selectedDate` older than yesterday; recovery card `locked`.
8. **edge_empty**: no targets set; no data this week; empty exercises.
9. Pages: activities (midweek, with the Hevy session expanded and one `partial` session), nutrition, me (healthy pipeline and a stale/failed one).
10. **large_font** (200% zoom) and **reduced_motion**.

## 12. Acceptance checklist

- [ ] Order is exactly: greeting, day chooser, streak card, recovery card, logged exercises, calorie budget, protein, weekly chart. The greeting has no card.
- [ ] Bottom nav has 4 tabs with the specified icons and labels; active state is clear; safe-area padding works on iPhone.
- [ ] Streak card matches the Strava structure: flame + number + "Days"; date numbers inside circles; white circle + black icon for activity days; white outline for today; dark filled circles for missed; dim outline for future; one marker per day (hollow circle / filled green dot / filled orange square / filled gray dot for `not_set`).
- [ ] Recovery card always visible with constant height, correct state, and the freeze indicator as icon plus text.
- [ ] Exercises card shows exactly 1 row at launch (most recent first) with a chevron when there are more; rows show icon, title, duration; rows are not clickable; the card opens Activities for the selected date.
- [ ] Calorie, protein, and weekly cards open Nutrition; the bar tap sets `selectedDate`.
- [ ] Ring is a plain flat circle (no apple, no glow), green fill, orange when over with "kcal over" and a dashed overflow arc.
- [ ] Protein is its own card: label, "Xg, Yg left", percentage at right, thin green bar, percentage outside the bar.
- [ ] Weekly chart has a visible dashed budget line; over-budget bars are orange and rise above it; selected-day label has accent color and underline.
- [ ] Day chooser drives every card except the streak; Activities scrolls to the selected day.
- [ ] Me page saves targets (effective today) and shows the pipeline health panel with text-plus-icon statuses.
- [ ] No red anywhere; nothing from the "do not copy" list.
- [ ] Contrast, grayscale, and 200% zoom checks pass.
