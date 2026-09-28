package ir.faipco.portal

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException
import java.util.concurrent.TimeUnit

/** کارهای پس‌زمینه‌ی کوتاه (WorkManager): ارسال رویدادها، همگام‌سازی محدوده‌ها و گزارش وضعیت. */
object Work {
    private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

    fun uploadNow(ctx: Context) {
        val request = OneTimeWorkRequestBuilder<UploadWorker>()
            .setConstraints(network)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(ctx).enqueueUniqueWork("upload", ExistingWorkPolicy.APPEND_OR_REPLACE, request)
    }

    fun syncNow(ctx: Context, forceRegister: Boolean) {
        val request = OneTimeWorkRequestBuilder<SyncWorker>()
            .setInputData(workDataOf("force" to forceRegister))
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(ctx).enqueueUniqueWork("sync", ExistingWorkPolicy.REPLACE, request)
    }

    /** روزی یک‌بار: گزارش وضعیت به سرور و گرفتن تغییرات محدوده‌ها (مصرف ناچیز). */
    fun schedulePeriodic(ctx: Context) {
        val request = PeriodicWorkRequestBuilder<SyncWorker>(24, TimeUnit.HOURS)
            .setConstraints(network)
            .build()
        WorkManager.getInstance(ctx).enqueueUniquePeriodicWork("daily-sync", ExistingPeriodicWorkPolicy.KEEP, request)
    }

    /** توکن باطل شد (مدیر گوشی را باطل کرد یا اتصال دوباره): پاک‌کردن توکن و محدوده‌ها. */
    suspend fun handleRevoked(ctx: Context) {
        Prefs.setDeviceToken(ctx, null)
        GeofenceController.clear(ctx)
    }
}

class UploadWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val token = Prefs.deviceToken(applicationContext) ?: return@withContext Result.success()
        val queue = Prefs.queue(applicationContext)
        if (queue.length() == 0) return@withContext Result.success()
        try {
            val results = Api.events(token, queue).optJSONArray("results")
            val done = mutableSetOf<String>()
            val messages = mutableListOf<String>()
            if (results != null) {
                for (i in 0 until results.length()) {
                    val r = results.getJSONObject(i)
                    done += r.optString("id")
                    r.optString("message").takeIf { it.isNotBlank() && it != "null" }?.let { messages += it }
                }
            }
            Prefs.removeEvents(applicationContext, done)
            messages.forEach { Notifier.show(applicationContext, it) }
            Result.success()
        } catch (e: ApiException) {
            when (e.code) {
                401 -> { Work.handleRevoked(applicationContext); Result.success() }
                in 500..599 -> Result.retry()
                else -> Result.failure()
            }
        } catch (e: IOException) {
            Result.retry()
        }
    }
}

class SyncWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val ctx = applicationContext
        val token = Prefs.deviceToken(ctx) ?: return@withContext Result.success()
        val force = inputData.getBoolean("force", false)
        // اول با پیکربندی ذخیره‌شده (بدون نیاز به اینترنت؛ مهم بعد از ری‌استارت گوشی)
        Prefs.geofenceConfig(ctx)?.let { GeofenceController.apply(ctx, it, force) }
        try {
            val config = Api.geofences(token)
            Prefs.setGeofenceConfig(ctx, config)
            GeofenceController.apply(ctx, config, force = false)
            Api.status(token, DeviceState.statusJson(ctx))
            if (Prefs.queue(ctx).length() > 0) Work.uploadNow(ctx)
            Result.success()
        } catch (e: ApiException) {
            if (e.code == 401) { Work.handleRevoked(ctx); Result.success() } else Result.retry()
        } catch (e: IOException) {
            Result.retry()
        }
    }
}
