from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tours", "0013_scene360_tripod_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_rotation",
            field=models.FloatField(default=0.0, validators=[MinValueValidator(-180), MaxValueValidator(180)]),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_tilt_x",
            field=models.FloatField(default=0.0, validators=[MinValueValidator(-70), MaxValueValidator(70)]),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_tilt_y",
            field=models.FloatField(default=0.0, validators=[MinValueValidator(-70), MaxValueValidator(70)]),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_radius",
            field=models.PositiveSmallIntegerField(default=900, validators=[MinValueValidator(350), MaxValueValidator(2400)]),
        ),
    ]
