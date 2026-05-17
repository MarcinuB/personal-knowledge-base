import { useEffect, useRef, useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { conversationsApi } from '../api/client';
import { streamChat } from '../api/chat';
import { DocumentUpload } from './DocumentUpload';
import type { MessageRead } from '../api/types';

interface Props {
  conversationId: string | null;
}

interface LocalMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  streaming?: boolean;
}

export function ChatWindow({ conversationId }: Props) {
  const queryClient = useQueryClient();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [localMessages, setLocalMessages] = useState<LocalMessage[]>([]);

  const { data: conversation, isLoading } = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: () => conversationsApi.get(conversationId!),
    enabled: !!conversationId,
  });

  // Sync server messages into local state when conversation loads or changes
  useEffect(() => {
    if (conversation) {
      setLocalMessages(conversation.messages.map(toLocal));
    } else {
      setLocalMessages([]);
    }
  }, [conversation]);

  // Auto-scroll on new messages or streaming
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [localMessages]);

  const send = useCallback(async () => {
    if (!conversationId || !input.trim() || streaming) return;

    const userMessage = input.trim();
    setInput('');
    setStreaming(true);

    const userLocal: LocalMessage = { id: crypto.randomUUID(), role: 'user', content: userMessage };
    const assistantLocal: LocalMessage = { id: crypto.randomUUID(), role: 'assistant', content: '', streaming: true };

    setLocalMessages((prev) => [...prev, userLocal, assistantLocal]);

    try {
      for await (const event of streamChat(conversationId, userMessage)) {
        if (event.type === 'token') {
          setLocalMessages((prev) =>
            prev.map((m) =>
              m.id === assistantLocal.id ? { ...m, content: m.content + event.content } : m,
            ),
          );
        } else if (event.type === 'error') {
          setLocalMessages((prev) =>
            prev.map((m) =>
              m.id === assistantLocal.id ? { ...m, content: `Error: ${event.content}`, streaming: false } : m,
            ),
          );
          break;
        } else if (event.type === 'done') {
          setLocalMessages((prev) =>
            prev.map((m) => (m.id === assistantLocal.id ? { ...m, streaming: false } : m)),
          );
          queryClient.invalidateQueries({ queryKey: ['conversation', conversationId] });
        }
      }
    } finally {
      setStreaming(false);
    }
  }, [conversationId, input, streaming, queryClient]);

  if (!conversationId) {
    return (
      <main className="flex-1 flex flex-col bg-gray-900 items-center justify-center">
        <p className="text-gray-400">Select or create a conversation to get started.</p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col bg-gray-900 min-w-0">
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {isLoading ? (
          <div className="flex justify-center">
            <p className="text-gray-400 text-sm">Loading…</p>
          </div>
        ) : (
          localMessages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-gray-700 p-4">
        <div className="flex items-end gap-2">
          {conversation && (
            <DocumentUpload
              collectionId={conversation.collection_id}
              disabled={streaming}
            />
          )}
          <textarea
            className="flex-1 bg-gray-800 text-white rounded-md px-4 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={1}
            placeholder="Type a message…"
            value={input}
            disabled={streaming}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <button
            onClick={send}
            disabled={!input.trim() || streaming}
            className="p-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-md transition-colors"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </main>
  );
}

function MessageBubble({ message }: { message: LocalMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-sm'
            : 'bg-gray-700 text-gray-100 rounded-bl-sm'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
            {message.streaming && <span className="animate-pulse">▋</span>}
          </div>
        )}
      </div>
    </div>
  );
}

function toLocal(m: MessageRead): LocalMessage {
  return { id: m.id, role: m.role as 'user' | 'assistant', content: m.content };
}
