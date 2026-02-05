# Architecture Overview

## Component Hierarchy

```
app/page.tsx (Main Orchestrator)
└── ChatLayout
    ├── Header (Branding)
    └── Main Content
        ├── ZeroState (state === 'idle')
        │   ├── Heading & Description
        │   ├── StarterChips
        │   │   └── Button (4x scenarios)
        │   └── FileUpload
        │       └── Drag & Drop Zone
        │
        └── MessageList (state !== 'idle')
            ├── Message[] (User messages)
            ├── ThinkingWidget ⭐
            │   └── Accordion
            │       └── ScrollArea
            │           └── Log Entry (8x animated)
            │               ├── Status Icon
            │               ├── Agent Badge
            │               ├── Timestamp
            │               └── Message
            │
            └── VerdictCard ⭐
                └── Card
                    ├── CardHeader
                    │   ├── Status Badge (PASS/FAIL)
                    │   ├── Title
                    │   └── Confidence Score
                    ├── CardContent
                    │   └── Findings Accordion
                    │       └── Finding Categories
                    │           └── Items List
                    └── CardFooter (CTA)
                        ├── Heading & Description
                        └── Action Buttons
                            ├── Generate Report
                            └── Decline

└── InputArea (Fixed Bottom)
    ├── File Upload Button
    ├── Text Input
    └── Send Button
```

## State Flow Diagram

```
┌─────────┐
│  IDLE   │ ◄──────────────────────────┐
└────┬────┘                             │
     │ uploadFile() or                  │
     │ startScenario()                  │
     ▼                                  │
┌───────────┐                           │
│ UPLOADING │ (500ms)                   │
└─────┬─────┘                           │
      │                                 │
      ▼                                 │
┌───────────┐                           │
│ THINKING  │ (~8s, sequential logs)   │
└─────┬─────┘                           │
      │                                 │
      ▼                                 │
┌───────────┐                           │
│  VERDICT  │ (show results + CTA)     │
└─────┬─────┘                           │
      │                                 │
      ├─── declineReport() ────┐        │
      │                        │        │
      └─── generateReport()    │        │
           │                   │        │
           ▼                   ▼        │
      ┌────────────┐      ┌──────────┐ │
      │ GENERATING │      │ COMPLETE │─┘
      └──────┬─────┘      └──────────┘
             │ (3s)
             │
             ▼
        ┌──────────┐
        │ COMPLETE │
        └──────────┘
```

## Data Flow

```
┌─────────────────┐
│  User Action    │
│  - Upload file  │
│  - Click chip   │
└────────┬────────┘
         │
         ▼
┌────────────────────────┐
│ useProcurementSimulation │
│ (State Machine Hook)     │
├──────────────────────────┤
│ • Manages state          │
│ • Triggers timers        │
│ • Generates logs         │
│ • Stores verdict         │
└────────┬───────────────┘
         │
         ├─── state ──────────────────┐
         │                            │
         ├─── thinkingLogs ───────┐   │
         │                        │   │
         ├─── verdictData ────┐   │   │
         │                    │   │   │
         └─── messages ────┐  │   │   │
                           │  │   │   │
         ┌─────────────────▼──▼───▼───▼──┐
         │      Page Components           │
         ├────────────────────────────────┤
         │ • Render based on state        │
         │ • Display logs as they appear  │
         │ • Show verdict when ready      │
         │ • Handle user interactions     │
         └────────────────────────────────┘
```

## Animation Timeline

### Thinking State (Total: ~8 seconds)

```
0s    ┌─────────────────────────┐
      │ State: THINKING         │
      │ Show: Empty ThinkingWidget
      └─────────────────────────┘

0.8s  ┌─────────────────────────┐
      │ Log 1: "Reading PDF..." │ ◄─── Fade in + Slide up
      └─────────────────────────┘

1.8s  ┌─────────────────────────┐
      │ Log 2: "Agent 1..."     │ ◄─── Stagger delay 0.3s
      └─────────────────────────┘

3.0s  ┌─────────────────────────┐
      │ Log 3: "Agent 2..."     │
      └─────────────────────────┘

4.2s  ┌─────────────────────────┐
      │ Log 4: "Agent 3..."     │
      └─────────────────────────┘

5.2s  ┌─────────────────────────┐
      │ Log 5: "Cross-validating..." │
      └─────────────────────────┘

6.1s  ┌─────────────────────────┐
      │ Log 6: "Computing..."   │
      └─────────────────────────┘

7.1s  ┌─────────────────────────┐
      │ Log 7: "Generating..."  │
      └─────────────────────────┘

7.9s  ┌─────────────────────────┐
      │ Log 8: "Complete."      │
      └─────────────────────────┘

8.4s  ┌─────────────────────────┐
      │ State: VERDICT          │
      │ Show: VerdictCard       │ ◄─── Spring animation
      └─────────────────────────┘
```

## File Responsibilities

### Core Logic
- `hooks/use-procurement-simulation.ts` - State management, timing, transitions
- `lib/simulation-data.ts` - Mock data, scenarios, timing constants
- `types/procurement.ts` - TypeScript interfaces

### Layout Components
- `components/procurement/chat-layout.tsx` - Main container, header
- `components/procurement/zero-state.tsx` - Landing page orchestrator
- `components/procurement/message-list.tsx` - Chat message container

### Interactive Components
- `components/procurement/starter-chips.tsx` - Quick action buttons
- `components/procurement/file-upload.tsx` - Drag & drop area
- `components/procurement/input-area.tsx` - Bottom input bar

### Display Components (The Stars)
- `components/procurement/thinking-widget.tsx` - Multi-agent logs viewer
- `components/procurement/verdict-card.tsx` - Results presentation

### UI Primitives (Shadcn/ui)
- `components/ui/button.tsx` - Buttons with variants
- `components/ui/card.tsx` - Card container
- `components/ui/accordion.tsx` - Collapsible sections
- `components/ui/badge.tsx` - Status indicators
- `components/ui/scroll-area.tsx` - Scrollable containers
- `components/ui/separator.tsx` - Divider lines
- `components/ui/sonner.tsx` - Toast notifications

## Key Design Patterns

### 1. Composition over Inheritance
Components are small, focused, and composed together.

### 2. Container/Presenter Pattern
- `page.tsx` - Container (logic)
- Components - Presenters (UI)

### 3. Custom Hooks for Logic
- `useProcurementSimulation` - Encapsulates all state logic
- Clean component code, reusable logic

### 4. Controlled Components
All form inputs and interactions are controlled by React state.

### 5. Optimistic UI Updates
State changes trigger immediate UI updates, then async operations.

### 6. Progressive Enhancement
Works without JavaScript for basic content, enhanced with interactions.

## Performance Optimizations

### 1. Code Splitting
- Next.js automatic route-based splitting
- Dynamic imports where beneficial

### 2. Lazy Animation Loading
- Framer Motion tree-shaken
- Only used variants are included

### 3. Memoization
- React hooks prevent unnecessary re-renders
- Callback functions memoized

### 4. Efficient Re-renders
- State updates batched
- Only affected components re-render

### 5. Asset Optimization
- Next.js automatic image optimization
- Font subsetting with next/font

## Styling Architecture

### 1. Utility-First (Tailwind)
- Rapid development
- Consistent spacing/colors
- Small bundle size (purged)

### 2. CSS Variables
- Theme colors in globals.css
- Easy theme switching
- Consistent across components

### 3. Component-Scoped Styles
- Tailwind classes in components
- No global style conflicts
- Easy to understand and modify

### 4. Custom Utility Classes
- `.gradient-bg` - Background gradients
- `.glassmorphism` - Backdrop blur effects
- `.floating-shadow` - Elevated cards
- `.smooth-transition` - Consistent animations

## Accessibility Features

### 1. Semantic HTML
- Proper heading hierarchy
- Meaningful element choices
- ARIA labels where needed

### 2. Keyboard Navigation
- Tab order logical
- Enter/Space activate buttons
- Accordion keyboard support

### 3. Focus Management
- Visible focus indicators
- Focus trap in modals (if added)
- Skip links (can be added)

### 4. Color Contrast
- WCAG AA compliant
- Status colors distinguishable
- Text readable on all backgrounds

### 5. Screen Reader Support
- Alt text on decorative elements
- ARIA live regions for toasts
- Descriptive button labels

## Testing Strategy (Future)

### Unit Tests
- `use-procurement-simulation.ts` - State transitions
- Utility functions in `lib/utils.ts`
- Mock data generators

### Component Tests
- Interactive elements (buttons, accordions)
- State-dependent rendering
- Animation triggers

### Integration Tests
- Full user flows
- State machine transitions
- File upload handling

### E2E Tests
- Complete scenarios
- Multi-device testing
- Performance benchmarks

## Deployment Checklist

- [x] Production build succeeds
- [x] No TypeScript errors
- [x] No console warnings
- [x] All animations smooth
- [x] Responsive on all devices
- [ ] Environment variables configured (when backend added)
- [ ] Analytics integrated (optional)
- [ ] Error tracking setup (optional)
- [ ] Performance monitoring (optional)

---

**Architecture Status**: Phase 1 Complete
**Scalability**: Ready for backend integration
**Maintainability**: High (well-organized, typed, documented)
