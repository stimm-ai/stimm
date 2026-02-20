/**
 * Stimm Protocol — TypeScript message types.
 *
 * Mirror of the Python Pydantic models in `stimm.protocol`.
 * All messages are exchanged as JSON over LiveKit reliable data channels.
 *
 * @module
 */

// ---------------------------------------------------------------------------
// Voice Agent → Supervisor
// ---------------------------------------------------------------------------

/** Real-time speech transcript from the voice agent's STT. */
export interface TranscriptMessage {
  type: "transcript";
  /** Whether this is a partial (streaming) or final transcript. */
  partial: boolean;
  text: string;
  timestamp: number;
  confidence: number;
}

/** Voice agent state transition. */
export interface StateMessage {
  type: "state";
  state: "listening" | "thinking" | "speaking";
  timestamp: number;
}

/** Emitted before the voice agent sends text to TTS. */
export interface BeforeSpeakMessage {
  type: "before_speak";
  text: string;
  turn_id: string;
}

/** Per-turn latency metrics. */
export interface MetricsMessage {
  type: "metrics";
  turn: number;
  vad_ms: number;
  stt_ms: number;
  llm_ttft_ms: number;
  tts_ttfb_ms: number;
  total_ms: number;
}

// ---------------------------------------------------------------------------
// Supervisor → Voice Agent
// ---------------------------------------------------------------------------

/** Voice agent operating mode. */
export type AgentMode = "autonomous" | "relay" | "hybrid";

/** Instruction for the voice agent to speak or incorporate. */
export interface InstructionMessage {
  type: "instruction";
  text: string;
  priority: "normal" | "interrupt";
  speak: boolean;
}

/** Additional context for the voice agent's working memory. */
export interface ContextMessage {
  type: "context";
  text: string;
  append: boolean;
}

/** Notification that a tool/action completed in the supervisor. */
export interface ActionResultMessage {
  type: "action_result";
  action: string;
  status: string;
  summary: string;
}

/** Switch the voice agent's operating mode. */
export interface ModeMessage {
  type: "mode";
  mode: AgentMode;
}

/** Cancel the voice agent's pending response and replace it. */
export interface OverrideMessage {
  type: "override";
  turn_id: string;
  replacement: string;
}

// ---------------------------------------------------------------------------
// Union types
// ---------------------------------------------------------------------------

/** Any message sent by the voice agent. */
export type VoiceAgentMessage =
  | TranscriptMessage
  | StateMessage
  | BeforeSpeakMessage
  | MetricsMessage;

/** Any message sent by the supervisor. */
export type SupervisorMessage =
  | InstructionMessage
  | ContextMessage
  | ActionResultMessage
  | ModeMessage
  | OverrideMessage;

/** Any stimm protocol message. */
export type StimmMessage = VoiceAgentMessage | SupervisorMessage;

/** The LiveKit data channel topic used by stimm. */
export const STIMM_TOPIC = "stimm";
