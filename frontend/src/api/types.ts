export interface Participant {
  id: number;
  role_key: string;
  name: string;
  model: string;
  color: string | null;
  system_prompt: string;
  sort_order: number;
  tools_enabled: string | null;
}

export interface ModeConfig {
  id: number;
  name: string;
  display_name: string;
  description: string | null;
  default_rounds: number;
  mode_json: Record<string, any>;
  participants: Participant[];
}

export interface Session {
  id: string;
  mode: string;
  topic: string;
  rounds: number;
  status: "pending" | "running" | "completed" | "error";
  created_at: string;
}

export interface Message {
  id: number;
  role_key: string;
  role: string;
  name: string;
  content: string;
  model: string | null;
  ts: string;
}

export interface WSEvent {
  type: "turn_start" | "token" | "turn_end" | "banner" | "session_end" | "error";
  payload: Record<string, any>;
}

export interface ProviderModel {
  id: number;
  model_name: string;
}

export interface Provider {
  id: number;
  name: string;
  base_url: string | null;
  api_key: string;
  models: ProviderModel[];
}

export interface GlobalHost {
  id: number;
  name: string;
  model: string;
  system_prompt: string;
  color: string;
}

export interface SessionCreate {
  mode: "six_hat" | "debate";
  topic: string;
  rounds?: number;
}

export interface StreamingMessage {
  role_key: string;
  role_name: string;
  color: string;
  tokens: string[];
  full_content: string | null;
  is_complete: boolean;
}
