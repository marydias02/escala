# assets/css/base Index

## Frozen Layer Rule

**ALL FILES IN THIS FOLDER ARE FROZEN EXCEPT THE `--custom-theme` VARIABLE IN `colors.css`.**

Only the hue value of `--custom-theme` in the `:root {}` block may be changed, and only with a design-team-provided integer. Do not modify any other variable, selector, or rule in this folder.

---

## File Map

| File | Role |
|---|---|
| `colors.css` | All color tokens: text, surface, border, status colors, and the theme palette derived from `--custom-theme` |
| `typography.css` | Font family imports, size/weight/line-height tokens, pre-built text utility classes |
| `spacing-borders-shadows.css` | Spacing scale, border width, border radius, and shadow tokens |
| `layout.css` | App shell structure: sidebar, header, main area, page layout |
| `grid-system.css` | Responsive column classes across `xs`→`xl` breakpoints |
| `reset.css` | CSS baseline normalization. Do not reference or override. |

---

## `colors.css` — Token Reference

### Base Colors

```css
--black: rgb(15, 15, 15)
--white: rgb(255, 255, 255)
--white-60 / --white-20 / --white-8 / --white-6 / --white-2   (alpha variants)
```

### Text / Icon Colors

```css
--text-icon-primary        /* near-black, main text */
--text-icon-secondary      /* 50% opacity, subdued text */
--text-icon-tertiary       /* 30% opacity, placeholder/disabled hint */
--text-icon-disabled       /* 16% opacity */
--text-icon-high-contrast  /* white, for text on dark backgrounds */
```

### Surface Colors (Backgrounds)

```css
--surface-lightest          /* barely-visible tint */
--surface-light             /* subtle background */
--surface-medium            /* card, panel backgrounds */
--surface-heavy             /* emphasized area */
--surface-heaviest          /* high-contrast area */
--surface-high-contrast     /* near-black */
--surface-page-background   /* #fcfcfc — the app page background */
--surface-modal             /* white */
```

### Border Colors

```css
--border-lightest
--border-light
--border-medium
--border-heavy
--border-heaviest
--border-modal
```

### Status Colors

```css
--positive-primary      /* dark green text */
--positive-highlight    /* vivid green accent */
--positive-background   /* light green background */
--positive-border       /* green border */

--warning-primary       /* amber text */
--warning-highlight     /* vivid amber */
--warning-background    /* light amber background */
--warning-border        /* amber border */

--negative-primary      /* red text */
--negative-highlight    /* vivid red */
--negative-background   /* light red background */
--negative-border       /* red border */
```

### Theme Mechanism

`--custom-theme` is a single integer (0–360) representing an HSL hue. The `.app[data-theme='custom-theme']` block in `colors.css` derives the full 16-step palette from it:

```css
:root {
  --custom-theme: 233;   /* ONLY THIS VALUE MAY BE CHANGED */
}

/* Auto-derived — do not manually edit */
--primary-color-1   /* lightest tint */
...
--primary-color-16  /* darkest shade */
--accent-primary    /* = --primary-color-13 */
--accent-sidebar    /* = --primary-color-14 */
```

Change `--custom-theme` and all derived colors update automatically. The `data-theme="custom-theme"` attribute on the root `html.Div` in `app.py` activates this palette.

---

## `typography.css` — Token Reference

### Font Variables

```css
--font-size-xs: 0.6875rem   /* 11px */
--font-size-sm: 0.8125rem   /* 13px */
--font-size-md: 0.9375rem   /* 15px */
--font-size-lg: 1.25rem     /* 20px */

--font-weight-base: 500
--font-weight-heavy: 550

--line-height-none: 100%
--line-height-md: 120%
--line-height-lg: 140%

--letter-spacing-none: 0%
--letter-spacing-sm: -0.5%
--letter-spacing-md: -1.5%
--letter-spacing-lg: -2%
```

Fonts loaded: **Inter** (UI font) and **JetBrains Mono** (code/mono).

### Pre-Built Typography Classes

Use these as `className` on `html.*` elements — never set font properties via `style={}`:

| Class | Semantic use | Size |
|---|---|---|
| `.heading-1` | Page title | 20px, heavy |
| `.heading-2` | Section title | 15px, heavy |
| `.heading-3` | Subsection title | 13px, heavy |
| `.body-xl` | Featured/highlighted text | 20px, heavy |
| `.body-md` | Large description | 15px, normal |
| `.body-sm` | Default body text | 13px, normal |
| `.body-xs` | Labels, captions | 11px, heavy |

---

## `spacing-borders-shadows.css` — Token Reference

### Spacing Scale

```css
--spacing-none: 0px
--spacing-1:  1px
--spacing-2:  2px
--spacing-4:  4px
--spacing-6:  6px
--spacing-8:  8px
--spacing-10: 10px
--spacing-12: 12px
--spacing-14: 14px
--spacing-16: 16px
--spacing-20: 20px
--spacing-24: 24px
--spacing-32: 32px
--spacing-40: 40px
--spacing-60: 60px
--spacing-80: 80px
```

### Border Radius

```css
--border-radius-none:  0px
--border-radius-xs:    4px    /* tight */
--border-radius-sm:    6px
--border-radius-md:    8px    /* standard card/button */
--border-radius-lg:    10px
--border-radius-xl:    16px
--border-radius-round: 100%   /* pill / circle */
```

### Border Widths

```css
--border-normal: 1px
--border-focus:  4px
```

### Shadows

```css
--shadow-sm: 0px 0px 8px 0px rgba(black, 0.04)
--shadow-md: 0px 2px 12px 0px rgba(black, 0.06)
```

---

## `grid-system.css` — Breakpoints

```css
xs: 0px      (all screens — mobile-first default)
sm: 640px    (small tablets and up)
md: 768px    (tablets and up)
lg: 1024px   (laptops and up)
xl: 1280px   (large displays)
```

Used via `Col` breakpoint props in `utils/base/grid_system/grid.py`.
