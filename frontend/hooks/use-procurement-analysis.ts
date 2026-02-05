import { useState, useCallback, useRef, useEffect } from 'react';
import {
  SimulationState,
  ThinkingLog,
  VerdictData,
  Message,
  ChatMessage,
} from '@/types/procurement';
import { apiClient } from '@/lib/api-client';

export interface UseProcurementAnalysisReturn {
  state: SimulationState;
  thinkingLogs: ThinkingLog[];
  verdictData: VerdictData | null;
  messages: Message[];
  chatMessages: ChatMessage[];
  showSplitView: boolean;
  gammaLink: string | null;
  error: string | null;
  isConnected: boolean;
  isChatLoading: boolean;
  uploadFile: (file: File) => void;
  generateReport: () => void;
  declineReport: () => void;
  sendChatMessage: (message: string) => Promise<void>;
  closeSplitView: () => void;
  reset: () => void;
}

export function useProcurementAnalysis(): UseProcurementAnalysisReturn {
  const [state, setState] = useState<SimulationState>('idle');
  const [thinkingLogs, setThinkingLogs] = useState<ThinkingLog[]>([]);
  const [verdictData, setVerdictData] = useState<VerdictData | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [showSplitView, setShowSplitView] = useState(false);
  const [gammaLink, setGammaLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isChatLoading, setIsChatLoading] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const threadIdRef = useRef<string | null>(null);

  // Cleanup function for EventSource
  const closeEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    }
  }, []);

  // Reset function
  const reset = useCallback(() => {
    closeEventSource();
    setState('idle');
    setThinkingLogs([]);
    setVerdictData(null);
    setMessages([]);
    setChatMessages([]);
    setShowSplitView(false);
    setGammaLink(null);
    setError(null);
    threadIdRef.current = null;
  }, [closeEventSource]);

  // Upload file handler
  const uploadFile = useCallback(async (file: File) => {
    try {
      setError(null);

      // Add user message
      const userMessage: Message = {
        id: `msg-${Date.now()}-user`,
        type: 'user',
        content: 'Please analyze this procurement document',
        fileName: file.name,
        timestamp: Date.now(),
      };
      setMessages([userMessage]);

      // Transition to uploading
      setState('uploading');

      // Upload the file
      const response = await apiClient.uploadDocument(file);
      threadIdRef.current = response.thread_id;

      // Transition to thinking
      setState('thinking');

      // Connect to SSE stream
      const eventSource = apiClient.connectToStream(response.thread_id, {
        onThinkingLog: (log) => {
          console.log('[SSE] Received thinking log:', log);

          const thinkingLog: ThinkingLog = {
            id: log.id,
            agent: log.agent,
            message: log.message,
            timestamp: log.timestamp,
            status: log.status,
          };

          setThinkingLogs((prev) => {
            // Check if this exact log ID already exists
            if (prev.some((l) => l.id === log.id)) {
              console.log('[SSE] Duplicate log ID, skipping:', log.id);
              return prev;
            }

            // Always append new logs - let ThinkingWidget determine status display
            console.log('[SSE] Adding new log:', {
              agent: log.agent,
              status: log.status,
              message: log.message,
              totalLogs: prev.length + 1
            });
            return [...prev, thinkingLog];
          });
        },
        onVerdict: (verdict) => {
          setVerdictData(verdict);
          setState('verdict');
        },
        onComplete: () => {
          closeEventSource();
        },
        onGammaLink: (link) => {
          setGammaLink(link);
        },
        onError: (errorMsg) => {
          setError(errorMsg);
          setState('idle');
          closeEventSource();
        },
      });

      eventSourceRef.current = eventSource;
      setIsConnected(true);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
      setState('idle');
    }
  }, [closeEventSource]);

  // Generate report handler
  const generateReport = useCallback(async () => {
    if (!threadIdRef.current) {
      setError('No analysis session found');
      return;
    }

    try {
      setState('generating');
      setShowSplitView(true);

      const response = await apiClient.submitReview(threadIdRef.current, true);

      if (response.gamma_link) {
        setGammaLink(response.gamma_link);
      }

      setState('complete');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to generate report';
      setError(errorMessage);
      setState('verdict');
    }
  }, []);

  // Decline report handler
  const declineReport = useCallback(async () => {
    if (!threadIdRef.current) {
      setError('No analysis session found');
      return;
    }

    try {
      await apiClient.submitReview(threadIdRef.current, false);
      setState('complete');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to submit review';
      setError(errorMessage);
    }
  }, []);

  // Send chat message handler
  const sendChatMessage = useCallback(async (message: string) => {
    console.log('[sendChatMessage] Called with message:', message);
    console.log('[sendChatMessage] Thread ID:', threadIdRef.current);

    if (!threadIdRef.current) {
      setError('No analysis session found');
      console.error('[sendChatMessage] No thread ID found');
      return;
    }

    try {
      // Add user message to chat messages
      const userChatMessage: ChatMessage = {
        id: `chat-${Date.now()}-user`,
        role: 'user',
        content: message,
        timestamp: Date.now(),
      };
      console.log('[sendChatMessage] Adding user chat message:', userChatMessage);
      setChatMessages((prev) => [...prev, userChatMessage]);

      // Set loading state
      setIsChatLoading(true);

      // Send to backend
      console.log('[sendChatMessage] Sending to backend...');
      const response = await apiClient.sendChatMessage(threadIdRef.current, message);
      console.log('[sendChatMessage] Backend response:', response);

      // Add AI response to chat messages
      const aiChatMessage: ChatMessage = {
        id: `chat-${Date.now()}-ai`,
        role: 'assistant',
        content: response.response,
        timestamp: Date.now(),
      };
      console.log('[sendChatMessage] Adding AI chat message:', aiChatMessage);
      setChatMessages((prev) => [...prev, aiChatMessage]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      console.error('[sendChatMessage] Error:', err);
      setError(errorMessage);
    } finally {
      setIsChatLoading(false);
    }
  }, []);

  // Close split view handler
  const closeSplitView = useCallback(() => {
    setShowSplitView(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeEventSource();
    };
  }, [closeEventSource]);

  return {
    state,
    thinkingLogs,
    verdictData,
    messages,
    chatMessages,
    showSplitView,
    gammaLink,
    error,
    isConnected,
    isChatLoading,
    uploadFile,
    generateReport,
    declineReport,
    sendChatMessage,
    closeSplitView,
    reset,
  };
}
