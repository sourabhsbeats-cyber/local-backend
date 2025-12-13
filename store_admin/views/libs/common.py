from rest_framework.pagination import PageNumberPagination

class TabulatorPagination(PageNumberPagination):
    page_size = 20
    page_query_param = "page"
    page_size_query_param = "size"
    max_page_size = 50  # ✅ cap at 50

def clean_percent(value):
    if value in (None, "", " ", "null"):
        return 0
    try:
        val = float(value)
    except:
        return 0
    if val.is_integer():
        return int(val)
    return val