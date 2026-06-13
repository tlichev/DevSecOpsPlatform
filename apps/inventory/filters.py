import django_filters
from .models import Device


class DeviceFilter(django_filters.FilterSet):
    site        = django_filters.ChoiceFilter(choices=Device.SITE_CHOICES, empty_label='All sites')
    device_type = django_filters.ChoiceFilter(choices=Device.DEVICE_TYPE_CHOICES, empty_label='All types')
    status      = django_filters.ChoiceFilter(choices=Device.STATUS_CHOICES, empty_label='Any status')
    vendor      = django_filters.CharFilter(lookup_expr='icontains')
    hostname    = django_filters.CharFilter(lookup_expr='icontains')
    ip_address  = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model  = Device
        fields = ['site', 'device_type', 'status', 'vendor']
