// Mirrors backend Pydantic schemas

export interface CollectionCreate {
  name: string;
  description?: string;
}

export interface CollectionRead {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  document_count: number;
}

export interface DocumentRead {
  id: string;
  filename: string;
  status: 'processing' | 'ready' | 'failed';
}

export interface ConversationCreate {
  collection_id: string;
  title?: string;
}

export interface MessageRead {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface ConversationRead {
  id: string;
  collection_id: string;
  title?: string;
  created_at: string;
  messages: MessageRead[];
}

export interface ConversationSummary {
  id: string;
  collection_id: string;
  title?: string;
  created_at: string;
}
