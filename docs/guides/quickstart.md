# Guia de Inicio Rapido - Athena Face

Aprenda a usar o Athena Face em 5 minutos.

## 1. Subir o Servico

```bash
# Clonar
git clone https://github.com/Jeffersonpl/athena-face.git
cd athena-face

# Configurar
cp .env.example .env

# Iniciar
docker-compose up -d
```

## 2. Verificar se esta Rodando

```bash
curl http://localhost:8001/health
```

Resposta esperada:
```json
{"status": "healthy", "model": "buffalo_l"}
```

## 3. Acessar a Interface

Abra no navegador:
```
http://localhost:8001/facial?api_key=demo_api_key_12345&tenant_id=DEMO&user_id=1&mode=register
```

## 4. Cadastrar uma Face

1. Permita acesso a webcam
2. Complete os challenges (virar cabeca, etc)
3. Aguarde a mensagem de sucesso

## 5. Testar Reconhecimento

Mude o modo para `recognize`:
```
http://localhost:8001/facial?api_key=demo_api_key_12345&tenant_id=DEMO&mode=recognize
```

## 6. Usar via API

### Registrar
```bash
curl -X POST http://localhost:8001/api/face/register \
  -H "X-API-Key: demo_api_key_12345" \
  -F "image=@sua_foto.jpg" \
  -F "user_id=1"
```

### Reconhecer
```bash
curl -X POST http://localhost:8001/api/face/recognize \
  -H "X-API-Key: demo_api_key_12345" \
  -F "image=@sua_foto.jpg"
```

## Proximo Passos

- [Configurar seu proprio Tenant](tenants.md)
- [Entender o Liveness Detection](liveness.md)
- [Referencia completa da API](../api/reference.md)

## Precisa de Ajuda?

- **Email**: jefferson@jeffersonpl.dev
- **Issues**: https://github.com/Jeffersonpl/athena-face/issues
