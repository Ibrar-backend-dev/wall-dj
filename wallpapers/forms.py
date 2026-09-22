"""The admin's add form, which takes a batch of files rather than one.

Django's stock FileField is single-file by design, so a multi-file input needs
a widget that opts in to ``multiple`` and a field whose ``clean()`` walks the
resulting list.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ngettext

from .models import Category, Wallpaper
from .validators import validate_media_extension

MAX_FILES_PER_UPLOAD = 10


class MultiFileInput(forms.ClearableFileInput):
    # Django 5 refuses attrs={"multiple": True} on a stock file widget; this
    # flag is the supported opt-in, and it also switches value_from_datadict
    # over to files.getlist().
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    """A FileField whose cleaned value is a *list* of uploaded files.

    Each file goes through the single-file ``clean()``, so ``validators`` run
    per file instead of once against the list - handing a list to
    FileExtensionValidator would just raise AttributeError.
    """

    widget = MultiFileInput

    def __init__(self, *args, max_files=None, **kwargs):
        self.max_files = max_files
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if data in (None, False):
            data = []
        elif not isinstance(data, (list, tuple)):
            data = [data]

        if not data:
            # Django's documented recipe has a hole here: [] is in
            # validators.EMPTY_VALUES, so looping over an empty list never
            # reaches Field.validate()'s required check and save_model would
            # be handed an empty batch.
            if self.required:
                raise ValidationError(self.error_messages["required"], code="required")
            return []

        if self.max_files is not None and len(data) > self.max_files:
            raise ValidationError(
                ngettext(
                    "Select at most %(max)d file at a time - you selected %(count)d.",
                    "Select at most %(max)d files at a time - you selected %(count)d.",
                    self.max_files,
                ),
                code="too_many_files",
                params={"max": self.max_files, "count": len(data)},
            )

        cleaned = []
        errors = []
        clean_one = super().clean
        for upload in data:
            try:
                cleaned.append(clean_one(upload, initial))
            except ValidationError as exc:
                # Name the file: with ten of them, "extension not allowed" on
                # its own does not say which one to drop. Every bad file is
                # reported at once rather than one per round trip.
                for message in exc.messages:
                    errors.append(
                        ValidationError(
                            "%(name)s: %(message)s",
                            code="invalid",
                            params={
                                "name": getattr(upload, "name", "?"),
                                "message": message,
                            },
                        )
                    )
        if errors:
            raise ValidationError(errors)
        return cleaned


class WallpaperBulkAddForm(forms.ModelForm):
    """Add form only - the change form keeps the stock ModelForm."""

    files = MultiFileField(
        label="Files",
        max_files=MAX_FILES_PER_UPLOAD,
        validators=[validate_media_extension],
        help_text=(
            f"Pick up to {MAX_FILES_PER_UPLOAD} files at once. Each one becomes its "
            "own published wallpaper, titled after the file's own name."
        ),
    )

    class Meta:
        model = Wallpaper
        # ModelAdmin.get_form recomputes this from the fieldsets; declared here
        # so the form is also usable on its own.
        fields = ("category",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.order_by("position", "name")
