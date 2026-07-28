export type TrustLevel = 'untrusted' | 'trusted';

export type PipelineState = 
  | 'received'
  | 'retrieving'
  | 'classifying'
  | 'analyzing'
  | 'validating'
  | 'awaiting_approval'
  | 'executing_tool'
  | 'complete'
  | 'failed';

export interface Chunk {
  chunk_id: string;
  source_doc_id: string;
  source_doc_title: string;
  matter_id: string;
  confidentiality_tag: 'public' | 'confidential' | 'privileged';
  text: string;
  embedding_score: number;
  page_ref: string;
  acl_check_passed: boolean;
}

export interface Claim {
  claim_id: string;
  text: string;
  supporting_chunk_ids: string[];
}

export interface QueryResponse {
  trace_id: string;
  status: PipelineState;
  answer?: string;
  claims?: Claim[];
  error?: string;
}

export interface TraceStage {
  id: number;
  trace_id: string;
  turn_id: string;
  message_id: string;
  timestamp: string;
  sender: string;
  recipient: string;
  message_type: string;
  trust_level: TrustLevel;
  payload_summary?: Record<string, any>;
}

export interface TraceSummary {
  trace_id: string;
  started_at: string;
  ended_at: string;
  message_count: number;
  message_types: string;
}

export interface ApprovalRequest {
  approval_id: string;
  trace_id: string;
  tool_name: string;
  parameters: string;
  requested_by: string;
  validated_by: string;
  originating_chunk_ids: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

export interface ChatSession {
  session_id: string;
  title: string;
  user_id: string;
  active_matter_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  trace_id?: string | null;
  metadata?: {
    claims?: Claim[];
    status?: PipelineState;
    error?: string;
  };
  timestamp: string;
}
