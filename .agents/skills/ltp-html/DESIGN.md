# LTPlabs Brand & Style Reference

> Unified guidance for HTML, CSS, dashboards, microsites, and presentation-like web files.
> Status: working standard, grounded in LTPlabs Brand Book 2025 and the live website checked 2026-07-17.

## 1. Design intent

LTPlabs should feel analytical, human, clear, capable, and forward-looking. Design should make complex business, analytics, and AI ideas easy to understand.

Core qualities:

- bright, spacious, editorial layouts;
- confident but quiet hierarchy;
- precise geometric structure softened by generous whitespace and rounded surfaces;
- deep navy for trust and authority;
- teal for analytics, systems, and capability signals;
- orange for action, energy, and measurable outcomes;
- human photography and purposeful technology imagery;
- restrained motion: reveal, rise, wipe, and subtle hover feedback.

Use dark sections as deliberate contrast bands, not as the default canvas for every page.

## 2. Authority and conflict rules

Use sources in this order:

1. Official `ltp_brand_book_2025.pdf` and supplied official logo assets.
2. Current `https://ltplabs.com/` expression.
3. Local HTML-slide guidance and extracted website notes.
4. The supplied alpha token dump, only where it does not conflict with 1 or 2.

The supplied alpha dump describes a dark immersive teal system. It is useful for an optional dark/technology mode, but it is not the default LTPlabs system: official assets and the current website are white-first and orange-led.

When values differ, preserve official asset values. For example, use `#ff6b00` as canonical brand orange; website scraping may report `#ff6a00` because of CSS/rendering or a website variant.

## 3. Canonical color tokens

### Brand colors

| Token | Hex | Role |
|---|---|---|
| `--ltp-navy` | `#19105f` | Primary brand dark, major headings, dark bands |
| `--ltp-teal` | `#007474` | Primary functional accent, links, diagrams, active states |
| `--ltp-mint` | `#00a590` | Secondary teal, gradients, supportive highlights |
| `--ltp-orange` | `#ff6b00` | Primary CTA, KPI emphasis, active energy, key outcomes |

### UI neutrals

| Token | Hex | Role |
|---|---|---|
| `--ltp-white` | `#ffffff` | Main page and card surface |
| `--ltp-off-white` | `#f4f7f9` | Soft section surface, alternate cards |
| `--ltp-gray-100` | `#eaecf0` | Borders, separators, muted badges |
| `--ltp-gray-500` | `#666666` | Secondary text, metadata |
| `--ltp-black` | `#000000` | Strong text where maximum contrast is needed |
| `--ltp-charcoal` | `#1c1f27` | Dark panel, footer, dark card surface |
| `--ltp-indigo` | `#16105f` | Deep supporting dark, close to navy |

### Semantic tokens

```css
:root {
  --color-bg: var(--ltp-white);
  --color-surface: var(--ltp-white);
  --color-surface-muted: var(--ltp-off-white);
  --color-surface-dark: var(--ltp-charcoal);
  --color-text: var(--ltp-black);
  --color-text-muted: var(--ltp-gray-500);
  --color-heading: var(--ltp-navy);
  --color-accent: var(--ltp-orange);
  --color-interactive: var(--ltp-teal);
  --color-interactive-soft: var(--ltp-mint);
  --color-border: var(--ltp-gray-100);
}
```

Color rules:

- Start with white, off-white, navy, and black. Add teal and orange with purpose.
- Orange owns primary action and impact emphasis. Do not use orange for every link, border, or decoration.
- Teal owns system behavior: data, analytics, capability, progress, and interactive states.
- Navy owns authority: headings, navigation, dark bands, and high-trust statements.
- Keep accent surfaces flat or very lightly tinted. Avoid neon glow and purple gradients.
- Check contrast for every text/surface pair. Never put small navy text on teal or orange without checking.

### Light mode is the default — always, no exceptions

Every deliverable must render in light mode regardless of the viewer's OS/browser dark-mode setting, a browser's forced-dark-mode rendering (e.g. Chrome's "Force Dark Mode for Web Contents" flag, or Windows/Android forced dark), or any theme preference stored by a *different* report. This has shipped broken twice, for two different reasons — both must be handled:

Every self-contained HTML deliverable must include both of these, unless a dark page was explicitly requested (see optional dark mode below):

```html
<meta name="color-scheme" content="light">
```

```css
:root { color-scheme: light; }
```

Do not rely on `prefers-color-scheme` media queries to build a dark variant unless the user explicitly asks for a dark page or a dark hero band (see below). The absence of a dark media query is not enough on its own — without the `color-scheme` declarations above, some browsers still forcibly invert colors.

**If the report includes a light/dark theme toggle** (see the Theme toggle component below), do not persist the user's choice with a bare `localStorage` key such as `localStorage.setItem("ltp-theme", ...)`. These deliverables are single portable HTML files opened via `file://` (downloaded, emailed, shared) — many browsers do not isolate `file://` origins from one another for `localStorage`. That means a dark-mode preference saved from opening *one* report can silently leak into the *next*, unrelated report the same person opens later, defaulting it to dark even though its own code correctly initializes to light. This is the actual root cause behind a "coworker opened it and it was dark by default" bug — not a browser or OS setting. If persistence across reloads is genuinely needed, scope the storage key to something unique per report (e.g. include a build ID or the report title in the key) so it cannot cross-contaminate other files; otherwise leave theme state in-memory only (reset to light on every fresh load).

### Optional dark technology mode

Use only for a hero, product demo, AI/analytics visual, or explicitly requested dark page:

```css
.ltp-dark {
  --color-bg: #060816;
  --color-surface: #0b1024;
  --color-surface-muted: #0a2a33;
  --color-text: #ffffff;
  --color-text-muted: #c7ccd6;
  --color-heading: #ffffff;
  --color-accent: #ff6b00;
  --color-interactive: #00a590;
  --color-border: rgb(255 255 255 / 16%);
}
```

Dark mode should still use white, navy/near-black, teal, mint, and orange. Do not turn it into a cyberpunk theme.

## 4. Typography

### Primary family

Use **Bw Modelica** for all core interface and presentation text. Bundle the font when distributing HTML:

```css
@font-face {
  font-family: "Bw Modelica";
  src: url("./assets/fonts/BwModelica-Regular.otf") format("opentype");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: "Bw Modelica";
  src: url("./assets/fonts/BwModelica-Medium.otf") format("opentype");
  font-weight: 500 600;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: "Bw Modelica";
  src: url("./assets/fonts/BwModelica-Bold.otf") format("opentype");
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}

:root {
  --font-sans: "Bw Modelica", "Arial", sans-serif;
}
```

Use a local relative path. Do not rely on `local()` alone. If no bundled font is possible, use a neutral geometric sans fallback and flag the deviation.

### Type scale

| Token | Desktop size | Weight | Line height | Tracking | Use |
|---|---:|---:|---:|---:|---|
| `display` | 48px | 400 | 1.30 | -0.02em | Hero statement |
| `h1` | 36px | 400 | 1.30 | -0.02em | Page title |
| `h2` | 28px | 400 | 1.21 | -0.01em | Section title |
| `h3` | 22px | 500 | 1.40 | 0 | Card or subsection title |
| `h4` | 18px | 500 | 1.40 | 0 | Small heading |
| `body-lg` | 18px | 400 | 1.56 | 0 | Lead paragraph |
| `body` | 16px | 400 | 1.60 | 0 | Default copy |
| `body-sm` | 14px | 400 | 1.50 | 0 | Supporting copy |
| `label` | 14px | 500 | 1.20 | 0 | Button/navigation |
| `meta` | 12px | 500 | 1.20 | 0.04em | Eyebrow, tag, metadata |

For responsive HTML, use `clamp()` around these values. Keep display headings short, usually no more than two lines. Headings are light and architectural; do not default to heavy 700/800 display type.

## 5. Layout and spacing

Use an airy grid. Default content max width: `1200px` to `1280px`. Align headings, copy, cards, and controls to shared vertical rails.

**Every section on a page shares one content-container width — hard rule, no exceptions.** Pick a single `--content-max` for the whole document (1280px default; 1440px acceptable if the page is chart/data-heavy throughout) and use it for every section: hero, cards, charts, and footer alike. Do not switch container widths section-to-section — that produces sections whose left/right edges don't line up as the reader scrolls. (`report.html`/`report_copy.html` mix `.container`/`.container.wide` across sections — treat that as a bug in those files, not a pattern to copy.) If one section is legitimately full-bleed (e.g. a hero background image), the *content inside* it still aligns to the page's single container width; only the background may extend edge-to-edge.

```css
:root {
  --space-1: 6px;
  --space-2: 8px;
  --space-3: 16px;
  --space-4: 24px;
  --space-5: 32px;
  --space-6: 48px;
  --space-7: 72px;
  --space-8: 96px;
  --space-9: 128px;
  --space-10: 192px;
  --content-max: 1280px;
  --gutter: clamp(20px, 4vw, 64px);
}
```

Use `6px`, `16px`, `32px`, `96px`, and `192px` as the principal rhythm. `8px`, `24px`, `48px`, and `72px` fill practical gaps.

- Section padding: usually `72px–96px`; use `128px–192px` for a statement hero.
- Card padding: usually `24px–32px`; never use `192px` as card padding.
- Keep one dominant focal point per viewport.
- Use two-column layouts for narrative plus visual; collapse to one column below tablet width.
- For HTML slides, every slide is `100dvh`, `overflow: hidden`, with content sized using `clamp()`.

## 6. Shape, borders, and depth

```css
:root {
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-card: 24px;
  --radius-pill: 9999px;
  --shadow-soft: 0 8px 24px rgb(25 16 95 / 8%);
  --shadow-float: 0 16px 40px rgb(25 16 95 / 12%);
}
```

Use `12px–24px` for cards and `8px–12px` for buttons. Pills belong to tags, compact filters, and small utility controls only. Prefer borders and tonal separation over heavy shadows. Never use glossy bevels, thick outlines, or gratuitous glow.

**Never use a colored left-border accent stripe** (e.g. `border-left: 3px solid var(--ltp-orange)`) on cards, callout boxes, or banners to signal status/emphasis — flagged explicitly as a recurring mistake to stop making. It reads as a generic dashboard-template tic, not an LTP pattern. For a "fixed" / "watch" / "note" style callout, use a flat tinted background (`--ltp-off-white` or a very light tint of the accent) with the accent color reserved for the label text or a small leading icon — never a border stripe on any edge.

## 7. Components

### Navigation

Use a clean white or transparent header, navy text, generous horizontal spacing, and one clear orange `Get in touch` action. Navigation labels are compact and medium weight. Language selection is a small utility control, not a focal point.

### Buttons

```css
.ltp-button {
  min-height: 44px;
  padding: 10px 16px;
  border: 0;
  border-radius: 12px;
  font: 500 14px/1.2 var(--font-sans);
  transition: background-color 160ms ease, color 160ms ease, transform 160ms ease;
}
.ltp-button--primary { background: var(--ltp-orange); color: #fff; }
.ltp-button--secondary { background: var(--ltp-navy); color: #fff; }
.ltp-button--outline { background: #fff; color: var(--ltp-navy); border: 1px solid var(--ltp-gray-100); }
.ltp-button:hover { transform: translateY(-1px); }
.ltp-button--primary:hover { background: #e85f00; }
```

Use orange primary actions. Use navy for secondary filled actions. Use teal for links, progress, and data interaction unless the action is a brand CTA.

### Cards and panels

White cards on white pages need either a `#eaecf0` border or a very soft navy-tinted shadow. Use `#f4f7f9` for grouped or alternate surfaces. Cards should be modular, calm, and content-led. Avoid equal visual weight across every card.

When a status icon (✓/!) sits beside a card heading, wrap the icon and the (title + body) text as a flex row with the icon **outside** the text column — never place the icon inline before just the `<h3>`. Putting it inside the heading alone indents the title but leaves the paragraph below flush left, breaking the visual alignment between them.

**If a card is built on `<figure>` instead of `<div>`** (e.g. a chart card using `<figure class="chart-card">…<figcaption>`), the card's own class must explicitly reset `margin: 0`. `<figure>`'s browser default is `margin: 1em 40px` — if the card class only sets `margin-bottom` (a common pattern), the left/right `40px` default survives, and that card sits visibly indented from every sibling `<div class="card">` even though nothing in the visible CSS looks wrong. Set `margin: 0` explicitly regardless of the underlying element; don't rely on the global reset in §11 alone.

### Tags and eyebrows

Use uppercase or compact sentence-case metadata at `12px`, medium weight, and slight tracking. Teal, orange, or muted gray badge fills are acceptable. Keep tags short. Do not turn every label into a pill.

### Data visualizations

Use navy/charcoal as structure, teal/mint as primary series, orange as selected series or outcome, and gray for context. Keep gridlines subtle. Use thin connectors, clean nodes, and clear annotations. Charts must remain readable without relying on color alone.

- **Legend placement**: for any chart with more than ~2 series, place the legend below the chart, never overlapping the title area above the plot.
- **Categorical palette fallback**: the brand accents (navy/teal/orange/mint) work well for 1–3 series or a highlight-vs-rest pattern (e.g. top slice pulled/colored, rest neutral), but fail colorblind-safety validation once a chart needs 5+ distinct categorical series (e.g. a multi-segment stacked bar). For those cases, fall back to a validated categorical palette rather than stretching brand colors past what they were designed for.
- **Interactive chart controls**: disable the charting library's default hover toolbar/modebar (e.g. Plotly's `displayModeBar: false`) by default for polished report-style dashboards, unless zoom/pan/export controls are explicitly wanted.

### Report index navigation (long reports, on by default)

Any multi-section report or dashboard long enough to need jumping between sections should ship with a report index: a small hamburger toggle fixed at the top-left corner that opens a slide-out panel listing every section as a jump link. This is an on-by-default feature for that class of deliverable — build it in, don't treat it as optional polish, and don't ship a long report without any way to jump between sections.

Verified pattern (from `report.html` / `report_copy.html`):

- **Toggle**: `position: fixed; top: 24px; left: 24px;` — three-line hamburger icon, transparent background, navy lines that shift to teal on hover.
- **Panel**: fixed, full height, `width: min(320px, 84vw)`, white surface, slides in from the left (`transform: translateX(-100%)` closed → `translateX(0)` open), `--shadow-float` for depth.
- **Overlay**: a fixed, full-viewport dim scrim behind the panel that closes it on click.
- **List content**: one link per section, a two-digit teal index number (`01`, `02`, …) plus the section's plain-language title — not its internal ID or slug. Each link points to that section's `id` (e.g. `#sec-01`).
- **Behavior**: closes on overlay click, on the panel's own close button, on Escape, and after clicking any link inside it. Starts closed on load.
- Give every top-level section a stable `id` (`sec-01`, `sec-02`, …) specifically so the index panel (and any other deep link) can target it.

If a theme toggle (light/dark) is also present, it lives at the mirrored position, `top: 24px; right: 24px;` — see the persistence warning in §3.

### Tabs and segmented controls

For switching between two or more views of the same section (e.g. "increase" vs. "decrease" cases, a metric selector) without navigating away, use a small pill-shaped segmented control, not a full tab bar with underlines.

- Container: inline-flex row of buttons, `border-radius: var(--radius-pill)`, small gap between buttons.
- Inactive button: white or off-white background, `1px solid var(--color-border)`, muted text.
- Active button: solid fill in a brand color (teal or orange — pick one meaning per control and keep it consistent, e.g. orange for "up/increase", teal for "down/decrease"), white text.
- Keep labels short and put counts inline where useful (e.g. "▲ Increase (6)") rather than in a separate badge.
- Panels toggled by the control should swap with `display: none` / `display: block` (or an `.active` class) — no page navigation, no layout jump.

### Theme toggle (light/dark)

**Off by default — do not build this in, and do not ask whether to build it in, unless the user explicitly requests a light/dark switch.** It carries real recurring engineering/QA cost (variable-remap audit, per-chart re-theming, persistence scoping) — worth it for a deliverable that gets reopened repeatedly, not for every report by default. If a deliverable clearly reads as long-lived (a persistent dashboard), a one-line mention that a toggle is available is fine, but proceed with the light-only build rather than blocking on an answer.

**If one is explicitly requested, read [`references/theme-toggle.md`](references/theme-toggle.md) before implementing** — the full verified pattern (CSS variable remap, toggle markup/CSS, no-flash boot script, scoped persistence, and Plotly/chart re-theming, including a couple of non-obvious bugs already hit and fixed) lives there rather than in this always-loaded file.

### Images and illustration

Prefer authentic people, teams, work, and business context. Technology imagery can be abstract or 3D, but must support the story. Avoid generic stock laptop shots, oversized decorative icons, and repeated hero imagery. Use the supplied LTP shape assets where relevant.

### Footer and dark bands

Dark charcoal/navy bands are useful for contact, proof, or closing sections. Use white logo variant, white text, teal structural accents, and orange action. Preserve large whitespace.

Footer construction rules (learned from building a full-page report):

- Background: `--ltp-charcoal` (`#1c1f27`) — not `--ltp-navy`. Charcoal is the footer/dark-panel token; navy is for headings and authority elements.
- **Width — hard rule, no exceptions:** the charcoal card's own background box must be exactly the **same content-container width used by every other section on the page** (see §5 — one container width per page, no `.wide` variant switched in just for the footer), sitting centered inside the plain `<footer>` element. The **card itself**, not just its contents, must stop at the container edges, same as any other card on the page.

  Right (structure only — use whatever single container class/width the rest of the page uses, not a special wider one):
  ```html
  <footer>
    <div class="container">
      <div class="footer-card">...</div>
    </div>
  </footer>
  ```
  ```css
  footer { margin-top: var(--space-7); } /* no background here */
  .footer-card { background: var(--ltp-charcoal); border-radius: var(--radius-card) var(--radius-card) 0 0; ... }
  ```
  Wrong:
  ```css
  footer { background: var(--ltp-charcoal); padding: 0; }         /* full-bleed — wrong */
  .footer-inner { width: min(...); margin-inline: auto; }          /* only the CONTENT is constrained, not the card */
  ```
- Corners: round the **top** corners only (`--radius-card` top-left/top-right); square the bottom so the band sits flush against the true bottom of the page with no gap beneath it — combined with the width rule, this gives the card its intended "floating island" look.
- Content layout: logo and info columns are **direct flex siblings** with `justify-content: space-between` across all of them — not a logo nested against a separately-gapped group of columns.
- Logo: **inline the SVG markup directly** (not `<img src>`), official white variant. Use this exact verified markup, sized via the wrapping element (e.g. `.footer-logo svg{height:28px;width:auto;}`):

```html
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 685.48 251.1" aria-label="LTP logo">
  <g fill="#fff">
    <polygon points="96.88 0 0 0 0 251.1 195.4 251.1 195.4 154.22 96.88 154.22 96.88 0"/>
    <path d="M685.48,96.88h0C685.48,43.38,642.11,0,588.61,0h-133.34v96.88h96.88,0s0,0,0,0c-53.5,0-96.88,43.37-96.88,96.88v57.34h96.88v-57.34h36.46c53.5,0,96.88-43.37,96.88-96.88h0Z"/>
    <polygon points="244.23 0 244.23 0 244.23 0 165.58 0 165.58 96.88 249.56 96.88 249.56 251.1 346.44 251.1 346.44 96.88 426.14 96.88 426.14 0 244.23 0 244.23 0"/>
  </g>
</svg>
```

This is the LTP symbol (white fill), extracted from the verified `report.html` reference build.

### Self-contained HTML deliverables

When a report or dashboard is meant to be a single portable file, inline every dependency directly into that one HTML file: charting library JS, embedded data (as a `window.DATA = {...}` script block), custom JS, and the logo SVG. No sibling files, no CDN `<script src>`. Verify with a quick check that no `<script src="...">` or `<link href="...">` remains pointing outside a `data:` URI.

### Fixed-count tile and card grids

When a section has a known, fixed number of stat tiles or cards meant to read as clean rows (e.g. 8 KPI tiles as 2 rows of 4), use an explicit `grid-template-columns: repeat(N, 1fr)` with a responsive step-down at narrower breakpoints — not `repeat(auto-fit, minmax(...))`. Auto-fit sizes columns off available width alone and can split an even count unevenly (e.g. 6 tiles on row one, 2 orphaned on row two), which reads as awkward rather than intentional.

## 8. Motion

Motion should communicate sequence and confidence:

- page entry: fade + 12–24px rise, staggered by 60–100ms;
- cards: subtle lift or border/accent change on hover;
- data: draw/reveal lines and nodes once, then remain stable;
- navigation: short color/opacity transitions;
- avoid bounce, neon pulse, parallax overload, and continuous decorative movement.

Always support `prefers-reduced-motion: reduce`.

## 9. Logo and asset rules

Use supplied official logo files. Prefer SVG for HTML. Available official variants include:

- full colour: `1_logo_cores.svg`;
- black: `2_logo_preto.svg`;
- white: `3_logo_branco.svg`;
- symbol-only variants when the full wordmark does not fit.

Do not redraw, recolor, stretch, rotate, crop, or add effects to the logo. Keep visible breathing room. Use full-colour logo on light backgrounds and white logo on dark backgrounds. Keep logo treatment consistent across a page or deck.

### Header and footer logo placement

Every LTP HTML deliverable that has a persistent header/nav bar (microsites, decks, dashboards — not necessarily a single scrolling report like `report.html`, which uses only a footer logo) carries the real logo in both the header and the footer. **Never fabricate a placeholder** — a redrawn SVG, a monogram, the wordmark set as styled text, or an approximation from memory. This has shipped wrong before (see §13); the verified markups below exist specifically so there's never a reason to reconstruct the logo from scratch. Copy them as-is; if a variant is needed that isn't covered here, pull it fresh from the official asset path in §12.

- **Header**: full-colour variant on the white/light header bar. Height ~`34px`, `width:auto`. Use this exact verified markup (`1_logo_cores.svg`, read directly from the official asset folder — same icon geometry as the footer symbol, in full brand color):

```html
<svg class="logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 685.48 251.1" aria-label="LTP logo">
  <path fill="#ff6b00" d="M685.48,96.88h-230.22V0s133.34,0,133.34,0c53.5,0,96.88,43.37,96.88,96.88h0Z"/>
  <polygon fill="#19105f" points="96.88 154.22 96.88 0 0 0 0 251.1 195.4 251.1 195.4 154.22 96.88 154.22"/>
  <path fill="#00a590" d="M552.15,96.88v96.88h36.46c53.5,0,96.88-43.37,96.88-96.88h-133.34Z"/>
  <path fill="#19105f" d="M244.23,0h-78.65v96.88h83.99v154.22h96.88V96.88h-5.33C287.6,96.88,244.23,53.51,244.23,0Z"/>
  <path fill="#ff6b00" d="M286.74-42.51h96.88V42.51c0,53.47-43.41,96.88-96.88,96.88h0V-42.51h0Z" transform="translate(383.62 -286.74) rotate(90)"/>
  <path fill="#007474" d="M552.15,96.88v154.22s-96.88,0-96.88,0v-57.34c0-53.5,43.37-96.88,96.88-96.88h0Z"/>
</svg>
```

- **Footer**: white variant on the charcoal dark band — the same icon geometry, single `#fff` fill, already given verbatim in §7 Footer construction. Height ~`30px`, `width:auto` (§7's copy-paste markup is already sized via `.footer-logo svg`; keep that as the canonical footer instance).
- **Header logo must swap with the theme, if the page has an optional dark mode or a theme toggle (see §3):** full-colour (`1_logo_cores.svg`, above) when the page is light, white (the same `#fff`-filled markup from §7) when the page/theme is dark. The header sits on whatever the page background is — unlike the footer, which is always on a fixed charcoal band regardless of overall theme — so its logo must react to theme state or it goes low-contrast (the colored mark's navy fill on a near-black `.ltp-dark` background is close to invisible). Swap by toggling which inline `<svg>` is rendered (e.g. two `<svg>` blocks, one shown per `data-theme` state via CSS `display`), not by recoloring the colored mark's fills with CSS — the colored mark's four brand-color fills are not meant to be swapped to white as a group; use the actual white markup.
- **Do not use a "descrição"/tagline lockup** (e.g. `3_logo_branco_descricao_1.svg`) for this header swap. Those assets bundle the icon with the full "LTPlabs" wordmark *and* a line of tagline copy underneath, sized for a large-format placement (a cover slide, a big dark hero) — at a normal header height (~34px) the tagline text renders illegibly. The icon-only markups above (light and dark) are the correct choice for a compact header bar.
- Do not place a logo asset with a baked-in background block (e.g. a cropped screenshot with its own dark rectangle) on a contrasting surface. Use a transparent-background asset matched to the surface underneath.
- The logo container is layout-only — no text node beside the image, no `color`/`font-weight` styling:

```css
.logo { display: flex; align-items: center; }
.logo svg { display: block; height: 34px; width: auto; }
footer .logo svg { height: 30px; }
```

- **Inline the SVG markup directly in the HTML, always** — never `<img src>` pointing at a sibling file or CDN.

## 10. Do and do not

### Do

- Lead with white/off-white surfaces and clear content hierarchy.
- Use Bw Modelica and bundle it for portable HTML.
- Use navy for authority, teal for systems, orange for action/outcomes.
- Keep headings light, short, and spacious.
- Use rounded white cards, restrained borders, and soft depth.
- Make data and AI feel understandable, useful, and human.

### Do not

- Make dark immersive backgrounds the default, or let the viewer's OS/browser dark mode invert the page — always declare light `color-scheme` (see §3).
- Use a colored left-border accent stripe on cards or callout banners.
- Fabricate a placeholder logo instead of using the verified official SVG markup (see §7, Footer and dark bands).
- Use the alpha dump's `#007474` + near-black + glow treatment as universal brand styling.
- Use purple gradients, generic indigo SaaS styling, neon cyberpunk visuals, or AI-generated decorative noise.
- Use Inter, Roboto, Arial, or system fonts as primary design choices when Bw Modelica is available.
- Overuse orange, pills, heavy shadows, or oversized icons.
- Put dense dashboards, long paragraphs, and multiple competing CTAs into one viewport.

## 11. Starter CSS

```html
<meta name="color-scheme" content="light">
```

```css
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4, p, figure, blockquote, ul, ol, dl { margin: 0; }
h1, h2, h3, h4 { color: var(--color-heading); font-weight: 400; }
h1 { font-size: clamp(2.25rem, 4vw, 3rem); line-height: 1.3; letter-spacing: -0.02em; }
h2 { font-size: clamp(1.75rem, 3vw, 2.25rem); line-height: 1.3; letter-spacing: -0.02em; }
.ltp-container { width: min(calc(100% - 2 * var(--gutter)), var(--content-max)); margin-inline: auto; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
```

## 12. Source record

- Official: `C:/Users/joao.deus/LTPlabs/LTP - General/01 - IMAGE&TEMPLATES/01 - GRAPHIC PROFILE/Graphic Profile/ltp_brand_book_2025.pdf`
- Official assets: same folder, `Logo/SVG/` and `Shapes/`.
- Current website: `https://ltplabs.com/` — checked 2026-07-17.
- Website extracts: `Downloads/DESIGN-ltplabs-com*.md` — useful observation, not authority.
- Unofficial local slide guidance: `GIT DOPP/skills-hub/ltpOS/skills/html-slides/` — implementation guidance, not brand authority.
- **Reference build**: `wrc-src/analytics_core/data/data/eda/report.html` (ROSE EDA report) is a useful example of this system applied end-to-end — self-contained, light mode, correct footer construction, no left-border cards. It is **not** flawless: it mixes `.container` (1280px) and `.container.wide` (1440px) across its own sections, which is the exact bug in §5's single-container-width rule. When checking how a rule looks in practice, cross-check against the written rules in this file rather than assuming the reference build got everything right — it's a real build with a real history of fixes, not a validated gold standard.

## 13. Known regressions to watch for

Confirmed failures from real builds, each already fixed by a rule elsewhere in this file — kept as a short index so they don't recur silently. Full rationale lives at the referenced section, not repeated here.

- Fabricated placeholder logo instead of the real SVG — §7/§9 Logo placement.
- Footer painted full-bleed instead of matching container width — §7 Footer, width rule.
- Footer columns/corners/spacing otherwise off — §7 Footer construction.
- Card title indented but body flush-left (icon wrapped around heading only) — §7 Cards and panels.
- Left-border accent stripes on cards — §6, §10.
- Dark mode by default — either missing `color-scheme` or an unscoped `localStorage` toggle key leaking across reports — §3.
- Long report with no index/jump navigation — §7 Report index navigation.
- `<figure class="chart-card">` sitting ~40px indented (unreset UA default margin) — §7 Cards and panels, §11.
- Sections at inconsistent content widths within one page (`.container` vs `.container.wide` mixed) — §5.

