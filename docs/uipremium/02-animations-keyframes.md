# Animations & Keyframes — ClinicForge UI

## Animation Philosophy

Every interaction has feedback. Nothing happens instantly — everything transitions. But animations are **fast** (200-400ms for interactions, 3-8s for ambient effects). The system uses two categories:

1. **Interaction animations** — triggered by user action (tap, hover, swipe)
2. **Ambient animations** — loop continuously to draw attention

---

## Interaction Animations

### fadeIn (0.3s)
Simple opacity reveal. Used for new elements appearing.
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

### slideUp (0.3s)
Content slides up with fade. Used for alerts, success messages.
```css
@keyframes slideUp {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
```

### slideIn (0.3s)
Slides from right. Used for toasts, notifications.
```css
@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
```

### modalIn (0.35s)
Scale + vertical shift for modal entrance. Uses spring-like cubic-bezier.
```css
@keyframes modalIn {
  from { opacity: 0; transform: scale(0.92) translateY(20px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
/* Easing: cubic-bezier(0.16, 1, 0.3, 1) — fast start, smooth settle */
```

### cardSlideLeft / cardSlideRight (0.3s)
Directional content transition for step-by-step navigation.
```css
@keyframes cardSlideLeft {
  from { opacity: 0; transform: translateX(40px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes cardSlideRight {
  from { opacity: 0; transform: translateX(-40px); }
  to { opacity: 1; transform: translateX(0); }
}
```

### toothPop (0.4s)
Bounce effect when a tooth state changes in the odontogram.
```css
@keyframes toothPop {
  0%   { transform: scale(1); }
  30%  { transform: scale(1.3); }
  60%  { transform: scale(0.95); }
  100% { transform: scale(1); }
}
```

### tooltipIn (0.4s)
Speech bubble popup with overshoot bounce.
```css
@keyframes tooltipIn {
  0%   { opacity: 0; transform: scale(0.8) translateY(8px); }
  50%  { opacity: 1; transform: scale(1.03) translateY(-2px); }
  100% { opacity: 1; transform: scale(1) translateY(0); }
}
/* Easing: cubic-bezier(0.16, 1, 0.3, 1) */
```

---

## Ambient Animations (Looping)

### guideWobble (6s infinite)
The `?` help button icon walks, shakes, grows, and shrinks to attract attention.
```css
@keyframes guideWobble {
  0%, 100% { transform: scale(1) rotate(0deg) translateX(0); }
  5%       { transform: scale(1.15) rotate(-8deg) translateX(-2px); }
  10%      { transform: scale(1.15) rotate(8deg) translateX(2px); }
  15%      { transform: scale(1.2) rotate(-5deg) translateX(-1px); }
  20%      { transform: scale(1.1) rotate(5deg) translateX(1px); }
  25%      { transform: scale(1.3) rotate(0deg) translateX(0); }
  30%      { transform: scale(0.9) rotate(0deg); }
  35%      { transform: scale(1.05) rotate(0deg); }
  40%, 100% { transform: scale(1) rotate(0deg) translateX(0); }
}
```
**Key insight**: The animation is active only for the first 40% of the cycle, then rests for 60%. This creates a "burst of movement then calm" pattern that feels organic.

### novaWobble (5s infinite)
Same pattern but more pronounced for the larger Nova button.
```css
@keyframes novaWobble {
  0%, 100% { transform: scale(1) rotate(0deg) translateX(0); }
  5%       { transform: scale(1.15) rotate(-10deg) translateX(-2px); }
  10%      { transform: scale(1.15) rotate(10deg) translateX(2px); }
  15%      { transform: scale(1.25) rotate(-6deg) translateX(-1px); }
  20%      { transform: scale(1.1) rotate(6deg) translateX(1px); }
  25%      { transform: scale(1.35) rotate(0deg) translateX(0); }
  30%      { transform: scale(0.85) rotate(0deg); }
  35%      { transform: scale(1.08) rotate(0deg); }
  40%, 100% { transform: scale(1) rotate(0deg) translateX(0); }
}
```

### guidePing / novaPing (3s infinite)
Expanding ring that fades out — radar pulse effect.
```css
@keyframes guidePing {
  0%   { transform: scale(1); opacity: 0.6; }
  50%  { transform: scale(1.6); opacity: 0; }
  100% { transform: scale(1); opacity: 0; }
}

@keyframes novaPing {
  0%   { transform: scale(1); opacity: 0.5; }
  50%  { transform: scale(1.7); opacity: 0; }
  100% { transform: scale(1); opacity: 0; }
}
```
Applied to a `<span>` with `absolute inset-0 rounded-full border-2` overlaying the button.

### Odontogram Selection Ring (8s infinite)
Spinning dashed circle around the selected tooth.
```css
/* Uses Tailwind's built-in spin but at 8s instead of 1s */
className="animate-[spin_8s_linear_infinite]"
/* Applied to: <circle strokeDasharray="4,3" stroke="#3b82f6" /> */
```

### pulseGlow (2s infinite)
Save button glow when changes are pending.
```css
@keyframes pulseGlow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.3); }
  50%      { box-shadow: 0 0 12px 4px rgba(59,130,246,0.15); }
}
```

---

## Hover/Active Patterns

### Standard Button
```tsx
className="hover:scale-110 active:scale-90 transition-all duration-200"
```

### Card Hover (GlassCard)
```tsx
// Scale with spring easing
style={{ transition: 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)' }}
// Scale: 1 → 1.015x
// Shadow: soft → elevated
// Background image: opacity 0.03 → 0.08
// Ken Burns zoom: scale 1.02 → 1.1 over 8s
```

### Sidebar Item Hover
```tsx
className="hover:scale-[1.03] active:scale-[0.97]"
// Spring easing: cubic-bezier(0.34, 1.56, 0.64, 1)
// Ring appears: ring-1 ring-white/[0.06]
// Background image fades in: opacity 0 → 0.12
// Gradient edge appears on left
```

### Touch Feedback (Mobile)
```tsx
className="active:scale-[0.98] touch-manipulation transition-all"
// touch-manipulation: prevents 300ms delay on iOS
// active:scale: gives instant visual feedback
```

---

## Easing Functions

| Name | Value | Use |
|------|-------|-----|
| Standard | `ease-out` | Most transitions |
| Spring | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Scale effects (overshoot bounce) |
| Smooth spring | `cubic-bezier(0.16, 1, 0.3, 1)` | Modal entrances, tooltips |
| Linear | `linear` | Continuous rotation (spin) |

---

## How to Stop Animations on Hover

For attention-grabber icons, the wobble stops on hover to feel responsive:
```css
.guide-btn .guide-icon {
  animation: guideWobble 6s ease-in-out infinite;
}
.guide-btn:hover .guide-icon {
  animation: none;
  transform: scale(1.1);
}

.nova-btn .nova-icon {
  animation: novaWobble 5s ease-in-out infinite;
}
.nova-btn:hover .nova-icon {
  animation: none;
  transform: scale(1.15) rotate(15deg);
  transition: transform 0.2s ease-out;
}
```
