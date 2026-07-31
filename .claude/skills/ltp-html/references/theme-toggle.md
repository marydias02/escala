# Theme toggle (light/dark)

> Only read this file if a light/dark toggle has been explicitly requested. Do not build this in, and do not ask whether to build it in, unless the user explicitly requests a light/dark switch — see DESIGN.md §7 for the off-by-default rule and when a one-line mention (not a build) is appropriate. Every item below (variable-remap audit, per-chart re-theming, persistence scoping) is real recurring engineering/QA cost, which is exactly why this lives outside DESIGN.md's default read path.

**Mechanism — CSS variable remap, not a second stylesheet.** Define a second block right after `:root{}` that overrides the same variable names under `:root[data-theme="dark"]`:

```css
:root[data-theme="dark"]{
  color-scheme:dark;
  --ltp-navy:#f1eefc; --ltp-teal:#1fb8ae; --ltp-mint:#2fd6bd; --ltp-orange:#ff6b00;
  --ltp-white:#12132a; --ltp-off-white:#191b34; --ltp-gray-100:rgb(255 255 255 / 14%); --ltp-gray-500:#a6acc2;
  --ltp-black:#f5f6fb; --ltp-charcoal:#05060d;
  --color-bg:#0a0b18; --color-surface:var(--ltp-white); --color-surface-muted:var(--ltp-off-white);
  --color-surface-dark:var(--ltp-charcoal); --color-text:var(--ltp-black); --color-text-muted:var(--ltp-gray-500);
  --color-heading:var(--ltp-navy); --color-accent:var(--ltp-orange); --color-interactive:var(--ltp-mint);
  --color-interactive-soft:var(--ltp-teal); --color-border:var(--ltp-gray-100);
  --shadow-soft:0 8px 24px rgb(0 0 0 / 45%); --shadow-float:0 16px 40px rgb(0 0 0 / 60%);
}
```

This only works if the page's CSS actually references `var(--color-*)`/`var(--ltp-*)` rather than hardcoded hex. **Before wiring up a toggle, audit for hardcoded hex/`rgba()` colors that bypass the token system** (a zebra-striped table row, a hardcoded `background:#fff` on a `<select>`, an active-state color) — these silently stay light-mode-colored after the toggle fires. Fix each to a variable; there is no generic sweep that catches this class of bug. Expect at least one explicit `:root[data-theme="dark"] .selector{...}` override for exactly this reason, on top of the base remap.

**Prefer semantic tokens (`--color-heading`, `--color-text`, `--color-border`) over raw brand tokens (`--ltp-navy`, `--ltp-black`) in component CSS**, so the remap stays legible. If a component only has `var(--ltp-navy)` to reach the right color, a full remap means redefining `--ltp-navy` itself to near-white in dark mode — works, but is semantically confusing (the token named "navy" no longer holds navy). If a literal navy is ever needed regardless of theme, use the hex directly or a separate non-flipping token, never `var(--ltp-navy)`.

**Toggle control**: mirrors the report-index toggle (DESIGN.md §7) — same fixed-position pattern, opposite corner (`top:24px; right:24px`), so the two bookend the header.

```html
<button class="theme-toggle" id="theme-toggle" aria-label="Switch to dark mode" aria-pressed="false" type="button">
  <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">...</svg>
  <span class="theme-toggle-thumb"></span>
  <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">...</svg>
</button>
```

```css
.theme-toggle{position:fixed;top:24px;right:24px;z-index:1001;width:56px;height:30px;border-radius:9999px;background:var(--ltp-off-white);border:1px solid var(--color-border);cursor:pointer;display:flex;align-items:center;justify-content:space-between;box-sizing:border-box;padding:0 6px;}
.theme-toggle-thumb{position:absolute;top:3px;left:3px;width:22px;height:22px;flex:none;border-radius:50%;background:var(--ltp-white);box-shadow:var(--shadow-soft);transform:translateX(0);transition:transform 340ms cubic-bezier(0.65,0,0.35,1),background-color 260ms ease;z-index:1;}
.theme-toggle[aria-pressed="true"] .theme-toggle-thumb{transform:translateX(28px);}
.theme-toggle svg{position:relative;z-index:2;width:14px;height:14px;stroke-width:2.4;color:var(--ltp-navy);opacity:.4;transition:opacity 340ms cubic-bezier(0.65,0,0.35,1),color 260ms ease;}
.theme-toggle .icon-sun{opacity:1;}
.theme-toggle[aria-pressed="true"] .icon-sun{opacity:.4;}
.theme-toggle[aria-pressed="true"] .icon-moon{opacity:1;}
```

- **The two icons must be direct children of `.theme-toggle`, siblings of `.theme-toggle-thumb` — not nested inside the thumb.** Nesting them inside the 22px-wide thumb forces them to wrap, reading as vertically stacked instead of flanking it. Correct order is sun → thumb → moon; `justify-content: space-between` puts the icons at the flex edges while the `position: absolute` thumb slides independently underneath/between them.
- **Both icons stay visible at all times**, same `color` (a token that itself flips with the theme, e.g. `var(--ltp-navy)`), differentiated only by `opacity` (active `1`, inactive `.4`) — do not hide the inactive icon with `display:none`; it reads as broken/empty rather than "off."
- Use `~300–350ms` with a slight ease-out curve (not linear, not the default `220ms ease`) for the thumb slide, and sync the icon opacity/color transition to the same duration so the whole toggle reads as one motion.
- Apply a short `background-color/color/border-color` transition (`~200ms ease`) to major surfaces (cards, table wrapper, footer card, index panel, tags, pills) so the theme switch doesn't look like a hard cut. Already covered by the page's `prefers-reduced-motion` guard if one exists per DESIGN.md §8 — don't add a second one.

**No-flash boot**: set the theme attribute *before* first paint, in an inline `<script>` placed in `<head>` immediately after the `color-scheme` meta tag — not in a deferred/end-of-body script, or the page will flash light before flipping dark on load.

```html
<script>
(function(){
  try{
    if(localStorage.getItem(THEME_KEY) === "dark"){
      document.documentElement.setAttribute("data-theme","dark");
    }
  }catch(e){}
})();
</script>
```

**Persistence must use a report-scoped storage key, never a bare shared one like `"ltp-theme"`** — see DESIGN.md §3's persistence rule (unscoped keys leak a dark preference across unrelated `file://` reports). Derive `THEME_KEY` from something unique to the report:

```js
var THEME_KEY = "ltp-theme::" + document.title;
```

The click handler mirrors the same key when saving:

```js
function setTheme(dark) {
  if (dark) { root.setAttribute("data-theme", "dark"); } else { root.removeAttribute("data-theme"); }
  try { localStorage.setItem(THEME_KEY, dark ? "dark" : "light"); } catch (e) {}
  applyState(dark);
}
btn.addEventListener("click", function () { setTheme(!isDark()); });
```

**Re-theming charts (Plotly or similar SVG-rendered charting libraries) needs its own pass — CSS variables can't reach into rendered SVG.** Two different techniques for two different cases:

- **Static charts** (rendered once, inline, at parse time): sweep every rendered chart instance after any theme change and patch just the chrome — title/legend/axis tick/gridline/zeroline/axis-line/hoverlabel colors — using the library's relayout/update API. Iterate axis keys with a pattern like `/^(xaxis|yaxis)\d*$/`, not a fixed `xaxis`/`yaxis`, so charts with subplots (`xaxis2`, `yaxis2`, …) are also caught.
- **Do not blanket-restyle per-trace data-label/text color** (e.g. Plotly's `textfont.color`) as part of this sweep. Charts with in-segment value labels drawn on top of colored fills (a 100%-stacked bar, for example) deliberately keep those labels white for contrast regardless of theme — a global restyle overwrites them to the page's text color and makes them illegible against their own fill. Chart *chrome* sits on the transparent page background and safely takes the theme color; per-trace *data* labels do not.
- **Dynamically re-rendered charts** (rebuilt on user interaction, not just drawn once at load) must read the current theme *at render time* inside their own render function and bake correct colors in — the generic sweep runs once per toggle click and won't catch a chart rebuilt later by a filter/tab change. Brand accent colors used for data series/marks (not chrome) don't need to flip with the theme.
