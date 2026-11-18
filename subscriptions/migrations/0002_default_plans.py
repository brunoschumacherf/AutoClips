from django.db import migrations


def seed(apps, schema_editor):
    plan = apps.get_model("subscriptions", "SubscriptionPlan")
    for name, minutes, clips, storage, height, socials in (
        ("Free", 60, 30, 2, 720, 0),
        ("Starter", 300, 150, 25, 1080, 1),
        ("Pro", 1200, 500, 100, 1080, 5),
        ("Business", 5000, 2000, 500, 1080, 20),
    ):
        plan.objects.get_or_create(name=name, defaults={
            "monthly_seconds": minutes * 60, "monthly_clips": clips,
            "storage_bytes": storage * 1024**3, "max_height": height, "social_accounts": socials,
        })


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
