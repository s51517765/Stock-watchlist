from django import forms
from .models import ScoreSetting


class ScoreSettingForm(forms.ModelForm):
    class Meta:
        model = ScoreSetting
        fields = [
            "score_circle",
            "score_triangle",
            "score_hyphen",
            "score_cross",
            "div_circle",
            "div_triangle",
            "threshold_high",
            "threshold_mid",
            "threshold_low",
        ]
        widgets = {
            "score_circle": forms.NumberInput(
                attrs={"step": "0.01", "class": "form-control"}
            ),
            "score_triangle": forms.NumberInput(
                attrs={"step": "0.01", "class": "form-control"}
            ),
            "score_hyphen": forms.NumberInput(
                attrs={"step": "0.01", "class": "form-control"}
            ),
            "score_cross": forms.NumberInput(
                attrs={"step": "0.01", "class": "form-control"}
            ),
            "div_circle": forms.NumberInput(attrs={"class": "form-control"}),
            "div_triangle": forms.NumberInput(attrs={"class": "form-control"}),
            "threshold_high": forms.NumberInput(attrs={"class": "form-control"}),
            "threshold_mid": forms.NumberInput(attrs={"class": "form-control"}),
            "threshold_low": forms.NumberInput(attrs={"class": "form-control"}),
        }
