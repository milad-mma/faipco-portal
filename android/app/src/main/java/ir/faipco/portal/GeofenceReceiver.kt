package ir.faipco.portal

import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.location.Location
import android.location.LocationManager
import android.os.Build
import com.google.android.gms.location.Geofence
import com.google.android.gms.location.GeofencingEvent
import org.json.JSONObject
import java.util.UUID
import kotlin.math.abs

/**
 * بیدار شدن لحظه‌ی ورود/خروج: رویداد در صف گوشی ذخیره و ارسالش به WorkManager سپرده می‌شود
 * (اگر اینترنت نباشد، با زمان واقعی‌اش بعداً ارسال می‌شود).
 */
class GeofenceReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val engine = intent.getStringExtra(GeofenceController.EXTRA_ENGINE) ?: "gms"
        if (engine == "platform") handlePlatform(context, intent) else handleGms(context, intent)
        Work.uploadNow(context)
    }

    private fun handleGms(ctx: Context, intent: Intent) {
        val event = GeofencingEvent.fromIntent(intent) ?: return
        if (event.hasError()) return
        val transition = when (event.geofenceTransition) {
            Geofence.GEOFENCE_TRANSITION_DWELL -> "dwell"
            Geofence.GEOFENCE_TRANSITION_ENTER -> "enter"
            Geofence.GEOFENCE_TRANSITION_EXIT -> "exit"
            else -> return
        }
        val location = event.triggeringLocation
        for (fence in event.triggeringGeofences.orEmpty()) {
            val siteId = fence.requestId.toIntOrNull() ?: continue
            enqueue(ctx, transition, siteId, location, "gms")
        }
    }

    @SuppressLint("MissingPermission")
    private fun handlePlatform(ctx: Context, intent: Intent) {
        val siteId = intent.getIntExtra(GeofenceController.EXTRA_SITE_ID, -1)
        if (siteId < 0 || !intent.hasExtra(LocationManager.KEY_PROXIMITY_ENTERING)) return
        val entering = intent.getBooleanExtra(LocationManager.KEY_PROXIMITY_ENTERING, false)
        val location = runCatching {
            (ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager)
                .getLastKnownLocation(LocationManager.PASSIVE_PROVIDER)
        }.getOrNull()
        enqueue(ctx, if (entering) "enter" else "exit", siteId, location, "platform")
    }

    private fun enqueue(ctx: Context, transition: String, siteId: Int, location: Location?, engine: String) {
        val now = System.currentTimeMillis()
        // زمان موقعیت اگر تازه باشد دقیق‌تر است؛ وگرنه زمان همین لحظه
        val at = location?.time?.takeIf { abs(now - it) < 10 * 60 * 1000 } ?: now
        val json = JSONObject()
            .put("id", UUID.randomUUID().toString())
            .put("transition", transition)
            .put("site_id", siteId)
            .put("occurred_at", at)
            .put("engine", engine)
            .put("is_mock", location?.let { isMock(it) } ?: false)
        if (location != null) {
            json.put("latitude", location.latitude).put("longitude", location.longitude)
            if (location.hasAccuracy()) json.put("accuracy", location.accuracy.toDouble())
        }
        Prefs.enqueueEvent(ctx, json)
    }

    @Suppress("DEPRECATION")
    private fun isMock(location: Location): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) location.isMock else location.isFromMockProvider
}
