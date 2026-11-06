"""Captura local privada, explicitamente fictícia; nenhum envio pela rede."""

import hashlib
import json
import os

from django.core.serializers.json import DjangoJSONEncoder

from base.exceptions import BusinessRuleViolationError
from core.fictitious import require_fictitious
from notifications.channels.base import BaseChannel, ChannelResult


def capture_local_message(*, recipient, subject, body, identity, schema):
    root = require_fictitious(schema=schema, recipient=recipient)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    folder = root / "messages"
    if folder.is_symlink():
        raise BusinessRuleViolationError("Diretório de captura inválido.")
    folder.mkdir(mode=0o700, exist_ok=True)
    folder.chmod(0o700)
    digest = hashlib.sha256(f"{schema}:{identity}".encode()).hexdigest()
    payload = json.dumps(
        {
            "environment": "fictitious",
            "schema": schema,
            "recipient": recipient,
            "subject": subject,
            "body": body,
        },
        cls=DjangoJSONEncoder,
        ensure_ascii=False,
        sort_keys=True,
    ).encode()
    target = folder / f"{digest}.json"
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if target.is_symlink() or target.read_bytes() != payload:
            raise BusinessRuleViolationError(
                "A identidade da captura local possui outro conteúdo."
            ) from None
    else:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
    return f"local-{digest}"


class LocalFixtureEmailChannel(BaseChannel):
    channel_name = "EMAIL"

    def send(self, recipient_address, subject, body, **meta):
        identity = capture_local_message(
            recipient=recipient_address,
            subject=subject,
            body=body,
            identity=meta["idempotency_key"],
            schema=meta["tenant_schema"],
        )
        return ChannelResult(
            success=True,
            channel="EMAIL",
            recipient_address=recipient_address,
            provider_message_id=identity,
            status_code=200,
        )
