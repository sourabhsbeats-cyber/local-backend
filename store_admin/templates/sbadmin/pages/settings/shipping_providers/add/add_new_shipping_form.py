from django import forms
from store_admin.models.setting_model import ShippingProviders
from django.core.exceptions import ValidationError
import re

class ShippingProviderForm(forms.ModelForm):
    # 1. Define choices at the top level
    CLASS_CODE_CHOICES = [
        ('', 'select'),
        ('Standard', 'Standard'),
        ('Ground', 'Ground'),
        ('Expedited', 'Expedited'),
        ('Priority', 'Priority'),
        ('Overnight', 'Overnight'),
        ('Freight Class', 'Freight Class'),
    ]

    # 2. Define the field HERE (outside Meta) to make the select work
    class_code = forms.ChoiceField(
        choices=CLASS_CODE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'class_code','required': 'required'
        })
    )

    class Meta:
        model = ShippingProviders
        fields = ['carrier_name', 'carrier_code', 'class_code', 'tracking_url']

        widgets = {
            'carrier_name': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'carrier_and_class',
                'placeholder': 'Carrier Name',
                'autocomplete': 'one-time-code',
                'required': 'required'
            }),
            'carrier_code': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'carrier_code',
                'placeholder': 'Carrier Code',
                'autocomplete': 'off'
            }),
            'tracking_url': forms.URLInput(attrs={
                'class': 'form-control',
                'id': 'tracking_url',
                'placeholder': 'Tracking Link',
                'required': 'required'
            }),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the field to not required
        self.fields['carrier_code'].required = False

    def clean_tracking_url(self):
        """
        Validates that {0} is present and no other placeholders exist.
        """
        tracking_url = self.cleaned_data.get('tracking_url')

        if tracking_url:
            # 1. Mandatory Check: {0} must be present
            if "{0}" not in tracking_url:
                raise ValidationError("The tracking URL is invalid. It must contain the '{0}' placeholder.")

            # 2. Strict Exclusion: Check for {any number other than 0}
            # This regex looks for curly braces containing any digits except a lone 0
            # It catches {1}, {2}, {10}, etc.
            invalid_placeholders = re.findall(r'\{([1-9][0-9]*)\}', tracking_url)

            if invalid_placeholders:
                raise ValidationError(
                    f"Forbidden placeholders found: {', '.join(['{' + p + '}' for p in invalid_placeholders])}. "
                    "Only '{0}' is allowed for the tracking ID."
                )

        return tracking_url

    def clean_carrier_name(self):
        carrier_name = self.cleaned_data.get('carrier_name')

        # 1. Start the query looking for ACTIVE records with the same name
        queryset = ShippingProviders.objects.filter(
            carrier_name__iexact=carrier_name,
            is_archived=0  # Only block if the existing one is NOT archived
        )

        # 2. If we are editing (instance exists), exclude the current record from the check
        if self.instance and self.instance.carrier_id:
            queryset = queryset.exclude(carrier_id=self.instance.carrier_id)

        # 3. Check if any records matching the criteria exist
        if queryset.exists():
            raise ValidationError(f"A carrier named '{carrier_name}' already exists in the system.")

        return carrier_name