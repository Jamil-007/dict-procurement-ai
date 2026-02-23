'use client';

import { useProcurementAnalysis } from '@/hooks/use-procurement-analysis';
import { ChatLayout } from '@/components/procurement/chat-layout';
import { ZeroState } from '@/components/procurement/zero-state';
import { MessageList } from '@/components/procurement/message-list';
import { ThinkingWidget } from '@/components/procurement/thinking-widget';
import { InputArea } from '@/components/procurement/input-area';
import { ReportPreview } from '@/components/procurement/report-preview';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Message } from '@/types/procurement';
import { AlertTriangle } from 'lucide-react';

const MAX_FILES = 3;

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
    isChatInFlight,
    uploadFiles,
    generateReport,
    declineReport,
    sendChatMessage,
    reset,
  } = useProcurementAnalysis();

  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [showReportCTA, setShowReportCTA] = useState(true);
  const [showChat, setShowChat] = useState(false);
  const [showFileLimitModal, setShowFileLimitModal] = useState(false);
  const [isGeneratingActionItems, setIsGeneratingActionItems] = useState(false);

  const handleFilesSelect = useCallback((newFiles: File[]) => {
    setPendingFiles((prev) => {
      const merged = [...prev, ...newFiles];
      if (merged.length > MAX_FILES) {
        setShowFileLimitModal(true);
      }
      return merged.slice(0, MAX_FILES);
    });
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
      console.log('[handleSend] Uploading files');
      uploadFiles(pendingFiles);
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
  }, [pendingFiles, uploadFiles, state, handleChatMessage]);

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

  const handleGenerateReport = async () => {
    setShowReportCTA(false);
    setShowChat(true);
    setIsGeneratingActionItems(true);
    
    try {
      // Show immediate feedback
      toast.info('Preparing action items...', { duration: 2000 });
      
      // Decline Gamma generation and request action items via chat
      await declineReport();
      
      // Get HIGH severity findings
      const highSeverityFindings = verdictData?.findings.filter(f => f.severity === 'high') || [];
      
      // Build action items request message
      let actionItemsQuery = 'Based on the analysis, please provide concise action items to fix the HIGH severity issues found in the procurement document.';
      
      if (highSeverityFindings.length > 0) {
        const categories = highSeverityFindings.map(f => f.category).join(', ');
        actionItemsQuery += ` Focus on: ${categories}.`;
      }
      
      actionItemsQuery += ' For each HIGH severity issue, provide: 1) What needs to be fixed, 2) How to fix it, and 3) The specific section or requirement to reference.';
      
      // Automatically send the action items request
      toast.success('Action items request sent. AI is analyzing...', { duration: 3000 });
      await handleChatMessage(actionItemsQuery);
    } finally {
      setIsGeneratingActionItems(false);
    }
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
                onFilesSelect={handleFilesSelect}
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
              onFilesSelect={handleFilesSelect}
              onRemoveFile={handleRemoveFile}
              onSend={handleSend}
              selectedFiles={pendingFiles}
              disabled={state === 'thinking' || state === 'uploading' || isChatInFlight}
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
            {showFileLimitModal && (
              <div
                className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
                onClick={() => setShowFileLimitModal(false)}
              >
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.2 }}
                  onClick={(e) => e.stopPropagation()}
                  className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl"
                >
                  <div className="flex flex-col items-center text-center space-y-4">
                    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
                      <AlertTriangle className="h-8 w-8 text-black" />
                    </div>
                    <h3 className="text-2xl font-bold text-black">Document limit reached</h3>
                    <p className="text-gray-600">
                      This version can only process up to 3 documents. More document support will
                      follow in the next update.
                    </p>
                    <div className="w-full pt-2">
                      <Button
                        onClick={() => setShowFileLimitModal(false)}
                        className="w-full bg-black hover:bg-gray-800 text-white rounded-full"
                        size="lg"
                      >
                        Okay
                      </Button>
                    </div>
                  </div>
                </motion.div>
              </div>
            )}
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
            isGenerating={state === 'generating' || isGeneratingActionItems || (!showReportCTA && isChatLoading)}
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
            onFilesSelect={handleFilesSelect}
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
          onFilesSelect={handleFilesSelect}
          onRemoveFile={handleRemoveFile}
          onSend={handleSend}
          selectedFiles={pendingFiles}
          disabled={state === 'thinking' || state === 'uploading' || isChatInFlight}
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
      {showFileLimitModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setShowFileLimitModal(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl"
          >
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
                <AlertTriangle className="h-8 w-8 text-black" />
              </div>
              <h3 className="text-2xl font-bold text-black">Document limit reached</h3>
              <p className="text-gray-600">
                This version can only process up to 3 documents. More document support will follow
                in the next update.
              </p>
              <div className="w-full pt-2">
                <Button
                  onClick={() => setShowFileLimitModal(false)}
                  className="w-full bg-black hover:bg-gray-800 text-white rounded-full"
                  size="lg"
                >
                  Okay
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
