from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm as DjPasswordChangeForm

User = get_user_model()


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name',
                'autocomplete': 'given-name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name',
                'autocomplete': 'family-name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address',
                'autocomplete': 'email',
            }),
        }


class AdminUserRoleForm(forms.ModelForm):
    """Admin-only form to change a user's role and active status."""
    class Meta:
        model = User
        fields = ('role', 'is_active')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }


class CustomPasswordChangeForm(DjPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attrs = {'class': 'form-control'}
        self.fields['old_password'].widget.attrs.update({**attrs, 'placeholder': 'Current password'})
        self.fields['new_password1'].widget.attrs.update({**attrs, 'placeholder': 'New password'})
        self.fields['new_password2'].widget.attrs.update({**attrs, 'placeholder': 'Confirm new password'})
        self.fields['old_password'].label = 'Current password'
        self.fields['new_password1'].label = 'New password'
        self.fields['new_password2'].label = 'Confirm password'
