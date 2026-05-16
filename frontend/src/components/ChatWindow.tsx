interface Props {
  conversationId: string | null;
}

export function ChatWindow({ conversationId }: Props) {
  return (
    <main className="flex-1 flex flex-col bg-gray-900">
      <div className="flex-1 flex items-center justify-center">
        {conversationId ? (
          <p className="text-gray-400">Loading conversation…</p>
        ) : (
          <p className="text-gray-400">Select or create a conversation to get started.</p>
        )}
      </div>
      <div className="border-t border-gray-700 p-4">
        <div className="flex gap-2">
          <textarea
            className="flex-1 bg-gray-800 text-white rounded-md px-4 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={1}
            placeholder="Type a message…"
            disabled={!conversationId}
          />
          <button
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-md px-4 py-2 text-sm font-medium transition-colors"
            disabled={!conversationId}
          >
            Send
          </button>
        </div>
      </div>
    </main>
  );
}
