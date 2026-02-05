# Procurement AI System - Phase 1 Prototype

A frontend-only prototype that simulates a multi-agent AI workflow for procurement document analysis. This application showcases a modern AI interface with sophisticated "Thinking" state visualization using static data and timers.

## Features

- **Modern AI Interface**: Clean, minimalist design inspired by Zola and Prompt Kit
- **Multi-Agent Simulation**: Visual representation of AI agents analyzing procurement documents
- **Thinking Process Showcase**: Real-time log visualization with animated agent interactions
- **Verdict Display**: Comprehensive results with findings categorization and confidence scores
- **Interactive CTA**: Option to generate formal PDF reports via Gamma integration
- **Split-Screen View**: Immersive report generation with shimmer skeleton loading animation
  - Smooth 50/50 split transition when generating reports
  - Chat interface on left, report preview on right
  - Professional skeleton loading with animated shimmer effect
- **Responsive Design**: Fully responsive layout optimized for all screen sizes

## Tech Stack

- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Components**: Shadcn/ui
- **Icons**: Lucide React
- **Animation**: Framer Motion

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

1. Install dependencies:
```bash
npm install
```

2. Run the development server:
```bash
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000) in your browser.

## Usage

### Zero State

When you first open the application, you'll see:
- **Quick Action Chips**: Pre-configured scenarios for instant testing
  - Check TOR Compliance
  - Analyze Budget Risk
  - Detect Liability Issues
  - Validate Requirements
- **File Upload**: Drag and drop area for PDF procurement documents

### Analysis Flow

1. **Upload or Select Scenario**: Either upload a PDF or click a quick action chip
2. **Thinking Process**: Watch as AI agents analyze the document
   - Sequential log entries appear with agent badges
   - Pulsing indicator shows active processing
   - Collapsible accordion for detailed view
3. **Verdict Card**: Review analysis results
   - PASS/FAIL status badge
   - Confidence score
   - Categorized findings with severity levels
4. **Report Generation**: Choose to generate a formal PDF report
   - "Yes, Generate" - Simulates Gamma integration
   - "No, Save Tokens" - Complete without report

## Project Structure

```
procurement-ai/
├── app/
│   ├── layout.tsx          # Root layout with Inter font
│   ├── page.tsx            # Main chat interface
│   └── globals.css         # Global styles
├── components/
│   ├── ui/                 # Shadcn/ui components
│   └── procurement/        # Custom components
│       ├── chat-layout.tsx
│       ├── zero-state.tsx
│       ├── starter-chips.tsx
│       ├── file-upload.tsx
│       ├── thinking-widget.tsx  # ⭐ CRITICAL
│       ├── verdict-card.tsx     # ⭐ CRITICAL
│       ├── input-area.tsx
│       └── message-list.tsx
├── hooks/
│   └── use-procurement-simulation.ts  # State machine
├── lib/
│   ├── utils.ts            # Utilities
│   └── simulation-data.ts  # Mock data
└── types/
    └── procurement.ts      # TypeScript interfaces
```

## Key Components

### ThinkingWidget
The showcase component that displays the multi-agent thinking process:
- Sequential log appearance with stagger animations
- Agent-specific color coding
- Real-time timestamps
- Collapsible accordion interface
- Pulsing activity indicator

### VerdictCard
Results presentation component featuring:
- Prominent status badges (PASS/FAIL)
- Confidence scoring
- Categorized findings with severity levels
- Expandable details sections
- Call-to-action for report generation

## Customization

### Mock Data

Edit `lib/simulation-data.ts` to customize:
- Thinking log messages and timing
- Verdict scenarios (PASS/FAIL)
- Finding categories and items
- Starter chip scenarios

### Timing Constants

Adjust simulation timing in `lib/simulation-data.ts`:
```typescript
export const TIMING_CONSTANTS = {
  UPLOAD_TO_THINKING: 500,      // ms
  THINKING_TO_VERDICT: 500,     // ms
  GENERATING_DURATION: 3000,    // ms
  TOAST_DURATION: 3000,         // ms
};
```

### Styling

- **Theme Colors**: Modify CSS variables in `app/globals.css`
- **Component Styles**: Tailwind classes in component files
- **Animations**: Framer Motion variants in components

## State Machine

The application uses a finite state machine with these states:

1. **idle** - Zero state, ready for input
2. **uploading** - File being processed
3. **thinking** - Multi-agent simulation in progress
4. **verdict** - Results displayed
5. **generating** - Report generation simulation
6. **complete** - Final state

## Future Backend Integration

This prototype is designed for easy backend integration:

1. Replace `useProcurementSimulation` hook with API calls
2. Keep component structure identical
3. Stream thinking logs via Server-Sent Events (SSE)
4. Map verdict data directly to API response
5. Integrate real Gamma API for report generation

## Performance

- Framer Motion animations optimized for 60fps
- Efficient re-renders with React hooks
- Lazy loading for optimal bundle size
- Debounced file upload handlers

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

This project is proprietary and confidential.

## Development

### Build for Production

```bash
npm run build
npm start
```

### Linting

```bash
npm run lint
```

## Acknowledgments

Built with modern best practices for AI interfaces, inspired by leading AI applications like Claude and ChatGPT.
