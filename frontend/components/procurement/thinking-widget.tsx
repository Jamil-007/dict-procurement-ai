'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, Loader2 } from 'lucide-react';
import { ThinkingLog } from '@/types/procurement';
import { cn } from '@/lib/utils';

interface ThinkingWidgetProps {
  logs: ThinkingLog[];
  isComplete?: boolean;
}

// Agent display names
const AGENT_DISPLAY_NAMES: Record<string, string> = {
  'PDF Parser': 'Document Extraction',
  'Specification Validator': 'Specification Validation',
  'LCCA Analyzer': 'Cost Analysis',
  'Market Researcher': 'Market Research',
  'Sustainability Analyst': 'Sustainability Check',
  'Domestic Preference Checker': 'Tatak Pinoy Verification',
  'Modality Advisor': 'Compliance Review',
  'Report Compiler': 'Report Generation',
  'Gamma Generator': 'Final Processing',
};

interface AgentLaneData {
  agentName: string;
  displayName: string;
  status: 'pending' | 'active' | 'complete';
  message: string;
  timestamp?: number;
  firstSeenTimestamp: number;
}

// Looping typewriter with scale effect on new letters
const LoopingTypeWriter: React.FC<{ text: string; speed?: number }> = ({ text, speed = 50 }) => {
  const [displayedText, setDisplayedText] = React.useState('');
  const [currentIndex, setCurrentIndex] = React.useState(0);
  const [isDeleting, setIsDeleting] = React.useState(false);

  React.useEffect(() => {
    if (isDeleting) {
      if (displayedText.length === 0) {
        setIsDeleting(false);
        setCurrentIndex(0);
      } else {
        const timeout = setTimeout(() => {
          setDisplayedText(prev => prev.slice(0, -1));
        }, speed / 2);
        return () => clearTimeout(timeout);
      }
    } else {
      if (currentIndex < text.length) {
        const timeout = setTimeout(() => {
          setDisplayedText(prev => prev + text[currentIndex]);
          setCurrentIndex(prev => prev + 1);
        }, speed);
        return () => clearTimeout(timeout);
      } else {
        // Pause before deleting
        const timeout = setTimeout(() => {
          setIsDeleting(true);
        }, 1000);
        return () => clearTimeout(timeout);
      }
    }
  }, [currentIndex, text, speed, displayedText, isDeleting]);

  React.useEffect(() => {
    // Reset when text changes
    setDisplayedText('');
    setCurrentIndex(0);
    setIsDeleting(false);
  }, [text]);

  return (
    <span className="inline-flex">
      {displayedText.split('').map((char, index) => {
        const isLast = index === displayedText.length - 1;
        return (
          <motion.span
            key={`${index}-${char}`}
            initial={isLast && !isDeleting ? { scale: 1.3 } : { scale: 1 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.2 }}
            className="inline-block"
          >
            {char === ' ' ? '\u00A0' : char}
          </motion.span>
        );
      })}
    </span>
  );
};

// Static typewriter for completion messages (no loop)
const TypeWriter: React.FC<{ text: string; speed?: number }> = ({ text, speed = 50 }) => {
  const [displayedText, setDisplayedText] = React.useState('');
  const [currentIndex, setCurrentIndex] = React.useState(0);

  React.useEffect(() => {
    if (currentIndex < text.length) {
      const timeout = setTimeout(() => {
        setDisplayedText(prev => prev + text[currentIndex]);
        setCurrentIndex(prev => prev + 1);
      }, speed);

      return () => clearTimeout(timeout);
    }
  }, [currentIndex, text, speed]);

  React.useEffect(() => {
    // Reset when text changes
    setDisplayedText('');
    setCurrentIndex(0);
  }, [text]);

  return (
    <span className="inline-flex">
      {displayedText.split('').map((char, index) => {
        const isLast = index === displayedText.length - 1;
        return (
          <motion.span
            key={`${index}-${char}`}
            initial={isLast ? { scale: 1.3 } : { scale: 1 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.2 }}
            className="inline-block"
          >
            {char === ' ' ? '\u00A0' : char}
          </motion.span>
        );
      })}
    </span>
  );
};

// Animated dots component
const AnimatedDots: React.FC = () => {
  const [dots, setDots] = React.useState('');

  React.useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => {
        if (prev === '...') return '';
        return prev + '.';
      });
    }, 500);

    return () => clearInterval(interval);
  }, []);

  return <span>{dots}</span>;
};

export function ThinkingWidget({ logs, isComplete }: ThinkingWidgetProps) {
  // Build sequential list of agents as they appear in logs
  const sequentialAgents = React.useMemo(() => {
    const agentOrder: string[] = [];
    const agentData: Record<string, AgentLaneData> = {};

    logs.forEach((log, index) => {
      const isLastLog = index === logs.length - 1;

      if (!agentData[log.agent]) {
        // First time seeing this agent
        agentOrder.push(log.agent);

        let initialStatus: 'pending' | 'active' | 'complete' = 'active';

        if (isComplete) {
          initialStatus = 'complete';
        } else if (!isLastLog) {
          initialStatus = 'complete';
        }

        agentData[log.agent] = {
          agentName: log.agent,
          displayName: AGENT_DISPLAY_NAMES[log.agent] || log.agent,
          status: initialStatus,
          message: log.message,
          timestamp: log.timestamp,
          firstSeenTimestamp: log.timestamp
        };
      } else {
        // Update existing agent
        const currentAgent = agentData[log.agent];
        currentAgent.message = log.message;
        currentAgent.timestamp = log.timestamp;

        if (isComplete) {
          currentAgent.status = 'complete';
        } else if (!isLastLog) {
          currentAgent.status = 'complete';
        } else {
          currentAgent.status = 'active';
        }
      }
    });

    return agentOrder.map(agentName => agentData[agentName]);
  }, [logs, isComplete]);

  const cardVariants = {
    hidden: {
      opacity: 0,
      y: 20,
    },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        type: "spring" as const,
        stiffness: 260,
        damping: 20
      }
    }
  };

  const renderAgentCard = (lane: AgentLaneData) => {
    return (
      <motion.div
        key={lane.agentName}
        variants={cardVariants}
        initial="hidden"
        animate="show"
        className={cn(
          "relative bg-white rounded-lg border-2 p-4 transition-all duration-300",
          lane.status === 'complete' && 'border-gray-200',
          lane.status === 'active' && 'border-black'
        )}
      >
        <div className="flex items-center gap-3">
          {/* Status Icon */}
          <div className="flex-shrink-0">
            {lane.status === 'complete' ? (
              <CheckCircle className="h-6 w-6 text-black" />
            ) : (
              <Loader2 className="h-6 w-6 text-black animate-spin" />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <h3 className={cn(
              "text-sm font-semibold mb-1",
              lane.status === 'complete' && 'text-gray-700',
              lane.status === 'active' && 'text-black'
            )}>
              {lane.status === 'active' ? (
                <LoopingTypeWriter text={lane.displayName} speed={40} />
              ) : (
                lane.displayName
              )}
            </h3>
            <p className="text-xs text-gray-500">
              {lane.status === 'active' ? (
                <>
                  Processing<AnimatedDots />
                </>
              ) : (
                <TypeWriter text={lane.message} speed={15} />
              )}
            </p>
          </div>
        </div>
      </motion.div>
    );
  };

  if (sequentialAgents.length === 0) {
    return null;
  }

  return (
    <div className="w-full space-y-3">
      <AnimatePresence mode="popLayout">
        {sequentialAgents.map((agent) => renderAgentCard(agent))}
      </AnimatePresence>
    </div>
  );
}
