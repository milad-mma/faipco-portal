package ir.faipco.portal

import android.app.Application

/** راه‌اندازی اولیه: کانال اعلان «ورود و خروج» و زمان‌بندی گزارش روزانه‌ی وضعیت. */
class FaipcoApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Notifier.createChannel(this)
        Work.schedulePeriodic(this)
    }
}
