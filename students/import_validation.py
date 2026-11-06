"""Leitura estrita dos arquivos de implantação, sem efeitos colaterais."""

import csv
import hashlib
import io
import json

from django.core.exceptions import ValidationError as DjangoValidationError

from base.exceptions import ValidationError
from base.validators import validate_cpf
from guardians.forms import GuardianEditForm
from students.forms import StudentForm

PERSON_FIELDS = [
    "source_id",
    "first_name",
    "last_name",
    "birth_date",
    "gender",
    "cpf",
    "rg_number",
    "phone_mobile",
    "email",
]
COLUMNS = {
    "students": PERSON_FIELDS + ["blood_type"],
    "guardians": PERSON_FIELDS,
    "links": [
        "student_source_id",
        "guardian_source_id",
        "relationship_type",
        "is_primary",
        "has_custody",
        "can_pickup",
    ],
}


def parse_import(files):
    """Valida o lote inteiro e retorna dados normalizados, sem presumir guarda."""
    from guardians.contracts import Guardian

    result, errors = {}, []
    for kind, columns in COLUMNS.items():
        content = files.get(kind, "")
        if len(content.encode("utf-8")) > 5_000_000:
            errors.append(f"{kind}: arquivo excede 5 MB.")
            continue
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
        if reader.fieldnames is None or set(reader.fieldnames) != set(columns):
            errors.append(f'{kind}: cabeçalho deve conter exatamente {", ".join(columns)}.')
            continue
        rows, seen, cpfs = [], set(), set()
        for number, raw in enumerate(reader, 2):
            if number > 10001:
                errors.append(f"{kind}: limite de 10000 linhas excedido.")
                break
            if None in raw or any(value is None for value in raw.values()):
                errors.append(f"{kind}, linha {number}: número de colunas inválido.")
                continue
            row = {key: value.strip() for key, value in raw.items()}
            if kind == "links":
                identity = (row["student_source_id"], row["guardian_source_id"])
                valid = row["relationship_type"] in Guardian.Relationship.values
                for field in ("is_primary", "has_custody", "can_pickup"):
                    valid = valid and row[field] in ("0", "1")
                    row[field] = row[field] == "1"
                if not valid:
                    errors.append(
                        f"{kind}, linha {number}: parentesco ou indicadores inválidos; use 0/1."
                    )
            else:
                identity = row["source_id"]
                form = (StudentForm if kind == "students" else GuardianEditForm)(row)
                form.fields.pop("enrollment_number", None)
                if not form.is_valid():
                    errors.append(
                        f'{kind}, linha {number}: campos inválidos: {", ".join(form.errors)}.'
                    )
                if row["cpf"]:
                    try:
                        cpf = validate_cpf(row["cpf"])
                        if cpf in cpfs:
                            errors.append(f"{kind}, linha {number}: CPF repetido no lote.")
                        cpfs.add(cpf)
                        row["cpf"] = cpf
                    except (ValidationError, DjangoValidationError):
                        errors.append(f"{kind}, linha {number}: CPF inválido.")
                row["email"] = row["email"].lower()
            if not identity or identity in seen:
                errors.append(f"{kind}, linha {number}: identificador ausente ou repetido.")
            seen.add(identity)
            row["_row"] = number
            rows.append(row)
        result[kind] = rows
    students = {row["source_id"] for row in result.get("students", [])}
    guardians = {row["source_id"] for row in result.get("guardians", [])}
    primaries = set()
    for row in result.get("links", []):
        if row["student_source_id"] not in students or row["guardian_source_id"] not in guardians:
            errors.append(f"links, linha {row['_row']}: referência de origem inexistente.")
        if row["is_primary"]:
            if row["student_source_id"] in primaries:
                errors.append(f"links, linha {row['_row']}: mais de um responsável principal.")
            primaries.add(row["student_source_id"])
        if row["is_primary"] and not row["has_custody"]:
            errors.append(
                f"links, linha {row['_row']}: responsável principal exige guarda confirmada."
            )
    if errors:
        raise ValidationError(errors={"files": errors})
    return result


def import_fingerprint(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
