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
            "sigma_pos_2_threshold",
            "sigma_pos_15_threshold",
            "sigma_neg_15_threshold",
            "sigma_neg_2_threshold",
            "sigma_pos_2_bg",
            "sigma_pos_2_fg",
            "sigma_pos_15_bg",
            "sigma_pos_15_fg",
            "sigma_neg_15_bg",
            "sigma_neg_15_fg",
            "sigma_neg_2_bg",
            "sigma_neg_2_fg",
            "sigma_other_bg",
            "sigma_other_fg",
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
            "sigma_pos_2_threshold": forms.NumberInput(
                attrs={"step": "0.1", "class": "form-control"}
            ),
            "sigma_pos_15_threshold": forms.NumberInput(
                attrs={"step": "0.1", "class": "form-control"}
            ),
            "sigma_neg_15_threshold": forms.NumberInput(
                attrs={"step": "0.1", "class": "form-control"}
            ),
            "sigma_neg_2_threshold": forms.NumberInput(
                attrs={"step": "0.1", "class": "form-control"}
            ),
            "sigma_pos_2_bg": forms.TextInput(attrs={"type": "color"}),
            "sigma_pos_2_fg": forms.TextInput(attrs={"type": "color"}),
            "sigma_pos_15_bg": forms.TextInput(attrs={"type": "color"}),
            "sigma_pos_15_fg": forms.TextInput(attrs={"type": "color"}),
            "sigma_neg_15_bg": forms.TextInput(attrs={"type": "color"}),
            "sigma_neg_15_fg": forms.TextInput(attrs={"type": "color"}),
            "sigma_neg_2_bg": forms.TextInput(attrs={"type": "color"}),
            "sigma_neg_2_fg": forms.TextInput(attrs={"type": "color"}),
            "sigma_other_bg": forms.TextInput(attrs={"type": "color"}),
            "sigma_other_fg": forms.TextInput(attrs={"type": "color"}),
        }
