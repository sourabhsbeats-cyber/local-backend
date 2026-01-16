from store_admin.models import Country, PaymentTerm
from django.core.cache import cache

from store_admin.models.organization_model import OrganizationInventoryLocation
from store_admin.models.setting_model import ShippingProviders


def common_master_data(request):
    countries = cache.get("country_list")
    if not countries:
        countries = list(Country.objects.filter().order_by("name"))
        cache.set("country_list", countries, 3600)

    payment_terms = cache.get("payment_terms_list")
    if not payment_terms:
        payment_terms = list(PaymentTerm.objects.all())
        cache.set("payment_terms_list", payment_terms, 3600)

    warehouse_locations = cache.get("warehouse_locations")
    if not warehouse_locations:
        warehouse_locations = list(OrganizationInventoryLocation.objects.all())
        cache.set("warehouse_locations", warehouse_locations, 3600)

    shipping_providers = None #cache.get("shipping_providers")
    if not shipping_providers:
        shipping_providers = list(ShippingProviders.objects.filter(is_archived=0,status=1).all())
        cache.set("shipping_providers", shipping_providers, 3600)

    return {
        "COUNTRY_LIST": countries,
        "PAYMENT_TERMS_LIST": payment_terms,
        "WAREHOUSE_LOCATIONS": warehouse_locations,
        "SHIPPING_PROVIDERS": shipping_providers,
    }