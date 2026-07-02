"""Views HTMX para o modulo de frequencia."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from attendance.forms import AttendanceRecordForm, JustificationForm
from attendance.selectors import AttendanceSelector, JustificationSelector
from attendance.services import AttendanceService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from classes.selectors import ClassSelector
from students.selectors import StudentSelector

logger = logging.getLogger(__name__)


@login_required
def attendance_records_list(request):
    """Lista registros de chamada com filtros por turma."""
    class_id = request.GET.get("class_obj") or None
    records = AttendanceSelector().list_records(class_id=class_id)
    return render(request, "attendance/records_list.html", {"records": records})


@login_required
def attendance_record_create(request):
    """Abre uma nova chamada (cria entradas pré-presente para todos os alunos)."""
    form = AttendanceRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cd = form.cleaned_data
            record = AttendanceService(user=request.user).open_attendance(
                {
                    "class_id": cd["class_obj"].pk,
                    "subject_id": cd["subject"].pk,
                    "teacher_id": cd["teacher"].pk,
                    "date": cd["date"],
                    "lesson_number": cd.get("lesson_number", 1),
                    "notes": cd.get("notes", ""),
                }
            )
            return redirect("attendance_record_fill", record_id=record.pk)
        except ValidationError as exc:
            for field, errs in exc.errors.items():
                for e in errs:
                    form.add_error(field if field != "__all__" else None, e)
    return render(
        request,
        "attendance/record_form.html",
        {"form": form, "title": "Abrir Chamada"},
    )


@login_required
def attendance_record_fill(request, record_id):
    """Tela de chamada bulk: lista alunos com radio presente/ausente/justificado."""
    record, entries = AttendanceSelector().get_record_with_entries(record_id)
    if record is None:
        from django.http import Http404

        raise Http404("Registro de chamada nao encontrado.")

    if request.method == "POST":
        entries_data = AttendanceService.parse_attendance_post(request.POST, entries)
        try:
            AttendanceService(user=request.user).record_attendance(record_id, entries_data)
        except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
            logger.warning(
                "Erro ao registrar chamada: %s", exc, extra={"record_id": str(record_id)}
            )
            messages.error(request, str(exc))
            return render(
                request,
                "attendance/record_fill.html",
                {"record": record, "entries": entries},
            )
        return redirect("attendance_records_list")

    return render(request, "attendance/record_fill.html", {"record": record, "entries": entries})


@login_required
def class_attendance_summary(request, class_id):
    """Resumo de frequência por aluno de uma turma (com alunos em risco)."""
    cls = ClassSelector().get_by_id(class_id)
    summary = AttendanceSelector().get_class_attendance_summary(cls.pk)
    return render(
        request,
        "attendance/summary.html",
        {"class_obj": cls, "summary": summary["summary"], "at_risk": summary["at_risk"]},
    )


@login_required
def student_attendance(request, student_id, class_id=None):
    """Histórico de frequência de um aluno."""
    student = StudentSelector().get_by_id(student_id)
    entries = AttendanceSelector().get_student_attendance(student_id, class_id=class_id)
    rate = None
    if class_id:
        rate = AttendanceSelector().get_student_attendance_rate(student_id, class_id)
    return render(
        request,
        "attendance/student_attendance.html",
        {"student": student, "entries": entries, "rate": rate, "class_id": class_id},
    )


@login_required
def students_at_risk(request):
    """Tela de alunos em risco (abaixo de 75%), filtro por turma."""
    from classes.selectors import ClassSelector

    classes = ClassSelector().list_ordered()
    selected = request.GET.get("class_obj")
    at_risk: list = []
    cls = None
    if selected:
        cls = ClassSelector().get_by_id(selected)
        at_risk = AttendanceSelector().get_students_at_risk(cls.pk)
    return render(
        request,
        "attendance/at_risk.html",
        {"classes": classes, "selected": selected, "cls": cls, "at_risk": at_risk},
    )


@login_required
def justifications_list(request):
    """Lista justificativas de ausência; filtra por situação via ?status=."""
    status = request.GET.get("status") or None
    justs = JustificationSelector().list_justifications(status=status)
    return render(request, "attendance/justifications_list.html", {"justifications": justs})


@login_required
def justification_create(request):
    """Submissão de justificativa por responsável/aluno."""
    form = JustificationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            cd = form.cleaned_data
            AttendanceService(user=request.user).submit_justification(
                {
                    "student_id": cd["student"].pk,
                    "start_date": cd["start_date"],
                    "end_date": cd["end_date"],
                    "reason": cd["reason"],
                }
            )
            return redirect("justifications_list")
        except ValidationError as exc:
            for field, errs in exc.errors.items():
                for e in errs:
                    form.add_error(field if field != "__all__" else None, e)
    return render(
        request,
        "attendance/justification_form.html",
        {"form": form, "title": "Nova Justificativa"},
    )


@login_required
def justification_approve(request, pk):
    """Coordenador aprova justificativa pendente."""
    if request.method != "POST":
        return redirect("justifications_list")
    try:
        AttendanceService(user=request.user).approve_justification(pk)
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        logger.warning("Erro ao aprovar justificativa: %s", exc, extra={"pk": str(pk)})
        messages.error(request, str(exc))
    return redirect("justifications_list")


@login_required
def justification_reject(request, pk):
    """Coordenador rejeita justificativa pendente."""
    if request.method != "POST":
        return redirect("justifications_list")
    try:
        AttendanceService(user=request.user).reject_justification(
            pk, request.POST.get("reason", "")
        )
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        logger.warning("Erro ao rejeitar justificativa: %s", exc, extra={"pk": str(pk)})
        messages.error(request, str(exc))
    return redirect("justifications_list")
