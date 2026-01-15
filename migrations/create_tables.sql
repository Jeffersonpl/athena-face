-- Migration: Criar tabelas para Athena Face
-- Execute este script em CADA banco de dados de tenant

-- Tabela de reconhecimentos faciais
CREATE TABLE IF NOT EXISTS facial_recognitions (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    face_embedding JSON NOT NULL COMMENT 'Embedding de 512 dimensões',
    image_path VARCHAR(255) NULL COMMENT 'Caminho da imagem de referência',
    confidence_score FLOAT DEFAULT 0 COMMENT 'Score de qualidade da imagem',
    liveness_passed BOOLEAN DEFAULT FALSE COMMENT 'Passou no teste de liveness',
    liveness_score FLOAT DEFAULT 0 COMMENT 'Score do liveness detection',
    verified_at TIMESTAMP NULL COMMENT 'Data da última verificação',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_user_id (user_id),
    INDEX idx_liveness (liveness_passed),
    INDEX idx_verified (verified_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela de logs de acesso
CREATE TABLE IF NOT EXISTS access_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NULL COMMENT 'ID do usuário (NULL se não reconhecido)',
    event_id BIGINT UNSIGNED NULL COMMENT 'ID do evento',
    turnstile_id INT NULL COMMENT 'ID da catraca',
    recognition_method ENUM('facial', 'qrcode', 'manual', 'card') DEFAULT 'facial',
    match_confidence FLOAT NULL COMMENT 'Confiança do match (0-1)',
    match_distance FLOAT NULL COMMENT 'Distância euclidiana',
    image_path VARCHAR(255) NULL COMMENT 'Imagem capturada',
    status ENUM('granted', 'denied', 'suspicious', 'error') DEFAULT 'granted',
    failure_reason VARCHAR(255) NULL COMMENT 'Motivo da falha',
    notes TEXT NULL COMMENT 'Observações adicionais',
    ip_address VARCHAR(45) NULL COMMENT 'IP da requisição',
    processing_time_ms INT NULL COMMENT 'Tempo de processamento em ms',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_user_created (user_id, created_at),
    INDEX idx_event_created (event_id, created_at),
    INDEX idx_status (status),
    INDEX idx_method (recognition_method),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela para garantir que users existe (caso não exista no banco)
CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    has_facial_recognition BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_email (email),
    INDEX idx_facial (has_facial_recognition)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;