# GlassCard & Sidebar — Premium Components

## GlassCard Component

`frontend_react/src/components/GlassCard.tsx`

The signature card component. Every dashboard card, stat box, and content panel uses this. It creates a glass-like surface with a background image that fades in on hover.

### Structure
```
┌─────────────────────────────┐
│  Background Image Layer     │  ← blur(2px), opacity 0.03 → 0.08 on hover
│  ┌───────────────────────┐  │
│  │  Gradient Overlay      │  │  ← subtle directional gradient
│  │  ┌─────────────────┐  │  │
│  │  │  Content (children) │  │  ← actual card content
│  │  └─────────────────┘  │  │
│  └───────────────────────┘  │
│  ════════════════════════   │  ← blue glow edge (1px), opacity 0 → 1 on hover
└─────────────────────────────┘
```

### Visual Effects

**Default state:**
- Background: `bg-white/[0.03]`
- Border: `border border-white/[0.06]`
- Rounded: `rounded-2xl`
- Shadow: `0 2px 8px rgba(0,0,0,0.1)`
- Image: `opacity: 0.03`, `filter: blur(2px)`, `scale: 1.02`

**Hover state:**
- Scale: `1.015` with spring easing `cubic-bezier(0.34, 1.56, 0.64, 1)` over 0.4s
- Shadow: `0 8px 40px rgba(0,0,0,0.25)`
- Image: `opacity: 0.08`, `scale: 1.1` (Ken Burns zoom over 8s)
- Gradient: adds `rgba(59,130,246,0.03)` blue tint at 50%
- Bottom glow: `linear-gradient(90deg, transparent, rgba(59,130,246,0.3), transparent)` fades in

**Touch handling:**
```tsx
onTouchStart={() => setHovered(true)}
onTouchEnd={() => setTimeout(() => setHovered(false), 500)}
// 500ms delay gives the user time to see the hover effect on mobile
```

### Background Images (CARD_IMAGES)

Each page/context has a themed background image:
```tsx
const CARD_IMAGES = {
  dashboard: '/images/dental-office.jpg',
  agenda: '/images/calendar-desk.jpg',
  patients: '/images/patient-care.jpg',
  chats: '/images/messaging.jpg',
  analytics: '/images/data-charts.jpg',
  marketing: '/images/marketing-ads.jpg',
  // etc.
};
```

---

## Sidebar Component

`frontend_react/src/components/Sidebar.tsx`

The sidebar is the main navigation. It collapses on mobile and has rich hover effects with background images per menu item.

### Sidebar States

```
┌──┐                    ┌──────────────────┐
│  │  Collapsed (64px)   │                  │  Expanded (256px)
│ 🏠│                    │ 🏠 Dashboard      │
│ 📅│                    │ 📅 Agenda         │
│ 👥│                    │ 👥 Pacientes      │
│ 💬│                    │ 💬 Chats          │
│  │                    │                  │
│ ↩│                    │ ↩ Cerrar sesion   │
└──┘                    └──────────────────┘
```

### Navigation Item Effects

**Default:**
```tsx
className="bg-transparent text-white/50 rounded-xl"
```

**Hover:**
```tsx
className="scale-[1.03] ring-1 ring-white/[0.06] bg-white/[0.04]"
// Background image fades in at opacity 0.12
// Gradient edge: bg-gradient-to-r from-blue-500/[0.06] to-transparent
// Spring easing: cubic-bezier(0.34, 1.56, 0.64, 1), 300ms
```

**Active (current page):**
```tsx
className="scale-[1.03] ring-1 ring-white/[0.12] shadow-lg shadow-white/[0.03] bg-white/[0.08]"
// Background image always visible at opacity 0.12
// Left indicator bar: w-[2px] h-5 bg-blue-400 rounded-r-full
// Text: text-white/85
// Icon: text-white
```

### Icon Styling
```tsx
// Default: text-white/40, size 18px
// Hover: text-white/70
// Active: text-white
// Lucide icons, no emojis
```

### Sidebar Tooltip (collapsed mode)
When sidebar is collapsed, hovering a nav item shows a tooltip to the right:
```tsx
// Position: left-full top-0 ml-3
// Background: #0d1117 border border-white/[0.08]
// Animation: sidebar-tooltip-in 0.15s ease-out
@keyframes sidebar-tooltip-in {
  from { opacity: 0; transform: translateX(-4px); }
  to { opacity: 1; transform: translateX(0); }
}
```

### Logout Button
Same scale hover (1.03) but with red color scheme:
```tsx
className="hover:bg-red-500/[0.08] text-red-400/60 hover:text-red-400"
```

### Mobile Behavior
- Opens as overlay with backdrop `bg-black/50`
- Slide-in from left with `transform transition-all duration-300`
- Close on backdrop click or navigation
