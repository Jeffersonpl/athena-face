# Casos de Uso - Athena Face

Este documento descreve os principais casos de uso do sistema Athena Face.

## Diagrama de Casos de Uso

```mermaid
graph TB
    subgraph Atores
        U[Usuario Final]
        A[Administrador]
        D[Desenvolvedor]
        S[Sistema Externo]
    end

    subgraph "Athena Face"
        UC1[UC01: Registrar Face]
        UC2[UC02: Verificar Identidade]
        UC3[UC03: Comparar Faces]
        UC4[UC04: Validar Liveness]
        UC5[UC05: Gerenciar Tenant]
        UC6[UC06: Gerar API Key]
        UC7[UC07: Integrar via API]
        UC8[UC08: Consultar Metricas]
    end

    U --> UC1
    U --> UC2
    U --> UC4
    A --> UC5
    A --> UC6
    A --> UC8
    D --> UC7
    S --> UC2
    S --> UC3

    UC1 -.-> UC4
    UC2 -.-> UC4
```

---

## UC01: Controle de Acesso em Eventos

### Descricao
Sistema de controle de acesso para eventos utilizando reconhecimento facial para validar a entrada de participantes.

### Atores
- **Participante**: Pessoa que deseja entrar no evento
- **Operador**: Funcionario que monitora o acesso
- **Sistema de Ingressos**: Sistema externo que gerencia vendas

### Pre-condicoes
- Participante comprou ingresso e fez pre-cadastro facial
- Totem/camera configurado na entrada

### Fluxo Principal

```mermaid
sequenceDiagram
    participant P as Participante
    participant T as Totem
    participant AF as Athena Face
    participant SI as Sistema Ingressos
    participant C as Catraca

    P->>T: Aproxima-se do totem
    T->>T: Detecta face
    T->>AF: POST /api/face/recognize
    AF->>AF: Extrai embedding
    AF->>AF: Busca match (1:N)

    alt Face reconhecida
        AF-->>T: {matched: true, user_id: X}
        T->>SI: Verifica ingresso(user_id)
        SI-->>T: {valido: true, tipo: VIP}
        T->>C: Libera catraca
        T->>P: "Bem-vindo, Joao!"
    else Face nao reconhecida
        AF-->>T: {matched: false}
        T->>P: "Face nao cadastrada"
    end
```

### Fluxos Alternativos

**FA01 - Liveness falha**
1. Sistema detecta possivel spoofing
2. Solicita nova captura
3. Apos 3 tentativas, aciona operador

**FA02 - Ingresso invalido**
1. Face reconhecida mas ingresso invalido
2. Direciona para bilheteria

### Pos-condicoes
- Acesso registrado no log de auditoria
- Metrica de tempo de verificacao coletada

### Requisitos Nao-Funcionais
- Tempo de resposta: < 2 segundos
- Disponibilidade: 99.9%
- Taxa de falsos positivos: < 0.1%

---

## UC02: Verificacao de Identidade (KYC)

### Descricao
Processo de Know Your Customer para verificar a identidade de usuarios em onboarding de servicos financeiros.

### Atores
- **Cliente**: Pessoa abrindo conta
- **Sistema Bancario**: Plataforma do banco
- **Compliance**: Equipe de conformidade

### Pre-condicoes
- Cliente possui documento com foto
- Aplicativo do banco instalado

### Fluxo Principal

```mermaid
sequenceDiagram
    participant C as Cliente
    participant App as App Banco
    participant AF as Athena Face
    participant OCR as Servico OCR
    participant DB as Database

    C->>App: Inicia abertura de conta
    App->>C: Solicita foto do documento

    C->>App: Envia foto do RG/CNH
    App->>OCR: Extrai dados do documento
    OCR-->>App: {nome, cpf, foto_doc}

    App->>C: Solicita selfie
    C->>App: Tira selfie com liveness

    App->>AF: POST /api/face/compare
    Note over AF: image1: foto_documento<br/>image2: selfie

    AF->>AF: Extrai embeddings
    AF->>AF: Calcula similaridade

    alt Faces correspondem
        AF-->>App: {match: true, similarity: 0.94}
        App->>DB: Registra verificacao OK
        App->>C: "Identidade verificada!"
    else Faces diferentes
        AF-->>App: {match: false, similarity: 0.32}
        App->>C: "Verificacao falhou"
    end
```

### Metricas de Sucesso
| Metrica | Meta |
|---------|------|
| Taxa de aprovacao | > 85% |
| Falsos positivos | < 0.01% |
| Tempo medio | < 30s |

---

## UC03: Autenticacao Biometrica

### Descricao
Substituir senha por reconhecimento facial para login em sistemas.

### Atores
- **Usuario**: Funcionario da empresa
- **Sistema Corporativo**: ERP, CRM, etc.

### Fluxo Principal

```mermaid
sequenceDiagram
    participant U as Usuario
    participant W as Web App
    participant AF as Athena Face
    participant AD as Active Directory

    U->>W: Acessa sistema
    W->>U: Exibe tela de login facial

    U->>W: Captura face
    W->>AF: POST /api/face/recognize

    AF->>AF: Verifica liveness
    AF->>AF: Busca embedding

    alt Usuario encontrado
        AF-->>W: {matched: true, user_id: "joao.silva"}
        W->>AD: Valida usuario ativo
        AD-->>W: {ativo: true, grupos: ["admin"]}
        W->>W: Cria sessao
        W->>U: Redireciona para dashboard
    else Usuario nao encontrado
        AF-->>W: {matched: false}
        W->>U: "Acesso negado"
    end
```

### Requisitos de Seguranca
- MFA opcional (face + token)
- Bloqueio apos 5 tentativas falhas
- Log de todas as tentativas

---

## UC04: Registro de Ponto por Face

### Descricao
Sistema de registro de ponto utilizando reconhecimento facial.

### Fluxo Principal

```mermaid
sequenceDiagram
    participant F as Funcionario
    participant R as Relogio Ponto
    participant AF as Athena Face
    participant RH as Sistema RH

    F->>R: Aproxima-se
    R->>AF: POST /api/face/recognize
    AF-->>R: {matched: true, user_id: 456}

    R->>RH: Registra ponto(user_id, timestamp, tipo)
    RH-->>R: OK

    R->>F: "Ponto registrado: 08:00"
```

### Regras de Negocio
- Intervalo minimo entre registros: 1 minuto
- Tolerancia de horario: +/- 10 minutos
- Foto armazenada para auditoria

---

## UC05: Busca de Pessoas Desaparecidas

### Descricao
Busca em banco de dados de pessoas desaparecidas a partir de foto.

### Fluxo Principal

```mermaid
sequenceDiagram
    participant A as Agente
    participant S as Sistema
    participant AF as Athena Face
    participant BD as Banco Desaparecidos

    A->>S: Upload foto
    S->>AF: POST /api/face/recognize
    Note over AF: tenant: policia<br/>threshold: 0.5

    AF->>BD: Busca embeddings
    BD-->>AF: 50.000 embeddings

    AF->>AF: Compara 1:N
    AF-->>S: matches[{user_id, similarity, dados}]

    S->>A: Exibe possiveis matches
```

---

## UC06: Anti-Fraude em Atendimento

### Descricao
Verificar se a pessoa no atendimento e a mesma do cadastro.

### Fluxo

```mermaid
flowchart TD
    A[Cliente chega] --> B[Atendente solicita documento]
    B --> C[Sistema busca foto do cadastro]
    C --> D[Captura foto ao vivo]
    D --> E{Faces correspondem?}
    E -->|Sim| F[Prossegue atendimento]
    E -->|Nao| G[Alerta de fraude]
    G --> H[Aciona seguranca]
```

---

## Matriz de Casos de Uso x Endpoints

| Caso de Uso | Endpoint Principal | Metodo |
|-------------|-------------------|--------|
| Controle de Acesso | `/api/face/recognize` | POST |
| KYC | `/api/face/compare` | POST |
| Autenticacao | `/api/face/recognize` | POST |
| Registro de Ponto | `/api/face/recognize` | POST |
| Busca Desaparecidos | `/api/face/recognize` | POST |
| Anti-Fraude | `/api/face/compare` | POST |
| Cadastro Inicial | `/api/face/register` | POST |

---

## Requisitos por Caso de Uso

| Caso de Uso | Liveness | Threshold | SLA |
|-------------|----------|-----------|-----|
| Controle Acesso | Basico | 0.4 | 2s |
| KYC | Avancado | 0.5 | 5s |
| Autenticacao | Basico | 0.4 | 1s |
| Registro Ponto | Opcional | 0.4 | 2s |
| Busca Desaparecidos | Nao | 0.5 | 10s |
| Anti-Fraude | Avancado | 0.45 | 3s |
