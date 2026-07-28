from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tours", "0012_ai_tour_architect"),
    ]

    operations = [
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_size",
            field=models.PositiveSmallIntegerField(
                default=132,
                validators=[MinValueValidator(72), MaxValueValidator(320)],
            ),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_yaw",
            field=models.FloatField(
                default=0.0,
                validators=[MinValueValidator(-180), MaxValueValidator(180)],
            ),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_pitch",
            field=models.FloatField(
                default=88.5,
                validators=[MinValueValidator(-89.5), MaxValueValidator(89.5)],
            ),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_offset_x",
            field=models.SmallIntegerField(
                default=0,
                validators=[MinValueValidator(-250), MaxValueValidator(250)],
            ),
        ),
        migrations.AddField(
            model_name="scene360",
            name="tripod_logo_offset_y",
            field=models.SmallIntegerField(
                default=0,
                validators=[MinValueValidator(-250), MaxValueValidator(250)],
            ),
        ),
    ]
