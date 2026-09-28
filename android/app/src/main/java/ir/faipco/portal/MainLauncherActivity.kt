package ir.faipco.portal

import android.net.Uri
import android.os.Bundle
import com.google.androidbrowserhelper.trusted.LauncherActivity

/**
 * ورود به اپ: پرتال را در TWA (Chrome تمام‌صفحه) باز می‌کند. پارامتر source=android-app به آدرس اضافه می‌شود
 * تا پرتال بداند داخل اپ است. با هر باز شدن، وضعیت گوشی و محدوده‌ها هم در پس‌زمینه به‌روز می‌شود.
 */
class MainLauncherActivity : LauncherActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Prefs.deviceToken(this) != null) Work.syncNow(this, forceRegister = false)
    }

    override fun getLaunchingUrl(): Uri {
        val base = super.getLaunchingUrl()
        if (base.getQueryParameter("source") != null) return base
        return base.buildUpon().appendQueryParameter("source", "android-app").build()
    }
}
