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
  isChatInFlight: boolean;
  uploadFiles: (files: File[]) => Promise<void>;
  generateReport: () => Promise<void>;
  declineReport: () => Promise<void>;
  sendChatMessage: (message: string) => Promise<void>;
  closeSplitView: () => void;
  reset: () => void;
}

function buildVerdictIntroMessage(verdict: VerdictData): string {
  const topCategories = verdict.findings
    .slice(0, 2)
    .map((finding) => finding.category)
    .filter(Boolean);

  const categoryText = topCategories.length
    ? `Key risk areas: ${topCategories.join(' and ')}.`
    : 'I can walk you through the key findings.';

  return `Analysis complete: ${verdict.status} with ${verdict.confidence}% confidence. ${categoryText} Which part should we review first?`;
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
  const [isChatInFlight, setIsChatInFlight] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const threadIdRef = useRef<string | null>(null);
  const chatAbortControllerRef = useRef<AbortController | null>(null);
  const activeChatMessageIdRef = useRef<string | null>(null);

  // Cleanup function for EventSource
  const closeEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    }
  }, []);

  const closeChatStream = useCallback(() => {
    if (chatAbortControllerRef.current) {
      chatAbortControllerRef.current.abort();
      chatAbortControllerRef.current = null;
    }
    activeChatMessageIdRef.current = null;
    setIsChatLoading(false);
    setIsChatInFlight(false);
  }, []);

  // Reset function
  const reset = useCallback(() => {
    closeEventSource();
    closeChatStream();
    setState('idle');
    setThinkingLogs([]);
    setVerdictData(null);
    setMessages([]);
    setChatMessages([]);
    setShowSplitView(false);
    setGammaLink(null);
    setError(null);
    threadIdRef.current = null;
  }, [closeEventSource, closeChatStream]);

  // Upload file handler
  const uploadFiles = useCallback(async (files: File[]) => {
    try {
      setError(null);

      if (!files.length) {
        setError('No PDF files selected');
        return;
      }

      const firstFile = files[0];
      const hasMore = files.length > 1;

      // Add user message
      const userMessage: Message = {
        id: `msg-${Date.now()}-user`,
        type: 'user',
        content: hasMore
          ? `Please analyze these procurement documents (${files.length} files)`
          : 'Please analyze this procurement document',
        fileName: hasMore ? `${firstFile.name} +${files.length - 1} more` : firstFile.name,
        timestamp: Date.now(),
      };
      setMessages([userMessage]);

      // Transition to uploading
      setState('uploading');

      // Upload the files
      const response = await apiClient.uploadDocuments(files);
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
          setShowSplitView(true);
          setChatMessages((prev) => {
            const introMessage: ChatMessage = {
              id: `chat-${Date.now()}-verdict-intro`,
              role: 'assistant',
              content: buildVerdictIntroMessage(verdict),
              timestamp: Date.now(),
            };
            return [...prev, introMessage];
          });
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

    if (isChatInFlight) {
      return;
    }

    try {
      setError(null);

      // Add user message to chat messages
      const userChatMessage: ChatMessage = {
        id: `chat-${Date.now()}-user`,
        role: 'user',
        content: message,
        timestamp: Date.now(),
      };
      console.log('[sendChatMessage] Adding user chat message:', userChatMessage);
      setChatMessages((prev) => [...prev, userChatMessage]);

      setIsChatLoading(true);
      setIsChatInFlight(true);
      const abortController = new AbortController();
      chatAbortControllerRef.current = abortController;
      let streamFinished = false;

      console.log('[sendChatMessage] Streaming from backend...');
      await apiClient.sendChatMessageStream(
        threadIdRef.current,
        message,
        {
          onStart: ({ message_id, timestamp }) => {
            activeChatMessageIdRef.current = message_id;
          },
          onDelta: ({ message_id, delta }) => {
            if (activeChatMessageIdRef.current !== message_id) {
              return;
            }

            setChatMessages((prev) => {
              const messageExists = prev.some((chatMessage) => chatMessage.id === message_id);

              if (!messageExists) {
                if (!delta.trim()) {
                  return prev;
                }
                setIsChatLoading(false);
                return [
                  ...prev,
                  {
                    id: message_id,
                    role: 'assistant',
                    content: delta,
                    timestamp: Date.now(),
                  },
                ];
              }

              setIsChatLoading(false);
              return prev.map((chatMessage) =>
                chatMessage.id === message_id
                  ? { ...chatMessage, content: `${chatMessage.content}${delta}` }
                  : chatMessage
              );
            });
          },
          onComplete: ({ message_id, response, timestamp }) => {
            if (activeChatMessageIdRef.current !== message_id) {
              return;
            }

            setChatMessages((prev) => {
              const messageExists = prev.some((chatMessage) => chatMessage.id === message_id);

              if (!messageExists) {
                return [
                  ...prev,
                  {
                    id: message_id,
                    role: 'assistant',
                    content: response,
                    timestamp,
                  },
                ];
              }

              return prev.map((chatMessage) =>
                chatMessage.id === message_id
                  ? { ...chatMessage, content: response, timestamp }
                  : chatMessage
              );
            });

            streamFinished = true;
            activeChatMessageIdRef.current = null;
            setIsChatLoading(false);
            setIsChatInFlight(false);
          },
          onError: (errorMsg) => {
            streamFinished = true;
            setError(errorMsg);
            activeChatMessageIdRef.current = null;
            setIsChatLoading(false);
            setIsChatInFlight(false);
          },
        },
        abortController.signal
      );

      if (!streamFinished) {
        activeChatMessageIdRef.current = null;
        setIsChatLoading(false);
        setIsChatInFlight(false);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      console.error('[sendChatMessage] Error:', err);
      setError(errorMessage);
      setIsChatLoading(false);
      setIsChatInFlight(false);
      activeChatMessageIdRef.current = null;
    } finally {
      chatAbortControllerRef.current = null;
    }
  }, [isChatInFlight]);

  // Close split view handler
  const closeSplitView = useCallback(() => {
    setShowSplitView(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeEventSource();
      closeChatStream();
    };
  }, [closeEventSource, closeChatStream]);

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
    isChatInFlight,
    uploadFiles,
    generateReport,
    declineReport,
    sendChatMessage,
    closeSplitView,
    reset,
  };
}
