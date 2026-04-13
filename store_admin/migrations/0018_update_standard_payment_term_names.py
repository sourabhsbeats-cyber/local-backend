from django.db import migrations


def upsert_payment_terms(apps, schema_editor):
    PaymentTerm = apps.get_model("store_admin", "PaymentTerm")

    target_terms = [
        ("Last day of Next Month", 30, 2),
        ("Last day of Next to Next Month", 60, 2),
        ("14th of Next Month", 30, 2),
    ]

    legacy_aliases = {
        "last date of next month (bambury)": "Last day of Next Month",
        "last date of next to next month (forcetech)": "Last day of Next to Next Month",
        "14th of next month (ingram)": "14th of Next Month",
    }

    existing = list(PaymentTerm.objects.all().order_by("id"))
    canonical_names = {name.lower(): name for name, _, _ in target_terms}

    # Rename legacy terms, but avoid unique collisions by merging duplicates.
    for term in existing:
        normalized = (term.name or "").strip().lower()
        if normalized not in legacy_aliases:
            continue

        target_name = legacy_aliases[normalized]
        duplicate = PaymentTerm.objects.filter(name__iexact=target_name).exclude(id=term.id).first()
        if duplicate:
            # Keep the existing canonical record, remove legacy duplicate.
            term.delete()
            continue

        term.name = target_name
        term.frequency = 60 if term.name == "Last day of Next to Next Month" else 30
        term.type = 2
        term.status = term.status or "Active"
        term.save()

    # Remove accidental duplicates that differ only by case/name variants.
    dedupe_map = {}
    for term in PaymentTerm.objects.all().order_by("id"):
        key = (term.name or "").strip().lower()
        if key in dedupe_map:
            term.delete()
        else:
            dedupe_map[key] = term.id

    # Ensure target terms exist.
    for name, frequency, ptype in target_terms:
        obj = PaymentTerm.objects.filter(name__iexact=name).first()
        if obj:
            obj.frequency = frequency
            obj.type = ptype
            obj.status = obj.status or "Active"
            obj.name = canonical_names.get((obj.name or "").strip().lower(), name)
            obj.save()
        else:
            PaymentTerm.objects.create(
                name=name,
                frequency=frequency,
                type=ptype,
                status="Active",
            )


class Migration(migrations.Migration):

    dependencies = [
        ("store_admin", "0017_vendorcontact_primary_mobile"),
    ]

    operations = [
        migrations.RunPython(upsert_payment_terms, migrations.RunPython.noop),
    ]
