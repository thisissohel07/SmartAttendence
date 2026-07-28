from django import forms
from django.contrib.auth.models import User
from .models import Student, Department, CampusConfig

class StudentRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter full name',
            'required': True
        })
    )
    roll_number = forms.CharField(
        max_length=10,
        min_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-uppercase font-monospace',
            'placeholder': 'e.g. 24WJ1A66B3',
            'maxlength': '10',
            'required': True
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'student@gmail.com',
            'required': True
        })
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        empty_label="Select Department",
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg',
            'required': True
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email').strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email is already registered.")
        return email

    def clean_roll_number(self):
        import re
        roll_number = self.cleaned_data.get('roll_number').strip().upper()
        
        # Validate XXWJXXXXXX pattern (e.g. 24WJ1A66B3)
        pattern = r'^[0-9]{2}WJ[0-9A-Z]{6}$'
        if not re.match(pattern, roll_number):
            raise forms.ValidationError("Invalid Roll Number format! Must match pattern XXWJXXXXXX (e.g. 24WJ1A66B3).")

        if Student.objects.filter(roll_number__iexact=roll_number).exists():
            raise forms.ValidationError("Roll number is already registered.")
        return roll_number


class VerifyOTPForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center tracking-widest fw-bold',
            'placeholder': '• • • • • •',
            'autocomplete': 'off',
            'required': True
        })
    )


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your registered email',
            'required': True
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email').strip().lower()
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("No account found with this email.")
        return email



class CampusConfigForm(forms.ModelForm):
    class Meta:
        model = CampusConfig
        fields = ['center_latitude', 'center_longitude', 'radius_meters', 'college_start_time', 'college_end_time']
        widgets = {
            'center_latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'center_longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'radius_meters': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'college_start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'college_end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }


class StudentProfileEditForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter full name',
            'required': True
        })
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        empty_label="Select Department",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )


class AdminLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter admin username',
            'required': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter admin password',
            'required': True
        })
    )

