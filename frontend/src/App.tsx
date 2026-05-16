import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';

export default function App() {
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        activeConversationId={activeConversationId}
        onConversationSelect={setActiveConversationId}
      />
      <ChatWindow conversationId={activeConversationId} />
    </div>
  );
}
