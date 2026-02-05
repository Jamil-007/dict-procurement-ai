# Quick Start Guide

## Get Running in 30 Seconds

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Try It Out

### Option 1: Quick Scenarios
Click any of the 4 starter chips:
- **Check TOR Compliance** - See a PASS verdict
- **Analyze Budget Risk** - See a FAIL verdict
- **Detect Liability Issues** - See a FAIL verdict
- **Validate Requirements** - See a PASS verdict

### Option 2: File Upload
1. Drag and drop any PDF file
2. Or click the upload area to browse
3. Watch the thinking process unfold
4. Review the verdict and findings

## What to Watch For

### The Showcase Features

**1. Thinking Widget** (The Star of the Show)
- Logs appear one by one (8 steps, ~8 seconds total)
- Pulsing blue/amber dot shows activity
- Agent badges are color-coded
- Click header to collapse/expand
- Timestamps update in real-time

**2. Verdict Card** (The Results)
- Large PASS/FAIL badge at top
- Confidence percentage (e.g., "94% confidence")
- Findings grouped by category
- Click categories to expand details
- CTA section at bottom with token cost

**3. Report Generation Flow**
- Click "Yes, Generate Report"
  - See loading animation
  - Toast notification appears
  - Download link appears after 3 seconds (simulated)
- Click "No, Save Tokens"
  - Flow completes immediately
  - Toast confirms token savings

## Expected Flow

1. **Zero State** (0s)
   - See welcome screen with chips and upload area

2. **Upload/Start** (0.5s)
   - Quick transition with toast notification

3. **Thinking** (~8s)
   - Watch logs appear sequentially
   - See pulsing indicator
   - Agent badges show who's "working"

4. **Verdict** (instant)
   - Results card slides in
   - All findings displayed
   - CTA buttons ready

5. **Generate** (optional, 3s)
   - Loading state on button
   - Simulated Gamma connection
   - Download link appears

## Keyboard Navigation

- **Tab** - Navigate between interactive elements
- **Enter/Space** - Activate buttons and accordions
- **Escape** - Close expanded accordions (native behavior)

## Mobile Testing

The app is fully responsive. Test on:
- iPhone viewport (390px)
- Tablet viewport (768px)
- Desktop viewport (1440px)

## Common Questions

**Q: Can I upload any PDF?**
A: Yes! The app accepts any PDF but uses mock analysis data.

**Q: Why does every upload show the same results?**
A: Phase 1 uses static mock data. Backend integration will provide real analysis.

**Q: Does the "Generate Report" button actually create a PDF?**
A: No, it's simulated. The Gamma integration comes in Phase 2.

**Q: How do I reset the flow?**
A: Refresh the page to return to zero state.

**Q: Can I customize the thinking logs?**
A: Yes! Edit `lib/simulation-data.ts` to change messages and timing.

## Performance

- Initial page load: ~100ms
- First contentful paint: <1s
- Interactive: <1.5s
- Build size: 160 kB (first load JS)

## Browser Requirements

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Troubleshooting

**Dev server won't start**
```bash
# Clear cache and reinstall
rm -rf node_modules .next
npm install
npm run dev
```

**Port 3000 already in use**
```bash
# Use a different port
PORT=3001 npm run dev
```

**Build fails**
```bash
# Check for TypeScript errors
npm run build
```

**Styles not loading**
```bash
# Rebuild Tailwind
npm run dev
# Hard refresh browser (Cmd+Shift+R)
```

## What's Next?

Once you've tested the prototype:
1. Review the code in `components/procurement/`
2. Check out `hooks/use-procurement-simulation.ts`
3. Customize `lib/simulation-data.ts`
4. Read `README.md` for full documentation
5. See `IMPLEMENTATION_SUMMARY.md` for technical details

## Development Mode Features

- Hot reload on file changes
- TypeScript error checking in real-time
- React DevTools support
- Source maps for debugging

## Production Build

```bash
# Test production build
npm run build
npm start

# Open http://localhost:3000
```

## Deploy to Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

---

**Status**: Ready to use! 🚀

The application is fully functional and ready for demonstration or further development.
