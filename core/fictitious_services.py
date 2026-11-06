"""Implantação reproduzível com identidades fictícias por comandos canônicos."""

import datetime as dt
import secrets

from base.exceptions import BusinessRuleViolationError
from base.services import BaseService, system_command
from core.fictitious import require_fictitious
from core.fictitious_selectors import FictitiousSelector


def fictional_cpf(number):
    digits = [int(char) for char in f"90000{number:04d}"]
    for size in (10, 11):
        remainder = (
            sum(value * weight for value, weight in zip(digits, range(size, 1, -1), strict=True))
            % 11
        )
        digits.append(0 if remainder < 2 else 11 - remainder)
    return "".join(map(str, digits))


class FictitiousSetupService(BaseService):
    @system_command
    def create_platform(self):
        """Primeiro operador existe apenas no banco reservado do ensaio, sem senha fixa."""
        from core.models import CustomUser
        from tenancy.contracts import Domain, School

        require_fictitious(schema="public")
        if CustomUser.all_objects.exists() or School.all_objects.exists():
            raise BusinessRuleViolationError("O ensaio exige banco fictício recém-migrado.")
        school = School.objects.create(schema_name="public", name="Plataforma fictícia")
        domain = Domain.objects.create(tenant=school, domain="platform.localhost", is_primary=True)
        password = secrets.token_urlsafe(24)
        user = CustomUser.objects.create_user(
            email="operator@example.test",
            password=password,
            is_superuser=True,
            is_staff=True,
            first_name="Operador",
            last_name="Fictício",
        )
        for obj in (school, domain, user):
            self._record_audit("INSERT", obj)
        self._log("fictitious_platform_created", user_id=str(user.pk))
        return user, password

    @system_command
    def activate_account(self, account, kind):
        from accounts.services import AccountService
        from accounts.staff_services import StaffAccountService
        from guardians.invitation_services import GuardianInvitationService

        require_fictitious(recipient=account.email)
        from notifications.outbox_selectors import OutboxSelector
        from notifications.outbox_services import OutboxService

        for delivery_id in list(OutboxSelector.pending_ids(limit=1000)):
            OutboxService().dispatch(delivery_id)
        token = FictitiousSelector.invitation(account.pk)
        password = secrets.token_urlsafe(24)
        activate = {
            "staff": StaffAccountService().activate_staff_invitation,
            "teacher": AccountService().activate_teacher_invitation,
            "guardian": GuardianInvitationService().activate_invitation,
        }[kind]
        account = activate(token, password)
        return account, {"id": str(account.pk), "email": account.email, "password": password}

    @system_command
    def create_population(self, administrator):
        from academic_calendar.services import CalendarService
        from accounts.staff_services import StaffAccountService
        from classes.services import ClassService
        from enrollments.services import EnrollmentApplicationService
        from guardians.invitation_services import GuardianInvitationService
        from service_requests.configuration_services import ServiceConfigurationService
        from students.import_services import AssistedImportService
        from teachers.services import SubjectService, TeacherService

        require_fictitious()
        credentials, people = {}, {"ADMIN": administrator}
        for key, role in (
            ("SUBSTITUTE", "ADMIN"),
            ("SECRETARY", "SECRETARY"),
            ("COORDINATOR", "COORDINATOR"),
            ("FINANCE", "FINANCE"),
        ):
            account = StaffAccountService(user=administrator).create_staff_user(
                {
                    "first_name": key.title(),
                    "last_name": "Fictício",
                    "email": f"{key.lower()}@example.test",
                    "role_name": role,
                }
            )
            people[key], credentials[key] = self.activate_account(account, "staff")
        today = dt.date.today()
        CalendarService(user=administrator).create_academic_year(
            {
                "name": str(today.year),
                "start_date": dt.date(today.year, 1, 1),
                "end_date": dt.date(today.year, 12, 31),
                "status": "ACTIVE",
            }
        )
        subject = SubjectService(user=administrator).create_subject(
            {"name": "Vivências infantis", "code": "INF", "workload": 200}
        )
        classes = []
        for index in (1, 2):
            teacher = TeacherService(user=administrator).create_teacher(
                {
                    "first_name": f"Professor {index}",
                    "last_name": "Fictício",
                    "email": f"teacher{index}@example.test",
                    "birth_date": dt.date(1990, 1, 1),
                    "hire_date": dt.date(today.year, 1, 1),
                    "gender": "NI",
                    "cpf": fictional_cpf(index),
                    "rg_number": f"FICTICIO{index}",
                    "phone_mobile": "11900000000",
                    "subjects": [subject],
                    "accepts_email_notifications": True,
                }
            )
            people[f"TEACHER{index}"], credentials[f"TEACHER{index}"] = self.activate_account(
                teacher.user, "teacher"
            )
            classes.append(
                ClassService(user=administrator).create_class(
                    {
                        "name": f"Infantil {index}",
                        "education_stage": "EARLY_CHILDHOOD",
                        "grade": "EARLY_PRE_1",
                        "academic_year": today.year,
                        "shift": "MORNING",
                        "class_teacher_id": teacher.pk,
                        "max_students": 20,
                    }
                )
            )
        files = self._files(today.year)
        imported = AssistedImportService(user=administrator)
        preview = imported.preview_import("piloto-ipe-integral", files)
        batch = imported.import_batch("piloto-ipe-integral", files)
        students = FictitiousSelector.imported_objects(batch, "students.Student")
        guardians = FictitiousSelector.imported_objects(batch, "guardians.Guardian")
        if any(student.user_id or student.email for student in students.values()) or any(
            guardian.user_id for guardian in guardians.values()
        ):
            raise BusinessRuleViolationError("A carga fictícia criou acesso indevido.")
        enrollment = EnrollmentApplicationService(user=people["SECRETARY"])
        for index, student in enumerate(students.values()):
            application = enrollment.create_application(
                {
                    "student_id": student.pk,
                    "application_type": "NEW",
                    "target_class_id": classes[index % 2].pk,
                }
            )
            application = enrollment.submit_application(
                application.pk, expected_version=application.version
            )
            application = enrollment.approve_application(
                application.pk, expected_version=application.version
            )
            enrollment.finalize_application(application.pk, expected_version=application.version)
        for key in ("G1", "G2"):
            account = GuardianInvitationService(user=administrator).send_invitation(
                guardians[key].pk
            )
            people[key], credentials[key] = self.activate_account(account, "guardian")
        config = ServiceConfigurationService(user=administrator)
        config.update_calendar(
            {
                "version": 0,
                "weekdays": [0, 1, 2, 3, 4],
                "opens_at": dt.time(8),
                "closes_at": dt.time(18),
                "closed_dates": [],
                "immediate_contact": "Contato fictício: procure a equipe de treinamento.",
            }
        )
        for key in ("SECRETARY", "COORDINATOR", "FINANCE"):
            config.update_department(
                key, enabled=True, user_ids=[people[key].pk, administrator.pk], version=0
            )
        self._log(
            "fictitious_population_created", student_count=len(students), class_count=len(classes)
        )
        return {
            "credentials": credentials,
            "people": people,
            "students": students,
            "classes": classes,
            "preview": preview,
        }

    @staticmethod
    def _files(year):
        from students.import_validation import COLUMNS

        students = [
            f"S{index},Criança {index},Fictícia,{year - 4}-01-01,NI,,,,," for index in (1, 2, 3)
        ]
        guardians = [
            f"G{index},Responsável {index},Fictício,1990-01-01,NI,{fictional_cpf(index + 10)},"
            f"FICTICIO{index},11900000000,{f'family{index}@example.test' if index < 3 else ''}"
            for index in (1, 2, 3)
        ]
        links = [
            "S1,G1,LEGAL,1,1,1",
            "S2,G1,LEGAL,1,1,1",
            "S3,G2,LEGAL,1,1,1",
            "S1,G3,OUTRO,0,0,1",
            "S1,G2,LEGAL,0,1,1",
        ]
        return {
            key: ",".join(COLUMNS[key]) + "\n" + "\n".join(rows) + "\n"
            for key, rows in (("students", students), ("guardians", guardians), ("links", links))
        }
