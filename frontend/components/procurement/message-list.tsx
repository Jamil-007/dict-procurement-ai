'use client';

import React from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { FileText, User, Bot } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Message } from '@/types/procurement';
import { cn } from '@/lib/utils';

interface MessageListProps {
  messages: Message[];
  chatMessages?: Message[];
  children?: React.ReactNode;
  isChatLoading?: boolean;
}

const messageVariants = {
  hidden: { opacity: 0, y: 10 },
  show: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
    },
  },
};

// Enhanced markdown formatter for AI messages
const formatMarkdown = (text: string) => {
  if (!text) return [];

  const lines = text.split('\n');
  const elements: JSX.Element[] = [];

  const processBold = (text: string) => {
    // Clean up multiple asterisks (e.g., **text:** ** -> **text:**)
    const cleanedText = text.replace(/\*\*([^*]+):\*\*\s*\*\*/g, '**$1:**');
    const parts = cleanedText.split(/(\*\*[^*]+\*\*)/g);
    
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
      }
      return part ? <span key={i}>{part}</span> : null;
    });
  };

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();

    // Headers
    if (trimmedLine.startsWith('### ')) {
      const headerText = trimmedLine.substring(4);
      elements.push(
        <h3 key={index} className="text-lg font-bold mt-4 mb-2 break-words">
          {processBold(headerText)}
        </h3>
      );
    } else if (trimmedLine.startsWith('## ')) {
      const headerText = trimmedLine.substring(3);
      elements.push(
        <h2 key={index} className="text-xl font-bold mt-4 mb-2 break-words">
          {processBold(headerText)}
        </h2>
      );
    } else if (trimmedLine.startsWith('# ')) {
      const headerText = trimmedLine.substring(2);
      elements.push(
        <h1 key={index} className="text-2xl font-bold mt-4 mb-2 break-words">
          {processBold(headerText)}
        </h1>
      );
    }
    // Bullet points
    else if (trimmedLine.startsWith('*') && !trimmedLine.startsWith('**')) {
      const bulletText = trimmedLine.substring(1).trim();
      elements.push(
        <div key={index} className="flex gap-2 ml-2 mb-1.5">
          <span className="text-gray-600 mt-0.5 shrink-0">•</span>
          <span className="flex-1 break-words">{processBold(bulletText)}</span>
        </div>
      );
    } else if (trimmedLine.startsWith('-') && !trimmedLine.startsWith('--')) {
      const bulletText = trimmedLine.substring(1).trim();
      elements.push(
        <div key={index} className="flex gap-2 ml-2 mb-1.5">
          <span className="text-gray-600 mt-0.5 shrink-0">•</span>
          <span className="flex-1 break-words">{processBold(bulletText)}</span>
        </div>
      );
    }
    // Regular text
    else if (trimmedLine) {
      elements.push(
        <p key={index} className="mb-2 leading-relaxed break-words">
          {processBold(trimmedLine)}
        </p>
      );
    }
    // Empty lines
    else if (index < lines.length - 1) {
      elements.push(<div key={index} className="h-1" />);
    }
  });

  return elements;
};

// Looping typewriter component for loading state
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
        const timeout = setTimeout(() => {
          setIsDeleting(true);
        }, 1000);
        return () => clearTimeout(timeout);
      }
    }
  }, [currentIndex, text, speed, displayedText, isDeleting]);

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

export function MessageList({ messages, chatMessages = [], children, isChatLoading = false }: MessageListProps) {
  const renderMessage = (message: Message) => (
    <motion.div
      key={message.id}
      variants={messageVariants}
      initial="hidden"
      animate="show"
      className={cn(
        'flex gap-3 items-start',
        message.type === 'user' ? 'justify-end' : 'flex-row'
      )}
    >
      {/* Avatar - only show for AI messages */}
      {message.type !== 'user' && (
        <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-white overflow-hidden">
          <Image
            src="/dict-logo.png"
            alt="DICT Logo"
            width={32}
            height={32}
            className="object-contain"
          />
        </div>
      )}

      {/* Message Content */}
      <div
        className={cn(
          'flex flex-col space-y-1',
          message.type === 'user' ? 'items-end max-w-[80%]' : 'items-start max-w-[80%]'
        )}
      >
        <div
          className={cn(
            'rounded-3xl px-4 py-2 smooth-transition overflow-hidden',
            message.type === 'user'
              ? 'bg-black text-white'
              : 'bg-gray-100 text-black'
          )}
        >
          {message.fileName && (
            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-400">
              <FileText className="h-4 w-4 shrink-0" />
              <span className="text-sm font-medium truncate">{message.fileName}</span>
            </div>
          )}
          <div className="text-sm break-words overflow-wrap-anywhere">
            {message.type === 'ai' ? formatMarkdown(message.content || '') : message.content}
          </div>
        </div>
        <span className="text-xs text-gray-500 px-2">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </motion.div>
  );

  return (
    <div className="w-full space-y-4 pb-32">
      {/* Initial messages (upload, etc.) */}
      {messages.map(renderMessage)}

      {/* Additional content like ThinkingWidget and VerdictCard */}
      {children}

      {/* Chat messages appear AFTER the verdict */}
      {chatMessages.length > 0 && (
        <div className="space-y-4 mt-4">
          {chatMessages.map(renderMessage)}
        </div>
      )}

      {/* Loading indicator when AI is thinking */}
      {isChatLoading && (
        <motion.div
          variants={messageVariants}
          initial="hidden"
          animate="show"
          className="flex gap-3 items-start flex-row mt-4"
        >
          {/* DICT Logo */}
          <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-white overflow-hidden">
            <Image
              src="/dict-logo.png"
              alt="DICT Logo"
              width={32}
              height={32}
              className="object-contain"
            />
          </div>

          {/* Loading message */}
          <div className="flex flex-col space-y-1 items-start max-w-[80%]">
            <div className="rounded-3xl px-4 py-2 bg-gray-100 text-black">
              <div className="text-sm text-gray-600">
                <LoopingTypeWriter text="Thinking..." speed={40} />
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
