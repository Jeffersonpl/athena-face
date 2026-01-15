/**
 * MediaPipe Face Detection Integration
 */

class MediaPipeFaceDetector {
    constructor() {
        this.faceDetection = null;
        this.camera = null;
        this.onResultsCallback = null;
        this.isActive = false;
    }

    /**
     * Inicializa MediaPipe Face Detection
     */
    async initialize(videoElement, onResults) {
        this.onResultsCallback = onResults;

        try {
            // Criar instância do Face Detection
            this.faceDetection = new FaceDetection({
                locateFile: (file) => {
                    return `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4/${file}`;
                }
            });

            // Configurar opções
            this.faceDetection.setOptions({
                model: 'short', // 'short' para faces próximas (< 2m)
                minDetectionConfidence: 0.5
            });

            // Callback de resultados
            this.faceDetection.onResults((results) => {
                if (this.isActive && this.onResultsCallback) {
                    this.onResultsCallback(results);
                }
            });

            // Inicializar câmera
            this.camera = new Camera(videoElement, {
                onFrame: async () => {
                    if (this.isActive) {
                        await this.faceDetection.send({ image: videoElement });
                    }
                },
                width: 1280,
                height: 720
            });

            console.log('✅ MediaPipe inicializado com sucesso');
            return true;

        } catch (error) {
            console.error('❌ Erro ao inicializar MediaPipe:', error);
            throw error;
        }
    }

    /**
     * Inicia detecção
     */
    async start() {
        if (!this.camera) {
            throw new Error('MediaPipe não foi inicializado');
        }

        this.isActive = true;
        await this.camera.start();
        console.log('▶️ Detecção iniciada');
    }

    /**
     * Para detecção
     */
    stop() {
        this.isActive = false;

        if (this.camera) {
            this.camera.stop();
        }

        console.log('⏸️ Detecção pausada');
    }

    /**
     * Libera recursos
     */
    dispose() {
        this.stop();

        if (this.faceDetection) {
            this.faceDetection.close();
            this.faceDetection = null;
        }

        this.camera = null;
        this.onResultsCallback = null;

        console.log('🗑️ MediaPipe recursos liberados');
    }
}

// Export global
window.MediaPipeFaceDetector = MediaPipeFaceDetector;