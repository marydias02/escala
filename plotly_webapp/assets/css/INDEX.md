# assets/css Index

This folder is split by ownership boundaries. Treat boundary rules as strict.

## Layer Ownership

| Folder | Ownership | Purpose | Edit policy |
|---|---|---|---|
| base/ | DS core | Tokens and base primitives | Frozen except `--custom-theme` in `:root {}` of `colors.css` |
| components/ | DS core | Canonical DS component styles | Frozen |
| custom/ | project | Project-specific reusable styling | Your extension zone |
| pages/ | project | Page-level composition overrides | Your extension zone |

## Non-Negotiable Boundaries

1. Never edit `base/` except `--custom-theme` in the `:root {}` block of `colors.css`.
2. Never edit components/ for project customization.
3. Put all project-specific styling in custom/ and pages/.

## Inventory Notes

Current component mapping highlights:

- components/cards maps to nested files under assets/css/components/cards/
- components/components_extra_design_system maps intentionally to assets/css/components/components_extra_ds.css

Current CSS-only support files without one-to-one Python component folders:

- datepicker.css
- dropdown.css
- table_actionbar.css
- table_flyout.css

Use live inventory checks during audits:

- list components/
- list assets/css/components/

## Extension Practices

For custom and pages layers:

- one file per concern
- descriptive filenames
- token-first styling via var(--...)
- avoid hardcoded values unless explicitly justified
