# Split-Screen View Feature

## Overview

The split-screen feature provides an immersive report viewing experience. When users click "Yes, Generate Report", the screen smoothly splits into two panels:

- **Left Panel (50%)**: Chat interface with conversation history
- **Right Panel (50%)**: Report preview with skeleton loading animation

## Visual Flow

```
┌─────────────────────────────┐
│                             │
│      Single View Mode       │
│      (Chat Interface)       │
│                             │
└─────────────────────────────┘
              │
              │ User clicks "Yes, Generate Report"
              ▼
┌──────────────┬──────────────┐
│              │              │
│    Chat      │   Report     │
│  Interface   │   Preview    │
│   (50%)      │   (50%)      │
│              │              │
└──────────────┴──────────────┘
```

## Components Created

### 1. Skeleton Component (`components/ui/skeleton.tsx`)
- Base skeleton loader with pulse animation
- Used as building block for complex loading states

### 2. ReportSkeleton Component (`components/procurement/report-skeleton.tsx`)
- **Shimmer Animation**: Smooth wave effect across placeholders
- Mimics the structure of the final report
- Multiple card skeletons for different sections:
  - Header section
  - Document information
  - Executive summary
  - Detailed findings (3 sections)
  - Recommendations
  - Chart placeholder

### 3. ReportPreview Component (`components/procurement/report-preview.tsx`)
Two states:

#### Loading State (`isLoading: true`)
- Shows header with "Generating Report" title
- Displays ReportSkeleton with shimmer animation
- Close button available (X icon)

#### Complete State (`isLoading: false`)
- Full report with actual data
- Sections:
  - **Header**: Title, status badge, date
  - **Document Info**: Analysis metadata
  - **Executive Summary**: High-level overview
  - **Detailed Findings**: Categorized findings with severity badges
  - **Recommendations**: Action items based on verdict
- Action buttons:
  - Download PDF (primary)
  - Close (X icon)

## Shimmer Animation

The signature shimmer effect is achieved with CSS:

```css
@keyframes shimmer {
  0% {
    background-position: -1000px 0;
  }
  100% {
    background-position: 1000px 0;
  }
}

.shimmer {
  animation: shimmer 2s infinite linear;
  background: linear-gradient(
    to right,
    hsl(var(--muted)) 0%,
    hsl(var(--muted) / 0.5) 50%,
    hsl(var(--muted)) 100%
  );
  background-size: 1000px 100%;
}
```

This creates a smooth, continuous wave that moves across skeleton elements, giving users visual feedback that content is being generated.

## Split-Screen Animation

The split is animated using Framer Motion:

```typescript
// Left panel (Chat)
<motion.div
  initial={{ width: '100%' }}
  animate={{ width: '50%' }}
  transition={{ duration: 0.5, ease: 'easeInOut' }}
>

// Right panel (Report)
<motion.div
  initial={{ width: 0, opacity: 0 }}
  animate={{ width: '50%', opacity: 1 }}
  transition={{ duration: 0.5, ease: 'easeInOut' }}
>
```

**Result**: Smooth 500ms transition where the chat compresses and the report slides in from the right.

## State Management

### New Hook Properties

Added to `useProcurementSimulation`:

```typescript
{
  showSplitView: boolean;        // Controls split-screen visibility
  closeSplitView: () => void;    // Closes the split view
}
```

### State Flow

1. User clicks "Yes, Generate Report"
2. `generateReport()` is called
3. `showSplitView` is set to `true`
4. State changes to `'generating'`
5. Page layout switches to split view
6. Right panel shows skeleton loading
7. After 3 seconds, state becomes `'complete'`
8. Report preview shows actual data
9. User can close with X button → `closeSplitView()`

## Layout Architecture

### Split View Mode
```typescript
<div className="h-screen flex overflow-hidden">
  <motion.div className="w-1/2">
    <ChatLayout>
      {/* Chat content */}
    </ChatLayout>
  </motion.div>

  <motion.div className="w-1/2">
    <ReportPreview />
  </motion.div>
</div>
```

### Single View Mode
```typescript
<div className="h-screen overflow-hidden">
  <ChatLayout>
    {/* Full width chat */}
  </ChatLayout>
</div>
```

## Key Features

### 1. Responsive Design
- Fixed 50/50 split on desktop
- Smooth transitions between states
- Proper overflow handling

### 2. Loading Experience
- Immediate visual feedback (skeleton appears instantly)
- Shimmer animation indicates progress
- User can close at any time

### 3. Report Content
- Professional layout with cards
- Color-coded severity badges
- Expandable sections for details
- Download button (simulated)

### 4. User Controls
- **Close (X) button**: Returns to single view
- **Download PDF button**: Simulates PDF download
- Maintains chat history on left

## User Experience Flow

1. **Initial State**: User sees verdict card with two buttons
2. **Click "Generate"**: Screen smoothly splits (500ms animation)
3. **Loading State**: Shimmer skeleton appears on right (3 seconds)
4. **Report Ready**: Skeleton fades out, actual report fades in
5. **Review**: User can scroll through report while chat remains visible
6. **Close**: Click X to return to single view

## Performance Considerations

- **Smooth Animations**: 60fps using GPU-accelerated transforms
- **Lazy Rendering**: Report only renders when needed
- **Efficient Updates**: Framer Motion handles layout calculations
- **No Layout Shifts**: Fixed heights prevent jank

## Accessibility

- Keyboard navigation supported
- Focus management when opening/closing
- ARIA labels on interactive elements
- High contrast for readability

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- CSS Grid and Flexbox support required
- Framer Motion compatible

## Future Enhancements

Potential improvements for Phase 2:

1. **Resizable Split**: Allow users to drag divider
2. **Mobile Responsive**: Stack panels vertically on mobile
3. **Multiple Reports**: Tabs for comparing multiple analyses
4. **Export Options**: CSV, JSON, Word formats
5. **Print Styling**: Optimized print layout
6. **Deep Linking**: Share specific report sections
7. **Real-time Updates**: Stream report sections as they generate

## Code Examples

### Using the Split View

```typescript
// In your component
const {
  showSplitView,
  generateReport,
  closeSplitView
} = useProcurementSimulation();

// Trigger split view
<Button onClick={generateReport}>
  Yes, Generate Report
</Button>

// Close split view
<Button onClick={closeSplitView}>
  Close Report
</Button>
```

### Customizing the Skeleton

Modify `components/procurement/report-skeleton.tsx`:

```typescript
// Add more skeleton sections
<Card>
  <CardHeader>
    <Skeleton className="h-6 w-1/3 shimmer" />
  </CardHeader>
  <CardContent className="space-y-3">
    <Skeleton className="h-4 w-full shimmer" />
    <Skeleton className="h-4 w-5/6 shimmer" />
  </CardContent>
</Card>
```

### Customizing the Report

Modify `components/procurement/report-preview.tsx` to add new sections, change layout, or adjust styling.

## Testing Checklist

- [x] Split animation is smooth (60fps)
- [x] Skeleton shimmer effect works
- [x] Report data displays correctly
- [x] Close button returns to single view
- [x] State persists during split
- [x] Overflow scrolling works on both sides
- [x] No layout shifts or jank
- [x] Keyboard navigation functional

## Known Limitations

1. **Fixed Split**: Currently 50/50, not adjustable
2. **Desktop Only**: Optimized for desktop, needs mobile adaptation
3. **Single Report**: Can only view one report at a time
4. **Simulated Data**: Report uses mock data (real data in Phase 2)

---

**Status**: Feature Complete ✅
**Animation Type**: Shimmer/Skeleton Loading
**Transition Duration**: 500ms
**Loading Duration**: 3 seconds (simulated)
