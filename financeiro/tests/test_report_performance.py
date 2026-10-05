"""Paginação determinística e streaming tenant-scoped do relatório."""

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from base import context
from base.tests.factories import StudentFactory
from financeiro.models import BillingEntry
from financeiro.selectors import BillingSelector


@pytest.mark.django_db
def test_paginate_and_stream_every_overdue_group(client, user):
    for _ in range(23):
        BillingEntry.objects.create(
            student=StudentFactory(first_name="Same", last_name="Name"),
            description="Fee",
            principal_value=10,
            due_date=timezone.localdate() - dt.timedelta(days=1),
        )
    selector = BillingSelector(user=user)
    first = selector.overdue_details()
    second = selector.overdue_details(page=2)
    assert first.total == 23 and len(first.items) == 20 and len(second.items) == 3
    assert len({row["student_id"] for row in first.items + second.items}) == 23
    assert selector.overdue_details(page_size=1000).page_size == 100
    client.force_login(user)
    response = client.get(reverse("finance_overdue_report"), {"page": 2}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert b'id="overdue-details"' in response.content
    assert b"<!DOCTYPE" not in response.content
    response = client.get(reverse("finance_overdue_report"), {"format": "csv"})
    assert response.streaming
    token = context.current_tenant.set("other_school")
    try:
        payload = b"".join(response.streaming_content)
        assert context.current_tenant.get() == "other_school"
    finally:
        context.current_tenant.reset(token)
    assert len(payload.decode().splitlines()) == 24


def _assert_overdue_snapshot_after_payment(user, schema, pay=None):
    """A payment between batches must not remove the unconsumed 501st group."""
    from itertools import islice

    from students.models import Student

    students = Student.objects.bulk_create(StudentFactory.build_batch(501))
    BillingEntry.objects.bulk_create(
        [
            BillingEntry(
                student=student,
                description="Streaming snapshot",
                principal_value=10,
                due_date=timezone.localdate() - dt.timedelta(days=1),
            )
            for student in students
        ]
    )
    stream = BillingSelector(user=user).iter_overdue_details(tenant_schema=schema)
    original_context = context.current_tenant.get()
    try:
        first = list(islice(stream, 500))
        assert len(first) == 500
        assert context.current_tenant.get() == original_context
        billing_id = BillingEntry.objects.get(student_id=first[0]["student_id"]).pk
        if pay:
            pay(billing_id)
        else:
            BillingEntry.objects.filter(pk=billing_id).update(
                paid_value=10, paid_principal_value=10
            )
        remaining = list(stream)
        assert len(remaining) == 1
        assert {row["student_id"] for row in first + remaining} == {
            student.pk for student in students
        }
        assert context.current_tenant.get() == original_context
    finally:
        stream.close()


@pytest.mark.django_db
def test_stream_preserves_all_groups_when_payment_changes_an_emitted_batch(user):
    _assert_overdue_snapshot_after_payment(user, "test_school")
