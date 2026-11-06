"""Ciclo de arquivos de imagem subordinado aos comandos transacionais."""

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from base.exceptions import BusinessRuleViolationError, ValidationError
from base.images import normalize_image

logger = logging.getLogger(__name__)
_journal = ContextVar("image_command_journal", default=None)


def _discard(storage, name: str, check_references=True) -> None:
    try:
        from base.ports import media_is_referenced

        if not check_references or not media_is_referenced(storage, name):
            storage.delete(name)
    except Exception:
        logger.warning("image_cleanup_failed", extra={"reason_code": "storage_delete"})


@contextmanager
def image_command_scope():
    """Compensa falhas do próprio comando; comandos filhos têm journals isolados."""
    parent = _journal.get()
    entries = []
    token = _journal.set(entries)
    try:
        yield
    except BaseException:
        for storage, name, committed, check_references in reversed(entries):
            if not committed[0]:
                _discard(storage, name, check_references)
        raise
    else:
        if parent is not None:
            parent.extend(entries)
    finally:
        _journal.reset(token)


def transactional_image_command(method):
    """Envolve inclusive a saída de atomic para compensar falhas de constraints."""

    @wraps(method)
    def wrapped(*args, **kwargs):
        with image_command_scope():
            with transaction.atomic():
                return method(*args, **kwargs)

    return wrapped


def image_updates(instance, data: dict, field_name: str) -> dict:
    """Salva o upload normalizado explicitamente, inclusive para QuerySet.update."""
    upload = data.get(field_name)
    if not upload or getattr(upload, "_committed", False):
        return {}
    if not hasattr(upload, "read"):
        raise ValidationError(errors={field_name: ["Envie um arquivo de imagem válido."]})
    try:
        normalized = normalize_image(upload, logo=field_name == "logo")
    except DjangoValidationError as exc:
        raise ValidationError(errors={field_name: exc.messages}) from exc
    entries = _journal.get()
    if entries is None:
        raise BusinessRuleViolationError("Imagem exige um comando transacional.")
    field = instance._meta.get_field(field_name)
    original_path = field.generate_filename(instance, "image.webp")
    from base.media import image_namespace

    directory = original_path.rsplit("/", 1)[0]
    _, category = directory.split("/", 1)
    from django.conf import settings
    from django.db import connection

    from base.context import current_tenant

    namespace = getattr(instance, "schema_name", "") or (
        current_tenant.get() if settings.TESTING else connection.schema_name
    )
    directory = f"{image_namespace(namespace)}/{category}"
    name = f"{directory}/optimized/v1/{uuid.uuid4().hex}.webp"
    committed = [False]
    # Registra antes da escrita para compensar também falhas parciais do backend.
    entry = [field.storage, name, committed, True]
    entries.append(entry)
    try:
        entry[1] = field.storage.save(name, normalized, max_length=field.max_length)
    except Exception as exc:
        raise ValidationError(errors={field_name: ["Não foi possível salvar a imagem."]}) from exc
    transaction.on_commit(lambda: committed.__setitem__(0, True))
    old_name = getattr(instance, field_name).name
    if old_name and old_name != entry[1]:
        from base.media import delete_replaced_file_after_commit

        delete_replaced_file_after_commit(field.storage, old_name, entry[1], check_references=True)
    return {field_name: entry[1]}


def register_command_artifact(storage, name):
    """Compensa arquivo privado temporário se o próprio comando/commit falhar.

    O chamador não pode aceitar transação externa: Django não oferece callback
    de rollback para um atomic arbitrário que englobe o comando.
    """
    entries = _journal.get()
    if entries is None:
        raise BusinessRuleViolationError("Artefato exige comando transacional.")
    committed = [False]
    entries.append((storage, name, committed, False))
    transaction.on_commit(lambda: committed.__setitem__(0, True))
