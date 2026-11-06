"""Allowlist explícita de exportação; novos campos exigem revisão e inclusão deliberada."""

FIELDS = {
    "core.BusinessUnit": (
        "name cnpj legal_name trade_name state_registration municipal_registration phone "
        "email contact_full_name contact_role contact_phone contact_email "
        "academic_year_start academic_year_end "
    ).split(),
    "core.RegistrationSequence": ("scope year current_value ").split(),
    "core.Role": ("name ").split(),
    "core.RoleModuleAccess": (
        "role_id module_key can_view can_create can_edit can_deactivate "
    ).split(),
    "core.CustomUser": (
        "last_login is_superuser email first_name last_name phone role_id is_staff "
        "access_mode email_verified_at expires_at "
    ).split(),
    "tenancy.School": (
        "schema_name name cnpj legal_name trade_name state_registration "
        "municipal_registration phone email contact_full_name contact_role contact_phone "
        "contact_email address academic_year_start academic_year_end "
    ).split(),
    "tenancy.Domain": ("domain tenant_id is_primary ").split(),
    "locations.State": ("code name ").split(),
    "locations.City": ("state_id name ibge_code ").split(),
    "addresses.Address": (
        "recipient street number complement district postal_code city state "
    ).split(),
    "addresses.SchoolAddress": ("school_id address_id is_primary ").split(),
    "addresses.BusinessUnitAddress": ("business_unit_id address_id is_primary ").split(),
    "addresses.TeacherAddress": ("teacher_id address_id is_primary ").split(),
    "addresses.StudentAddress": ("student_id address_id is_primary ").split(),
    "addresses.GuardianAddress": ("guardian_id address_id is_primary ").split(),
    "students.Student": (
        "origin_import_batch_id user_id enrollment_number first_name last_name birth_date "
        "gender blood_type observations nationality cpf rg_number rg_issuer rg_state "
        "phone_mobile email accepts_email_notifications accepts_whatsapp_notifications "
    ).split(),
    "students.AssistedImportBatch": ("source_key status manifest counts ").split(),
    "guardians.Guardian": (
        "origin_import_batch_id user_id first_name last_name email birth_date gender "
        "nationality cpf rg_number rg_issuer rg_state phone phone_whatsapp phone_mobile "
        "accepts_email_notifications accepts_whatsapp_notifications "
    ).split(),
    "guardians.StudentGuardian": (
        "origin_import_batch_id student_id guardian_id relationship_type is_primary "
        "has_custody can_pickup "
    ).split(),
    "teachers.Subject": ("name code workload ").split(),
    "teachers.Teacher": (
        "user_id registration_number hire_date birth_date gender nationality cpf "
        "rg_number rg_issuer rg_state phone_mobile accepts_email_notifications "
        "accepts_whatsapp_notifications "
    ).split(),
}

MEDIA_FIELDS = {
    "core.BusinessUnit": ["logo"],
    "core.CustomUser": ["avatar"],
    "tenancy.School": ["logo"],
    "students.Student": ["photo"],
    "guardians.Guardian": ["avatar"],
}

RELATION_FIELDS = {"teachers.Teacher": ["subjects"]}
