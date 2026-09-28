package ir.faipco.portal

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

/** اعلان‌های بومی اپ (نتیجه‌ی ثبت خودکار ورود/خروج). اعلان‌های پرتال از طریق TWA جدا می‌آیند. */
object Notifier {
    private const val CHANNEL = "attendance"

    fun createChannel(ctx: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(CHANNEL, ctx.getString(R.string.channel_attendance), NotificationManager.IMPORTANCE_DEFAULT)
            ctx.getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
        }
    }

    fun show(ctx: Context, text: String) {
        if (!DeviceState.notifications(ctx)) return
        val open = PendingIntent.getActivity(
            ctx, 0, Intent(ctx, MainLauncherActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(ctx.getString(R.string.app_name))
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(ctx).notify(text.hashCode(), notification)
        } catch (e: SecurityException) {
            // اجازه‌ی اعلان برداشته شده
        }
    }
}
