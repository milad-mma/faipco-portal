package ir.faipco.portal

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.location.LocationManager
import android.os.Build
import android.util.Log
import com.google.android.gms.location.Geofence
import com.google.android.gms.location.GeofencingRequest
import com.google.android.gms.location.LocationServices
import kotlinx.coroutines.tasks.await
import org.json.JSONObject

/**
 * ثبت محدوده‌های سایت‌ها در سیستم‌عامل. اپ بعد از ثبت می‌خوابد؛ خود اندروید با کمترین مصرف (دکل و Wi-Fi)
 * تغییر محل را دنبال می‌کند و فقط لحظه‌ی ورود/خروج GeofenceReceiver را بیدار می‌کند. سرویس دائمی در کار نیست.
 *
 * - گوشی دارای سرویس‌های گوگل: GeofencingClient (ورود = DWELL بعد از مکث loitering، خروج = EXIT).
 * - گوشی بدون سرویس‌های گوگل: موتور داخلی اندروید (LocationManager.addProximityAlert) با ورود/خروج.
 */
object GeofenceController {
    private const val TAG = "FaipcoGeofence"
    const val EXTRA_SITE_ID = "site_id"
    const val EXTRA_ENGINE = "engine"
    private const val GMS_REQUEST_CODE = 9000

    private fun mutableFlag() = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) PendingIntent.FLAG_MUTABLE else 0

    private fun gmsIntent(ctx: Context): PendingIntent {
        val intent = Intent(ctx, GeofenceReceiver::class.java).putExtra(EXTRA_ENGINE, "gms")
        return PendingIntent.getBroadcast(ctx, GMS_REQUEST_CODE, intent, PendingIntent.FLAG_UPDATE_CURRENT or mutableFlag())
    }

    private fun platformIntent(ctx: Context, siteId: Int): PendingIntent {
        val intent = Intent(ctx, GeofenceReceiver::class.java)
            .setAction("ir.faipco.portal.PROXIMITY.$siteId")
            .putExtra(EXTRA_ENGINE, "platform")
            .putExtra(EXTRA_SITE_ID, siteId)
        return PendingIntent.getBroadcast(ctx, 10000 + siteId, intent, PendingIntent.FLAG_UPDATE_CURRENT or mutableFlag())
    }

    /** همه‌ی محدوده‌های ثبت‌شده‌ی قبلی (هر دو موتور) را برمی‌دارد. */
    @SuppressLint("MissingPermission")
    suspend fun clear(ctx: Context) {
        runCatching { LocationServices.getGeofencingClient(ctx).removeGeofences(gmsIntent(ctx)).await() }
        val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        for (id in Prefs.registeredSiteIds(ctx)) runCatching { lm.removeProximityAlert(platformIntent(ctx, id)) }
        Prefs.setRegisteredSiteIds(ctx, emptyList())
        Prefs.setRegistered(ctx, null, 0, null)
    }

    /**
     * پیکربندی را ثبت می‌کند اگر عوض شده یا force (بعد از ری‌استارت گوشی سیستم محدوده‌ها را پاک می‌کند).
     * خروجی: true اگر محدوده‌ها الان ثبت‌اند.
     */
    @SuppressLint("MissingPermission")
    suspend fun apply(ctx: Context, config: JSONObject, force: Boolean): Boolean {
        val version = config.optString("version")
        if (!DeviceState.fineLocation(ctx) || !DeviceState.backgroundLocation(ctx)) {
            Prefs.setRegistered(ctx, null, 0, null)
            return false
        }
        if (!force && version.isNotEmpty() && version == Prefs.registeredVersion(ctx)) return true

        clear(ctx)
        val sites = config.optJSONArray("sites")
        if (!config.optBoolean("enabled", true) || sites == null || sites.length() == 0) {
            // ثبت خودکار خاموش یا سایتی با GPS تنظیم نشده: «ثبت‌شده» با صفر محدوده
            Prefs.setRegistered(ctx, version, 0, DeviceState.engine(ctx))
            return true
        }
        val ids = mutableListOf<Int>()
        return try {
            if (DeviceState.hasGms(ctx)) {
                val loitering = config.optInt("loitering_ms", 120000)
                val responsiveness = config.optInt("responsiveness_ms", 180000)
                val fences = (0 until sites.length()).map { i ->
                    val s = sites.getJSONObject(i)
                    ids += s.getInt("id")
                    Geofence.Builder()
                        .setRequestId(s.getInt("id").toString())
                        .setCircularRegion(s.getDouble("latitude"), s.getDouble("longitude"), s.getDouble("radius").toFloat())
                        .setExpirationDuration(Geofence.NEVER_EXPIRE)
                        .setTransitionTypes(Geofence.GEOFENCE_TRANSITION_DWELL or Geofence.GEOFENCE_TRANSITION_EXIT)
                        .setLoiteringDelay(loitering)
                        .setNotificationResponsiveness(responsiveness)
                        .build()
                }
                val request = GeofencingRequest.Builder()
                    .setInitialTrigger(GeofencingRequest.INITIAL_TRIGGER_DWELL)
                    .addGeofences(fences)
                    .build()
                LocationServices.getGeofencingClient(ctx).addGeofences(request, gmsIntent(ctx)).await()
                Prefs.setRegistered(ctx, version, fences.size, "gms")
            } else {
                val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager
                for (i in 0 until sites.length()) {
                    val s = sites.getJSONObject(i)
                    val id = s.getInt("id")
                    lm.addProximityAlert(
                        s.getDouble("latitude"), s.getDouble("longitude"), s.getDouble("radius").toFloat(),
                        -1L, platformIntent(ctx, id),
                    )
                    ids += id
                }
                Prefs.setRegistered(ctx, version, ids.size, "platform")
            }
            Prefs.setRegisteredSiteIds(ctx, ids)
            true
        } catch (e: Exception) {
            Log.w(TAG, "ثبت محدوده‌ها ناموفق بود", e)
            Prefs.setRegistered(ctx, null, 0, null)
            false
        }
    }
}
