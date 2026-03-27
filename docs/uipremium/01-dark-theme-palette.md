# Dark Theme Palette — ClinicForge Design System

## Core Philosophy

ClinicForge uses an ultra-dark theme where surfaces are barely visible against the background. The goal is **depth through transparency** — elements don't have solid backgrounds, they use `rgba(255,255,255)` at very low opacities (0.02 to 0.08) so the deep space background bleeds through everything.

No light mode exists. Every component must follow this system.

---

## Background Hierarchy

```
Level 0 — Body/Root:        #06060e (deep space black)
Level 1 — Page surfaces:    #0a0e1a (slightly lifted)
Level 2 — Modals/Panels:    #0d1117 (elevated)
Level 3 — Glass surfaces:   rgba(255,255,255, 0.02-0.08) (transparent glass)
```

### Glass Surface Scale (most used)

| Opacity | Tailwind | Use |
|---------|----------|-----|
| `0.02` | `bg-white/[0.02]` | Barely there — empty states, absent elements |
| `0.03` | `bg-white/[0.03]` | Cards, containers, panels (primary surface) |
| `0.04` | `bg-white/[0.04]` | Inputs, form controls, inactive buttons |
| `0.06` | `bg-white/[0.06]` | Hover states, badges, secondary buttons |
| `0.08` | `bg-white/[0.08]` | Active states, selected items, pressed buttons |
| `0.10` | `bg-white/[0.10]` | Strong hover, emphasis states |
| `0.12` | `bg-white/[0.12]` | Maximum emphasis before solid |

---

## Text Opacity Scale

| Opacity | Tailwind | Use |
|---------|----------|-----|
| `1.0` | `text-white` | Headings, names, primary data |
| `0.85` | `text-white/85` | Active nav items |
| `0.70` | `text-white/70` | Body text, secondary buttons |
| `0.50` | `text-white/50` | Labels, subtitles, muted info |
| `0.40` | `text-white/40` | Descriptions, timestamps |
| `0.30` | `text-white/30` | Placeholders, dividers, very muted |
| `0.20` | `text-white/20` | Empty state icons |

---

## Border Scale

| Opacity | Tailwind | Use |
|---------|----------|-----|
| `0.04` | `border-white/[0.04]` | Inner dividers (inside cards) |
| `0.06` | `border-white/[0.06]` | Card borders, section separators |
| `0.08` | `border-white/[0.08]` | Input borders, modal borders |
| `0.10` | `border-white/[0.10]` | Button borders, emphasis |
| `0.12` | `border-white/[0.12]` | Active/selected borders |
| `0.15` | `border-white/[0.15]` | Strong emphasis |
| `0.20` | `border-white/[0.20]` | Hover borders |

---

## Semantic Colors (Dark Variant)

All semantic colors use the `{color}-500/10` pattern for backgrounds and `{color}-400` for text:

```css
/* Success */
bg-green-500/10    text-green-400    border-green-500/20

/* Warning */
bg-yellow-500/10   text-yellow-400   border-yellow-500/20

/* Danger */
bg-red-500/10      text-red-400      border-red-500/20

/* Info */
bg-blue-500/10     text-blue-400     border-blue-500/20

/* Emerald (positive) */
bg-emerald-500/10  text-emerald-400  border-emerald-500/20

/* Amber (tips) */
bg-amber-500/10    text-amber-400    border-amber-500/20

/* Violet (Nova/AI) */
bg-violet-500/10   text-violet-400   border-violet-500/20
```

---

## Card Pattern (Standard)

```tsx
<div className="bg-white/[0.03] rounded-2xl border border-white/[0.06] p-4 sm:p-6">
  <h3 className="text-lg font-bold text-white">Title</h3>
  <p className="text-sm text-white/40">Description</p>
</div>
```

## Input Pattern

```tsx
<input className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm" />
```

## Button Patterns

```tsx
{/* Primary */}
<button className="bg-white text-[#0a0e1a] px-4 py-2 rounded-lg font-medium">

{/* Secondary */}
<button className="bg-white/[0.06] text-white/70 border border-white/[0.08] hover:bg-white/[0.10] active:bg-white/[0.14] px-4 py-2 rounded-lg">

{/* Ghost */}
<button className="text-white/40 hover:text-white/60 hover:bg-white/[0.06] px-3 py-2 rounded-lg transition-all">

{/* Danger */}
<button className="text-red-400 hover:bg-red-500/10 px-3 py-2 rounded-lg transition-colors">
```

## Scrollbar

```css
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: #0a0e1a; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
```
