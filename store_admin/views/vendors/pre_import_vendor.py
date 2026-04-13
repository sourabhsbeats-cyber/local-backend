import os
import uuid

import pandas as pd
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from store_admin.AuthHandler import StrictJWTCookieAuthentication
from store_admin.views.vendors.vendor_import_utils import (
    CORE_REQUIRED_COLUMNS,
    normalize_text,
    validate_vendor_row,
)

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_ROWS = 500
ALLOWED_EXTS = (".csv", ".xlsx")


def normalize_duplicate_action(value):
    if not value:
        return "skip"
    normalized = str(value).strip().lower().replace('-', '_')
    if normalized in ["skip", "skip_duplicate", "skipduplicates", "skip_duplicates"]:
        return "skip"
    if normalized in ["update", "overwrite", "overwrite_existing", "update_existing", "overwriteexisting"]:
        return "update"
    return normalized


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def pre_import_check(request):
    file = request.FILES.get('file')
    import_type = request.data.get('import_type')
    duplicate_action = normalize_duplicate_action(request.data.get('duplicate_action'))

    if not file:
        return JsonResponse({"status": False, "message": "No file uploaded"})

    if file.size > MAX_FILE_SIZE:
        return JsonResponse({"status": False, "message": "File size exceeds 5 MB"})

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTS:
        return JsonResponse({"status": False, "message": "Only CSV or XLSX files allowed"})

    if import_type != "vendor":
        return JsonResponse({"status": False, "message": "Only vendor import is supported"})

    file_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.MEDIA_ROOT, "imports")
    os.makedirs(upload_dir, exist_ok=True)
    saved_path = os.path.join(upload_dir, f"{file_id}_pending{ext}")

    try:
        with open(saved_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        df = pd.read_csv(saved_path) if ext == ".csv" else pd.read_excel(saved_path)

        if len(df) > MAX_ROWS:
            os.remove(saved_path)
            return JsonResponse({"status": False, "message": f"Maximum {MAX_ROWS} records only allowed"})

        df.columns = [c.strip() for c in df.columns]

        missing_cols = [c for c in CORE_REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            os.remove(saved_path)
            return JsonResponse({"status": False, "message": f"Template Error. Missing details: {', '.join(missing_cols)}"})

        df = df.where(pd.notnull(df), None)
        error_log = []
        valid_records = []

        seen_vendor_codes = set()
        seen_vendor_names = set()
        seen_company_names = set()

        for index, row in df.iterrows():
            row_num = index + 2
            clean_row = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
            row_errors = validate_vendor_row(
                clean_row,
                row_num,
                seen_vendor_codes,
                seen_vendor_names,
                seen_company_names,
            )

            if row_errors:
                error_log.extend(row_errors)
            else:
                clean_row["Vendor Code"] = normalize_text(clean_row.get("Vendor Code"))
                clean_row["Vendor Name"] = normalize_text(clean_row.get("Vendor Name"))
                clean_row["Company Name"] = normalize_text(clean_row.get("Company Name"))
                valid_records.append(clean_row)

        if error_log:
            os.remove(saved_path)
            return JsonResponse({"status": False, "errors": error_log})

        return JsonResponse({
            "status": True,
            "message": "Validation completed click next to confirm the import",
            "duplicate_action": duplicate_action,
            "data": {
                "file_id": file_id,
                "total_rows": len(df),
                "valid_count": len(valid_records),
                "invalid_count": 0,
                "preview_data": valid_records[:5],
                "errors": []
            }
        })
    except Exception as e:
        if os.path.exists(saved_path):
            os.remove(saved_path)
        return JsonResponse({"status": False, "message": f"Error in import: {str(e)}"})
