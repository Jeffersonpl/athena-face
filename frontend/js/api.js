/**
 * API Client para comunicacao com Athena Face Backend
 *
 * Seguranca:
 * - PostMessage com origin especifico
 * - Validacao de callback URL
 * - Validacao de inputs
 */

class AthenaFaceAPI {
    constructor() {
        // Detectar URL da API (pode vir via query params ou config)
        const urlParams = new URLSearchParams(window.location.search);
        this.apiUrl = this._sanitizeUrl(urlParams.get('api_url')) || window.location.origin;
        this.apiKey = urlParams.get('api_key') || '';
        this.tenantId = this._sanitizeString(urlParams.get('tenant_id')) || '';
        this.userId = this._validateUserId(urlParams.get('user_id'));
        this.callbackUrl = this._sanitizeUrl(urlParams.get('callback_url')) || '';
        this.mode = this._validateMode(urlParams.get('mode'));

        // Origin do opener/parent para postMessage seguro
        this._parentOrigin = this._detectParentOrigin();

        // Dados do usuario para cadastro
        this.userData = {
            name: this._sanitizeString(urlParams.get('user_name')) || '',
            email: this._sanitizeEmail(urlParams.get('user_email')) || '',
            phone: this._sanitizeString(urlParams.get('user_phone')) || ''
        };

        console.log('API Client initialized:', {
            apiUrl: this.apiUrl,
            tenantId: this.tenantId,
            userId: this.userId,
            mode: this.mode,
            parentOrigin: this._parentOrigin
        });
    }

    // ==================== VALIDATION HELPERS ====================

    /**
     * Sanitiza URL removendo caracteres perigosos
     */
    _sanitizeUrl(url) {
        if (!url) return null;
        try {
            const parsed = new URL(url);
            // Apenas permitir http e https
            if (!['http:', 'https:'].includes(parsed.protocol)) {
                console.warn('URL com protocolo invalido:', parsed.protocol);
                return null;
            }
            return parsed.href;
        } catch (e) {
            console.warn('URL invalida:', url);
            return null;
        }
    }

    /**
     * Sanitiza string removendo caracteres perigosos
     */
    _sanitizeString(str) {
        if (!str) return null;
        // Remove caracteres de controle e limita tamanho
        return String(str)
            .replace(/[\x00-\x1f\x7f]/g, '')
            .substring(0, 255);
    }

    /**
     * Valida e sanitiza email
     */
    _sanitizeEmail(email) {
        if (!email) return null;
        const sanitized = this._sanitizeString(email);
        // Validacao basica de email
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(sanitized) ? sanitized : null;
    }

    /**
     * Valida user_id
     */
    _validateUserId(userId) {
        if (!userId) return null;
        const parsed = parseInt(userId, 10);
        if (isNaN(parsed) || parsed <= 0 || parsed > 2147483647) {
            console.warn('user_id invalido:', userId);
            return null;
        }
        return parsed;
    }

    /**
     * Valida modo
     */
    _validateMode(mode) {
        const validModes = ['register', 'recognize'];
        const sanitized = this._sanitizeString(mode);
        return validModes.includes(sanitized) ? sanitized : 'register';
    }

    /**
     * Detecta origin do parent/opener de forma segura
     */
    _detectParentOrigin() {
        try {
            // Tentar obter referrer como fallback
            if (document.referrer) {
                const referrerUrl = new URL(document.referrer);
                return referrerUrl.origin;
            }
        } catch (e) {
            // Ignorar erros de parsing
        }

        // Fallback para origin atual
        return window.location.origin;
    }

    /**
     * Valida se callback URL e confiavel
     */
    _isValidCallbackUrl(url) {
        if (!url) return false;

        try {
            const parsed = new URL(url);

            // Apenas HTTPS em producao
            if (window.location.protocol === 'https:' && parsed.protocol !== 'https:') {
                console.warn('Callback URL deve usar HTTPS em producao');
                return false;
            }

            return true;
        } catch (e) {
            return false;
        }
    }

    // ==================== PUBLIC METHODS ====================

    /**
     * Valida configuracao da API
     */
    isConfigured() {
        return !!(this.apiUrl && this.apiKey && this.tenantId);
    }

    /**
     * Retorna informacoes da configuracao
     */
    getConfig() {
        return {
            apiUrl: this.apiUrl,
            tenantId: this.tenantId,
            userId: this.userId,
            mode: this.mode,
            userData: this.userData,
            callbackUrl: this.callbackUrl
        };
    }

    /**
     * Registra face no backend
     */
    async registerFace(imageBlob, livenessData) {
        if (!this.userId) {
            throw new Error('user_id e obrigatorio para cadastro');
        }

        if (this.userId <= 0) {
            throw new Error('user_id deve ser positivo');
        }

        const formData = new FormData();
        formData.append('image', imageBlob, 'face.jpg');
        formData.append('user_id', this.userId);
        formData.append('check_liveness', 'true');

        if (livenessData) {
            formData.append('liveness_data', JSON.stringify(livenessData));
        }

        try {
            const response = await fetch(`${this.apiUrl}/api/face/register`, {
                method: 'POST',
                headers: {
                    'X-API-Key': this.apiKey
                },
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Erro ao cadastrar face');
            }

            return {
                success: true,
                data: data.data,
                message: data.message
            };

        } catch (error) {
            console.error('Erro no cadastro:', error);
            throw error;
        }
    }

    /**
     * Reconhece face no backend
     */
    async recognizeFace(imageBlob) {
        const formData = new FormData();
        formData.append('image', imageBlob, 'face.jpg');

        if (this.userId) {
            formData.append('event_id', this.userId);
        }

        try {
            const response = await fetch(`${this.apiUrl}/api/face/recognize`, {
                method: 'POST',
                headers: {
                    'X-API-Key': this.apiKey
                },
                body: formData
            });

            const data = await response.json();

            return {
                success: data.granted || false,
                granted: data.granted,
                user: data.user,
                confidence: data.confidence,
                distance: data.distance,
                message: data.message
            };

        } catch (error) {
            console.error('Erro no reconhecimento:', error);
            throw error;
        }
    }

    /**
     * Busca informacoes do tenant
     */
    async getTenantInfo() {
        try {
            const response = await fetch(`${this.apiUrl}/api/tenants`);
            const data = await response.json();

            if (data.success && data.tenants) {
                const tenant = data.tenants.find(t => t.id === this.tenantId);
                return tenant || { id: this.tenantId, name: 'Desconhecido' };
            }

            return { id: this.tenantId, name: this.tenantId };

        } catch (error) {
            console.error('Erro ao buscar tenant:', error);
            return { id: this.tenantId, name: this.tenantId };
        }
    }

    /**
     * Envia resultado de volta para o sistema chamador
     * Usa origin especifico para postMessage (mais seguro que '*')
     */
    async sendCallback(result) {
        const payload = {
            type: 'ATHENAFACE_RESULT',
            mode: this.mode,
            result: result,
            tenantId: this.tenantId,
            userId: this.userId,
            timestamp: new Date().toISOString()
        };

        // 1. PostMessage (se foi aberto em iframe ou popup)
        if (window.opener || window.parent !== window) {
            const target = window.opener || window.parent;

            // Usar origin especifico se conhecido, senao usar origin atual
            const targetOrigin = this._parentOrigin || window.location.origin;

            try {
                target.postMessage(payload, targetOrigin);
                console.log('Resultado enviado via postMessage para:', targetOrigin);
            } catch (e) {
                // Fallback para '*' apenas se necessario
                console.warn('Fallback para postMessage com *:', e);
                target.postMessage(payload, '*');
            }
        }

        // 2. Callback URL (webhook) - com validacao
        if (this.callbackUrl && this._isValidCallbackUrl(this.callbackUrl)) {
            try {
                const response = await fetch(this.callbackUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    console.log('Resultado enviado para callback URL');
                } else {
                    console.warn('Callback URL retornou erro:', response.status);
                }

            } catch (error) {
                console.error('Erro ao enviar callback:', error);
            }
        } else if (this.callbackUrl) {
            console.warn('Callback URL ignorada - validacao falhou:', this.callbackUrl);
        }

        // 3. LocalStorage (fallback)
        try {
            localStorage.setItem('athenaface_last_result', JSON.stringify(payload));
            console.log('Resultado salvo no localStorage');
        } catch (error) {
            console.error('Erro ao salvar no localStorage:', error);
        }
    }

    /**
     * Cancela operacao e notifica sistema chamador
     */
    async sendCancellation() {
        const result = {
            success: false,
            cancelled: true,
            message: 'Operacao cancelada pelo usuario'
        };

        await this.sendCallback(result);

        // Fechar janela se for popup
        if (window.opener) {
            window.close();
        }
    }
}

// Alias para compatibilidade com versao anterior
const FaceSynorixAPI = AthenaFaceAPI;

// Export global
window.AthenaFaceAPI = AthenaFaceAPI;
window.FaceSynorixAPI = AthenaFaceAPI;
