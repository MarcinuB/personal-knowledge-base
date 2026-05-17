import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { collectionsApi, conversationsApi } from '../api/client';
import type { CollectionRead } from '../api/types';

interface Props {
  activeConversationId: string | null;
  onConversationSelect: (id: string) => void;
}

type View = 'conversations' | 'collections' | 'create-collection';

export function Sidebar({ activeConversationId, onConversationSelect }: Props) {
  const [view, setView] = useState<View>('conversations');
  const queryClient = useQueryClient();

  const { data: conversations, isLoading: convLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: conversationsApi.list,
  });

  const { data: collections, isLoading: colLoading } = useQuery({
    queryKey: ['collections'],
    queryFn: collectionsApi.list,
    enabled: view === 'collections' || view === 'create-collection',
  });

  const createConversation = useMutation({
    mutationFn: (collection: CollectionRead) =>
      conversationsApi.create({ collection_id: collection.id }),
    onSuccess: (conv) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      onConversationSelect(conv.id);
      setView('conversations');
    },
  });

  const createCollection = useMutation({
    mutationFn: (name: string) => collectionsApi.create({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      setView('collections');
    },
  });

  const headerTitle: Record<View, string> = {
    conversations: 'Knowledge Base',
    collections: 'New Conversation',
    'create-collection': 'New Collection',
  };

  return (
    <aside className="w-64 flex-shrink-0 bg-gray-800 flex flex-col">
      <div className="p-4 border-b border-gray-700 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">{headerTitle[view]}</h1>
        {view !== 'conversations' && (
          <button
            onClick={() => setView(view === 'create-collection' ? 'collections' : 'conversations')}
            className="text-gray-400 hover:text-white text-sm transition-colors"
          >
            ✕
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {view === 'conversations' && (
          <ConversationList
            conversations={conversations ?? []}
            isLoading={convLoading}
            activeId={activeConversationId}
            onSelect={onConversationSelect}
          />
        )}
        {view === 'collections' && (
          <CollectionPicker
            collections={collections ?? []}
            isLoading={colLoading}
            isPending={createConversation.isPending}
            onPick={(col) => createConversation.mutate(col)}
            onNewCollection={() => setView('create-collection')}
          />
        )}
        {view === 'create-collection' && (
          <NewCollectionForm
            isPending={createCollection.isPending}
            error={createCollection.error?.message}
            onSubmit={(name) => createCollection.mutate(name)}
            onCancel={() => setView('collections')}
          />
        )}
      </div>

      <div className="p-4 border-t border-gray-700">
        {view === 'conversations' && (
          <button
            onClick={() => setView('collections')}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-md py-2 px-4 text-sm font-medium transition-colors"
          >
            + New Conversation
          </button>
        )}
        {view === 'collections' && (
          <p className="text-gray-400 text-xs text-center">Select a collection to start</p>
        )}
        {view === 'create-collection' && (
          <p className="text-gray-400 text-xs text-center">Enter a name for your collection</p>
        )}
      </div>
    </aside>
  );
}

function ConversationList({
  conversations,
  isLoading,
  activeId,
  onSelect,
}: {
  conversations: { id: string; title?: string; created_at: string }[];
  isLoading: boolean;
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  if (isLoading) {
    return (
      <div className="p-2 space-y-2 animate-pulse">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-12 bg-gray-700 rounded-md" />
        ))}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <p className="text-gray-400 text-sm px-4 py-8 text-center">
        No conversations yet.
      </p>
    );
  }

  return (
    <ul className="p-2 space-y-1">
      {conversations.map((conv) => (
        <li key={conv.id}>
          <button
            onClick={() => onSelect(conv.id)}
            className={`w-full text-left rounded-md px-3 py-2 text-sm transition-colors ${
              conv.id === activeId
                ? 'bg-blue-600 text-white'
                : 'text-gray-300 hover:bg-gray-700'
            }`}
          >
            <div className="font-medium truncate">{conv.title ?? 'New conversation'}</div>
            <div className={`text-xs mt-0.5 ${conv.id === activeId ? 'text-blue-200' : 'text-gray-500'}`}>
              {formatDistanceToNow(new Date(conv.created_at.endsWith('Z') ? conv.created_at : conv.created_at + 'Z'), { addSuffix: true })}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

function CollectionPicker({
  collections,
  isLoading,
  isPending,
  onPick,
  onNewCollection,
}: {
  collections: CollectionRead[];
  isLoading: boolean;
  isPending: boolean;
  onPick: (col: CollectionRead) => void;
  onNewCollection: () => void;
}) {
  if (isLoading) {
    return (
      <div className="p-2 space-y-2 animate-pulse">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-14 bg-gray-700 rounded-md" />
        ))}
      </div>
    );
  }

  return (
    <div className="p-2 space-y-1">
      {collections.length === 0 ? (
        <p className="text-gray-400 text-sm px-2 py-4 text-center">
          No collections yet.
        </p>
      ) : (
        <ul className="space-y-1">
          {collections.map((col) => (
            <li key={col.id}>
              <button
                onClick={() => onPick(col)}
                disabled={isPending}
                className="w-full text-left rounded-md px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-50 transition-colors"
              >
                <div className="font-medium truncate">{col.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {col.document_count} {col.document_count === 1 ? 'document' : 'documents'}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
      <button
        onClick={onNewCollection}
        className="w-full text-left rounded-md px-3 py-2 text-sm text-blue-400 hover:bg-gray-700 transition-colors"
      >
        + New Collection
      </button>
    </div>
  );
}

function NewCollectionForm({
  isPending,
  error,
  onSubmit,
  onCancel,
}: {
  isPending: boolean;
  error?: string;
  onSubmit: (name: string) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState('');

  return (
    <div className="p-4 space-y-3">
      <input
        type="text"
        autoFocus
        placeholder="Collection name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && name.trim()) onSubmit(name.trim());
          if (e.key === 'Escape') onCancel();
        }}
        className="w-full bg-gray-700 text-white rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-400"
      />
      {error && <p className="text-red-400 text-xs">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={() => { if (name.trim()) onSubmit(name.trim()); }}
          disabled={!name.trim() || isPending}
          className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-md py-2 text-sm font-medium transition-colors"
        >
          {isPending ? 'Creating…' : 'Create'}
        </button>
        <button
          onClick={onCancel}
          className="px-3 py-2 text-sm text-gray-400 hover:text-white transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
