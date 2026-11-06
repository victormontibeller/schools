"""Allowlist explícita de exportação; novos campos exigem revisão e inclusão deliberada."""

FIELDS = {
    "classes.Class": (
        "name grade education_stage shift academic_year max_students class_teacher_id "
    ).split(),
    "classes.Enrollment": (
        "student_id class_obj_id academic_year enrollment_date status cancel_reason "
    ).split(),
    "rooms.Room": ("name code capacity type resources observations floor building ").split(),
    "agenda.TimeSlot": ("start_time end_time slot_number shift ").split(),
    "agenda.Schedule": (
        "class_obj_id teacher_id subject_id room_id time_slot_id day_of_week valid_from "
        "valid_until "
    ).split(),
    "enrollments.EnrollmentApplication": (
        "student_id target_class_id source_enrollment_id result_enrollment_id "
        "academic_year application_number application_type status priority notes "
        "origin_school destination_school reviewed_by_id reviewed_at waitlisted_at "
    ).split(),
    "enrollments.EnrollmentTransition": (
        "application_id from_status to_status actor_id reason "
    ).split(),
    "enrollments.DocumentRequirement": (
        "application_type code label is_required allows_physical display_order "
    ).split(),
    "enrollments.StudentDocument": (
        "application_id requirement_id requirement_code requirement_label is_required "
        "allows_physical status delivery_method decision_reason verified_by_id "
        "verified_at "
    ).split(),
    "attendance.AttendanceRecord": (
        "class_obj_id subject_id teacher_id date lesson_number lesson_content notes "
    ).split(),
    "attendance.AttendanceEntry": ("record_id student_id status justification note ").split(),
    "attendance.AttendanceJustification": (
        "student_id start_date end_date reason status approved_by_id approved_at "
        "rejection_reason "
    ).split(),
    "activities.Activity": (
        "class_obj_id subject_id teacher_id title description type modality due_date "
        "max_score weight score_status scores_launched_at "
    ).split(),
    "activities.ActivitySubmission": (
        "activity_id student_id score submitted_at feedback "
    ).split(),
    "activities.ActivityGroup": ("activity_id name score feedback ").split(),
    "activities.ActivityGroupMember": ("activity_id group_id student_id ").split(),
    "academic_calendar.AcademicYear": ("name start_date end_date status ").split(),
    "academic_calendar.Holiday": ("name date type is_recurring ").split(),
    "academic_calendar.CalendarEvent": (
        "title description start_date end_date start_time end_time type recurrence "
        "audience class_obj_id academic_year_id is_public is_cancelled cancel_reason "
    ).split(),
    "student_diary.DiaryCategory": (
        "name section display_order is_required is_enabled applies_morning " "applies_afternoon "
    ).split(),
    "student_diary.DiaryOption": ("category_id label display_order is_enabled ").split(),
    "student_diary.DailyDiary": ("student_id class_obj_id teacher_id date notes ").split(),
    "student_diary.DiarySheet": (
        "class_obj_id date status review_feedback submitted_at submitted_by_id "
        "reviewed_at reviewed_by_id "
    ).split(),
    "student_diary.DiaryPublication": (
        "sheet_id revision_number published_at published_by_id "
    ).split(),
    "student_diary.DiaryPublishedEntry": (
        "publication_id student_id answers_snapshot notes "
    ).split(),
    "student_diary.DiaryViewReceipt": (
        "entry_id guardian_id first_viewed_at last_viewed_at view_count "
    ).split(),
    "student_diary.DiaryAnswer": ("diary_id category_id option_id ").split(),
}

MEDIA_FIELDS = {
    "enrollments.StudentDocument": ["file"],
    "attendance.AttendanceJustification": ["document"],
}

RELATION_FIELDS = {}
