package ir.faipco.portal

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.Build
import android.os.PowerManager
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.core.location.LocationManagerCompat
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.common.GoogleApiAvailability
import org.json.JSONObject

/** وضعیت دسترسی‌ها و سرویس‌های گوشی؛ همان چیزی که به سرور گزارش می‌شود. */
object DeviceState {
    private fun granted(ctx: Context, perm: String) =
        ContextCompat.checkSelfPermission(ctx, perm) == PackageManager.PERMISSION_GRANTED

    fun fineLocation(ctx: Context) = granted(ctx, Manifest.permission.ACCESS_FINE_LOCATION)

    /** اندروید ۹ و قبل‌تر دسترسی جدای «همیشه» ندارد؛ همان دسترسی موقعیت کافی است. */
    fun backgroundLocation(ctx: Context) =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) granted(ctx, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
        else fineLocation(ctx)

    fun notifications(ctx: Context) = NotificationManagerCompat.from(ctx).areNotificationsEnabled()

    fun batteryUnrestricted(ctx: Context): Boolean {
        val pm = ctx.getSystemService(Context.POWER_SERVICE) as PowerManager
        return pm.isIgnoringBatteryOptimizations(ctx.packageName)
    }

    fun locationEnabled(ctx: Context): Boolean {
        val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        return LocationManagerCompat.isLocationEnabled(lm)
    }

    fun hasGms(ctx: Context): Boolean =
        GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(ctx) == ConnectionResult.SUCCESS

    fun engine(ctx: Context) = if (hasGms(ctx)) "gms" else "platform"

    fun statusJson(ctx: Context): JSONObject {
        val count = Prefs.registeredCount(ctx)
        val registered = Prefs.registeredVersion(ctx) != null && backgroundLocation(ctx)
        return JSONObject()
            .put("fine_location", fineLocation(ctx))
            .put("background_location", backgroundLocation(ctx))
            .put("notifications", notifications(ctx))
            .put("battery_unrestricted", batteryUnrestricted(ctx))
            .put("location_enabled", locationEnabled(ctx))
            .put("has_gms", hasGms(ctx))
            .put("engine", Prefs.registeredEngine(ctx) ?: engine(ctx))
            .put("geofences_registered", registered)
            .put("geofence_count", if (registered) count else 0)
            .put("app_version_code", BuildConfig.VERSION_CODE)
            .put("app_version_name", BuildConfig.VERSION_NAME)
            .put("os_version", Build.VERSION.RELEASE ?: "")
            .put("sdk_int", Build.VERSION.SDK_INT)
    }

    fun registerInfo(ctx: Context): JSONObject = JSONObject()
        .put("device_uid", Prefs.deviceUid(ctx))
        .put("manufacturer", Build.MANUFACTURER ?: "")
        .put("model", Build.MODEL ?: "")
        .put("os_version", Build.VERSION.RELEASE ?: "")
        .put("sdk_int", Build.VERSION.SDK_INT)
        .put("app_version_code", BuildConfig.VERSION_CODE)
        .put("app_version_name", BuildConfig.VERSION_NAME)
}
