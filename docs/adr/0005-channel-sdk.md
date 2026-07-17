# ADR-0005 — Channel SDK para Comunicação com Provedores Externos

**Status:** Aceito; a escolha do provedor de e-mail foi atualizada pelo ADR-0014
**Data:** 2026-06-29

## Contexto

O módulo `notifications/` envia mensagens por e-mail e mantém o WhatsApp preparado como canal
futuro. Cada provedor possui API diferente. O código inicial continha chamadas diretas a
`django.core.mail.send_mail` e stubs espalhados em tasks Celery, gerando duplicação e dificultando
a troca de provedores. Web Push foi adiado; a PWA permanece apenas instalável e offline.

## Decisão

**Adotar o padrão Channel SDK**: cada canal de comunicação implementa a interface `BaseChannel` com um único método `send()` que retorna `ChannelResult`. Toda lógica de renderização de template, criação de `MessageLog` e retry fica no `MessageTransport`, que orquestra o canal.

### Estrutura

```
notifications/
├── channels/
│   ├── base.py        — BaseChannel (ABC), ChannelResult (dataclass)
│   ├── email.py       — EmailChannel → Resend API
│   └── whatsapp.py    — WhatsAppChannel → stub (twilio plugável)
├── transport.py       — MessageTransport (render + send + log + retry)
└── tasks.py           — Celery wrappers finos → chamam transport
```

### Interface

```python
class BaseChannel(ABC):
    channel_name: str

    @abstractmethod
    def send(self, recipient_address: str, subject: str, body: str, **meta) -> ChannelResult:
        ...

@dataclass
class ChannelResult:
    success: bool
    channel: str
    recipient_address: str
    error_message: str = ""
```

### Contrato

1. **Todo canal implementa `BaseChannel`** — novo provedor = nova classe, sem alterar tasks ou transport.
2. **`MessageTransport` é o orquestrador único** de renderização e envio;
   `MessageDeliveryService` é o único responsável por persistir e reconciliar `MessageLog`.
3. **Configuração segura do provedor** — secrets ficam em variáveis de ambiente; configurações não
   secretas e remetentes verificados podem ficar em `School.settings`.

## Consequências

### Positivas

- **Plugabilidade**: trocar Twilio por Z-API requer apenas implementar `WhatsAppChannel.send()`.
- **Testabilidade**: `BaseChannel` pode ser mockado; `MessageTransport` testável com canal fake.
- **Zero duplicação**: `MessageLog.objects.create()` aparece somente em `MessageDeliveryService`.
- **Segurança**: credenciais isoladas por Tenant, nunca hardcoded.

### Negativas

- Abstração adiciona uma camada extra de indireção (3 arquivos vs 1 monolítico).
- O transporte precisa persistir o log antes da rede e reconciliar o resultado depois, sem manter
  uma transação aberta durante a chamada externa.

## Alternativas consideradas

1. **Chamadas diretas nas tasks Celery** (rejeitada) — acoplamento com provedor, código duplicado por canal, difícil testar.
2. **Adapter pattern com herança** (rejeitada) — excessivamente complexo para a variedade atual de canais (2 ativos, 2 planejados).
3. **Django signals para log** (rejeitada) — adiciona acoplamento invisível, difícil rastrear fluxo.

## Referências

- `docs/03_ENGINEERING_RULES.md` — "Toda dependência externa deve ser abstraída atrás de uma interface"
- `docs/10_CODING_STANDARDS.md` — DRY, KISS
- `notifications/channels/base.py` — implementação de referência
