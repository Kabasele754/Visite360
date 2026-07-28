from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tours", "0015_rename_tours_scene_tour_id_0b520b_idx_tours_scene_tour_id_1e0b94_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="scene360",
            name="camera_limits_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="scene360",
            name="camera_pitch_min",
            field=models.FloatField(
                default=-82.0,
                validators=[MinValueValidator(-89.5), MaxValueValidator(89.5)],
            ),
        ),
        migrations.AddField(
            model_name="scene360",
            name="camera_pitch_max",
            field=models.FloatField(
                default=62.0,
                validators=[MinValueValidator(-89.5), MaxValueValidator(89.5)],
            ),
        ),
    ]
