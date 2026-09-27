import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

// Mock the hooks and components
vi.mock('@/hooks/use-procurement-analysis', () => ({
  useProcurementAnalysis: () => ({
    state: 'verdict',
    thinkingLogs: [],
    verdictData: null,
    messages: [],
    chatMessages: [],
    showSplitView: false,
    gammaLink: null,
    error: null,
    isConnected: false,
    isChatLoading: false,
    isChatInFlight: false,
    threadId: 'test-thread-123',
    uploadFiles: vi.fn(),
    generateReport: vi.fn(),
    declineReport: vi.fn(),
    sendChatMessage: vi.fn(),
    reset: vi.fn(),
  }),
}));

vi.mock('@/components/procurement/chat-layout', () => ({
  ChatLayout: ({ children }: any) => <div data-testid="chat-layout">{children}</div>,
}));

vi.mock('@/components/procurement/zero-state', () => ({
  ZeroState: () => <div data-testid="zero-state">Zero State</div>,
}));

vi.mock('@/components/procurement/message-list', () => ({
  MessageList: ({ children }: any) => <div data-testid="message-list">{children}</div>,
}));

vi.mock('@/components/procurement/input-area', () => ({
  InputArea: () => <div data-testid="input-area">Input Area</div>,
}));

vi.mock('@/components/procurement/form-generator', () => ({
  FormGenerator: () => <div data-testid="form-generator">Form Generator</div>,
}));

vi.mock('@/components/procurement/thinking-widget', () => ({
  ThinkingWidget: () => <div>Thinking Widget</div>,
}));

vi.mock('@/components/procurement/report-preview', () => ({
  ReportPreview: () => <div>Report Preview</div>,
}));

describe('Page Integration', () => {
  it('shows form generator when threadId exists and not in idle state', async () => {
    const ProcurementPage = (await import('@/app/page')).default;
    render(<ProcurementPage />);

    // FormGenerator should be present
    expect(screen.getByTestId('form-generator')).toBeInTheDocument();
  });
});
