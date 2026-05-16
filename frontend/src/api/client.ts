import type {
  CollectionCreate,
  CollectionRead,
  ConversationCreate,
  ConversationRead,
  ConversationSummary,
  DocumentRead,
} from './types';

const BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// Collections
export const collectionsApi = {
  list: () => request<CollectionRead[]>('/collections'),
  get: (id: string) => request<CollectionRead>(`/collections/${id}`),
  create: (body: CollectionCreate) =>
    request<CollectionRead>('/collections', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  delete: (id: string) =>
    request<void>(`/collections/${id}`, { method: 'DELETE' }),
  uploadDocument: (collectionId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<DocumentRead>(`/collections/${collectionId}/documents`, {
      method: 'POST',
      headers: {},
      body: form,
    });
  },
};

// Conversations
export const conversationsApi = {
  list: () => request<ConversationSummary[]>('/conversations'),
  get: (id: string) => request<ConversationRead>(`/conversations/${id}`),
  create: (body: ConversationCreate) =>
    request<ConversationRead>('/conversations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  delete: (id: string) =>
    request<void>(`/conversations/${id}`, { method: 'DELETE' }),
};
