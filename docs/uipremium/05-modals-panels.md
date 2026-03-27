# Modals & Panels — ClinicForge UI

## Modal Types

ClinicForge uses 3 modal patterns:

1. **Centered floating card** — OnboardingGuide (with 3D tilt)
2. **Slide-over panel** — AppointmentForm (right side)
3. **Bottom sheet / centered** — Generic Modal (mobile drawer, desktop centered)

---

## 1. OnboardingGuide — 3D Tilt Card

`frontend_react/src/components/OnboardingGuide.tsx`

### Entrance Animation
```css
@keyframes modalIn {
  from { opacity: 0; transform: scale(0.92) translateY(20px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
/* Duration: 0.35s, Easing: cubic-bezier(0.16, 1, 0.3, 1) */
```

### 3D Tilt Effect
The card tilts following the mouse/finger position:
```tsx
const handlePointerMove = (e) => {
  const rect = cardRef.current.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width - 0.5) * 8;   // ±4 degrees
  const y = ((e.clientY - rect.top) / rect.height - 0.5) * -8;   // ±4 degrees
  setTilt({ x, y });
};

// Applied as:
style={{
  transform: `perspective(800px) rotateY(${tilt.x}deg) rotateX(${tilt.y}deg)`,
  transition: 'transform 0.15s ease-out',
}}
```

### Swipe Gestures
```tsx
// Touch start: record position
// Touch move: follow finger (damped 0.4x)
// Touch end: if dx > 50px → next/prev step
// Last step + swipe left → close modal

const handleTouchMove = (e) => {
  const dx = e.touches[0].clientX - touchStart.x;
  if (Math.abs(dx) > Math.abs(dy)) {
    setSwipeX(dx * 0.4); // damped follow
  }
};
```

### Card Styling
```tsx
className="w-full max-w-md bg-[#0c1018]/95 backdrop-blur-2xl border border-white/[0.08] rounded-3xl shadow-2xl shadow-black/40"
```

### Step Transition Direction
Steps slide left or right based on navigation direction:
```tsx
const animClass = direction === 'next'
  ? 'animate-[cardSlideLeft_0.3s_ease-out]'
  : 'animate-[cardSlideRight_0.3s_ease-out]';
```

### Step Dot Indicators
```tsx
// Active: w-5 bg-blue-500
// Completed: w-1.5 bg-blue-500/30
// Pending: w-1.5 bg-white/[0.08]
// All: h-1 rounded-full transition-all duration-300
// Clickable with direction-aware animation
```

---

## 2. AppointmentForm — Slide-Over Panel

`frontend_react/src/components/AppointmentForm.tsx`

### Slide Animation
```tsx
className={`fixed inset-y-0 right-0 z-[70] w-full md:w-[450px]
  bg-[#0d1117] backdrop-blur-xl shadow-2xl
  transform transition-transform duration-300 ease-out
  border-l border-white/[0.08] flex flex-col
  ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
```

### Backdrop
```tsx
className="fixed inset-0 bg-black/20 backdrop-blur-sm z-[60] transition-opacity duration-300"
```

### Tab Navigation
```tsx
// Active tab:
"border-b-2 border-blue-500 text-blue-600"
// Inactive tab:
"border-transparent text-white/40 hover:text-white/70 hover:bg-white/[0.04]"
```

### Source Badge in Header
Shows who created the appointment (Ventas IA, Nova, Manual, GCal):
```tsx
<span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${cfg.bg} ${cfg.text}`}>
  {cfg.label}
</span>
```

### Footer (Sticky)
```tsx
className="sticky bottom-0 bg-[#0d1117]/90 backdrop-blur-md border-t border-white/[0.06] p-4"
```

---

## 3. Generic Modal — Bottom Sheet (Mobile) / Centered (Desktop)

`frontend_react/src/components/Modal.tsx`

### Mobile: Bottom Sheet
```tsx
// Container: flex items-end (pushes modal to bottom)
// Content: rounded-t-2xl (only top corners rounded)
// Max height: max-h-[92vh]
```

### Desktop: Centered
```tsx
// Container: flex items-center justify-center p-4
// Content: rounded-2xl
// Max height: max-h-[85vh]
// Sizes: max-w-md, max-w-2xl, max-w-4xl
```

### Global Modal CSS
```css
.modal-overlay {
  @apply fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4;
}
.modal-content {
  @apply bg-[#0d1117] rounded-2xl shadow-elevated max-w-lg w-full max-h-[90vh] overflow-y-auto border border-white/[0.08];
}
.modal-footer {
  @apply flex justify-end gap-3 p-4 border-t border-white/[0.06] bg-white/[0.02] rounded-b-2xl;
}
```

---

## Backdrop Pattern

All modals share the same backdrop pattern:
```tsx
// Standard: bg-black/50 backdrop-blur-sm
// Heavy: bg-black/60 backdrop-blur-sm (OnboardingGuide)
// Light: bg-black/20 backdrop-blur-sm (AppointmentForm)
// Click backdrop → close modal
```

---

## Z-Index Hierarchy

```
z-[9999] — Nova tooltip
z-[9998] — Nova widget button & panel
z-[201]  — OnboardingGuide modal
z-[200]  — OnboardingGuide backdrop
z-[100]  — Generic notification toast
z-[70]   — AppointmentForm slide-over
z-[60]   — AppointmentForm backdrop
z-[50]   — Generic modal
z-[30]   — Odontogram floating save button
z-10     — Selected tooth (scale bump)
```
