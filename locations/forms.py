from django import forms
from django.utils.translation import gettext_lazy as _
from datetime import date
from .models import Location, Unit, Meter, MeterLedger, ParkingPlace, Lease, LeaseLedger, SalePayment, SaleStatus


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'address', 'google_pin', 'focal_point']
        labels = {
            'name': _('Location Name'),
            'address': _('Location Address'),
            'google_pin': _('Google Pin'),
            'focal_point': _('Focal Point'),
        }
        help_texts = {
            'google_pin': _('Optional — paste a Google Maps share link'),
            'focal_point': _('Optional — e.g. "Main entrance", "Floor 3"'),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if hasattr(field, 'widget'):
                if isinstance(field.widget, forms.Textarea):
                    field.widget.attrs.update({'class': 'form-control', 'rows': 3})
                else:
                    field.widget.attrs.update({'class': 'form-control'})


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'sqm', 'unit_type', 'lease', 'sale_status', 'sale_price',
                  'buyer_name', 'buyer_contact', 'buyer_email', 'buyer_phone',
                  'sale_contract', 'sale_agreement_date',
                  'installment_count', 'installment_start_date', 'installment_amount',
                  'sale_notes']
        labels = {
            'name': _('Unit Name'),
            'sqm': _('Area (sqm)'),
            'unit_type': _('Unit Type'),
            'lease': _('Assign Lease'),
            'sale_status': _('Sale Status'),
            'sale_price': _('Sale Price (€)'),
            'buyer_name': _('Buyer Name'),
            'buyer_contact': _('Buyer Contact Person'),
            'buyer_email': _('Buyer Email'),
            'buyer_phone': _('Buyer Phone'),
            'sale_contract': _('Sale Contract'),
            'sale_agreement_date': _('Sale Agreement Date'),
            'installment_count': _('Number of Installments'),
            'installment_start_date': _('Installment Start Date'),
            'installment_amount': _('Amount per Installment (€)'),
            'sale_notes': _('Sale Notes'),
        }
        help_texts = {
            'installment_count': _('Total number of payment installments'),
            'installment_amount': _('Optional — leave blank to calculate from sale price'),
        }
        widgets = {
            'sale_agreement_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'installment_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'sale_agreement_date':
                continue  # already configured in widgets
            if hasattr(field, 'widget'):
                if isinstance(field, forms.ChoiceField) and isinstance(field.widget, forms.Select):
                    field.widget.attrs.update({'class': 'form-select'})
                elif isinstance(field.widget, forms.Select):
                    field.widget.attrs.update({'class': 'form-select'})
                elif isinstance(field.widget, forms.Textarea):
                    field.widget.attrs.update({'class': 'form-control', 'rows': 3})
                else:
                    field.widget.attrs.update({'class': 'form-control'})


class MeterForm(forms.ModelForm):
    class Meta:
        model = Meter
        fields = ['name', 'unit', 'meter_type', 'reading_metric', 'serial_number', 'kesco_debitor_id']
        labels = {
            'name': _('Meter Name'),
            'unit': _('Assigned Unit'),
            'meter_type': _('Meter Type'),
            'reading_metric': _('Reading Metric'),
            'serial_number': _('Serial Number'),
            'kesco_debitor_id': _('KESCO Debitor ID'),
        }
        help_texts = {
            'kesco_debitor_id': _('Optional — link to KESCO ElDebitorId (e.g. 160) for automatic sync'),
        }

    def __init__(self, *args, lock_unit=False, **kwargs):
        super().__init__(*args, **kwargs)
        if lock_unit:
            self.fields.pop('unit', None)
        for field in self.fields.values():
            if hasattr(field, 'widget'):
                if isinstance(field.widget, forms.Select):
                    field.widget.attrs.update({'class': 'form-select'})
                else:
                    field.widget.attrs.update({'class': 'form-control'})


class MeterLedgerForm(forms.ModelForm):
    class Meta:
        model = MeterLedger
        fields = ['month', 'year', 'reading', 'billed_amount']
        labels = {
            'month': _('Month'),
            'year': _('Year'),
            'reading': _('Reading'),
            'billed_amount': _('Billed Amount (€)'),
        }
        help_texts = {
            'billed_amount': _('Enter the current third-party expense still owed by the tenant. Use 0 if the prior bill was paid before the new bill arrived.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide raw month/year, replace with month picker
        self.fields['month'].widget = forms.HiddenInput()
        self.fields['month'].required = False
        self.fields['year'].widget = forms.HiddenInput()
        self.fields['year'].required = False

        if self.instance and self.instance.pk:
            initial_val = f'{self.instance.year:04d}-{self.instance.month:02d}'
            self.fields['billing_period'] = forms.CharField(
                label=_('Billing Period'),
                required=False,
                widget=forms.TextInput(attrs={
                    'type': 'month',
                    'class': 'form-control',
                    'id': 'id_billing_period',
                }),
                initial=initial_val,
            )
        else:
            self.fields['billing_period'] = forms.CharField(
                label=_('Billing Period'),
                required=True,
                widget=forms.TextInput(attrs={
                    'type': 'month',
                    'class': 'form-control',
                    'id': 'id_billing_period',
                    'placeholder': _('Select month & year'),
                }),
            )

        for field_name, field in self.fields.items():
            if field_name in ('month', 'year', 'billing_period'):
                continue
            if hasattr(field, 'widget'):
                if isinstance(field.widget, forms.Select):
                    field.widget.attrs.update({'class': 'form-select'})
                elif not isinstance(field.widget, forms.HiddenInput):
                    field.widget.attrs.update({'class': 'form-control'})

    def clean_billing_period(self):
        """Parse month picker and set month/year fields."""
        val = self.cleaned_data.get('billing_period')
        if val:
            year, month = val.split('-')
            self.cleaned_data['month'] = int(month)
            self.cleaned_data['year'] = int(year)
        return val


class ParkingPlaceForm(forms.ModelForm):
    class Meta:
        model = ParkingPlace
        fields = ['label', 'covered']
        labels = {
            'label': _('Label'),
            'covered': _('Covered'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if hasattr(field, 'widget'):
                if isinstance(field.widget, forms.CheckboxInput):
                    pass
                elif isinstance(field.widget, forms.Select):
                    field.widget.attrs.update({'class': 'form-select'})
                else:
                    field.widget.attrs.update({'class': 'form-control'})

    def clean_label(self):
        """Check for duplicate parking label within the same location."""
        label = self.cleaned_data.get('label')
        location = None
        if self.instance and self.instance.pk:
            location = self.instance.location
        elif self.initial and 'location' in self.initial:
            location = self.initial['location']
        elif hasattr(self, '_location'):
            location = self._location

        if label and location:
            qs = ParkingPlace.objects.filter(location=location, label=label)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    _('Parking place with label "%(label)s" already exists in this location.'),
                    code='duplicate',
                    params={'label': label},
                )
        return label


class ParkingBulkCreateForm(forms.Form):
    """Form for bulk creating multiple parking places at once."""
    labels = forms.CharField(
        label=_('Parking Labels'),
        widget=forms.Textarea(attrs={
            'rows': 8,
            'class': 'form-control',
            'placeholder': 'P1\nP2\nP3\nP4',
        }),
        help_text=_('Enter one label per line'),
    )
    covered = forms.BooleanField(
        label=_('Covered'),
        required=False,
        initial=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_labels(self):
        """Parse labels from textarea, one per line."""
        raw = self.cleaned_data.get('labels', '')
        labels = [line.strip() for line in raw.split('\n') if line.strip()]
        if not labels:
            raise forms.ValidationError(_('Please enter at least one parking label.'))
        return labels


class LeaseLedgerForm(forms.ModelForm):
    class Meta:
        model = LeaseLedger
        fields = ['month', 'year', 'amount_due', 'amount_paid', 'status', 'payment_date', 'notes', 'payment_slip']
        labels = {
            'month': _('Month'),
            'year': _('Year'),
            'amount_due': _('Amount Due (€)'),
            'amount_paid': _('Amount Paid (€)'),
            'status': _('Status'),
            'payment_date': _('Payment Date'),
            'notes': _('Notes'),
            'payment_slip': _('Payment Slip'),
        }
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'payment_slip': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, lease=None, **kwargs):
        self.lease = lease
        super().__init__(*args, **kwargs)

        # Hide raw month/year, replace with month picker
        self.fields['month'].widget = forms.HiddenInput()
        self.fields['month'].required = False
        self.fields['year'].widget = forms.HiddenInput()
        self.fields['year'].required = False

        # Compute valid month range from lease dates
        min_val = None
        max_val = None
        if lease:
            if lease.start_date:
                min_val = f'{lease.start_date.year:04d}-{lease.start_date.month:02d}'
            if lease.end_date:
                # Allow 1 month after lease expires for final settlement
                end_month = lease.end_date.month
                end_year = lease.end_date.year
                if end_month == 12:
                    end_month = 1
                    end_year += 1
                else:
                    end_month += 1
                max_val = f'{end_year:04d}-{end_month:02d}'
            elif lease.is_active:
                # Open-ended active lease: allow up to 2 years ahead
                today = date.today()
                max_val = f'{today.year:04d}-{today.month:02d}'
                # Add 12 months buffer
                if today.month + 12 > 12:
                    max_val = f'{today.year + 1:04d}-{today.month:02d}'

        attrs = {
            'type': 'month',
            'class': 'form-control',
            'id': 'id_billing_period',
            'placeholder': _('Select month & year'),
        }
        if min_val:
            attrs['min'] = min_val
        if max_val:
            attrs['max'] = max_val

        if self.instance and self.instance.pk:
            initial_val = f'{self.instance.year:04d}-{self.instance.month:02d}'
            attrs.pop('placeholder', None)  # no placeholder for existing records
            self.fields['billing_period'] = forms.CharField(
                label=_('Billing Period'),
                required=False,
                widget=forms.TextInput(attrs=attrs),
                initial=initial_val,
            )
        else:
            self.fields['billing_period'] = forms.CharField(
                label=_('Billing Period'),
                required=True,
                widget=forms.TextInput(attrs=attrs),
            )

        # Configure payment_date with date picker
        self.fields['payment_date'].widget.attrs.update({'type': 'date', 'class': 'form-control'})

        for field_name, field in self.fields.items():
            if field_name in ('month', 'year', 'payment_date', 'notes', 'billing_period'):
                continue
            if hasattr(field, 'widget'):
                if isinstance(field.widget, forms.Select):
                    field.widget.attrs.update({'class': 'form-select'})
                else:
                    field.widget.attrs.update({'class': 'form-control'})

    def clean_billing_period(self):
        """Parse month picker and validate against lease period."""
        val = self.cleaned_data.get('billing_period')
        if val:
            year, month = val.split('-')
            year, month = int(year), int(month)
            self.cleaned_data['month'] = month
            self.cleaned_data['year'] = year

            # Validate against lease dates
            if self.lease:
                start = self.lease.start_date
                end = self.lease.end_date
                entry_date = date(year, month, 1)

                if start and entry_date < date(start.year, start.month, 1):
                    raise forms.ValidationError(
                        _('This period is before the lease started (%(start)s).'),
                        code='invalid',
                        params={'start': start.strftime('%B %Y')},
                    )

                if end:
                    # Allow 1 month after end date
                    grace_month = end.month
                    grace_year = end.year
                    if grace_month == 12:
                        grace_month = 1
                        grace_year += 1
                    else:
                        grace_month += 1
                    max_date = date(grace_year, grace_month, 1)
                    if entry_date > max_date:
                        raise forms.ValidationError(
                            _('This period is more than 1 month after the lease ended (%(end)s). Final settlement allowed until %(grace)s.'),
                            code='invalid',
                            params={
                                'end': end.strftime('%B %Y'),
                                'grace': max_date.strftime('%B %Y'),
                            },
                        )
                elif not self.lease.is_active and not end:
                    raise forms.ValidationError(
                        _('Cannot add entries for an inactive lease with no end date.'),
                        code='invalid',
                    )

        return val


class LeaseForm(forms.ModelForm):
    class Meta:
        model = Lease
        fields = ['name', 'contact', 'phone', 'email', 'contract', 'start_date', 'end_date', 'is_active', 'monthly_payment', 'advance_months', 'deposit', 'notes']
        labels = {
            'name': _('Responsible Party'),
            'contact': _('Contact Person'),
            'phone': _('Phone'),
            'email': _('Email'),
            'contract': _('Contract (PDF)'),
            'start_date': _('Start Date'),
            'end_date': _('End Date'),
            'is_active': _('Active'),
            'monthly_payment': _('Monthly Payment (€)'),
            'advance_months': _('Months in Advance'),
            'deposit': _('Deposit (€)'),
            'notes': _('Notes'),
        }
        help_texts = {
            'contract': _('Upload the lease contract — PDF only'),
            'advance_months': _('How many months the tenant must pay in advance'),
            'deposit': _('Optional security deposit amount'),
            'end_date': _('Leave blank for open-ended lease'),
        }
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder': 'Optional'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in ('start_date', 'end_date', 'notes'):
                continue  # already configured in widgets
            if hasattr(field, 'widget'):
                if isinstance(field.widget, forms.ClearableFileInput):
                    pass  # file input keeps default styling
                else:
                    field.widget.attrs.update({'class': 'form-control'})


class SalePaymentForm(forms.ModelForm):
    class Meta:
        model = SalePayment
        fields = ['installment_number', 'due_date', 'amount_due', 'amount_paid',
                  'payment_date', 'payment_slip', 'notes']
        labels = {
            'installment_number': _('Installment #'),
            'due_date': _('Due Date'),
            'amount_due': _('Amount Due (€)'),
            'amount_paid': _('Amount Paid (€)'),
            'payment_date': _('Payment Date'),
            'payment_slip': _('Payment Slip'),
            'notes': _('Notes'),
        }
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'payment_slip': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in ('due_date', 'payment_date', 'notes'):
                continue  # already configured in widgets
            if hasattr(field, 'widget'):
                if isinstance(field.widget, forms.ClearableFileInput):
                    pass
                else:
                    field.widget.attrs.update({'class': 'form-control'})
