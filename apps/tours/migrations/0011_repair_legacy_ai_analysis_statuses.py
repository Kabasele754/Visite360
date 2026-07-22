from django.db import migrations


def repair_ai_statuses(apps, schema_editor):
    Scene360 = apps.get_model("tours", "Scene360")
    Scene360.objects.filter(ai_analysis_status="done").update(ai_analysis_status="ready")
    Scene360.objects.filter(ai_analysis_status="error").update(ai_analysis_status="failed")


def reverse_ai_statuses(apps, schema_editor):
    Scene360 = apps.get_model("tours", "Scene360")
    Scene360.objects.filter(ai_analysis_status="ready").update(ai_analysis_status="done")
    Scene360.objects.filter(ai_analysis_status="failed").update(ai_analysis_status="error")


class Migration(migrations.Migration):
    dependencies = [("tours", "0010_hotspot_door_and_advanced_display")]
    operations = [migrations.RunPython(repair_ai_statuses, reverse_ai_statuses)]
