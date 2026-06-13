from django import forms
from .models import Device


class DeviceForm(forms.ModelForm):
    ssh_password_plain = forms.CharField(
        required=False,
        label='SSH Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
            'placeholder': 'Leave blank to keep existing password',
            'id': 'id_ssh_password_plain',
        }),
    )

    class Meta:
        model = Device
        fields = [
            'hostname', 'ip_address', 'wan_ip', 'loopback_ip',
            'site', 'device_type', 'vendor', 'model', 'os_version',
            'description', 'snmp_community', 'snmp_version', 'ssh_username',
        ]
        widgets = {
            'hostname':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. R-SOFIA-01'}),
            'ip_address':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': '192.168.100.x'}),
            'wan_ip':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'loopback_ip':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'site':           forms.Select(attrs={'class': 'form-select'}),
            'device_type':    forms.Select(attrs={'class': 'form-select'}),
            'vendor':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cisco'}),
            'model':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ASR1001-X'}),
            'os_version':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 16.9.3'}),
            'description':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'snmp_community': forms.TextInput(attrs={'class': 'form-control'}),
            'snmp_version':   forms.Select(attrs={'class': 'form-select'}),
            'ssh_username':   forms.TextInput(attrs={'class': 'form-control'}),
        }

    def save(self, commit=True):
        device = super().save(commit=False)
        plaintext = self.cleaned_data.get('ssh_password_plain', '').strip()
        if plaintext:
            device.set_encrypted_password(plaintext)
        if commit:
            device.save()
        return device
