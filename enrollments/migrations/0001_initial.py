import base.media
import base.upload_validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('classes', '0002_initial'),
        ('students', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentRequirement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('version', models.PositiveIntegerField(default=0)),
                ('application_type', models.CharField(choices=[('NEW', 'Nova matrícula'), ('REENROLLMENT', 'Rematrícula'), ('INTERNAL_TRANSFER', 'Transferência interna'), ('INBOUND_TRANSFER', 'Transferência recebida'), ('OUTBOUND_TRANSFER', 'Transferência de saída')], max_length=30, verbose_name='Tipo de solicitação')),
                ('code', models.SlugField(verbose_name='Código')),
                ('label', models.CharField(max_length=120, verbose_name='Documento')),
                ('is_required', models.BooleanField(default=True, verbose_name='Obrigatório')),
                ('allows_physical', models.BooleanField(default=False, verbose_name='Aceita conferência física')),
                ('display_order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_deleted', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Requisito documental',
                'verbose_name_plural': 'Requisitos documentais',
                'ordering': ['application_type', 'display_order', 'label'],
            },
        ),
        migrations.CreateModel(
            name='EnrollmentApplication',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('version', models.PositiveIntegerField(default=0)),
                ('academic_year', models.PositiveIntegerField(verbose_name='Ano letivo')),
                ('application_number', models.CharField(max_length=20, unique=True, verbose_name='Protocolo')),
                ('application_type', models.CharField(choices=[('NEW', 'Nova matrícula'), ('REENROLLMENT', 'Rematrícula'), ('INTERNAL_TRANSFER', 'Transferência interna'), ('INBOUND_TRANSFER', 'Transferência recebida'), ('OUTBOUND_TRANSFER', 'Transferência de saída')], default='NEW', max_length=30, verbose_name='Tipo de solicitação')),
                ('status', models.CharField(choices=[('PRE_ENROLLMENT', 'Pré-matrícula'), ('CORRECTION_REQUIRED', 'Correção necessária'), ('UNDER_REVIEW', 'Em análise'), ('WAITLISTED', 'Lista de espera'), ('APPROVED', 'Aprovada'), ('ENROLLED', 'Matriculada'), ('TRANSFERRED', 'Transferida'), ('REJECTED', 'Recusada'), ('CANCELLED', 'Cancelada')], default='PRE_ENROLLMENT', max_length=30, verbose_name='Situação')),
                ('priority', models.PositiveSmallIntegerField(default=0, verbose_name='Prioridade')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Observações')),
                ('origin_school', models.CharField(blank=True, default='', max_length=200, verbose_name='Escola de origem')),
                ('destination_school', models.CharField(blank=True, default='', max_length=200, verbose_name='Escola de destino')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Revisado em')),
                ('waitlisted_at', models.DateTimeField(blank=True, null=True, verbose_name='Entrada na espera')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_deleted', to=settings.AUTH_USER_MODEL)),
                ('result_enrollment', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='result_application', to='classes.enrollment', verbose_name='Matrícula resultante')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_enrollment_applications', to=settings.AUTH_USER_MODEL, verbose_name='Revisado por')),
                ('source_enrollment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='source_applications', to='classes.enrollment', verbose_name='Matrícula de origem')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='enrollment_applications', to='students.student', verbose_name='Aluno')),
                ('target_class', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='enrollment_applications', to='classes.class', verbose_name='Turma de destino')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Solicitação de matrícula',
                'verbose_name_plural': 'Solicitações de matrícula',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EnrollmentReminder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('version', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('PENDING', 'Pendente'), ('SENDING', 'Enviando'), ('SENT', 'Enviado'), ('FAILED', 'Falhou')], default='PENDING', max_length=10, verbose_name='Situação')),
                ('message_log_id', models.UUIDField(blank=True, null=True, verbose_name='Log de mensagem')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Enviado em')),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reminders', to='enrollments.enrollmentapplication', verbose_name='Solicitação')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_deleted', to=settings.AUTH_USER_MODEL)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='enrollment_reminders', to=settings.AUTH_USER_MODEL, verbose_name='Destinatário')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Lembrete documental',
                'verbose_name_plural': 'Lembretes documentais',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EnrollmentTransition',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('version', models.PositiveIntegerField(default=0)),
                ('from_status', models.CharField(blank=True, default='', max_length=30, verbose_name='De')),
                ('to_status', models.CharField(choices=[('PRE_ENROLLMENT', 'Pré-matrícula'), ('CORRECTION_REQUIRED', 'Correção necessária'), ('UNDER_REVIEW', 'Em análise'), ('WAITLISTED', 'Lista de espera'), ('APPROVED', 'Aprovada'), ('ENROLLED', 'Matriculada'), ('TRANSFERRED', 'Transferida'), ('REJECTED', 'Recusada'), ('CANCELLED', 'Cancelada')], max_length=30, verbose_name='Para')),
                ('reason', models.TextField(blank=True, default='', verbose_name='Motivo')),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='enrollment_transitions', to=settings.AUTH_USER_MODEL, verbose_name='Ator')),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transitions', to='enrollments.enrollmentapplication', verbose_name='Solicitação')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_deleted', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Transição de matrícula',
                'verbose_name_plural': 'Transições de matrícula',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='StudentDocument',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('version', models.PositiveIntegerField(default=0)),
                ('requirement_code', models.SlugField(verbose_name='Código do requisito')),
                ('requirement_label', models.CharField(max_length=120, verbose_name='Documento')),
                ('is_required', models.BooleanField(default=True, verbose_name='Obrigatório')),
                ('allows_physical', models.BooleanField(default=False, verbose_name='Aceita conferência física')),
                ('status', models.CharField(choices=[('PENDING', 'Pendente'), ('SUBMITTED', 'Entregue'), ('VERIFIED', 'Verificado'), ('REJECTED', 'Recusado'), ('WAIVED', 'Dispensado')], default='PENDING', max_length=20, verbose_name='Situação')),
                ('delivery_method', models.CharField(blank=True, choices=[('DIGITAL', 'Digital'), ('PHYSICAL', 'Físico')], default='', max_length=10, verbose_name='Forma de entrega')),
                ('file', models.FileField(blank=True, null=True, storage=base.media.get_private_storage, upload_to=base.media.TenantMediaPath('documents/enrollments'), validators=[base.upload_validators.validate_document_upload], verbose_name='Arquivo')),
                ('decision_reason', models.TextField(blank=True, default='', verbose_name='Motivo')),
                ('verified_at', models.DateTimeField(blank=True, null=True, verbose_name='Verificado em')),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='documents', to='enrollments.enrollmentapplication', verbose_name='Solicitação')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_deleted', to=settings.AUTH_USER_MODEL)),
                ('requirement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='snapshots', to='enrollments.documentrequirement', verbose_name='Requisito de origem')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_updated', to=settings.AUTH_USER_MODEL)),
                ('verified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_enrollment_documents', to=settings.AUTH_USER_MODEL, verbose_name='Verificado por')),
            ],
            options={
                'verbose_name': 'Documento de matrícula',
                'verbose_name_plural': 'Documentos de matrícula',
                'ordering': ['requirement_label'],
            },
        ),
        migrations.AddConstraint(
            model_name='documentrequirement',
            constraint=models.UniqueConstraint(condition=models.Q(('is_active', True)), fields=('application_type', 'code'), name='uniq_active_document_requirement_type_code'),
        ),
        migrations.AddIndex(
            model_name='enrollmentapplication',
            index=models.Index(fields=['status', '-priority', 'created_at'], name='enrollments_status_22b4c9_idx'),
        ),
        migrations.AddIndex(
            model_name='enrollmentapplication',
            index=models.Index(fields=['application_number'], name='enrollments_applica_62070b_idx'),
        ),
        migrations.AddIndex(
            model_name='enrollmentapplication',
            index=models.Index(fields=['student', 'academic_year'], name='enrollments_student_e878a6_idx'),
        ),
        migrations.AddIndex(
            model_name='enrollmentapplication',
            index=models.Index(fields=['target_class', 'status'], name='enrollments_target__cecb80_idx'),
        ),
        migrations.AddConstraint(
            model_name='enrollmentapplication',
            constraint=models.UniqueConstraint(condition=models.Q(('is_active', True), ('status__in', ['PRE_ENROLLMENT', 'CORRECTION_REQUIRED', 'UNDER_REVIEW', 'WAITLISTED', 'APPROVED'])), fields=('student', 'academic_year'), name='uniq_open_enrollment_application_student_year'),
        ),
        migrations.AddConstraint(
            model_name='enrollmentreminder',
            constraint=models.UniqueConstraint(condition=models.Q(('is_active', True)), fields=('application', 'recipient'), name='uniq_active_enrollment_reminder_recipient'),
        ),
        migrations.AddIndex(
            model_name='enrollmenttransition',
            index=models.Index(fields=['application', 'created_at'], name='enrollments_applica_31f1e2_idx'),
        ),
        migrations.AddIndex(
            model_name='studentdocument',
            index=models.Index(fields=['application', 'status'], name='enrollments_applica_7b65ed_idx'),
        ),
        migrations.AddIndex(
            model_name='studentdocument',
            index=models.Index(fields=['application', 'is_required'], name='enrollments_applica_f3b439_idx'),
        ),
        migrations.AddConstraint(
            model_name='studentdocument',
            constraint=models.UniqueConstraint(condition=models.Q(('is_active', True)), fields=('application', 'requirement_code'), name='uniq_active_application_document_code'),
        ),
    ]
