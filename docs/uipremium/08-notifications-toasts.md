# Notifications, Toasts & Status Indicators

## Premium Notification Toast

`frontend_react/src/components/Layout.tsx`

Full-width gradient-bordered toast that slides in from the right.

### Structure
```
┌─ Gradient border (1px) ──────────────────┐
│ ┌─ Glassmorphic card ─────────────────┐  │
│ │  ┌──────┐                           │  │
│ │  │ Icon │  Title              [×]   │  │
│ │  │ glow │  Subtitle · time         │  │
│ │  └──────┘                    ● dot  │  │
│ │  ═══ Shine overlay (hover) ═══════  │  │
│ └─────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### Gradient Border by Type
```tsx
// Urgency:
"bg-gradient-to-r from-red-500 via-rose-500 to-red-600"

// Appointment/New Patient:
"bg-gradient-to-r from-emerald-500 via-green-500 to-emerald-600"

// Handoff:
"bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-600"
```

### Card Inner
```tsx
className="bg-white/95 backdrop-blur-xl rounded-[15px] p-4"
// Hover: hover:scale-[1.02] active:scale-[0.98]
// Transition: duration-300
```

### Icon Glow
```tsx
<div className="w-12 h-12 rounded-xl shadow-inner overflow-hidden">
  <div className="animate-pulse w-full h-full bg-{color}-500/20" />
  <Icon className="absolute text-{color}-600" />
</div>
```

### Shine Effect
```tsx
// Overlay div:
className="bg-gradient-to-tr from-transparent via-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700"
```

### Pulse Dot
```tsx
<div className="h-1 w-1 rounded-full bg-{color}-500 animate-ping" />
```

---

## Toast CSS Classes (index.css)

```css
.toast {
  @apply p-4 rounded-lg shadow-lg border-l-4 animate-slide-in;
}
.toast-success { @apply bg-green-500/10 border-green-500 text-green-400; }
.toast-warning { @apply bg-yellow-500/10 border-yellow-500 text-yellow-400; }
.toast-error   { @apply bg-red-500/10 border-red-500 text-red-400; }
.toast-info    { @apply bg-blue-500/10 border-blue-500 text-blue-400; }
```

---

## Connection Status Chip

Always visible in the top header:

```tsx
// Connected:
"bg-green-500/10 text-green-400" + <Wifi size={12} />

// Reconnecting:
"bg-orange-500/10 text-orange-400 animate-pulse" + <WifiOff size={12} />

// Disconnected:
"bg-red-500/10 text-red-400" + <WifiOff size={12} />
```

---

## Alert Boxes (In-Component)

Standard pattern for error/success/warning messages:

```tsx
// Error:
"bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl"

// Success:
"bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl"

// Warning:
"bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 rounded-xl"

// Info (tips):
"bg-amber-500/[0.06] border border-amber-500/15 rounded-xl"
```

All with `animate-[slideUp_0.3s_ease-out]` entrance.

---

## Meta Token Banner

`frontend_react/src/components/MetaTokenBanner.tsx`

Full-width banner at the top of the page when Meta token is expiring:

```tsx
// Expired:
"bg-rose-600 text-white"

// Expiring soon:
"bg-amber-500 text-white"

// Animation: animate-in slide-in-from-top duration-500
// Icon: AlertTriangle with animate-pulse
// Button: bg-white/20 hover:bg-white/30 backdrop-blur-md rounded-xl
```

---

## Badge System

```css
.badge { @apply inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium; }
.badge-success { @apply bg-green-500/10 text-green-400; }
.badge-warning { @apply bg-yellow-500/10 text-yellow-400; }
.badge-danger  { @apply bg-red-500/10 text-red-400; }
.badge-info    { @apply bg-blue-500/10 text-blue-400; }
```

### Source Badges (Agenda)
```tsx
// Ventas IA: bg-blue-500/10 text-blue-400
// Nova:     bg-purple-500/10 text-purple-400
// Manual:   bg-green-500/10 text-green-400
// GCal:     bg-white/[0.06] text-white/50
```
