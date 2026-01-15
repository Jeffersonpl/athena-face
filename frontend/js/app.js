
/**
 * Athena Face - Aplicacao Principal (VERSAO AVANCADA)
 * Inclui challenges aleatorios e validacao de tempo
 */

// ==================== CONFIGURACOES ====================
const CONFIG = {
    VIDEO_WIDTH: 640,
    VIDEO_HEIGHT: 480,
    MIN_FACE_RATIO: 0.10,
    MAX_FACE_RATIO: 0.6,
    CENTER_TOLERANCE: 0.20,
    DETECTION_CONFIDENCE: 0.3,

    // Configuracoes de liveness avancadas
    MIN_CHALLENGE_TIME_MS: 500,    // Tempo minimo para completar um challenge
    MAX_CHALLENGE_TIME_MS: 10000,  // Tempo maximo para completar um challenge
    CHALLENGE_TIMEOUT_MS: 15000,   // Timeout total para todos os challenges
    MIN_BLINKS_REQUIRED: 2,        // Numero minimo de piscadas
    BLINK_CHECK_ENABLED: false,    // Habilita verificacao de blink (requer face mesh)

    // Pool de challenges disponiveis
    CHALLENGE_POOL: [
        { action: 'Vire levemente para a ESQUERDA', check: 'turnLeft', icon: '👈' },
        { action: 'Vire levemente para a DIREITA', check: 'turnRight', icon: '👉' },
        { action: 'Incline a cabeca para BAIXO', check: 'tiltDown', icon: '👇' },
        { action: 'Incline a cabeca para CIMA', check: 'tiltUp', icon: '👆' },
        { action: 'Posicao CENTRAL - olhe para frente', check: 'center', icon: '🎯' },
        { action: 'Aproxime-se um pouco', check: 'moveCloser', icon: '🔍' },
        { action: 'Afaste-se um pouco', check: 'moveFarther', icon: '🔭' }
    ],

    // Numero de challenges a serem selecionados
    NUM_CHALLENGES: 4
};

// ==================== GLOBAL STATE ====================
const app = {
    api: null,
    detector: null,
    stream: null,
    detectionInterval: null,

    elements: {
        video: null,
        canvas: null,
        statusCard: null,
        challengeBox: null,
        checksContainer: null,
        videoContainer: null,
        progressFill: null,
        progressLabel: null,
        startBtn: null,
        captureBtn: null,
        retryBtn: null,
        cancelBtn: null,
        tenantName: null,
        checkFace: null,
        checkQuality: null,
        checkPosition: null,
        checkLiveness: null
    },

    state: {
        detectionActive: false,
        checks: {
            faceDetected: false,
            quality: false,
            position: false,
            liveness: false
        },
        liveness: {
            startTime: null,
            frames: [],
            challenges: [],
            selectedChallenges: [],
            currentChallengeIndex: 0,
            challengeCompleted: false,
            challengeStartTime: null,
            blinkCount: 0,
            lastFaceSize: 0
        },
        lastDetection: null,
        securityFlags: {
            tooFastCompletion: false,
            suspiciousMovement: false,
            staticFace: false
        }
    }
};

// ==================== INICIALIZACAO ====================

async function init() {
    console.log('🚀 Iniciando Athena Face...');

    captureElements();
    app.api = new AthenaFaceAPI();

    if (!app.api.isConfigured()) {
        showError('Configuracao Invalida',
            'Parametros obrigatorios: api_key, tenant_id');
        return;
    }

    const tenant = await app.api.getTenantInfo();
    app.elements.tenantName.textContent = tenant.name;

    setupEventListeners();
    updateUIForMode();

    console.log('✅ Athena Face pronto!');
}

function captureElements() {
    app.elements = {
        video: document.getElementById('video'),
        canvas: document.getElementById('canvas-overlay'),
        statusCard: document.getElementById('status-card'),
        challengeBox: document.getElementById('challenge-box'),
        checksContainer: document.getElementById('checks-container'),
        videoContainer: document.getElementById('video-container'),
        progressFill: document.getElementById('progress-fill'),
        progressLabel: document.querySelector('.progress-label'),
        startBtn: document.getElementById('start-btn'),
        captureBtn: document.getElementById('capture-btn'),
        retryBtn: document.getElementById('retry-btn'),
        cancelBtn: document.getElementById('cancel-btn'),
        tenantName: document.getElementById('tenant-name'),
        checkFace: document.getElementById('check-face'),
        checkQuality: document.getElementById('check-quality'),
        checkPosition: document.getElementById('check-position'),
        checkLiveness: document.getElementById('check-liveness')
    };
}

function setupEventListeners() {
    app.elements.startBtn.addEventListener('click', handleStartCapture);
    app.elements.captureBtn.addEventListener('click', handleCapture);
    app.elements.retryBtn.addEventListener('click', handleRetry);
    app.elements.cancelBtn.addEventListener('click', handleCancel);

    window.addEventListener('message', handleMessage);

    window.addEventListener('beforeunload', (e) => {
        if (app.state.detectionActive) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
}

function updateUIForMode() {
    const mode = app.api.mode;

    if (mode === 'register') {
        updateStatus('info', '📝', 'Modo: Cadastro Facial',
            'Vamos cadastrar sua face no sistema');
        app.elements.startBtn.querySelector('.btn-text').textContent = 'Iniciar Cadastro';
    } else if (mode === 'recognize') {
        updateStatus('info', '🔍', 'Modo: Reconhecimento',
            'Vamos verificar sua identidade');
        app.elements.startBtn.querySelector('.btn-text').textContent = 'Iniciar Reconhecimento';
    }
}

/**
 * Seleciona challenges aleatorios do pool
 */
function selectRandomChallenges() {
    // Criar copia do pool e embaralhar
    const shuffled = [...CONFIG.CHALLENGE_POOL].sort(() => Math.random() - 0.5);

    // Garantir que 'center' esteja sempre no final
    const centerChallenge = shuffled.find(c => c.check === 'center');
    const otherChallenges = shuffled.filter(c => c.check !== 'center');

    // Selecionar N-1 challenges aleatorios + center no final
    const selected = otherChallenges.slice(0, CONFIG.NUM_CHALLENGES - 1);

    if (centerChallenge) {
        selected.push(centerChallenge);
    }

    console.log('🎲 Challenges selecionados:', selected.map(c => c.check));
    return selected;
}

// ==================== HANDLERS ====================

async function handleStartCapture() {
    try {
        showLoading(app.elements.startBtn);
        updateStatus('info', '⏳', 'Iniciando camera...', 'Aguarde um momento');

        // Detectar se e mobile
        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

        // Configuracao otimizada de camera
        const constraints = {
            video: {
                width: { ideal: isMobile ? 640 : 1280 },
                height: { ideal: isMobile ? 480 : 720 },
                facingMode: 'user',
                aspectRatio: { ideal: 4/3 }
            },
            audio: false
        };

        console.log('📹 Solicitando camera com constraints:', constraints);

        app.stream = await navigator.mediaDevices.getUserMedia(constraints);

        console.log('✅ Camera obtida:', app.stream.getTracks()[0].getSettings());

        // Configurar video
        app.elements.video.srcObject = app.stream;
        app.elements.video.setAttribute('playsinline', '');
        app.elements.video.setAttribute('autoplay', '');

        // Aguardar video carregar
        await new Promise((resolve, reject) => {
            app.elements.video.onloadedmetadata = () => {
                app.elements.video.play()
                    .then(resolve)
                    .catch(reject);
            };

            setTimeout(() => reject(new Error('Timeout ao carregar video')), 10000);
        });

        console.log('✅ Video carregado:', {
            width: app.elements.video.videoWidth,
            height: app.elements.video.videoHeight
        });

        // Configurar canvas
        app.elements.canvas.width = app.elements.video.videoWidth;
        app.elements.canvas.height = app.elements.video.videoHeight;

        // Selecionar challenges aleatorios
        app.state.liveness.selectedChallenges = selectRandomChallenges();

        // Inicializar deteccao MediaPipe
        await initializeMediaPipe();

        // Atualizar UI
        app.elements.startBtn.style.display = 'none';
        app.elements.videoContainer.style.display = 'block';
        app.elements.captureBtn.style.display = 'flex';
        showChecks();

        app.state.detectionActive = true;
        app.state.liveness.startTime = Date.now();

        updateStatus('info', '👤', 'Posicione seu rosto',
            'Centralize no oval e aguarde as verificacoes');

        hideLoading(app.elements.startBtn);

    } catch (error) {
        console.error('❌ Erro ao iniciar camera:', error);

        let message = 'Erro ao acessar camera';
        let details = error.message;

        if (error.name === 'NotAllowedError') {
            message = 'Permissao de camera negada';
            details = 'Permita acesso a camera nas configuracoes do navegador';
        } else if (error.name === 'NotFoundError') {
            message = 'Camera nao encontrada';
            details = 'Verifique se voce tem uma camera conectada';
        } else if (error.name === 'NotReadableError') {
            message = 'Camera em uso';
            details = 'Feche outros aplicativos que estejam usando a camera';
        }

        updateStatus('error', '❌', message, details);
        hideLoading(app.elements.startBtn);
        showNotification('error', message);
    }
}

/**
 * Inicializa MediaPipe com tratamento de erros
 */
async function initializeMediaPipe() {
    try {
        console.log('🔄 Inicializando MediaPipe...');

        // Verificar se bibliotecas estao carregadas
        if (typeof FaceDetection === 'undefined') {
            throw new Error('MediaPipe Face Detection nao carregado');
        }

        const faceDetection = new FaceDetection({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4/${file}`;
            }
        });

        faceDetection.setOptions({
            model: 'short',
            minDetectionConfidence: CONFIG.DETECTION_CONFIDENCE
        });

        faceDetection.onResults(onFaceDetectionResults);

        // Iniciar loop de deteccao manual (mais confiavel que Camera)
        app.detectionInterval = setInterval(async () => {
            if (app.state.detectionActive && app.elements.video.readyState === 4) {
                try {
                    await faceDetection.send({ image: app.elements.video });
                } catch (error) {
                    console.warn('⚠️ Erro na deteccao:', error);
                }
            }
        }, 100); // 10 FPS

        console.log('✅ MediaPipe inicializado');

    } catch (error) {
        console.error('❌ Erro ao inicializar MediaPipe:', error);
        throw error;
    }
}

async function handleCapture() {
    if (!allChecksPassed()) {
        showNotification('warning', 'Complete todas as verificacoes primeiro');
        return;
    }

    // Verificar flags de seguranca
    if (app.state.securityFlags.tooFastCompletion) {
        showNotification('warning', 'Verificacao muito rapida. Tente novamente.');
        handleRetry();
        return;
    }

    try {
        showLoading(app.elements.captureBtn);
        app.state.detectionActive = false;

        // Parar deteccao
        if (app.detectionInterval) {
            clearInterval(app.detectionInterval);
        }

        updateStatus('info', '⏳', 'Processando...', 'Enviando imagem para analise');

        const blob = await captureFrame();

        // Preparar dados de liveness para o backend
        const livenessData = {
            frames: app.state.liveness.frames,
            challenges: app.state.liveness.challenges,
            totalTime: Date.now() - app.state.liveness.startTime,
            blinkCount: app.state.liveness.blinkCount,
            securityFlags: app.state.securityFlags
        };

        let result;

        if (app.api.mode === 'register') {
            result = await app.api.registerFace(blob, livenessData);
            updateStatus('success', '✅', 'Cadastro realizado!',
                'Seu reconhecimento facial foi configurado');
        } else {
            result = await app.api.recognizeFace(blob);

            if (result.granted) {
                updateStatus('success', '✅', 'Acesso liberado!',
                    `Bem-vindo, ${result.user?.name || 'Usuario'}!`);
            } else {
                updateStatus('error', '❌', 'Acesso negado',
                    'Face nao reconhecida no sistema');
            }
        }

        await app.api.sendCallback(result);

        if (result.success || result.granted) {
            showSuccessAnimation();

            setTimeout(() => {
                if (window.opener) {
                    window.close();
                }
            }, 2000);
        } else {
            app.elements.captureBtn.style.display = 'none';
            app.elements.retryBtn.style.display = 'flex';
        }

    } catch (error) {
        console.error('❌ Erro ao processar:', error);
        updateStatus('error', '❌', 'Erro no processamento', error.message);

        app.elements.captureBtn.style.display = 'none';
        app.elements.retryBtn.style.display = 'flex';

        showNotification('error', error.message);
    } finally {
        hideLoading(app.elements.captureBtn);
    }
}

function handleRetry() {
    resetState();

    app.elements.retryBtn.style.display = 'none';
    app.elements.startBtn.style.display = 'flex';
    app.elements.videoContainer.style.display = 'none';
    hideChecks();

    updateStatus('info', '⏳', 'Pronto para comecar',
        'Clique em "Iniciar" quando estiver pronto');
}

async function handleCancel() {
    if (confirm('Deseja realmente cancelar?')) {
        await app.api.sendCancellation();

        if (window.opener) {
            window.close();
        } else {
            window.history.back();
        }
    }
}

function handleMessage(event) {
    console.log('📨 Mensagem recebida:', event.data);

    if (event.data.type === 'ATHENAFACE_CLOSE') {
        window.close();
    }
}

// ==================== FACE DETECTION ====================

function onFaceDetectionResults(results) {
    const ctx = app.elements.canvas.getContext('2d');
    ctx.clearRect(0, 0, app.elements.canvas.width, app.elements.canvas.height);

    if (!results.detections || results.detections.length === 0) {
        resetChecks(['faceDetected']);
        updateStatus('warning', '⚠️', 'Nenhuma face detectada',
            'Posicione seu rosto no centro da tela');
        updateUI();
        return;
    }

    if (results.detections.length > 1) {
        resetChecks(['faceDetected']);
        updateStatus('warning', '⚠️', 'Multiplas faces detectadas',
            'Certifique-se de estar sozinho');
        updateUI();
        return;
    }

    const detection = results.detections[0];
    app.state.lastDetection = detection;

    processDetection(detection, ctx);
}

function processDetection(detection, ctx) {
    drawBoundingBox(detection, ctx);

    app.state.checks.faceDetected = true;
    app.state.checks.quality = checkQuality(detection);
    app.state.checks.position = checkPosition(detection);

    if (app.state.liveness.startTime && app.state.checks.quality && app.state.checks.position) {
        recordFrame(detection);
        processLiveness(detection);
        checkForStaticFace(detection);
    }

    // Verificar timeout dos challenges
    checkChallengeTimeout();

    updateUI();
}

function checkQuality(detection) {
    const bbox = detection.boundingBox;
    const ratio = bbox.width * bbox.height;

    const isQualityGood = ratio > CONFIG.MIN_FACE_RATIO && ratio < CONFIG.MAX_FACE_RATIO;

    const desc = app.elements.checkQuality.parentElement.querySelector('.check-description');
    if (isQualityGood) {
        desc.textContent = 'Qualidade boa ✓';
    } else if (ratio < CONFIG.MIN_FACE_RATIO) {
        desc.textContent = 'Aproxime-se mais da camera';
    } else {
        desc.textContent = 'Afaste-se um pouco';
    }

    return isQualityGood;
}

function checkPosition(detection) {
    const centerX = detection.boundingBox.xCenter;
    const centerY = detection.boundingBox.yCenter;

    const isPositionGood =
        Math.abs(centerX - 0.5) < CONFIG.CENTER_TOLERANCE &&
        Math.abs(centerY - 0.5) < CONFIG.CENTER_TOLERANCE;

    const desc = app.elements.checkPosition.parentElement.querySelector('.check-description');
    if (isPositionGood) {
        desc.textContent = 'Posicao centralizada ✓';
    } else {
        const offsetX = centerX - 0.5;
        const offsetY = centerY - 0.5;

        if (Math.abs(offsetX) > Math.abs(offsetY)) {
            desc.textContent = offsetX < 0 ? 'Mova para a direita →' : 'Mova para a esquerda ←';
        } else {
            desc.textContent = offsetY < 0 ? 'Mova para baixo ↓' : 'Mova para cima ↑';
        }
    }

    return isPositionGood;
}

// ==================== LIVENESS ====================

function recordFrame(detection) {
    const elapsed = Date.now() - app.state.liveness.startTime;

    app.state.liveness.frames.push({
        time: elapsed,
        position: {
            x: detection.boundingBox.xCenter,
            y: detection.boundingBox.yCenter
        },
        size: detection.boundingBox.width * detection.boundingBox.height,
        score: detection.score[0]
    });

    if (app.state.liveness.frames.length > 120) {
        app.state.liveness.frames.shift();
    }
}

function processLiveness(detection) {
    const centerX = detection.boundingBox.xCenter;
    const centerY = detection.boundingBox.yCenter;
    const faceSize = detection.boundingBox.width * detection.boundingBox.height;

    const challenges = app.state.liveness.selectedChallenges;

    if (app.state.liveness.currentChallengeIndex < challenges.length) {
        showChallenge(centerX, centerY, faceSize);
    }
}

function showChallenge(x, y, faceSize) {
    const challenges = app.state.liveness.selectedChallenges;
    const challenge = challenges[app.state.liveness.currentChallengeIndex];

    // Iniciar timer do challenge se ainda nao iniciou
    if (!app.state.liveness.challengeStartTime) {
        app.state.liveness.challengeStartTime = Date.now();
    }

    updateChallengeBox(challenge);

    if (!app.state.liveness.challengeCompleted && checkChallengeCompleted(challenge.check, x, y, faceSize)) {
        const completionTime = Date.now() - app.state.liveness.challengeStartTime;

        // Verificar se foi muito rapido (possivelmente automatizado)
        if (completionTime < CONFIG.MIN_CHALLENGE_TIME_MS) {
            console.warn('⚠️ Challenge completado muito rapido:', completionTime, 'ms');
            app.state.securityFlags.tooFastCompletion = true;
        }

        completeChallenge(challenge, completionTime);
    }
}

function checkChallengeCompleted(check, x, y, faceSize) {
    const lastSize = app.state.liveness.lastFaceSize || faceSize;
    app.state.liveness.lastFaceSize = faceSize;

    switch(check) {
        case 'turnLeft':
            return x < 0.35;
        case 'turnRight':
            return x > 0.65;
        case 'tiltDown':
            return y > 0.58;
        case 'tiltUp':
            return y < 0.42;
        case 'center':
            return Math.abs(x - 0.5) < 0.12 && Math.abs(y - 0.5) < 0.12;
        case 'moveCloser':
            return faceSize > lastSize * 1.15 && faceSize > 0.15;
        case 'moveFarther':
            return faceSize < lastSize * 0.85 && faceSize < 0.35;
        default:
            return false;
    }
}

function completeChallenge(challenge, completionTime) {
    app.state.liveness.challengeCompleted = true;

    app.state.liveness.challenges.push({
        challenge: challenge.action,
        check: challenge.check,
        completed: true,
        time: Date.now() - app.state.liveness.startTime,
        completionTime: completionTime
    });

    app.elements.challengeBox.style.background = 'linear-gradient(135deg, #10b981, #059669)';
    showNotification('success', `Desafio completado! ${challenge.icon}`);

    setTimeout(() => {
        app.state.liveness.currentChallengeIndex++;
        app.state.liveness.challengeCompleted = false;
        app.state.liveness.challengeStartTime = null;

        const challenges = app.state.liveness.selectedChallenges;

        if (app.state.liveness.currentChallengeIndex >= challenges.length) {
            app.state.checks.liveness = true;
            app.elements.challengeBox.classList.remove('active');
            updateStatus('success', '✓', 'Liveness verificado!',
                'Todas verificacoes de seguranca passaram');
        } else {
            app.elements.challengeBox.style.background =
                'linear-gradient(135deg, var(--primary), var(--secondary))';
        }
    }, 1000);
}

function checkChallengeTimeout() {
    if (!app.state.liveness.startTime) return;

    const totalTime = Date.now() - app.state.liveness.startTime;

    // Timeout total
    if (totalTime > CONFIG.CHALLENGE_TIMEOUT_MS && !app.state.checks.liveness) {
        console.warn('⚠️ Timeout nos challenges');
        showNotification('warning', 'Tempo esgotado. Tente novamente.');
        handleRetry();
    }
}

function checkForStaticFace(detection) {
    const frames = app.state.liveness.frames;
    if (frames.length < 20) return;

    // Verificar se a face esta muito estatica (possivel foto)
    const recentFrames = frames.slice(-20);
    const positions = recentFrames.map(f => f.position);

    let totalMovement = 0;
    for (let i = 1; i < positions.length; i++) {
        const dx = positions[i].x - positions[i-1].x;
        const dy = positions[i].y - positions[i-1].y;
        totalMovement += Math.sqrt(dx*dx + dy*dy);
    }

    const avgMovement = totalMovement / positions.length;

    // Se movimento medio for muito baixo, marcar como suspeito
    if (avgMovement < 0.001) {
        app.state.securityFlags.staticFace = true;
        console.warn('⚠️ Face muito estatica detectada');
    }
}

function updateChallengeBox(challenge) {
    const challenges = app.state.liveness.selectedChallenges;
    const current = app.state.liveness.currentChallengeIndex + 1;
    const total = challenges.length;

    app.elements.challengeBox.classList.add('active');
    app.elements.challengeBox.querySelector('.challenge-icon').textContent = challenge.icon;
    app.elements.challengeBox.querySelector('.challenge-text').textContent = challenge.action;
    app.elements.challengeBox.querySelector('.progress-current').textContent = current;
    app.elements.challengeBox.querySelector('.progress-total').textContent = total;
}

// ==================== DESENHO ====================

function drawBoundingBox(detection, ctx) {
    const bbox = detection.boundingBox;
    const x = bbox.xCenter * app.elements.canvas.width - (bbox.width * app.elements.canvas.width) / 2;
    const y = bbox.yCenter * app.elements.canvas.height - (bbox.height * app.elements.canvas.height) / 2;
    const width = bbox.width * app.elements.canvas.width;
    const height = bbox.height * app.elements.canvas.height;

    const allGood = app.state.checks.quality && app.state.checks.position;
    const color = allGood ? '#10b981' : '#f59e0b';

    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.strokeRect(x, y, width, height);

    const cornerLength = 20;
    ctx.beginPath();
    ctx.moveTo(x, y + cornerLength);
    ctx.lineTo(x, y);
    ctx.lineTo(x + cornerLength, y);
    ctx.moveTo(x + width - cornerLength, y);
    ctx.lineTo(x + width, y);
    ctx.lineTo(x + width, y + cornerLength);
    ctx.moveTo(x + width, y + height - cornerLength);
    ctx.lineTo(x + width, y + height);
    ctx.lineTo(x + width - cornerLength, y + height);
    ctx.moveTo(x + cornerLength, y + height);
    ctx.lineTo(x, y + height);
    ctx.lineTo(x, y + height - cornerLength);
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.stroke();

    ctx.fillStyle = color;
    ctx.font = 'bold 14px Inter';
    ctx.fillText(`${Math.round(detection.score[0] * 100)}%`, x + 5, y - 5);
}

// ==================== UI ====================

function updateUI() {
    updateCheckIcons();
    updateProgress();
}

function updateCheckIcons() {
    updateCheckIcon('face', app.state.checks.faceDetected);
    updateCheckIcon('quality', app.state.checks.quality);
    updateCheckIcon('position', app.state.checks.position);
    updateCheckIcon('liveness', app.state.checks.liveness);
}

function updateCheckIcon(checkName, passed) {
    const element = app.elements[`check${checkName.charAt(0).toUpperCase() + checkName.slice(1)}`];
    element.className = `check-icon ${passed ? 'success' : 'pending'}`;
    element.querySelector('.icon').textContent = passed ? '✓' : '⏳';
}

function updateProgress() {
    const checks = Object.values(app.state.checks);
    const total = checks.length;
    const completed = checks.filter(v => v).length;
    const percentage = (completed / total) * 100;

    app.elements.progressFill.style.width = `${percentage}%`;
    app.elements.progressLabel.textContent = `${Math.round(percentage)}%`;

    app.elements.captureBtn.disabled = !allChecksPassed();
}

function updateStatus(type, icon, text, details = '') {
    app.elements.statusCard.className = `status-card ${type}`;
    app.elements.statusCard.querySelector('.status-icon').textContent = icon;
    app.elements.statusCard.querySelector('.status-text').textContent = text;
    app.elements.statusCard.querySelector('.status-details').textContent = details;
}

// ==================== UTILS ====================

function allChecksPassed() {
    return Object.values(app.state.checks).every(v => v);
}

async function captureFrame() {
    const canvas = document.createElement('canvas');
    canvas.width = app.elements.video.videoWidth;
    canvas.height = app.elements.video.videoHeight;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(app.elements.video, 0, 0);

    return new Promise((resolve) => {
        canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.95);
    });
}

function showLoading(button) {
    button.classList.add('loading');
    button.disabled = true;
}

function hideLoading(button) {
    button.classList.remove('loading');
    button.disabled = false;
}

function showChecks() {
    app.elements.checksContainer.classList.add('visible');
}

function hideChecks() {
    app.elements.checksContainer.classList.remove('visible');
}

function resetChecks(except = []) {
    for (let key in app.state.checks) {
        if (!except.includes(key)) {
            app.state.checks[key] = false;
        }
    }
}

function resetState() {
    app.state.detectionActive = false;
    app.state.checks = {
        faceDetected: false,
        quality: false,
        position: false,
        liveness: false
    };
    app.state.liveness = {
        startTime: null,
        frames: [],
        challenges: [],
        selectedChallenges: [],
        currentChallengeIndex: 0,
        challengeCompleted: false,
        challengeStartTime: null,
        blinkCount: 0,
        lastFaceSize: 0
    };
    app.state.securityFlags = {
        tooFastCompletion: false,
        suspiciousMovement: false,
        staticFace: false
    };

    if (app.detectionInterval) {
        clearInterval(app.detectionInterval);
        app.detectionInterval = null;
    }

    if (app.stream) {
        app.stream.getTracks().forEach(track => track.stop());
        app.stream = null;
    }
}

function showNotification(type, message) {
    const container = document.getElementById('notification-container');

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    container.appendChild(notification);

    setTimeout(() => notification.classList.add('show'), 10);

    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function showSuccessAnimation() {
    const celebration = document.createElement('div');
    celebration.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-size: 100px;
        z-index: 10000;
        animation: iconBounce 1s ease;
    `;
    celebration.textContent = '🎉';

    document.body.appendChild(celebration);

    setTimeout(() => celebration.remove(), 2000);
}

function showError(title, message) {
    updateStatus('error', '❌', title, message);
    app.elements.startBtn.disabled = true;
    showNotification('error', message);
}

// ==================== INIT ====================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
