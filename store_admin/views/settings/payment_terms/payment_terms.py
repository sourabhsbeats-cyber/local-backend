from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required

@login_required


@login_required
def manage_payment_terms(request):
    if request.method == "POST":
        action = request.POST.get("action")

        # --- Create ---
        if action == "create":
            PaymentTerm.objects.create(
                name=request.POST.get("name"),
                type=request.POST.get("type"),
                frequency=request.POST.get("frequency"),
                status=request.POST.get("status"),
            )
            messages.success(request, "Payment Term created successfully.")
            return redirect("payment_terms")

        # --- Edit ---
        elif action == "edit":
            term = get_object_or_404(PaymentTerm, id=request.POST.get("term_id"))
            term.name = request.POST.get("name")
            term.frequency = request.POST.get("frequency")
            term.type = request.POST.get("type")
            term.status = request.POST.get("status")
            term.save()
            messages.success(request, f"Payment Term '{term.name}' updated successfully.")
            return redirect("payment_terms")

        # --- Delete ---
        elif action == "delete":
            term = get_object_or_404(PaymentTerm, id=request.POST.get("term_id"))
            term.delete()
            messages.warning(request, f"Payment Term '{term.name}' deleted successfully.")
            return redirect("payment_terms")

    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = PaymentTerm.objects.all().order_by("name")

    if search_query:
        terms = terms.filter(name__icontains=search_query)

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "sbadmin/pages/settings/payment_terms/manage_payment_terms.html",
        {"terms": page_obj, "page_obj": page_obj, "search_query": search_query},
    )
