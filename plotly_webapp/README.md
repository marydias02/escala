# Dash Template

Dash Template is the company design system starter repository for Dash applications.
The intended workflow is simple: clone the repository, install dependencies, run the app, and start building on top of the existing design system instead of redefining it.

## Purpose

This repository exists to provide:

- a ready-to-run Dash application shell
- reusable UI components and styling primitives
- a consistent starting point for internal projects
- a constrained extension model so teams build with the design system instead of around it

## Who This Is For

This repository is for engineers and other contributors who need to start a new project using the company design system.

If you are new to the repository, start with:

- this `README.md` for setup and first run
- root `INDEX.md` for repository navigation and where to look next

## AI Design System Guide

This repository includes two skills for Codex and Claude Code.

**`ds-guide`** - answers questions about the design system (structure, rules, components, workflows).
**`update-ds-guide`** - UI/UX team tool that audits docs against the current repo state after changes.

### Install

**Codex:**
```bash
mkdir -p .agents/skills/ds-guide && cp docs/skills/ds-guide/SKILL.md .agents/skills/ds-guide/SKILL.md
mkdir -p .agents/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .agents/skills/update-ds-guide/SKILL.md
```

**Claude Code:**
```bash
mkdir -p .claude/skills/ds-guide && cp docs/skills/ds-guide/SKILL.md .claude/skills/ds-guide/SKILL.md
mkdir -p .claude/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .claude/skills/update-ds-guide/SKILL.md
```

Restart your AI tool after running these commands.

### Usage

| Skill | Codex | Claude Code | Who runs it |
|---|---|---|---|
| DS Guide | `$ds-guide "question"` | `/ds-guide "question"` | Developers |
| Update DS Guide | `$update-ds-guide` | `/update-ds-guide` | UI/UX team |

## Prerequisites

- Python `3.11`
- `uv`

## Quick Start

Clone the repository using either SSH or HTTPS:

```bash
git clone git@git.ltplabs.net:internal/technology/tech-delivery/uiux/dash-template.git
```

```bash
git clone https://git.ltplabs.net/internal/technology/tech-delivery/uiux/dash-template.git
```

Enter the project directory:

```bash
cd existing_repo
```

Install the project dependencies:

```bash
uv sync
```

Run the application:

```bash
uv run app.py
```

By default, Dash will start a local development server. Open the local URL shown in the terminal, which is typically `http://127.0.0.1:8050/`.

## Project Entry Point

The application entry point is:

- `app.py`

This file defines the Dash application shell, shared layout structure, and page container wiring.

## Repository Overview

At a high level, the repository is organized around a few core areas:

- `app.py`: application entry point
- `components/`: reusable design system components
- `assets/`: base styles, component styles, images, icons, scripts, and custom overrides
- `pages/`: Dash page modules and route composition
- `callbacks/`: callback logic
- `utils/`: shared helper utilities

The root `INDEX.md` will be the main navigation map for this repository.

## Extension Boundaries

Use these boundaries when implementing features:

- `assets/css/base/` and `assets/css/components/` are frozen DS layers.
- All project-specific styling must go in `assets/css/custom/` and `assets/css/pages/`.
- New reusable UI belongs in `components/`.
- New behavior belongs in `callbacks/`.
- Page composition belongs in `pages/`.

See `docs/navigation.md`, `docs/best_practices.md`, and `docs/workflows.md` for the complete implementation model.

## Working Model

This repository should be treated as a plug-and-play design system foundation.

The default expectation is:

- start from the existing components and styles
- reuse before creating
- extend carefully
- avoid unnecessary deviations from the design system

See `docs/best_practices.md` for the full rule set and rationale.

If a project needs exceptions, they should be deliberate and justified.

## Theme Color

The only color customization allowed in this design system is the theme hue.

Open `assets/css/base/colors.css` and locate the `--custom-theme` variable inside `:root {}`:

```css
--custom-theme: <HSL value>;
```

The HSL value is provided by the design team. Never define your own.
This is the only variable in `assets/css/base/` you are permitted to change.

## Documentation

The `docs/` folder contains the design system knowledge base:

- `docs/overview.md` - what a design system is, tokens, reusable components, and the Figma reference
- `docs/navigation.md` - how the repo is organized and where to find things
- `docs/best_practices.md` - rules, conventions, and what never to do
- `docs/workflows.md` - step-by-step guides for common tasks
- `docs/resources.md` - external links (Figma, Dash docs, icons, and related references)