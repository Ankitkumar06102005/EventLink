from django import forms
from .models import Profile, Virtue, Event


class ProfileForm(forms.ModelForm):
    virtues = forms.ModelMultipleChoiceField(
        queryset=Virtue.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Profile
        fields = ['full_name', 'class_name', 'section', 'net_number', 'about_you', 'profile_picture', 'virtues']


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'date', 'location']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
