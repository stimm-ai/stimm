/**
 * AudioStreamer - Module partagé pour le streaming audio en temps réel
 * 
 * Ce module centralise la logique de lecture audio pour les interfaces TTS et Voicebot
 * en éliminant la duplication de code entre les deux interfaces.
 * 
 * Fonctionnalités :
 * - Gestion unifiée d'AudioContext
 * - File d'attente audio avec lecture séquentielle
 * - Décodage PCM et WAV
 * - Gestion d'erreurs avec méthodes alternatives
 * - Suivi de latence et métriques
 */

class AudioStreamer {
    /**
     * Crée une instance d'AudioStreamer
     * @param {Object} options - Options de configuration
     * @param {number} options.sampleRate - Taux d'échantillonnage par défaut (utilise les constantes du fournisseur)
     * @param {string} options.encoding - Encodage audio par défaut (utilise les constantes du fournisseur)
     * @param {Function} options.onPlaybackStart - Callback déclenché au début de la lecture
     * @param {Function} options.onPlaybackEnd - Callback déclenché à la fin de la lecture
     * @param {Function} options.onError - Callback pour les erreurs de lecture
     */
    constructor(options = {}) {
        this.options = {
            sampleRate: 44100, // Valeur par défaut temporaire, sera remplacée par les constantes du fournisseur
            encoding: 'pcm_s16le', // Valeur par défaut temporaire
            onPlaybackStart: () => {},
            onPlaybackEnd: () => {},
            onError: () => {},
            ...options
        };

        // État du streaming audio
        this.audioContext = null;
        this.audioQueue = [];
        this.isPlayingAudio = false;
        this.audioChunkCounter = 0;
        this.playbackStarted = false;
        this.firstAudioChunkReceived = false;

        // Métriques de performance
        this.metrics = {
            firstChunkLatency: null,
            playbackStartLatency: null,
            totalChunksPlayed: 0,
            totalBytesPlayed: 0
        };

        this.initialize();
    }

    /**
     * Initialise l'AudioStreamer
     */
    async initialize() {
        console.log('🎵 AudioStreamer initialisé');
        
        // Charger les constantes du fournisseur depuis l'API
        try {
            const response = await fetch('/api/provider-constants');
            if (response.ok) {
                const providerConstants = await response.json();
                this.providerConstants = providerConstants;
                console.log('✅ Constantes du fournisseur chargées:', providerConstants);
            } else {
                console.warn('⚠️ Impossible de charger les constantes du fournisseur, utilisation des valeurs par défaut');
            }
        } catch (error) {
            console.warn('⚠️ Erreur lors du chargement des constantes du fournisseur:', error);
        }
    }

    /**
     * Ajoute un chunk audio à la file d'attente
     * @param {ArrayBuffer|Blob} audioData - Données audio à jouer
     * @param {Object} metadata - Métadonnées optionnelles (latence, etc.)
     */
    addAudioChunk(audioData, metadata = {}) {
        // Suivi du premier chunk pour la latence
        if (!this.firstAudioChunkReceived) {
            this.firstAudioChunkReceived = true;
            this.metrics.firstChunkLatency = metadata.latency || Date.now();
            console.log(`⏱️ Premier chunk audio reçu après ${this.metrics.firstChunkLatency}ms`);
        }

        this.audioChunkCounter++;
        this.metrics.totalChunksPlayed++;
        
        if (audioData.byteLength) {
            this.metrics.totalBytesPlayed += audioData.byteLength;
        }

        console.log(`🎵 Chunk audio ${this.audioChunkCounter} ajouté: ${audioData.byteLength || audioData.size} bytes`);

        // Ajouter à la file d'attente
        this.audioQueue.push(audioData);

        // Démarrer la lecture si pas déjà en cours
        if (!this.isPlayingAudio) {
            this.playAudioQueue();
        }
    }

    /**
     * Lit tous les chunks audio dans la file d'attente
     */
    async playAudioQueue() {
        if (this.isPlayingAudio || this.audioQueue.length === 0) return;

        this.isPlayingAudio = true;

        // Suivi du début de lecture
        if (!this.playbackStarted) {
            this.playbackStarted = true;
            this.metrics.playbackStartLatency = Date.now();
            this.options.onPlaybackStart();
            console.log('🎵 Début de la lecture audio');
        }

        // Initialiser l'AudioContext si nécessaire
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            console.log('🎵 AudioContext initialisé');
        }

        // Reprendre l'AudioContext si suspendu (requis par les navigateurs)
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
            console.log('🎵 AudioContext repris');
        }

        // Lire tous les chunks dans la file d'attente
        while (this.audioQueue.length > 0) {
            const audioData = this.audioQueue.shift();

            try {
                console.log(`🎵 Lecture du chunk audio: ${audioData.byteLength || audioData.size} bytes`);
                await this.playAudioDirect(audioData);
            } catch (error) {
                console.error('❌ Échec de lecture du chunk audio:', error);
                await this.tryAlternativePlayback(audioData);
            }
        }

        this.isPlayingAudio = false;
        this.options.onPlaybackEnd();
        console.log('🎵 Lecture audio terminée');
    }

    /**
     * Méthode principale de lecture audio basée sur la configuration
     * @param {ArrayBuffer|Blob} audioData - Données audio à jouer
     */
    async playAudioDirect(audioData) {
        // Convertir en ArrayBuffer si c'est un Blob
        let arrayBuffer;
        if (audioData instanceof Blob) {
            arrayBuffer = await audioData.arrayBuffer();
        } else {
            arrayBuffer = audioData;
        }

        console.log(`🎵 Lecture audio: ${arrayBuffer.byteLength} bytes, encoding: ${this.options.encoding}, sampleRate: ${this.options.sampleRate}`);

        try {
            // Basé sur l'encoding configuré
            if (this.options.encoding === 'pcm_s16le' || this.options.encoding === 'linear16') {
                // Décoder comme PCM 16-bit little-endian
                const audioBuffer = this.audioContext.createBuffer(1, arrayBuffer.byteLength / 2, this.options.sampleRate);
                const channelData = audioBuffer.getChannelData(0);
                
                // Convertir Int16 en Float32
                const int16Array = new Int16Array(arrayBuffer);
                for (let i = 0; i < int16Array.length; i++) {
                    channelData[i] = int16Array[i] / 32768.0;
                }
                
                const source = this.audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.audioContext.destination);
                
                await new Promise((resolve) => {
                    source.onended = () => {
                        console.log('🎵 Chunk PCM terminé');
                        resolve();
                    };
                    source.start();
                    console.log('🎵 Chunk PCM démarré');
                });
                
            } else if (this.options.encoding === 'mp3') {
                // Décoder comme MP3
                const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
                const source = this.audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.audioContext.destination);
                
                await new Promise((resolve) => {
                    source.onended = () => {
                        console.log('🎵 Chunk MP3 terminé');
                        resolve();
                    };
                    source.start();
                    console.log('🎵 Chunk MP3 démarré');
                });
                
            } else {
                // Fallback: décodage générique (pour WAV, etc.)
                const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
                const source = this.audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.audioContext.destination);
                
                await new Promise((resolve) => {
                    source.onended = () => {
                        console.log('🎵 Chunk générique terminé');
                        resolve();
                    };
                    source.start();
                    console.log('🎵 Chunk générique démarré');
                });
            }
            
        } catch (error) {
            console.log('🔄 Échec du décodage principal, essai en méthode alternative...');
            throw error; // Laisser la méthode alternative gérer
        }
    }

    /**
     * Méthode alternative de lecture (décodage WAV)
     * @param {ArrayBuffer|Blob} audioData - Données audio à jouer
     */
    async tryAlternativePlayback(audioData) {
        console.log('🔄 Essai de méthode de lecture alternative...');
        try {
            // Convertir en ArrayBuffer si c'est un Blob
            let arrayBuffer;
            if (audioData instanceof Blob) {
                arrayBuffer = await audioData.arrayBuffer();
            } else {
                arrayBuffer = audioData;
            }
            
            // Essayer de décoder en WAV
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);
            
            await new Promise((resolve) => {
                source.onended = resolve;
                source.start();
            });
            
            console.log('✅ Lecture alternative réussie');
        } catch (error) {
            console.error('❌ Lecture alternative échouée:', error);
            this.options.onError(error);
        }
    }

    /**
     * Arrête la lecture audio et vide la file d'attente
     */
    stopPlayback() {
        console.log('🛑 Arrêt de la lecture audio');
        
        // Vider la file d'attente
        this.audioQueue = [];
        this.isPlayingAudio = false;
        
        // Réinitialiser l'état
        this.firstAudioChunkReceived = false;
        this.audioChunkCounter = 0;
        this.playbackStarted = false;
        
        console.log('✅ Lecture audio arrêtée');
    }

    /**
     * Nettoie les ressources audio
     */
    cleanup() {
        this.stopPlayback();
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
            console.log('🧹 AudioContext fermé');
        }
        
        // Réinitialiser les métriques
        this.metrics = {
            firstChunkLatency: null,
            playbackStartLatency: null,
            totalChunksPlayed: 0,
            totalBytesPlayed: 0
        };
    }

    /**
     * Met à jour la configuration de l'AudioStreamer
     * @param {Object} newConfig - Nouvelle configuration
     */
    updateConfig(newConfig) {
        this.options = {
            ...this.options,
            ...newConfig
        };
        
        // Si des constantes de fournisseur sont disponibles, les utiliser pour les valeurs par défaut
        if (this.providerConstants && newConfig.provider) {
            const providerType = newConfig.providerType || 'tts'; // 'tts' ou 'stt'
            const providerName = newConfig.provider;
            
            if (this.providerConstants[providerType] && this.providerConstants[providerType][providerName]) {
                const providerConfig = this.providerConstants[providerType][providerName];
                
                // Mettre à jour les valeurs par défaut avec les constantes du fournisseur
                if (providerConfig.SAMPLE_RATE && !this.options.sampleRate) {
                    this.options.sampleRate = providerConfig.SAMPLE_RATE;
                }
                if (providerConfig.ENCODING && !this.options.encoding) {
                    this.options.encoding = providerConfig.ENCODING;
                }
                
                console.log(`🎵 Configuration mise à jour avec les constantes de ${providerName}:`, {
                    sampleRate: this.options.sampleRate,
                    encoding: this.options.encoding
                });
            }
        }
        
        console.log('🎵 AudioStreamer configuration updated:', this.options);
    }

    /**
     * Récupère les métriques de performance
     * @returns {Object} Métriques de performance
     */
    getMetrics() {
        return {
            ...this.metrics,
            currentQueueSize: this.audioQueue.length,
            isPlaying: this.isPlayingAudio,
            totalChunks: this.audioChunkCounter
        };
    }

    /**
     * Vérifie si la lecture est en cours
     * @returns {boolean} True si en cours de lecture
     */
    isPlaying() {
        return this.isPlayingAudio;
    }

    /**
     * Récupère la taille de la file d'attente
     * @returns {number} Nombre de chunks en attente
     */
    getQueueSize() {
        return this.audioQueue.length;
    }
}

// Export pour usage module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AudioStreamer;
}

// Export global pour usage navigateur
window.AudioStreamer = AudioStreamer;