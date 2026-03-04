# Changelog

## [0.1.13](https://github.com/stimm-ai/stimm/compare/stimm-v0.1.12...stimm-v0.1.13) (2026-03-04)


### Bug Fixes

* enhance README with logo, description, and badges for better visibility ([271b06b](https://github.com/stimm-ai/stimm/commit/271b06b49bf1d15a0fb9c65845f6b78cd5e3c3f5))

## [0.1.9](https://github.com/stimm-ai/stimm/compare/stimm-v0.1.8...stimm-v0.1.9) (2026-02-28)


### Bug Fixes

* split release workflow by tag prefix for independent npm/PyPI releases ([4d5d53a](https://github.com/stimm-ai/stimm/commit/4d5d53aa0b29a554b7242409d6f186ae7f5bd6ac))

## [0.1.8](https://github.com/stimm-ai/stimm/compare/stimm-v0.1.7...stimm-v0.1.8) (2026-02-28)


### Bug Fixes

* trigger release workflow on stimm-v* tags from release-please ([b49db08](https://github.com/stimm-ai/stimm/commit/b49db0876943138cfbb77841c3ce0889a2df154b))

## [0.1.7](https://github.com/stimm-ai/stimm/compare/stimm-v0.1.6...stimm-v0.1.7) (2026-02-28)


### Bug Fixes

* prevent repo livekit/ from shadowing installed packages in CI ([c7532d4](https://github.com/stimm-ai/stimm/commit/c7532d42cd2a1d4c4a5e1a14ba501f13c962115a))

## [0.1.6](https://github.com/stimm-ai/stimm/compare/stimm-v0.1.5...stimm-v0.1.6) (2026-02-28)


### Bug Fixes

* refine PYTHONPATH setup for isolated interpreter to prevent ImportError ([12b93e2](https://github.com/stimm-ai/stimm/commit/12b93e2827b5b00c248cc42e84e3353edade19fc))

## [0.1.5](https://github.com/stimm-ai/stimm/compare/stimm-v0.1.4...stimm-v0.1.5) (2026-02-28)


### Features

* add Hume plugin to optional dependencies ([2c15264](https://github.com/stimm-ai/stimm/commit/2c152647b936eab758dca1063af131460944b006))
* enhance STT/TTS functionality for Hume provider and add support for additional providers ([a2da5a8](https://github.com/stimm-ai/stimm/commit/a2da5a88fbae4d030cea8a10307eb8426732de23))
* update Hume provider default model and presets configuration ([1063b0f](https://github.com/stimm-ai/stimm/commit/1063b0fba2b058c9d0a8852ceb8f2a241da65187))

## [0.1.4](https://github.com/stimm-ai/stimm/compare/stimm-v0.1.3...stimm-v0.1.4) (2026-02-26)


### Bug Fixes

* remove src/livekit stubs that shadow real livekit-agents in editable installs ([f20adf0](https://github.com/stimm-ai/stimm/commit/f20adf036e43e0becb3f18261e14fba7655c2fdb))
* update purge_livekit_rooms script to include agent dispatch deletion in documentation and functionality ([f22daaa](https://github.com/stimm-ai/stimm/commit/f22daaab22cd9022b0c4f98a5d4f5b10e5bcd4bd))

## [0.1.3](https://github.com/stimm-ai/stimm/compare/stimm-v0.1.2...stimm-v0.1.3) (2026-02-26)


### Features

* add backend decision handling and input formatting to ConversationSupervisor ([4af8d32](https://github.com/stimm-ai/stimm/commit/4af8d32b8fed2237ce9c3b22e710a07cd2c3a33f))
* add beta class with GeminiTTS structure to Google plugin ([d156d3e](https://github.com/stimm-ai/stimm/commit/d156d3e6fa184a2019a27daa539eb8d3e93d8eb0))
* add database models for administrable RAG configurations ([6419e32](https://github.com/stimm-ai/stimm/commit/6419e3229a055557b904fc003536fe855410bdd5))
* add docs optional dependencies and hatch commands for MkDocs ([bcb70d1](https://github.com/stimm-ai/stimm/commit/bcb70d161a3f7e6c21308ec688d9fbb075671fea))
* add document management API endpoints ([5b04cdc](https://github.com/stimm-ai/stimm/commit/5b04cdc51ee0941df1b50c4bf983c077e9a8c222))
* add document management database schema ([c13f4e0](https://github.com/stimm-ai/stimm/commit/c13f4e08d7035b86c791bbdf692a1f4136b31f86))
* add document management frontend components ([eca826d](https://github.com/stimm-ai/stimm/commit/eca826d2cfa3ac79fa59ae7a393250bf8245f704))
* add favicon icons and metadata for VoiceBot agent management app ([2c1efd5](https://github.com/stimm-ai/stimm/commit/2c1efd56617de714c13eb12cd4d00a5ca231c5dc))
* add frontend RAG administration pages ([a2ec134](https://github.com/stimm-ai/stimm/commit/a2ec1348839d28cb5c86430f24c32c44f8d19b87))
* Add Hume.ai TTS provider implementation ([fa4fd80](https://github.com/stimm-ai/stimm/commit/fa4fd800fad10a7319f726e424941371aa04eced))
* add lightweight stub packages for LiveKit plugins and implement basic class structures ([1b8af91](https://github.com/stimm-ai/stimm/commit/1b8af9100d22e4e8e2a97bdfc1f9dbe774c214d2))
* add livekit stub packages and minimal class structures for CI import checks ([ccf2871](https://github.com/stimm-ai/stimm/commit/ccf28715e86b5fc15ac765ea718d683b6ca27ff1))
* add local dev config files for WSL2 testing ([af3bedf](https://github.com/stimm-ai/stimm/commit/af3bedf27e55fc4007e3a6b7e9c4d932d7d78016))
* add minimal stub of livekit.agents.Agent for testing in both repo-root and src paths ([5058dde](https://github.com/stimm-ai/stimm/commit/5058ddea0f5992349f4633d53d9a17c149bbc0f9))
* add MkDocs documentation site with structure and configuration ([ef9a244](https://github.com/stimm-ai/stimm/commit/ef9a244df38918f46feaf8191313088a869dda6b))
* add provider catalog and load functionality from providers.json ([e0c2326](https://github.com/stimm-ai/stimm/commit/e0c232694d0e543cf3a7df4a9cf54739de5084e4))
* add script to purge LiveKit rooms and enhance conversation supervisor with instant feedback handling ([2774f5a](https://github.com/stimm-ai/stimm/commit/2774f5a6db1382300ed3759a71b8182a579eceb4))
* add top-level livekit stub package for CI import-check ([50b3869](https://github.com/stimm-ai/stimm/commit/50b3869de99fe76525939c759cb72db75161ddfa))
* Adds CI workflow for testing ([b787011](https://github.com/stimm-ai/stimm/commit/b78701173216c367a50b8f85348c2f9142883796))
* Adds platform overview page with quick access links ([d43ad7e](https://github.com/stimm-ai/stimm/commit/d43ad7ed194eef00e68a4e52452cb25d5bcae2ff))
* **ci:** Add SAST tools for Python and Next.js ([6e638d6](https://github.com/stimm-ai/stimm/commit/6e638d656839fbce5d5840addbd81042ee56aa55))
* **cli:** add CLI usage guide and pyaudio dependency for VoiceBot CLI tool ([c004dc2](https://github.com/stimm-ai/stimm/commit/c004dc2eea7314edaf5437903bab3c28084ed77d))
* **conversation_supervisor:** implement instant feedback context injection and improve acknowledgment handling ([8aae12b](https://github.com/stimm-ai/stimm/commit/8aae12b9767c83c2a5f06bff56422864f96ec248))
* **docker:** implement multi-stage build and trim dependencies ([b71cb79](https://github.com/stimm-ai/stimm/commit/b71cb7926bae166499b60f2422c5f97aa417515a))
* enable WebRTC for WSL2 (Docker + client) ([28bea5b](https://github.com/stimm-ai/stimm/commit/28bea5b77e07884c1fff833945b1e9116cf2537d))
* enhance ConversationSupervisor and VoiceAgent for improved context handling and instruction synchronization ([475522a](https://github.com/stimm-ai/stimm/commit/475522a59764fd35d1deaa342efebb59c00dc3f9))
* enhance logging and deduplication handling in ConversationSupervisor, VoiceAgent, and Worker ([9c5ea03](https://github.com/stimm-ai/stimm/commit/9c5ea03b106dd99b33188cf957ba493eb51f4d3e))
* enhance transcript handling in ConversationSupervisor and Worker to prevent duplicate entries ([b8190af](https://github.com/stimm-ai/stimm/commit/b8190af43bc9826e73103d2cc97775c5048bd7f7))
* implement AccessToken and VideoGrants classes; add VAD plugin and update CI configuration ([7ffdb0e](https://github.com/stimm-ai/stimm/commit/7ffdb0e1bb539547af5106e32f8183c57bfe1923))
* implement comprehensive document management for RAG system ([8caabac](https://github.com/stimm-ai/stimm/commit/8caabaca44b24517fc1b3b706ef118e6046c36b9))
* implement ConversationSupervisor, RoomManager, and worker for multi-session voice management ([33de1d3](https://github.com/stimm-ai/stimm/commit/33de1d3a51659fef87af080744ae4e2c22562ca9))
* implement document processing and management services ([06e202f](https://github.com/stimm-ai/stimm/commit/06e202f1c34eee41a9d3f95d5a05b8fa4fa47b83))
* implement RAG provider registry and service layer ([e0adf51](https://github.com/stimm-ai/stimm/commit/e0adf51c6526505a8676491bcdae0bbeb9e410ff))
* Implement WebRTC signaling, media handling, and Silero VAD for real-time audio communication. ([e9b9f01](https://github.com/stimm-ai/stimm/commit/e9b9f017c50c401b8102e50d5092008b288f3512))
* Implement WebRTC signaling, media handling, and VAD services with client-side components and tests, and remove deprecated documentation. ([b6e6ce6](https://github.com/stimm-ai/stimm/commit/b6e6ce6484784e5239fbb8ab0bae2f18f0ae4d85))
* initialize Docusaurus website with essential configurations ([9ee7316](https://github.com/stimm-ai/stimm/commit/9ee7316be7ada6c52dcc461d4191a2b836d176b3))
* integrate RAG configurations with agents ([b4d4585](https://github.com/stimm-ai/stimm/commit/b4d4585731c45f332ac9e02e0f1eac623c445c63))
* Optimize audio streaming by sending raw binary data over WebSocket and add refactoring documentation. ([b3fd4fa](https://github.com/stimm-ai/stimm/commit/b3fd4fa7b2cf40005ae73a999e2560cafbc71d6f))
* **provider:** enhance provider catalog with new helper functions and extras resolution ([978ce68](https://github.com/stimm-ai/stimm/commit/978ce683e19a19f670461c3fc73ccbfb0f4d2ed9))
* **room:** implement inactivity timeout and watchdog for automatic room shutdown ([805b2c2](https://github.com/stimm-ai/stimm/commit/805b2c26d27ccafb75d9d2ff7a6c1a28383d57a4))
* update integration documentation and add supervisor observability logs guide ([e911d5d](https://github.com/stimm-ai/stimm/commit/e911d5dcc4913989b88a14ee356466a09c860330))
* update process method in ConversationSupervisor and Worker to include optional system prompt ([e6fb2ca](https://github.com/stimm-ai/stimm/commit/e6fb2ca4642812cca7f1b28a0fea214c28684299))
* **webrtc:** add debug script to validate voicebot VAD→STT chain ([8db18de](https://github.com/stimm-ai/stimm/commit/8db18dee6030fc146eea894c24f43f167db20343))
* **worker:** enhance TTS constructor selection for Google providers ([61ce2da](https://github.com/stimm-ai/stimm/commit/61ce2da922cad18a20181a7fbae8212861a325e5))


### Bug Fixes

* Add system dependencies for audio processing ([86028f2](https://github.com/stimm-ai/stimm/commit/86028f2b8a6201a02fa1802f6653c14783ada0a5))
* Adds test audio files for mono and stereo formats ([eefe428](https://github.com/stimm-ai/stimm/commit/eefe428e76c9749de86aefd8c65e53a11977669b))
* CI - add setup_env.sh, fix uv sync --extra dev, remove broken semgrep from lint ([ad7306f](https://github.com/stimm-ai/stimm/commit/ad7306f876d7183289d40bba20c0123bb1801caf))
* Disable preloading of non-ONNX-compatible embedding models ([1d0f6f5](https://github.com/stimm-ai/stimm/commit/1d0f6f5d26bd3fb20a20c91675ff484dc51a1a72))
* Disable preloading of non-ONNX-compatible embedding models ([60ff463](https://github.com/stimm-ai/stimm/commit/60ff4632b1d4643efb79eab691de3f6f843bf7aa))
* **examples:** use AgentSession+JobContext entrypoint (livekit-agents v1) ([9bc5392](https://github.com/stimm-ai/stimm/commit/9bc5392900a21717b102f4c3b6214398176ae816))
* Improve RAG UI form layout and add retrieval verification script ([275efbf](https://github.com/stimm-ai/stimm/commit/275efbfbdef6cae9ff0a34c7dd3d95fbddb14357))
* Improves agent_id UUID handling with validation\n\nAdds a helper method to safely convert and validate agent_id values to UUID objects.\nImproves error handling by raising ValueError for invalid formats.\nMaintains backward compatibility while making the code more robust. ([a1fe6dc](https://github.com/stimm-ai/stimm/commit/a1fe6dc5f92faa7e6554c8ffca64681700416074))
* Improves CI service readiness checks and provider test configuration ([7d9a52b](https://github.com/stimm-ai/stimm/commit/7d9a52b0e4a2d88389218950fc25c901e1bf1191))
* Improves CI workflow with better service management ([d7411cc](https://github.com/stimm-ai/stimm/commit/d7411cc9d40f6a9389539f240c525937225be5d7))
* Improves ElevenLabs audio stream handling ([515d832](https://github.com/stimm-ai/stimm/commit/515d832a5b6484607b70101ebd3ca4dca13d858b))
* Improves model caching and security configurations ([5af5079](https://github.com/stimm-ai/stimm/commit/5af5079f68ac694d54a8ee89693b7379d5b105f5))
* Optimizes streaming test by validating with first audio chunk ([562a323](https://github.com/stimm-ai/stimm/commit/562a3233a26da0ccedf72124c4a3bed5cd3a8aaf))
* remove pytest marker filter, no tests are marked ([ddcd72f](https://github.com/stimm-ai/stimm/commit/ddcd72ff2d430bc636ef9cc41ebbd9855fe23e84))
* remove unnecessary blank line in voice_agent.py ([b71ff36](https://github.com/stimm-ai/stimm/commit/b71ff36ebbf08dd59f546a77827328351611e162))
* reorder import statements for consistency in agent modules ([dd16074](https://github.com/stimm-ai/stimm/commit/dd16074a1334d843b815fb0940fec418d2764167))
* reorder import statements for consistency in worker module ([2789556](https://github.com/stimm-ai/stimm/commit/2789556d628404de91b14129357b1972d3ad3405))
* supervisor-client onData optional params for livekit-client compat ([5957c9a](https://github.com/stimm-ai/stimm/commit/5957c9a874f740fb3e3f058ad7326d0a80d3b967))
* update Python path for LiveKit plugin validation scripts in CI workflow ([5db9068](https://github.com/stimm-ai/stimm/commit/5db9068e30f529bf4b72ffcb45d67261cc1b9b0d))
* update version to 0.1.2 in package-lock.json and enhance entrypoint to keep alive until disconnection ([af617f0](https://github.com/stimm-ai/stimm/commit/af617f0925ee98b8071396b89beceecd33967753))
* update version to 0.1.2 in package.json, pyproject.toml, and uv.lock ([69293ac](https://github.com/stimm-ai/stimm/commit/69293ac0927eca68d534cdacb4fffe9a6eb392f0))
* Updates agent update logic and cache invalidation ([329386b](https://github.com/stimm-ai/stimm/commit/329386b0519443d2b1c078105ae3b6512a9186ab))
* Updates audio sample rate and output format for hume.ai ([678653b](https://github.com/stimm-ai/stimm/commit/678653b39e4406001d94141b7bdea12e65d6e077))
* Updates Deepgram TTS provider to match API specifications ([515a167](https://github.com/stimm-ai/stimm/commit/515a167afd113f86dd3c6016de5a4c935ad1c8f1))
* Updates RAG config handling to support null values ([433baab](https://github.com/stimm-ai/stimm/commit/433baab168bd1af41ea11c975440687677f74242))
* use timedelta for AccessToken.ttl (livekit-api compat) ([1587d8a](https://github.com/stimm-ai/stimm/commit/1587d8a52e560fe3273136b7900430d283a1e2a2))


### Dependencies

* add document processing dependencies ([bba5870](https://github.com/stimm-ai/stimm/commit/bba587093cda46eceb84fead87642bae15e3d448))


### Documentation

* add CI/CD handoff for release workflows ([8f4544a](https://github.com/stimm-ai/stimm/commit/8f4544a99937245b773e9edc892368e936fdeca6))
* Add linting and formatting checks to CI pipeline ([11d95b1](https://github.com/stimm-ai/stimm/commit/11d95b1fc561b3591a275caa99725480b14a118c))
* Add linting and formatting checks to CI pipeline ([f06a785](https://github.com/stimm-ai/stimm/commit/f06a78513fe9d52727b5db9beb60b52944991120))
* Adds architecture diagram to document how it works ([93a3139](https://github.com/stimm-ai/stimm/commit/93a313925686a5ed0ecc58772fd22470e8b0b3c5))
* Adds CONTRIBUTING.md with project guidelines ([685a00c](https://github.com/stimm-ai/stimm/commit/685a00c475e34ddc5b981ebbfcfef0c365ee8497))
* Adds documentation link and expands README sections ([230ddf2](https://github.com/stimm-ai/stimm/commit/230ddf2764513b9a43380fd052ee20004d4ae759))
* Adds documentation links and reorganizes user guides ([ed4b78d](https://github.com/stimm-ai/stimm/commit/ed4b78d18e6f61ecbc5403edf256d1e5e932cdab))
* Adds execute permission to setup_env.sh script ([b6bb321](https://github.com/stimm-ai/stimm/commit/b6bb321dd38db1c0fb437efdd556a0159176872d))
* Adds security note for trusted source download ([dedd0e5](https://github.com/stimm-ai/stimm/commit/dedd0e535039a166b0aec86ba6bf606bf551e7dc))
* fix release process order (push commit before tag) ([4bb0d99](https://github.com/stimm-ai/stimm/commit/4bb0d99c293e356aca07677a515df96e2512fa49))
* **integration:** add development testing guide and cleanup examples ([90f8bf9](https://github.com/stimm-ai/stimm/commit/90f8bf92196b62d78b5115b87f2146b7f178c39a))
* Organizes documentation into logical categories ([95b5bfa](https://github.com/stimm-ai/stimm/commit/95b5bfafa5c9d98aa31c83b03104ad5d9b2bd3a2))
* Remove diagram generation script and add audio-to-audio pipeline diagram to README. ([02fc86c](https://github.com/stimm-ai/stimm/commit/02fc86cd7bee3500485204a888c4b7d8950c0496))
* Removes Discord community links from documentation ([fe38d51](https://github.com/stimm-ai/stimm/commit/fe38d514b6c7214780a9068d12eb136b3d04f68e))
* Removes social media links from documentation ([6a6eba6](https://github.com/stimm-ai/stimm/commit/6a6eba63f9dc6218ba9bba02e286d1400581c6d6))
* Removes WebSocket fallback documentation ([d1b1e8a](https://github.com/stimm-ai/stimm/commit/d1b1e8a6ce30c275fdf7fa95645a2eaeba07fc32))
* renumber and add new phases to the big refactor task list, and delete the old task tracking file. ([8f21b01](https://github.com/stimm-ai/stimm/commit/8f21b01f85d416e61ad7b1514002188bdae75830))
* rewrite README for clarity and link to new documentation ([b7f29f6](https://github.com/stimm-ai/stimm/commit/b7f29f6dc4d79ca2f37ea9ae717abe3fe208344c))
* **task.md:** mark 7 phases as complete and update progress table ([b7d89d7](https://github.com/stimm-ai/stimm/commit/b7d89d7eb05c8bda888823f265919e8de3732821))
* update README with branding and badges ([17b3a64](https://github.com/stimm-ai/stimm/commit/17b3a64ea44bb65e8a3133ca2b36f62eefe692a4))
* Updates documentation for new AI provider integrations ([6d701cb](https://github.com/stimm-ai/stimm/commit/6d701cb52398d7b2e55a7234f0f4ce05e93752c4))
* Updates documentation to reflect Qdrant-only RAG support ([14a3829](https://github.com/stimm-ai/stimm/commit/14a382951ad29f78cb1469008c476621a25386d9))
* Updates documentation to use ruff for code formatting and linting ([a9e201c](https://github.com/stimm-ai/stimm/commit/a9e201c22ef9c9bda697154a416bcf54aecf1284))
* Updates tooling to use ruff instead of black, isort, and flake8 ([58004ab](https://github.com/stimm-ai/stimm/commit/58004ab1bc9a4c54f115c543eefcb5be3c38afeb))
* Updates UI styling and adds favicon ([6bcd093](https://github.com/stimm-ai/stimm/commit/6bcd0933f1619cca33dd2f0699b136e5af30be9a))
