from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0003_add_product_is_active')]

    operations = [
        migrations.AddField(
            model_name='product', name='source',
            field=models.CharField(max_length=16, default='pchome', db_index=True, verbose_name='資料來源'),
        ),
        migrations.AddField(
            model_name='product', name='product_url',
            field=models.URLField(max_length=512, blank=True, default='', verbose_name='商品網址'),
        ),
        migrations.AlterField(
            model_name='product', name='id',
            field=models.CharField(max_length=64, primary_key=True, serialize=False, verbose_name='來源商品 ID'),
        ),
    ]
