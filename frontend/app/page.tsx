'use client';

import { useProcurementAnalysis } from '@/hooks/use-procurement-analysis';
import { ChatLayout } from '@/components/procurement/chat-layout';
import { ZeroState } from '@/components/procurement/zero-state';
import { MessageList } from '@/components/procurement/message-list';
import { ThinkingWidget } from '@/components/procurement/thinking-widget';
import { InputArea } from '@/components/procurement/input-area';
import { ReportPreview } from '@/components/procurement/report-preview';
import { toast } from 'sonner';
import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Message } from '@/types/procurement';

export default function ProcurementPage() {
  const {
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
    reset,
  } = useProcurementAnalysis();

  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [showReportCTA, setShowReportCTA] = useState(true);
  const [showChat, setShowChat] = useState(false);

  const handleFileSelect = useCallback((file: File) => {
    setPendingFiles(prev => [...prev, file]);
  }, []);

  const handleRemoveFile = useCallback((index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleChatMessage = useCallback(async (message: string) => {
    console.log('[handleChatMessage] Called with:', message);
    await sendChatMessage(message);
  }, [sendChatMessage]);

  const handleSend = useCallback((message: string) => {
    console.log('[handleSend] Called with message:', message);
    console.log('[handleSend] Pending files:', pendingFiles.length);
    console.log('[handleSend] Current state:', state);
    console.log('[handleSend] Message trimmed:', message.trim());

    if (pendingFiles.length > 0) {
      console.log('[handleSend] Uploading file');
      // Upload the first file
      uploadFile(pendingFiles[0]);
      setPendingFiles([]);
      setShowReportCTA(true); // Reset CTA for new analysis
    } else if ((state === 'verdict' || state === 'generating' || state === 'complete') && message.trim()) {
      console.log('[handleSend] Sending chat message');
      // Send chat message if analysis is complete or verdict is shown
      handleChatMessage(message);
    } else if (state === 'idle' && message.trim()) {
      console.log('[handleSend] Idle state - showing upload reminder');
      // User tried to chat without uploading a document
      toast.info('Please upload a procurement PDF document first to start analysis', {
        description: 'Click the paperclip icon or drop a file to begin',
        duration: 4000,
      });
    } else {
      console.log('[handleSend] No action taken - state or message invalid');
    }
  }, [pendingFiles, uploadFile, state, handleChatMessage]);

  // Show toast notifications based on state changes
  useEffect(() => {
    if (state === 'uploading') {
      toast.info('Uploading document...');
    } else if (state === 'thinking') {
      toast.info('Analyzing document...');
    } else if (state === 'verdict') {
      toast.success('Analysis complete!');
    } else if (state === 'generating') {
      toast.info('Connecting to Gamma...');
    } else if (state === 'complete') {
      toast.success('Process complete!');
    }
  }, [state]);

  // Show error notifications
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  // Debug state changes
  useEffect(() => {
    console.log('[State Change] New state:', state);
  }, [state]);

  // Debug messages changes
  useEffect(() => {
    console.log('[Messages Change] New messages count:', messages.length);
    if (messages.length > 0) {
      console.log('[Messages Change] Latest message:', messages[messages.length - 1]);
    }
  }, [messages]);

  // Debug chat messages changes
  useEffect(() => {
    console.log('[Chat Messages Change] New chat messages count:', chatMessages.length);
    if (chatMessages.length > 0) {
      console.log('[Chat Messages Change] Latest:', chatMessages[chatMessages.length - 1]);
    }
  }, [chatMessages]);

  const handleGenerateReport = () => {
    setShowReportCTA(false);
    setShowChat(true); // Also enable chat after report generation
    generateReport();
  };

  const handleDeclineReport = () => {
    setShowReportCTA(false);
    setShowChat(true);
    declineReport();
    toast.info('Tokens saved. You can now chat about the document.');
  };

  // Split view layout
  if (showSplitView) {
    return (
      <div className="h-screen flex overflow-hidden">
        {/* Left side - Chat */}
        <motion.div
          initial={{ width: '100%' }}
          animate={{ width: '50%' }}
          transition={{ duration: 0.5, ease: 'easeInOut' }}
          className="border-r border-border h-full overflow-hidden"
        >
          <ChatLayout>
            {state === 'idle' && (
              <ZeroState
                onFileSelect={handleFileSelect}
                onScenarioSelect={() => {}}
              />
            )}

            {state !== 'idle' && (
              <MessageList
                messages={messages}
                chatMessages={chatMessages.map(cm => ({
                  id: cm.id,
                  type: cm.role === 'user' ? 'user' : 'ai',
                  content: cm.content,
                  timestamp: cm.timestamp
                }))}
                isChatLoading={isChatLoading}
              />
            )}

            <InputArea
              onFileSelect={handleFileSelect}
              onRemoveFile={handleRemoveFile}
              onSend={handleSend}
              selectedFiles={pendingFiles}
              disabled={state === 'thinking' || state === 'uploading'}
              isSplitView={true}
              fileOnly={state === 'idle'}
              placeholder={
                state === 'idle'
                  ? 'Upload a PDF to start analysis...'
                  : (state === 'verdict' || state === 'generating' || state === 'complete')
                  ? 'Ask about the analyzed document...'
                  : 'Ask about procurement documents...'
              }
            />
          </ChatLayout>
        </motion.div>

        {/* Right side - Report Preview */}
        <motion.div
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: '50%', opacity: 1 }}
          transition={{ duration: 0.5, ease: 'easeInOut' }}
          className="h-full overflow-hidden"
        >
          <ReportPreview
            isLoading={state === 'generating'}
            verdictData={verdictData}
            gammaLink={gammaLink}
            onGenerateReport={handleGenerateReport}
            onDeclineReport={handleDeclineReport}
            isGenerating={state === 'generating'}
            showCTA={showReportCTA}
            onReset={reset}
          />
        </motion.div>
      </div>
    );
  }

  // Normal single view layout
  return (
    <div className="h-screen overflow-hidden">
      <ChatLayout>
        {state === 'idle' && (
          <ZeroState
            onFileSelect={handleFileSelect}
            onScenarioSelect={() => {}}
          />
        )}

        {state !== 'idle' && (
          <MessageList
            messages={messages}
            chatMessages={chatMessages.map(cm => ({
              id: cm.id,
              type: cm.role === 'user' ? 'user' : 'ai',
              content: cm.content,
              timestamp: cm.timestamp
            }))}
            isChatLoading={isChatLoading}
          >
            {state === 'thinking' && thinkingLogs.length > 0 && (
              <ThinkingWidget
                logs={thinkingLogs}
                isComplete={state !== 'thinking'}
              />
            )}
          </MessageList>
        )}

        <InputArea
          onFileSelect={handleFileSelect}
          onRemoveFile={handleRemoveFile}
          onSend={handleSend}
          selectedFiles={pendingFiles}
          disabled={state === 'thinking' || state === 'uploading'}
          isSplitView={false}
          fileOnly={state === 'idle'}
          placeholder={
            state === 'idle'
              ? 'Upload a PDF to start analysis...'
              : (state === 'verdict' || state === 'generating' || state === 'complete')
              ? 'Ask about the analyzed document...'
              : 'Ask about procurement documents...'
          }
        />
      </ChatLayout>
    </div>
  );
}
