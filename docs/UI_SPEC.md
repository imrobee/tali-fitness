# UI Spec: web app (4 pages)

Stack: **React + Vite + TypeScript (strict)**, built to static files, calling the FastAPI JSON API (`ARCHITECTURE.md` section 11). Mobile-first for iPhone Safari ("Add to Home Screen" via Safari, no service worker or PWA features). Also usable on desktop.

All business rules (streak, kinds of day, calorie status, greeting, today) are computed **server-side**. The front end renders what the API returns and only does presentation math (formatting, ring geometry, chart scaling), in pure functions with unit tests.

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
- **`selectedDate`** is shared state synced to the URL (`?date=YYYY-MM-DD`). Default: `today` from the API. Cannot go past today or before `earliest_date`. Tab switches keep it. Dashboard and Nutrition show the day chooser; Activities lists only that day (Slice 7a; it scrolled to and highlighted it in 6b).
- **Sign-in gate** (Slice 8a, `AUTH_SPEC.md` section 9): the app asks the server (`GET /auth/me`) and shows the pages only to a signed-in browser. Otherwise the **launch screen** (D117): one centred column, max 360px, 24px side padding, at every size. Top to bottom: the app icon (88px), the "tali" wordmark (120px wide, the page's `h1`, `aria-label` "tali"), 60px of space, a **Sign in with Google** pill in Google's button colours with their "G" (a plain link to `/auth/login?next=<this page>`, no Google script in the page), the note "This app is limited to invited users only. To learn more about the app, check out the Demo version." (12.5px, `--launch-note`), and a mint outlined **Demo version** button: a plain link to the demo service (`demo_url` from `GET /auth/method`; without one it does nothing). Buttons are 48px, 15px text, with a mint focus ring. A faint ring is cropped by the bottom-right corner (`aria-hidden`). No theme toggle on this screen; it follows the saved theme. In local key mode (`GET /auth/method` says `key`) a **Dev key** field and **Sign in** take the Google button's place. Any 401 brings the screen back; the server unreachable shows "Can't reach the server" with Retry. **On the demo service** (`GET /auth/method` says `demo`) there is no launch screen: opening it starts a demo visit, and every page header shows a **Demo data** pill (mint outline and text, beside the theme toggle). The Me page's Account card says "A demo visit: synthetic data, and nothing you change is saved." instead of Sign out, and Data and sync has no Sync now or Run Health Push. A write shows the server's "Demo mode: changes aren't saved." where that control shows its errors. Nothing about sign-in is kept in browser storage; the old API key's `localStorage` entry is deleted on every load. Screenshots: `launch-iphone.png`, `launch-desktop.png`, `launch-light-iphone.png`.
- Dark-first. All reference images are dark.

## 2. Dashboard: order and click targets

Top to bottom. Every card responds to the **day chooser** (`selectedDate`) except the streak card, which always shows the current week.

| # | Element | Notes | Tap target |
|---|---|---|---|
| 1 | Greeting | `h1`, large bold, not in a card, no subtitle | none |
| 2 | Day chooser | Pill, not in a card | its own buttons |
| 3 | Streak card | Always the current Mon-Sun week and the real streak. For reading only: the day chooser picks the day (Rob, 2026-10-27) | none |
| 4 | Recovery day card | Constant height (Slice 7d: no freeze pill). Hidden on a day with an activity, unless a recovery day is logged (so it can be undone) | its button |
| 5 | Activities card | Collapsible. **Whole card opens Activities** for `selectedDate`; rows are **not** individually clickable | whole card, except the expand button |
| 6 | Calorie budget card | Ring | **whole card opens Nutrition** for `selectedDate` |
| 7 | Protein card | | whole card opens Nutrition |
| 8 | Calories by day card | Week containing `selectedDate` | whole card opens Nutrition; tapping a bar sets `selectedDate` instead |

The Last week card (Slice 7b) was removed from the dashboard (Rob, 2026-10-27); `GET /summary/week` stays. Every card title has one style: 17px, semibold, white. A tapped card (or tab) opens its page at the top.

Implement "whole card is a link" with the **stretched link pattern** (one `<a>` in the card title whose pseudo-element covers the card; the expand button and chart bars sit above it with `position: relative`). Do not nest buttons inside anchors.

Card style: radius 24px, padding 16px, gap 12px, page padding 16px, system font stack (`-apple-system, system-ui`).

## 3. Reference images (what to take, what to ignore)

Reference images live in `docs/design-reference/`. This text is authoritative where an image and the text disagree.

**Strava iOS streak widget to Streak card.** Take: dark rounded card; gray title "Your streak"; left block orange flame with the number inside (dark numeral) and the unit label **"Days"** in orange below; right block 7 circles Mon-Sun with the **day-of-month number inside** and single-letter weekday labels below. States: activity day = solid white circle with a black activity icon; past day without a qualifying day = dark filled circle (one step lighter than the card) with white date number; today (pending) = white outlined ring with date number; future = dim thin outline with a white date number (Rob, 2026-11-05). Ignore the Strava logo. Add: one calorie marker per day (section 5.3).

**MyNetDiary to Day chooser, Calorie card, Protein card, Weekly chart.** Take: pill with calendar icon, "Today", and chevrons; dark card with three-column rhythm and a calorie ring that fills **green** (ours is a **plain circular ring, not an apple**); protein row (label, "21g, 109g left", percentage at right, thin green bar); weekly bars with a **dashed budget line**, green when under, **orange and rising above the line** when over, two-line labels (`Mo` over `19`), today's label in an accent color with an underline. Ignore: apple shape, `...` menu, Exercise/Steps/Water/Notes column, meal columns, "View All Meals", pencil icon.

**Concept mock (generated) is overall feel only. DO NOT COPY:** neon/teal glowing ring; orange-filled day circles with flame/heart icons and badges; three-dot markers; garbled copy; "Synced 2h ago"; five-tab nav with Home/Calendar/Trends/Log/Settings; teal protein bar with the percentage inside it; weekly chart without a dashed budget line. Take: card rhythm, dark palette, large bold greeting, "Eaten / Budget" pairing, the always-visible recovery card idea.

## 4. Rules the UI must reflect (source of truth: `ARCHITECTURE.md` section 8; Slice 7d)

- A good day: food logged within budget and a workout. Over budget is fine once; **two over-budget days in a row** end the streak. A rest day (food without a workout, a workout without food, or a logged recovery day) is fine once; **two rest days in a row** end it. **A day with nothing logged** ends it.
- **Relaxed weekends** (a setting on Me, from today on) and a **vacation or injury break**: only a day with nothing logged ends the streak.
- The count is every day that kept the streak.
- Today never ends the streak before midnight; yesterday that would end it is **at risk** (count shown unchanged with a quiet message) until today ends.
- Recovery days only for today or yesterday.

## 5. Components

### 5.1 Greeting
`"<greeting>, <nickname>"` from the API (no nickname: just the greeting). Large bold white, left aligned. Refetch the dashboard when the tab becomes visible so the greeting and "today" stay correct across boundaries.

### 5.2 Day chooser
Full-width pill: `‹`, calendar icon (22px) + label (17px), `›`. Label: "Today", "Yesterday", or "Sat, Oct 17". `›` disabled on today; `‹` disabled at `earliest_date`. Tapping the middle opens the phone's date picker (an invisible date input over it, as on the vacation chips), limited to `earliest_date`..today. Buttons ≥ 44px tall. Accessible names: "Previous day", "Next day", "Choose a day. Showing Sat, Oct 17".

### 5.3 Streak card
Title "Your streak" top-left, styled like every card title. Layout: flame+count block, then the 7-day row; the flame's bottom lines up with the bottom of the rings. The days are not buttons. No overflow menu (pause is not in v1).

The circle shows what happened that day, from `kind`, `state` and `primary_activity_type` (Slice 7d):

| Day | Circle |
|---|---|
| a workout (any kind) | Solid white circle, **one** black icon for `primary_activity_type` (longest activity). No badges, "+N", or "x2". Fallback icon for unknown types |
| a rest day without a workout (`kind = recovery`) | Soft-tinted circle with a **snowflake** |
| today, no workout yet | Like a future day but in white: thin white outline, white date number. Not a rest day yet, even with food logged; the snowflake only when a recovery day is logged by hand (`recovery_logged`) |
| yesterday `at_risk`, no workout | Dark filled circle with a dashed edge (healable); never red |
| anything else (missed, over without a workout, before the data) | Dark filled circle (one step lighter than the card) with the date number. No red |
| `future` | Dim thin outline with a white date number, no ring |

**Calorie ring** (Slice 7d; replaces the marker under the circle): a 2.5px ring around each circle (42px across around a 28px circle, with a 4.5px blank gap between them; Rob, 2026-11-05), for past days and today, live for today. Three states only:

| `calorie_status` | Ring |
|---|---|
| `not_logged` | grey (`--neutral`), full circle |
| `within`, or `not_set` (logged without a budget: nothing to be over) | green, full circle |
| `over` | orange, **cut off at the very bottom**, with a small orange **triangle** in the gap, so "over" never relies on colour alone |

No ring on future days. Weekday letters sit below the circles. Rings stay 42px. On phones (up to 460px wide) a small flame, the count and "Days" move to the right of the title row and the circles span the width; at 200% zoom the week wraps three a row (3 + 3 + 1).

Footer: one quiet line only when relevant (copy in section 9).

### 5.4 Recovery day card (always visible)
Same slot and the same height in every state. Title and body left, button right. Acts on `selectedDate`. A logged recovery day makes that day a rest day (a manual override, kept by Rob in Slice 7d; the single freeze and its pill are gone). State comes from `recovery.state` (ARCHITECTURE 8.3):

| State | Meaning | Title / body | Button |
|---|---|---|---|
| `available` | today or yesterday would end the streak, and a rest day would help | "Taking a recovery day?" / "Logging it makes this a rest day, so your streak keeps going." | **Log recovery** |
| `logged` | a recovery day is logged for `selectedDate` | "Recovery day logged" / "This is a rest day. Two rest days in a row end the streak." | **Undo** |
| `blocked` | the day before was a rest day, so a second one would end the streak anyway | "Rest day yesterday" / "Two rest days in a row end the streak. A workout keeps it going." | none |
| `counted` | the day already keeps the streak | "This day counted" / "Nice work. No recovery needed." | none |
| `locked` | older than yesterday | "Recovery day" / "Recovery days can only be set for today or yesterday." | none |

`POST /recovery` on success refetches the dashboard. Errors show inline text from the API message.

### 5.5 Logged exercises card
- Title "Logged exercises" with a small gray count. Shows the activities for `selectedDate`, **ordered most recent first by start time**.
- **Collapsed by default on launch: exactly 1 row** (`COLLAPSED_EXERCISE_COUNT = 1`). A **down chevron** button at the bottom center expands to all rows; the chevron rotates up to collapse (`aria-expanded`, label "Show 2 more exercises" / "Show fewer exercises"). Session-only state. Height animation off under reduced motion.
- 0 activities: "No exercises logged for this day." and no chevron. 1 activity: no chevron.
- **Row** (card-in-card on the elevated surface; **not clickable, no `>`**): icon in a circle (run, weightlifting, cycling, swim, walk, yoga, HIIT, generic fallback), **title** (Strava activity name), **duration as subtitle** (`32 min`, `1 h 05 min`, `1 h`).
- The whole card links to `/activities?date=<selectedDate>`.

### 5.6 Calorie budget card
- Title "Calorie budget". Three columns: **Eaten** (e.g. `654`), the ring, **Budget** (e.g. `1,853`), with small gray captions above the numbers. Eaten and Budget are each centred in their column (Rob, 2026-11-05).
- **Ring** (plain circle, SVG): ~180px, ~16px stroke, round caps, starts at 12 o'clock, clockwise, flat color, **no glow**. Track: elevated surface. Fill: **green** by `eaten / budget`. Center: large **remaining** number (green) with caption "kcal left".
- **Over budget:** ring full and **orange**, center shows the overage in orange with caption "kcal over" (the non-colour cue). No dashed overflow arc (removed by Rob, Slice 7d).
- No fill animation: the ring is drawn at its value straight away, also when switching pages (Rob, Slice 7d). No budget set: empty ring and a "Set your calorie budget" link to Me. The ring is centred in the card: the two side columns are always equal.

### 5.7 Protein card
Left "Protein" (bold) and "21g, 109g left" (gray); right the percentage (`16%`, nearest whole number). Thin (~8px) full-width rounded bar: elevated-surface track, **green** fill, capped at 100%. The percentage may exceed 100% in text. **Never turns orange.** The percentage is **outside** the bar. No goal set: "Set a protein goal" link to Me.

### 5.8 Calories by day card
Title "Calories by day", with "This week" (or "Oct 19 – 25" for another week) at the right of the title row. One bar per day, Mon-Sun, for the week containing `selectedDate`. **Dashed horizontal line at the budget** (step line if budgets differ across the week), with no figure printed on it (Rob, Slice 7d; the budget is in the spoken summary and on the calorie card). Bar color from `status`: `within` green; `over` **orange and rising above the dashed line**; `not_set` **neutral gray** (`--neutral`; no budget line segment for that day); `not_logged` and `future` get **no bar**. Y max = `max(1.25 x budget, tallest bar x 1.1)`. Bars ~22px wide with rounded tops. Two-line x labels (`Mo` over `19`); the selected day's two lines use the accent color, and only the date number has a 2px underline. Tapping a bar sets `selectedDate`. Today's bar is live.

## 6. Other pages (v1)

### 6.1 Activities
- Title "Activities". **Day-grouped list, newest first**, default last 30 days with a "Load older" button. Day header: "Mon, Oct 19" plus a "Today" or "Yesterday" chip. When arriving with `?date=` (from the calendar or the dashboard), the list shows only that day, from any month, with "Showing one day" and a **Show all days** button that clears `?date=`.
- Activity item (card): icon circle, title, time range, duration, and a type summary: run = `5.2 km · 5:41 /km · 29 min`; strength = `9 exercises · 22 sets · 3,491 kg`.
- Strength summary omits the volume when it is 0 (bodyweight, cardio, and timed sets only): `6 exercises · 12 sets`.
- **Tap an item to expand** (here items are interactive): lifting shows exercises and sets by kind: `Set 1  20 kg × 8`; sets entered in lb show `18.1 kg (40 lb) × 12`; bodyweight `Set 1  10 reps`; distance `Set 1  21 km · 1 h`; timed hold `Set 1  1 min 30 s`. Equipment appears as a muted suffix. An exercise note appears as one muted line under the exercise name. If `parse_status` is not `ok`, show a small "Couldn't read some sets" tag and the raw description in a collapsible monospace block.
- Empty, loading (skeleton), and error states.
- **Order:** calendar card, personal records card, then the list. The training trend and muscle volume cards were taken off the page (Rob, 2026-11-05); their API endpoints, SQL and component tests stay.
- **Muscle volume card:** not on any page since 2026-11-05 (see Order above).
- **Personal records card:** title "Personal records" (no count). Five rows, then "Show N more" (chevron, `aria-expanded`). A row: exercise name, the estimated 1-rep max at the right, and "From 22.5 kg × 6 on Oct 17 · Chest". No "New" chip, no "Up … on the record before" line and no formula footer (Rob, 2026-11-05). The row's accessible name is the whole sentence.
- **Weights follow the unit set on Me** everywhere: sets ("44.1 lb (20 kg) × 8"; a set typed in the chosen unit shows exactly what was typed, "40 lb × 12"), volume, records, the training trend's lifting line, the weight card, last week's average weight.
- **Calendar card:** title "Calendar" with a **Week / Month** switch (a pill of two buttons, the pressed one filled white; `aria-pressed`). Under it `‹ October 2026 ›` (`Oct 12 – 18` in week view); the arrows go to the server's `previous` and `next` dates and are disabled when those are null. Then `M T W T F S S` and full Monday-Sunday weeks of circles (36px, shrinking with their column at 200% zoom). A day with training: **solid white circle with a dark date number** (numbers, not icons, because in a month grid the numbers are how you find a day). A valid recovery day: the tinted snowflake circle. Today without training: white outline. Days of the neighbouring months: the same at lower opacity. Future days: dim and disabled. The filtered day: a 2px accent ring around its circle and `aria-pressed`. Tapping a day filters the list to it; tapping it again clears the filter. Accessible name: `"Wednesday, October 14: 2 activities, the longest a strength session."`, `"... recovery day."`, `"... no activity."`, `"... not yet."`.
- **Training trend card:** not on any page since 2026-11-05 (see Order above).
- Built (Slice 6b): only lifting sessions with sets, and sessions whose text was only partly read, open; other activities are plain rows. A strength session with no sets shows its duration instead of "0 exercises".

### 6.2 Nutrition
Title "Nutrition", the day chooser, then the **calorie budget card, protein card, and weekly calorie budget card** (same components as the dashboard, not links here), then the **calorie trend card** (Slice 7a): title "Calorie trend" with the Week / Month switch; one line of text, "7-day average: 1,742 kcal and 112 g of protein a day" (the week ending yesterday; Rob, 2026-11-05); one bar per period for the average kcal **per logged day**, coloured like the weekly card (`within` green, `over` orange, `not_set` neutral, nothing logged: no bar), a dashed segment at each period's average budget with the value at the right end, the running period lighter with a dashed edge. The trend card does not follow the day chooser.

**Weight card** (Slice 7b, below the calorie trend): title "Weight"; two lines, "Last weigh-in: 74.8 kg" and "7-day average: 74.9 kg" (Rob, 2026-11-05); "Down 0.3 kg on last week." (rounded to a tenth); "1.9 kg above your goal of 73.0 kg." (from the average; "Set a weight goal on Me to see how far you are from it." with no goal). The chart: one dot per weigh-in, its weight printed above it in the person's unit where it fits (`labelledDots`: the latest always, then only dots far enough apart not to overlap); a solid line for the 7-day average that bends **only at weigh-ins** (no vertex on a day without one, so every rise or fall sits on a real dot); a dashed line at the goal, first and last dates and the goal under it. The chart starts at the first weigh-in in the range, so the first point is always at the left edge (a single weigh-in sits at the left too). Each dot has a title with its day and weight; the screen-reader summary is the three sentences. Days with no weigh-in have no dot. Not affected by the day chooser.

### 6.3 Me
- **Profile and targets:** nickname, calorie budget (kcal), protein goal (g), weight goal (one decimal; 30-250 kg or 67-551 lb) with a **kg / lb switch** beside it (Slice 7b). The switch saves the preference at once and converts the goal on screen (72.575 kg reads 160 lb); it never changes stored data. An untouched goal is never saved again from its rounded text. Helper text: "Changes apply from today. Past days keep their old targets." Sanity limits (calories 800-6000, protein 0-400). Save button with inline errors.
- **How your streak works** (Slice 7d): the rules of 4 and ARCHITECTURE 8 as a bulleted list in plain words, never the internal names S, O, R, M (text in `web/src/lib/streakRules.ts`). The weekend rule is not in the list.
- **Weekends** (its own card, Rob, 2026-11-05): title "Weekends" with a **Strict / Relaxed** switch at the right, saved at once, applying from today. Under it the weekend rule, which follows the switch ("Weekends follow the same rules as weekdays." / "On weekends, only a day with nothing logged ends the streak."), then "Changes apply from today."
- **Vacation or injury** (Slice 7d): help "During a break, only a day with nothing logged ends your streak." Then a **Log break** button that opens the form (a break still running or to come shows it open): a **From** row and a **To** row, each with a date chip showing a calendar icon and **"Choose date"** in the accent colour until a date is picked, then the date ("Mon, Nov 2"). The native date input lies invisibly over the chip, so a tap anywhere opens the phone's picker. **Save break**; **End break** when one is running or to come. Past dates are allowed (a forgotten break). "Last break: Oct 12 – Oct 15" under it once one has ended. Errors from the API inline.
- **Timezone:** shown read-only ("Asia/Manila") in v1.
- **Account:** "Signed in" and **Sign out** (no email or name). Sign out ends the session on the server, drops every page's data from memory, and shows the sign-in screen.
- **Data and sync** panel (from `/pipeline/health`): per source (Strava, Apple Health) "Last successful sync" as relative time plus clock time, status shown as icon **and** text (OK / Delayed / Failed), failures in the last 7 days; "Quarantined records: N" expandable to a list (source, reason, raw snippet); "Data quality: N passed, N warnings, N failed" expandable to the check list. Under Strava a **Sync now** button (Slice 7c): "Syncing..." while Airflow works, then "Synced. New activities are in." and every page reloads; the API's reason when refused ("Try again in 90 s."). Under Apple Health a **Run Health Push** link (`shortcuts://run-shortcut?name=Health%20Push`): the server cannot reach the phone, so it opens the Shortcut.

## 7. Design tokens (`web/src/theme/tokens.css`; components must not use raw hex)

Two themes (Rob, 2026-11-04; D116). Dark is the default and keeps the original true-black and iOS-grey surfaces and white text; the data colours, buttons and the whole light theme come from the **Tali brand guide**. Light is a token swap under `[data-theme="light"]` on `<html>`. Values below are the built ones.

| Token | Intent | Dark | Light |
|---|---|---|---|
| `--surface` | page background | `#000000` | `#F5F7F6` Paper |
| `--card` | card background | `#1C1C1E` | `#FFFFFF` |
| `--card-border` | card hairline (inset, takes no space) | transparent | `#D6DEDB` |
| `--card-elevated` | missed circles, exercise rows, secondary buttons | `#2C2C2E` | `#EBF0EE` |
| `--text` / `--text-secondary` / `--text-dim` | text (dim: future days only) | `#FFFFFF` / `#A1A1A6` / `#636366` | `#10231F` / `#3E4F4B` / `#7A8B87` |
| `--within-budget` | ring, bars, within marker, protein | `#4CCB9F` Mint | `#1F6F66` Teal |
| `--over-budget` | over ring, bars, marker | `#F5A524` amber | `#CF6F00` |
| `--flame` / `--on-flame` | streak flame, count and "Days" **only**; never a ring | `#FF8A3D` / `#10231F` | `#C2550C` / `#FFFFFF` (the guide's `#C4560C` is 4.48:1 on white) |
| `--done-core` / `--on-done-core` | a day with a workout: the circle inside the ring, and its icon | `#F5F7F6` / `#10231F` | `#10231F` / `#F5F7F6` |
| `--ring-track` | calorie ring track; hollow ring of a day not counted yet | `#3A3A3C` | `#CFDAD6` |
| `--accent` | selected day, active tab, links, focus ring | `#4CCB9F` | `#1F6F66` |
| `--button` / `--on-button` | primary button | `#4CCB9F` / `#10231F` | `#1F6F66` / `#F5F7F6` |
| `--neutral` | `not_set` marker and bar | `#6E6E73` | `#7A8B87` |

`--over-budget` is one token shared by ring, bars, and marker. **No red anywhere**, and over budget never gets warning styling (it does not break the streak). The streak orange stays off rings so it never reads as "over".

**Theme toggle:** a 40px sun/moon button at the right of every page's title (`aria-label` "Switch to light mode" / "Switch to dark mode"). The choice is saved in `localStorage` (`fitness-tracker.theme`) and applied before first paint by `public/theme-init.js` (a file, because the CSP allows same-origin scripts only). Colours ease for 150ms during a switch, not under `prefers-reduced-motion`. `theme-color` follows the page background.

**Type:** the system font stack in both themes (SF Pro on iPhone). Outfit and DM Sans were tried and dropped (D116).

**Mark:** a Mint ring around a Paper core on a Surface square (`web/public/favicon.svg`; the launch screen shows it above the "tali" wordmark; `apple-touch-icon.png` is the same, full-bleed).

## 8. Accessibility (required)

- Semantic HTML: `<main>`, `<nav aria-label="Primary">`, one `h1` per page, logical heading order, visible `:focus-visible`, touch targets >= 44px.
- **Contrast:** markers, bars, ring >= 3:1 non-text contrast; text >= 4.5:1. Check with a contrast tool. Verify markers and bars in grayscale and under a color-vision-deficiency simulation; they must stay distinguishable by **shape and bar position**.
- Each streak circle plus marker is **one** element: `"<Weekday>, <Month> <day>: <state>. <activity or none>. Calories: <not logged | within budget | over budget | logged, no budget set>."` Example: `"Tuesday, October 13: qualifying day. Workout. Calories within budget."`
- Streak summary: `"Streak: 12 days. Today: workout logged."` plus at-risk status.
- Ring: `"Calories: 654 eaten of 1,853, 1,199 left."` or `"... 320 over budget."` Protein: `"Protein: 21 of 130 grams, 16 percent."` Chart: summary (`"Weekly calories: 4 days within budget, 1 over, budget 1,853."`) plus per-bar labels.
- Every status is text plus icon or shape (the over-budget ring has its gap and triangle).
- Respect `prefers-reduced-motion` and `prefers-contrast`. Use rem units and verify at 200% zoom. Checked in Slice 6b at a 197px-wide viewport (a 393px phone at 200%): no horizontal scroll; the streak week wraps to two rows (4 + 3, circles stay 32px), the calorie ring shrinks to the card and its figures stack, weekly bars narrow so they never touch. Slice 7a, same check on Activities, Nutrition, Dashboard and Me: 0px horizontal scroll; card headers wrap so the Week / Month switch drops under the title; the calendar keeps 7 columns and its circles shrink; trend charts keep only the first and last axis labels (every bar keeps its spoken label).

## 9. Copy (no red, no shame, no exclamation marks, no modals)

| Situation | Copy |
|---|---|
| Yesterday not logged (at risk) | "Yesterday isn't logged. Fill it in to keep your 12-day streak." (no action on the card: the day chooser picks yesterday) |
| Streak broke at midnight | "Fresh start today. Your best was 12 days." |
| Today counted | "Nice. Today's counted." |
| Yesterday a second rest day (at risk) | "Yesterday was a second rest day in a row. Log its workout to keep your 12-day streak." |
| Yesterday a second over-budget day (at risk) | "Yesterday was a second day over budget. Check its food log to keep your 12-day streak." |
| Today would be a second rest day | "Yesterday was a rest day. A workout today keeps your streak going." |
| Today would be a second over-budget day | "Yesterday was over budget too. Staying within it today keeps your streak going." |
| Over budget | No message on its own; the ring and bars convey it (only a second day in a row matters) |
| Recovery states | see 5.4 |
| Empty exercises | "No exercises logged for this day." |
| Stale data (Me panel) | "Last sync 9 hours ago" with status text |

The at-risk, fresh-start, and counted messages appear as one quiet line at the bottom of the streak card.

## 10. Loading, empty, and error states

Skeleton cards while loading (no layout jump). Per-card error with a "Retry" button rather than a full-page error. Offline or API down: banner "Can't reach the server" with retry; never show stale numbers without saying so. 401 goes to the sign-in screen.

## 11. Visual verification loop (the agent must do this)

- The demo API (`APP_ENV=demo`) runs with `NOW_OVERRIDE` so greeting and "today" are deterministic. `scripts/seed_demo.py load <name>` builds a scenario by replaying synthetic Strava and Shortcut payloads through the real pipeline (D119); the hosted demo builds `midweek` as of the real time instead.
- `make screenshots` renders each scenario at **393x852** (iPhone) and **1280x800** (desktop), dark scheme, to `docs/screenshots/`; midweek also gets its four pages in the light theme at iPhone size (`midweek-*light-iphone.png`), switched with the toggle and checked across a reload. Compare with sections 3, 5, and 12; fix; repeat.
- **Staging:** M1 (Slice 6a) renders only `midweek`, `at_risk`, and `edge_empty` at 393x852. The full set below, at both sizes, is due by M2 (Slice 6b).

Scenarios:
1. **midweek** (also the public demo): now Sat 2026-10-17 14:00. A 12-day streak: this week Mon run, Tue run, Wed recovery, Thu strength, Fri run, Sat counted with 708 of 1,853 kcal (meals pushed before 13:05) and 3 activities (walk, Full Body, run); Sun future. Last week holds the one over-budget day (2,173). Greeting "Good afternoon, Sam" (a made-up athlete). Data and sync: both sources OK, 1 Strava failure in the last 7 days, 3 quarantined records, data quality 12 passed / 3 warnings / 0 failed.
2. **fresh_monday**: now Mon 2026-10-19 15:55. Nothing logged today; prior week healthy; recovery card `available`.
3. **over_budget**: 2,173 of 1,853.
4. **at_risk**: yesterday not logged; streak shows the unchanged count and the quiet message; recovery card `blocked`.
5. **rest_yesterday**: yesterday was a rest day; today pending; recovery card `blocked` (Slice 7d; was freeze_used).
6. **recovery_logged** (today is a valid recovery day) and **counted** (today already qualifies).
7. **past_day**: `selectedDate` older than yesterday; recovery card `locked`.
8. **edge_empty**: no targets set; no data this week; empty exercises.
9. Pages: activities (midweek, with the Hevy session expanded and one `partial` session), nutrition, me (healthy pipeline and a stale/failed one).
10. **large_font** (200% zoom) and **reduced_motion**.

## 12. Acceptance checklist

- [ ] Order is exactly: greeting, day chooser, streak card, recovery card, logged exercises, calorie budget, protein, weekly chart, last week (Slice 7b). The greeting has no card.
- [ ] Bottom nav has 4 tabs with the specified icons and labels; active state is clear; safe-area padding works on iPhone.
- [ ] Streak card matches the Strava structure: flame + number + "Days"; date numbers inside circles; white circle + black icon for activity days; white outline for today; dark filled circles for missed; dim outline for future; one marker per day (hollow circle / filled green dot / filled orange square / filled gray dot for `not_set`).
- [ ] Recovery card always visible with constant height and the correct state (no freeze pill since Slice 7d).
- [ ] Exercises card shows exactly 1 row at launch (most recent first) with a chevron when there are more; rows show icon, title, duration; rows are not clickable; the card opens Activities for the selected date.
- [ ] Calorie, protein, and weekly cards open Nutrition; the bar tap sets `selectedDate`.
- [ ] Ring is a plain flat circle (no apple, no glow, no animation), centred in its card, green fill, orange when over with "kcal over".
- [ ] Protein is its own card: label, "Xg, Yg left", percentage at right, thin green bar, percentage outside the bar.
- [ ] Weekly chart has a visible dashed budget line; over-budget bars are orange and rise above it; selected day in accent color, underline under the date only.
- [ ] Day chooser drives every card except the streak and the trend cards; Activities lists only the selected day, with Show all days.
- [ ] Me page saves targets (effective today) and shows the pipeline health panel with text-plus-icon statuses.
- [ ] No red anywhere; nothing from the "do not copy" list.
- [ ] Contrast, grayscale, and 200% zoom checks pass.
