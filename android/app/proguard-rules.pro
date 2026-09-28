# کلاس‌های مدل JSON نداریم (org.json)؛ قوانین پیش‌فرض کافی است.
-keep class com.google.androidbrowserhelper.** { *; }

# security-crypto → Tink: کلاس‌های annotation که در classpath نیستند (خطای «Missing classes» در R8)
-dontwarn com.google.errorprone.annotations.**
-dontwarn javax.annotation.**
-dontwarn com.google.api.client.http.**
-dontwarn org.joda.time.Instant
