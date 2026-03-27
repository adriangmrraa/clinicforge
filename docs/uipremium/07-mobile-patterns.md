# Mobile Patterns — Touch, Responsive & Mobile-First

## Touch Feedback

Every tappable element has instant visual feedback:

```tsx
// Standard button:
className="active:scale-90 transition-all duration-200"

// Card/list item:
className="active:scale-[0.98] touch-manipulation transition-all"

// Large button:
className="active:scale-95 transition-transform"
```

**`touch-manipulation`** is critical on iOS — it disables the 300ms tap delay and double-tap-to-zoom, making the app feel native.

---

## MobileAgenda — 4 View Modes

`frontend_react/src/components/MobileAgenda.tsx`

### View Mode Toggle
```tsx
<div className="flex items-center gap-1 px-4 pt-3 pb-2">
  {views.map(v => (
    <button className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all duration-200
      ${active
        ? 'bg-white/[0.08] text-white border border-white/[0.12]'
        : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04]'
      }
    `}>
      <Icon size={14} /> {label}
    </button>
  ))}
</div>
```

### Day View
- DateStrip horizontal scroll with snap
- Event cards: full detail (time, patient, treatment, professional, phone)

### Week View
- Events grouped by date with headers
- Date header: `EEE d MMM` format with count badge
- Compact cards (smaller text, no phone)
- Separator line between groups

### Month View
- 7-column CSS grid calendar
- Day cells with dot indicators (max 3 dots)
- Tap day → show events below + can switch to day view
- Selected day: `bg-blue-600 text-white`
- Today: `bg-blue-500/10 text-blue-400 border border-blue-500/20`
- Default: `bg-white/[0.03] text-white/50`

### List View
- ALL events chronologically (past + future, up to 3 years)
- Past events: `opacity-50` (dimmed)
- "Hoy" separator: blue line with label
- Scrollable — past events above, future below

---

## DateStrip — Horizontal Date Picker

`frontend_react/src/components/DateStrip.tsx`

```tsx
// Container:
"bg-white/[0.02] border-b border-white/[0.06] py-2"

// Date buttons:
"min-w-[56px] h-16 rounded-xl snap-center transition-all duration-200"

// Selected: bg-blue-600 text-white shadow-md scale-105
// Today:    bg-blue-500/10 text-blue-400 border border-blue-500/20
// Default:  bg-white/[0.03] text-white/50 hover:bg-white/[0.06]
```

Uses `scroll-snap-type: x mandatory` for precise snapping.

---

## Event Cards (Mobile)

```tsx
className={`bg-white/[0.03] rounded-xl p-4 border-l-4 border border-white/[0.06]
  ${getStatusColor(status)}
  active:scale-[0.98] hover:bg-white/[0.05]
  transition-all duration-200 touch-manipulation`}
```

Status colors (left border):
- `confirmed` → `border-l-green-500`
- `cancelled` → `border-l-red-500`
- `completed` → `border-l-gray-500`
- `no-show` → `border-l-orange-500`
- `scheduled` → `border-l-blue-500`

---

## Safe Areas (iOS)

```css
.safe-top { padding-top: max(0.75rem, env(safe-area-inset-top)); }
.safe-bottom { padding-bottom: max(0.75rem, env(safe-area-inset-bottom)); }
```

Used in:
- Nova button position: `bottom: max(1.5rem, env(safe-area-inset-bottom))`
- Mobile panels: `maxHeight: '-webkit-fill-available'`

---

## Responsive Breakpoints

```
Mobile first → sm (640px) → md (768px) → lg (1024px)

Key breakpoints:
- < 768px:  MobileAgenda, sidebar hidden, full-screen modals
- >= 768px: FullCalendar desktop, sidebar visible, slide-over modals
- >= 1024px: Sidebar expanded by default
```

### Mobile-Specific Patterns

```tsx
// Hide on mobile, show on desktop:
className="hidden sm:inline"

// Full width on mobile, fixed width on desktop:
className="w-full md:w-[450px]"

// Bottom sheet on mobile, centered on desktop:
className="flex items-end lg:items-center justify-center"

// Smaller touch targets on mobile:
className="text-[10px] lg:text-xs"
```

---

## Scroll Isolation

Critical for nested scrollable areas:

```tsx
// Page container:
className="h-screen overflow-hidden"

// Scrollable content:
className="flex-1 min-h-0 overflow-y-auto"

// Inner scrollable:
className="overflow-y-auto pb-24"  // pb-24 = space for floating buttons
```

**pb-24** at the bottom of scrollable content ensures the floating Nova button doesn't cover the last items.

---

## Overscroll Prevention

```css
.overscroll-contain {
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}
```

Prevents iOS rubber-band bounce from bleeding through to the background.
