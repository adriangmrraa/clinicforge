# ClinicForge UI Premium — Design System Documentation

## Documents

| File | Content |
|------|---------|
| [01-dark-theme-palette.md](01-dark-theme-palette.md) | Color system, opacity scales, glass surfaces, background hierarchy |
| [02-animations-keyframes.md](02-animations-keyframes.md) | All keyframe animations, easing functions, hover/active patterns |
| [03-glasscard-sidebar.md](03-glasscard-sidebar.md) | GlassCard (Ken Burns, blur, glow edge), Sidebar (hover images, tooltips) |
| [04-floating-widgets.md](04-floating-widgets.md) | Nova button (wobble, ping), Guide button, tooltip popup sequence |
| [05-modals-panels.md](05-modals-panels.md) | 3D tilt card, slide-over panel, bottom sheet, z-index hierarchy |
| [06-odontogram-interactive.md](06-odontogram-interactive.md) | Tooth SVG anatomy, state colors with glow, toothPop, floating save |
| [07-mobile-patterns.md](07-mobile-patterns.md) | Touch feedback, view modes, DateStrip, safe areas, scroll isolation |
| [08-notifications-toasts.md](08-notifications-toasts.md) | Premium toasts, connection status, alert boxes, badge system |

## Quick Reference

### The 3 Core Principles

1. **Depth through transparency** — No solid backgrounds. Everything uses `bg-white/[0.02-0.08]` so the `#06060e` root bleeds through.

2. **Every tap has feedback** — `active:scale-90` on buttons, `active:scale-[0.98]` on cards, `touch-manipulation` everywhere.

3. **Ambient + Interactive** — Floating buttons have continuous wobble animations that **stop** on hover, replaced by static scale transform.

### Standard Component Pattern

```tsx
<div className="bg-white/[0.03] rounded-2xl border border-white/[0.06] p-4">
  <h3 className="text-white font-bold">Title</h3>
  <p className="text-white/40 text-sm">Description</p>
  <button className="bg-white/[0.06] border border-white/[0.08] text-white/70
    hover:bg-white/[0.10] active:scale-95 transition-all duration-200 rounded-lg px-4 py-2">
    Action
  </button>
</div>
```
