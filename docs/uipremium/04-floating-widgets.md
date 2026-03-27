# Floating Widgets — Nova & Guide Button

## Nova Widget (Voice AI Copilot)

`frontend_react/src/components/NovaWidget.tsx`

The purple floating button in the bottom-right corner. Always visible on every page.

### Button Design

```
         ┌─ Ping ring (expanding border, 3s loop)
         │
    ╭────┼────╮
    │  ╭──╮   │  ← Gradient: from-violet-600 to-indigo-600
    │  │✦ │   │  ← Sparkles icon with novaWobble animation
    │  ╰──╯   │
    ╰─────────╯
         │
         └─ Shadow: shadow-lg shadow-violet-500/25
```

**CSS:**
```tsx
className="nova-btn fixed bottom-6 right-6 z-[9998] w-14 h-14 rounded-full
  bg-gradient-to-br from-violet-600 to-indigo-600
  shadow-lg shadow-violet-500/25
  flex items-center justify-center text-white
  hover:scale-110 active:scale-90
  transition-all duration-200"
style={{ bottom: 'max(1.5rem, env(safe-area-inset-bottom))' }}
```

**Key detail:** `env(safe-area-inset-bottom)` ensures the button doesn't hide behind the iPhone home bar.

### Icon Animation
```css
.nova-btn .nova-icon {
  animation: novaWobble 5s ease-in-out infinite;
}
.nova-btn:hover .nova-icon {
  animation: none;
  transform: scale(1.15) rotate(15deg);
  transition: transform 0.2s ease-out;
}
```

### Ping Ring
```tsx
<span className="absolute inset-0 rounded-full border-2 border-violet-400/40 animate-[novaPing_3s_ease-out_infinite]" />
```

### Alert Badge
```tsx
{alertCount > 0 && (
  <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center z-10">
    {alertCount > 9 ? '9+' : alertCount}
  </span>
)}
```

### Panel (When Opened)
- Mobile: `fixed inset-0` (full screen)
- Desktop: `fixed bottom-6 right-6 w-[420px] h-[560px]`
- Background: `bg-[#0f0f17]`
- Border (desktop): `border border-violet-500/20 rounded-2xl`
- Backdrop (mobile): `bg-black/60 backdrop-blur-sm`

---

## Guide Button (Help)

`frontend_react/src/components/Layout.tsx`

The blue `?` circle in the top header. Opens the OnboardingGuide modal.

### Button Design
```tsx
className="guide-btn relative flex items-center justify-center w-9 h-9 rounded-full
  bg-blue-500/10 text-blue-400 border border-blue-500/20
  hover:bg-blue-500/25 hover:scale-110 active:scale-90
  transition-all duration-200"
```

### Icon Animation
```css
.guide-btn .guide-icon {
  animation: guideWobble 6s ease-in-out infinite;
}
.guide-btn:hover .guide-icon {
  animation: none;
  transform: scale(1.1);
}
```

### Ping Ring
```tsx
<span className="absolute inset-0 rounded-full border-2 border-blue-400/40 animate-[guidePing_3s_ease-out_infinite]" />
```

---

## Tooltip Popups (First Visit)

Both buttons show a speech bubble tooltip the first time the user visits. Timed sequence:

```
0s          3s         7s         8s         12s
|           |          |          |          |
|           ├── Nova tooltip appears
|           |          ├── Nova tooltip disappears
|           |          |          ├── Guide tooltip appears
|           |          |          |          ├── Guide tooltip disappears
```

### Implementation
```tsx
// Only once per session
useEffect(() => {
  if (sessionStorage.getItem('tooltips_shown')) return;
  const t1 = setTimeout(() => setNovaTooltip(true), 3000);
  const t2 = setTimeout(() => setNovaTooltip(false), 7000);
  const t3 = setTimeout(() => setGuideTooltip(true), 8000);
  const t4 = setTimeout(() => {
    setGuideTooltip(false);
    sessionStorage.setItem('tooltips_shown', '1');
  }, 12000);
  return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4); };
}, []);
```

### Nova Tooltip
```tsx
<div className="w-56 px-3 py-2.5 rounded-xl bg-violet-500/90 backdrop-blur-md text-white text-[11px] shadow-xl shadow-violet-500/20"
  style={{ animation: 'tooltipIn 0.4s cubic-bezier(0.16,1,0.3,1)' }}>
  Soy Nova, tu asistente de voz...
  <div className="absolute -bottom-1.5 right-5 w-3 h-3 bg-violet-500/90 rotate-45" />
</div>
```

### Guide Tooltip
```tsx
<div className="absolute top-12 right-0 w-52 px-3 py-2 rounded-xl bg-blue-500/90 backdrop-blur-md text-white text-[11px] shadow-xl shadow-blue-500/20"
  style={{ animation: 'tooltipIn 0.4s cubic-bezier(0.16,1,0.3,1)' }}>
  Toca aca para ver una guia...
  <div className="absolute -top-1.5 right-4 w-3 h-3 bg-blue-500/90 rotate-45" />
</div>
```

### Speech Bubble Arrow
The triangle pointer is a `3x3` div rotated 45 degrees, positioned at the edge:
```tsx
// Pointing up (for guide tooltip below button):
<div className="absolute -top-1.5 right-4 w-3 h-3 bg-blue-500/90 rotate-45" />

// Pointing down (for Nova tooltip above button):
<div className="absolute -bottom-1.5 right-5 w-3 h-3 bg-violet-500/90 rotate-45" />
```
