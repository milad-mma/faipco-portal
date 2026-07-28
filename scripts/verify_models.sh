#!/usr/bin/env bash
# تست سریع صحت مدل‌های SQLAlchemy (بدون نیاز به دیتابیس واقعی)
# اجرا: bash scripts/verify_models.sh
set -e
cd "$(dirname "$0")/../backend"

python3 -c "
from app.db.session import Base
import app.models  # noqa

print('تعداد جدول‌های شناسایی‌شده:', len(Base.metadata.tables))
for table_name in sorted(Base.metadata.tables.keys()):
    print(' -', table_name)
print('همه مدل‌ها و رابطه‌ها بدون خطا Load شدند ✅')
"
