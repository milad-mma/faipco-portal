package ir.faipco.portal

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** بعد از روشن شدن گوشی یا نصب نسخه‌ی جدید، محدوده‌ها دوباره ثبت می‌شوند (سیستم‌عامل آن‌ها را پاک کرده است). */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            if (Prefs.deviceToken(context) != null) Work.syncNow(context, forceRegister = true)
        }
    }
}
