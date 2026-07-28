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
  chunk_id: str;
  source_doc_id: str;
  source_doc_title: str;
  matter_id: str;
  confidentiality_tag: 'public' | 'confidential' | 'privileged';
  text: str;
  embedding_score: number;
  page_ref: str;
  acl_check_passed: boolean;
}

export interface Claim {
  claim_id: str;
  text: str;
  supporting_chunk_ids: str[];
}

export interface QueryResponse {
  trace_id: str;
  status: PipelineState;
  answer?: str;
  claims?: Claim[];
  error?: str;
}

export interface TraceStage {
  id: number;
  trace_id: str;
  turn_id: str;
  message_id: str;
  timestamp: str;
  sender: str;
  recipient: str;
  message_type: str;
  trust_level: TrustLevel;
  payload_summary?: Record<string, any>;
}

export interface TraceSummary {
  trace_id: str;
  started_at: str;
  ended_at: str;
  message_count: number;
  message_types: str;
}

export interface ApprovalRequest {
  approval_id: str;
  trace_id: str;
  tool_name: str;
  parameters: str;
  requested_by: str;
  validated_by: str;
  originating_chunk_ids: str;
  status: 'pending' | 'approved' | 'rejected';
  created_at: str;
}

type str = string;
