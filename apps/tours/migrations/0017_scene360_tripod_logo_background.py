from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tours", "0016_scene360_camera_pitch_limits")]

    operations = [
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_background_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_background_color",
            field=models.CharField(default="#FFFFFF", max_length=9),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_background_opacity",
            field=models.FloatField(default=0.94, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_background_width",
            field=models.PositiveSmallIntegerField(default=160, validators=[MinValueValidator(72), MaxValueValidator(520)]),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_background_height",
            field=models.PositiveSmallIntegerField(default=160, validators=[MinValueValidator(72), MaxValueValidator(520)]),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_background_radius",
            field=models.PositiveSmallIntegerField(default=50, help_text="Background corner radius as a percentage.", validators=[MinValueValidator(0), MaxValueValidator(50)]),
        ),
    ]
