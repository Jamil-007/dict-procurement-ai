import { VerdictData } from '@/types/procurement';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface AnalyzeResponse {
  thread_id: string;
  status: string;
}

export interface ReviewResponse {
  status: string;
  gamma_link?: string;
}

export interface ChatResponse {
  response: string;
}

export interface StatusResponse {
  status: string;
  verdict?: VerdictData;
  gamma_link?: string;
}

export interface StreamCallbacks {
  onThinkingLog?: (log: any) => void;
  onVerdict?: (verdict: VerdictData) => void;
  onComplete?: () => void;
  onError?: (error: string) => void;
  onGammaLink?: (link: string) => void;
}

export interface ChatStreamStartEvent {
  message_id: string;
  timestamp: number;
}

export interface ChatStreamDeltaEvent {
  message_id: string;
  delta: string;
}

export interface ChatStreamCompleteEvent {
  message_id: string;
  response: string;
  timestamp: number;
}

export interface ChatStreamCallbacks {
  onStart?: (event: ChatStreamStartEvent) => void;
  onDelta?: (event: ChatStreamDeltaEvent) => void;
  onComplete?: (event: ChatStreamCompleteEvent) => void;
  onError?: (error: string) => void;
}

export class APIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      let details;

      try {
        const errorData = await response.json();
        errorMessage = errorData.error || errorData.detail || errorMessage;
        details = errorData;
      } catch {
        // If parsing JSON fails, use the status text
      }

      throw new APIError(errorMessage, response.status, details);
    }

    return response.json();
  }

  async uploadDocuments(files: File[]): Promise<AnalyzeResponse> {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));

    const response = await fetch(`${this.baseUrl}/analyze`, {
      method: 'POST',
      body: formData,
    });

    return this.handleResponse<AnalyzeResponse>(response);
  }

  connectToStream(threadId: string, callbacks: StreamCallbacks): EventSource {
    const eventSource = new EventSource(`${this.baseUrl}/stream/${threadId}`);

    eventSource.addEventListener('thinking_log', (event) => {
      try {
        const log = JSON.parse(event.data);
        if (callbacks.onThinkingLog) {
          callbacks.onThinkingLog(log);
        }
      } catch (error) {
        console.error('Failed to parse thinking log:', error);
      }
    });

    eventSource.addEventListener('verdict', (event) => {
      try {
        const verdict = JSON.parse(event.data);
        if (callbacks.onVerdict) {
          callbacks.onVerdict(verdict);
        }
      } catch (error) {
        console.error('Failed to parse verdict:', error);
      }
    });

    eventSource.addEventListener('complete', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (callbacks.onComplete) {
          callbacks.onComplete();
        }
        // Close the connection when complete
        eventSource.close();
      } catch (error) {
        console.error('Failed to parse complete event:', error);
      }
    });

    eventSource.addEventListener('gamma_link', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.link && callbacks.onGammaLink) {
          callbacks.onGammaLink(data.link);
        }
      } catch (error) {
        console.error('Failed to parse gamma link:', error);
      }
    });

    eventSource.addEventListener('error', (event: Event) => {
      const messageEvent = event as MessageEvent;
      try {
        if (messageEvent.data) {
          const errorData = JSON.parse(messageEvent.data);
          if (callbacks.onError) {
            callbacks.onError(errorData.error || 'Stream error occurred');
          }
        } else {
          if (callbacks.onError) {
            callbacks.onError('Connection error occurred');
          }
        }
      } catch {
        if (callbacks.onError) {
          callbacks.onError('Connection error occurred');
        }
      }
      eventSource.close();
    });

    eventSource.onerror = (event) => {
      console.error('EventSource error:', event);
      if (callbacks.onError) {
        callbacks.onError('Connection to server lost');
      }
      eventSource.close();
    };

    return eventSource;
  }

  async submitReview(
    threadId: string,
    generateGamma: boolean
  ): Promise<ReviewResponse> {
    const response = await fetch(`${this.baseUrl}/review`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        thread_id: threadId,
        action: generateGamma ? 'generate_gamma' : 'chat_only',
      }),
    });

    return this.handleResponse<ReviewResponse>(response);
  }

  async sendChatMessage(
    threadId: string,
    query: string
  ): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        thread_id: threadId,
        query,
      }),
    });

    return this.handleResponse<ChatResponse>(response);
  }

  async sendChatMessageStream(
    threadId: string,
    query: string,
    callbacks: ChatStreamCallbacks,
    signal?: AbortSignal
  ): Promise<void> {
    const response = await fetch(`${this.baseUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        thread_id: threadId,
        query,
      }),
      signal,
    });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      let details;

      try {
        const errorData = await response.json();
        errorMessage = errorData.error || errorData.detail || errorMessage;
        details = errorData;
      } catch {
        // Fall back to status text if body is not JSON
      }

      throw new APIError(errorMessage, response.status, details);
    }

    if (!response.body) {
      throw new APIError('Streaming response body not available');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const processSSEEvent = (rawEvent: string) => {
      const lines = rawEvent.split('\n');
      let eventName = 'message';
      const dataLines: string[] = [];

      for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        if (!line || line.startsWith(':')) {
          continue;
        }

        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim();
          continue;
        }

        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim());
        }
      }

      if (!dataLines.length) {
        return;
      }

      let payload: any;
      try {
        payload = JSON.parse(dataLines.join('\n'));
      } catch {
        callbacks.onError?.('Failed to parse stream payload');
        throw new APIError('Failed to parse stream payload');
      }

      if (eventName === 'chat_start') {
        callbacks.onStart?.(payload as ChatStreamStartEvent);
        return;
      }

      if (eventName === 'chat_delta') {
        callbacks.onDelta?.(payload as ChatStreamDeltaEvent);
        return;
      }

      if (eventName === 'chat_complete') {
        callbacks.onComplete?.(payload as ChatStreamCompleteEvent);
        return;
      }

      if (eventName === 'error') {
        const message = payload?.error || 'Stream error occurred';
        callbacks.onError?.(message);
        throw new APIError(message);
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      let boundaryIndex = buffer.indexOf('\n\n');

      while (boundaryIndex !== -1) {
        const rawEvent = buffer.slice(0, boundaryIndex).trim();
        buffer = buffer.slice(boundaryIndex + 2);

        if (rawEvent) {
          processSSEEvent(rawEvent);
        }

        boundaryIndex = buffer.indexOf('\n\n');
      }
    }

    const tail = (buffer + decoder.decode()).trim();
    if (tail) {
      processSSEEvent(tail);
    }
  }

  async getStatus(threadId: string): Promise<StatusResponse> {
    const response = await fetch(`${this.baseUrl}/status/${threadId}`);
    return this.handleResponse<StatusResponse>(response);
  }

  async healthCheck(): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/health`);
    return this.handleResponse<{ status: string }>(response);
  }
}

export const apiClient = new APIClient();
