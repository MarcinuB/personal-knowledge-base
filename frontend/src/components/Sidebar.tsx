interface Props {
  activeConversationId: string | null;
  onConversationSelect: (id: string) => void;
}

export function Sidebar({ activeConversationId: _activeConversationId, onConversationSelect: _onConversationSelect }: Props) {
  return (
    <aside className="w-64 flex-shrink-0 bg-gray-800 flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-semibold text-white">Knowledge Base</h1>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        <p className="text-gray-400 text-sm px-2 py-4">No conversations yet.</p>
      </div>
      <div className="p-4 border-t border-gray-700">
        <button className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-md py-2 px-4 text-sm font-medium transition-colors">
          New Conversation
        </button>
      </div>
    </aside>
  );
}
