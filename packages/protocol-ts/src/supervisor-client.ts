/**
 * StimmSupervisorClient — TypeScript supervisor for Node.js consumers.
 *
 * Connects to a LiveKit room as a data-only participant and provides
 * a typed event-driven interface for receiving voice agent messages
 * and sending instructions back.
 *
 * @example
 * ```ts
 * import { StimmSupervisorClient } from "@stimm/protocol";
 *
 * const client = new StimmSupervisorClient({
 *   livekitUrl: "ws://localhost:7880",
 *   token: supervisorToken,
 * });
 *
 * client.on("transcript", async (msg) => {
 *   if (!msg.partial) {
 *     const result = await myAgent.process(msg.text);
 *     await client.instruct({ text: result, speak: true, priority: "normal" });
 *   }
 * });
 *
 * await client.connect();
 * ```
 *
 * @module
 */

import { Room, DataPacket_Kind, RoomEvent } from "livekit-client";
import type {
  AgentMode,
  TranscriptMessage,
  StateMessage,
  BeforeSpeakMessage,
  MetricsMessage,
  InstructionMessage,
  ContextMessage,
  ActionResultMessage,
  ModeMessage,
  OverrideMessage,
  StimmMessage,
} from "./messages.js";

import { STIMM_TOPIC } from "./messages.js";

// ---------------------------------------------------------------------------
// Event types
// ---------------------------------------------------------------------------

type VoiceAgentEventMap = {
  transcript: TranscriptMessage;
  state: StateMessage;
  before_speak: BeforeSpeakMessage;
  metrics: MetricsMessage;
};

type VoiceAgentEvent = keyof VoiceAgentEventMap;

type EventHandler<T> = (msg: T) => void | Promise<void>;

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

export interface StimmSupervisorClientOptions {
  /** LiveKit server WebSocket URL. */
  livekitUrl: string;
  /** Access token with data-channel permissions. */
  token: string;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export class StimmSupervisorClient {
  private room: Room;
  private url: string;
  private token: string;
  private handlers: Map<string, Array<EventHandler<any>>> = new Map();
  private _connected = false;

  constructor(options: StimmSupervisorClientOptions) {
    this.url = options.livekitUrl;
    this.token = options.token;
    this.room = new Room();
  }

  /** Whether the client is currently connected. */
  get connected(): boolean {
    return this._connected;
  }

  // -- Connection -----------------------------------------------------------

  /** Connect to the LiveKit room. */
  async connect(): Promise<void> {
    this.room.on(RoomEvent.DataReceived, this.onData.bind(this));
    await this.room.connect(this.url, this.token);
    this._connected = true;
  }

  /** Disconnect from the room. */
  async disconnect(): Promise<void> {
    await this.room.disconnect();
    this._connected = false;
  }

  // -- Receiving messages ---------------------------------------------------

  /** Register a handler for voice agent events. */
  on<E extends VoiceAgentEvent>(
    event: E,
    handler: EventHandler<VoiceAgentEventMap[E]>,
  ): void {
    const list = this.handlers.get(event) ?? [];
    list.push(handler as EventHandler<any>);
    this.handlers.set(event, list);
  }

  /** Remove a handler. */
  off<E extends VoiceAgentEvent>(
    event: E,
    handler: EventHandler<VoiceAgentEventMap[E]>,
  ): void {
    const list = this.handlers.get(event);
    if (!list) return;
    const idx = list.indexOf(handler as EventHandler<any>);
    if (idx >= 0) list.splice(idx, 1);
  }

  private onData(
    payload: Uint8Array,
    participant?: unknown,
    kind?: DataPacket_Kind,
    topic?: string,
  ): void {
    if (topic !== STIMM_TOPIC) return;

    try {
      const text = new TextDecoder().decode(payload);
      const msg = JSON.parse(text) as StimmMessage;
      const handlers = this.handlers.get(msg.type) ?? [];
      for (const handler of handlers) {
        Promise.resolve(handler(msg)).catch((err) => {
          console.error(`[stimm] Error in ${msg.type} handler:`, err);
        });
      }
    } catch (err) {
      console.error("[stimm] Failed to deserialize message:", err);
    }
  }

  // -- Sending messages to voice agent --------------------------------------

  private async send(msg: Record<string, unknown>): Promise<void> {
    const payload = new TextEncoder().encode(JSON.stringify(msg));
    await this.room.localParticipant.publishData(payload, {
      topic: STIMM_TOPIC,
      reliable: true,
    });
  }

  /** Send an instruction to the voice agent. */
  async instruct(
    msg: Omit<InstructionMessage, "type">,
  ): Promise<void> {
    await this.send({ type: "instruction", ...msg });
  }

  /** Add context to the voice agent's working memory. */
  async addContext(msg: Omit<ContextMessage, "type">): Promise<void> {
    await this.send({ type: "context", ...msg });
  }

  /** Notify the voice agent that a tool/action completed. */
  async sendActionResult(
    msg: Omit<ActionResultMessage, "type">,
  ): Promise<void> {
    await this.send({ type: "action_result", ...msg });
  }

  /** Switch the voice agent's operating mode. */
  async setMode(mode: AgentMode): Promise<void> {
    await this.send({ type: "mode", mode });
  }

  /** Cancel the voice agent's pending response and replace it. */
  async override(msg: Omit<OverrideMessage, "type">): Promise<void> {
    await this.send({ type: "override", ...msg });
  }
}
