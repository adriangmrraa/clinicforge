# Odontogram — Interactive Dental Chart

`frontend_react/src/components/Odontogram.tsx`

## Overview

A full FDI dental chart with 32 teeth, each with 5 clickable surfaces, 10 possible states, colored SVG fills with glow effects, and a floating save button.

---

## Tooth SVG Structure

Each tooth is a 40x40 SVG with 4 outer surfaces + 1 center circle:

```
        ┌───────┐
       ╱ TOP     ╲
      ╱   ┌───┐   ╲
     │LEFT│ O │RIGHT│    O = Occlusal (center circle, r=7)
      ╲   └───┘   ╱
       ╲ BOTTOM  ╱
        └───────┘

ViewBox: 0 0 40 40
Outer circle radius: 18, center (20,20)
Inner circle radius: 7
```

### SVG Paths
```tsx
const SURFACE_PATHS = {
  top:    'M20,2 A18,18 0 0,1 38,20 L27,20 A7,7 0 0,0 20,13 Z',
  right:  'M38,20 A18,18 0 0,1 20,38 L20,27 A7,7 0 0,0 27,20 Z',
  bottom: 'M20,38 A18,18 0 0,1 2,20 L13,20 A7,7 0 0,0 20,27 Z',
  left:   'M2,20 A18,18 0 0,1 20,2 L20,13 A7,7 0 0,0 13,20 Z',
};
```

---

## State Colors (Dark Theme)

Each state has: `fill` (translucent), `stroke` (visible), `glow` (drop-shadow)

| State | Fill | Stroke | Glow |
|-------|------|--------|------|
| healthy | `rgba(255,255,255,0.06)` | `rgba(255,255,255,0.20)` | none |
| caries | `rgba(239,68,68,0.12)` | `#ef4444` | `drop-shadow(0 0 4px rgba(239,68,68,0.3))` |
| restoration | `rgba(59,130,246,0.12)` | `#3b82f6` | `drop-shadow(0 0 4px rgba(59,130,246,0.3))` |
| root_canal | `rgba(249,115,22,0.12)` | `#f97316` | `drop-shadow(0 0 4px rgba(249,115,22,0.3))` |
| crown | `rgba(139,92,246,0.12)` | `#8b5cf6` | `drop-shadow(0 0 4px rgba(139,92,246,0.3))` |
| implant | `rgba(99,102,241,0.12)` | `#6366f1` | `drop-shadow(0 0 4px rgba(99,102,241,0.3))` |
| prosthesis | `rgba(20,184,166,0.12)` | `#14b8a6` | `drop-shadow(0 0 4px rgba(20,184,166,0.3))` |
| extraction | `rgba(255,255,255,0.03)` | `rgba(255,255,255,0.15)` | none |
| missing | `rgba(255,255,255,0.02)` | `rgba(255,255,255,0.10)` | none |
| treatment_planned | `rgba(234,179,8,0.12)` | `#eab308` | `drop-shadow(0 0 4px rgba(234,179,8,0.3))` |

**Key insight:** Pathological states glow subtly (drop-shadow at 0.3 opacity). Healthy/absent states don't glow — they're barely visible against the dark background.

---

## Animations

### toothPop — State Change Feedback
```css
@keyframes toothPop {
  0%   { transform: scale(1); }
  30%  { transform: scale(1.3); }    /* overshoot */
  60%  { transform: scale(0.95); }   /* undershoot */
  100% { transform: scale(1); }      /* settle */
}
/* Duration: 0.4s ease-out */
```

Triggered by `justChanged` flag. The flag is set for 500ms then cleared:
```tsx
setChangedTeeth(prev => new Set(prev).add(toothId));
setTimeout(() => {
  setChangedTeeth(prev => { const next = new Set(prev); next.delete(toothId); return next; });
}, 500);
```

### Selection Ring — Spinning Dashed Circle
```tsx
<circle cx="20" cy="20" r="19.5"
  fill="none" stroke="#3b82f6" strokeWidth="1.5"
  strokeDasharray="4,3"
  className="animate-[spin_8s_linear_infinite]"
/>
```

### Surface Color Transitions
All `<path>` and `<circle>` elements have `transition-all duration-500` for smooth color changes.

### Extraction X Overlay
```tsx
{state === 'extraction' && (
  <g className="animate-[fadeIn_0.3s_ease-out]">
    <line x1="6" y1="6" x2="34" y2="34" stroke="#dc2626" strokeWidth="2" />
    <line x1="34" y1="6" x2="6" y2="34" stroke="#dc2626" strokeWidth="2" />
  </g>
)}
```

---

## Interaction Flow

```
1. User taps tooth → tooth becomes "selected"
   - Selection ring appears (spinning dashed circle)
   - scale-115, z-10 (pops above neighbors)

2. User taps state button (e.g., "Caries")
   - Selected tooth changes color with toothPop animation
   - SVG fill/stroke transition over 500ms
   - Glow appears via CSS filter

3. If tooth was already selected → tapping same tooth applies current state
   - This allows rapid: select tooth → tap tooth again = apply state

4. hasChanges becomes true → floating save button activates
   - Button glows with pulseGlow animation
   - Disabled state removed
```

---

## Floating Save Button

```tsx
<div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30">
  <button className={`
    flex items-center gap-1.5 px-5 py-2.5 rounded-full text-xs font-semibold
    transition-all duration-200 shadow-lg active:scale-95
    ${hasChanges
      ? 'bg-blue-600 hover:bg-blue-500 shadow-blue-600/30'
      : 'bg-white/[0.06] text-white/30 cursor-not-allowed'
    }
  `}
  style={hasChanges ? { animation: 'pulseGlow 2s ease-in-out infinite' } : undefined}
  >
```

**Key detail:** The save button is `fixed` at the bottom center, not inside the scrollable container. This ensures it's always visible while scrolling through states and legend.

---

## State Selector Buttons

```tsx
// Active state:
`${STATE_BTN[s.id]} ring-2 ring-offset-1 ring-offset-[#06060e] ring-blue-400 scale-105`

// Inactive state:
'bg-white/[0.04] border-white/[0.10] text-white/50 hover:border-white/[0.20] hover:bg-white/[0.06]'

// All: active:scale-90 transition-all duration-200 ease-out
```

**ring-offset-[#06060e]** — The ring offset matches the background color so the gap between button and ring is dark, not white.
