# سیستم اطلاعیه


```bash
curl -X POST http://localhost:8000/api/v1/notices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "title": "اطلاعیه تعطیلی", "body": "روز پنج‌شنبه تعطیل است.", "priority": "high",
    "targets": [{"target_type": "site", "target_id": 1}, {"target_type": "role", "target_id": 1}]
  }'

curl -X POST http://localhost:8000/api/v1/notices/1/publish -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/v1/notices -H "Authorization: Bearer $TOKEN"       # نمای Admin (نیازمند notices.view)
curl http://localhost:8000/api/v1/notices/me -H "Authorization: Bearer $TOKEN"    # اطلاعیه‌های خودِ کاربر لاگین‌شده
```

`/notices/me` هوشمند است: بر اساس Site/Department/نقش‌های کاربر، فقط اطلاعیه‌های
واقعاً مرتبط را برمی‌گرداند — دقیقاً طبق طراحی `notice_targets`
(all / site / department / role / employee).

### حذف اطلاعیه

حذف همیشه **Soft-Delete** است:

```bash
curl -X DELETE http://localhost:8000/api/v1/notices/1 -H "Authorization: Bearer $TOKEN"
```

- بلافاصله از پنل همه‌ی کسانی که اطلاعیه را دریافت کرده بودند کنار می‌رود.
- رکورد فیزیکی هرگز پاک نمی‌شود — در گزارش «ارسالی من» و گزارش کامل Admin با
  برچسب «حذف شده» باقی می‌ماند (تا آمار بازدید از دست نرود).
- فقط خودِ فرستنده یا Admin اجازه حذف دارند.

