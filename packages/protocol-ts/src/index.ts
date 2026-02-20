/**
 * @stimm/protocol — TypeScript types and supervisor client
 * for Stimm dual-agent voice orchestration.
 *
 * @packageDocumentation
 */

// Message types
export type {
  TranscriptMessage,
  StateMessage,
  BeforeSpeakMessage,
  MetricsMessage,
  InstructionMessage,
  ContextMessage,
  ActionResultMessage,
  ModeMessage,
  OverrideMessage,
  AgentMode,
  VoiceAgentMessage,
  SupervisorMessage,
  StimmMessage,
} from "./messages.js";

export { STIMM_TOPIC } from "./messages.js";

// Supervisor client
export {
  StimmSupervisorClient,
  type StimmSupervisorClientOptions,
} from "./supervisor-client.js";
