"""Propagação automática de contexto operacional nas tarefas Celery."""

from celery.signals import before_task_publish, task_postrun, task_prerun

from base import context


@before_task_publish.connect
def add_operational_context(headers=None, **kwargs) -> None:
    """Copia correlation ID e schema corrente para os headers da mensagem."""
    if headers is None:
        return
    headers.setdefault(
        "correlation_id",
        context.correlation_id.get() or context.generate_correlation_id(),
    )
    headers.setdefault("tenant_schema", context.current_tenant.get() or "public")


@task_prerun.connect
def activate_operational_context(task=None, **kwargs) -> None:
    """Ativa os headers no worker antes do corpo da tarefa."""
    if task is None:
        return
    headers = getattr(task.request, "headers", None) or {}
    tokens = (
        context.correlation_id.set(
            headers.get("correlation_id") or context.generate_correlation_id()
        ),
        context.current_tenant.set(headers.get("tenant_schema") or "public"),
    )
    task.request._schools_context_tokens = tokens


@task_postrun.connect
def reset_operational_context(task=None, **kwargs) -> None:
    """Evita que workers reutilizados vazem contexto para a próxima tarefa."""
    if task is None:
        return
    tokens = getattr(task.request, "_schools_context_tokens", None)
    if not tokens:
        return
    context.correlation_id.reset(tokens[0])
    context.current_tenant.reset(tokens[1])
    del task.request._schools_context_tokens
