package ir.faipco.portal

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * حافظه‌ی اپ:
 * - توکن دستگاه در EncryptedSharedPreferences (رمزشده با Android Keystore).
 * - شناسه‌ی نصب، تنظیمات محدوده‌ها و صف رویدادهای ارسال‌نشده در SharedPreferences معمولی.
 */
object Prefs {
    private const val PLAIN = "faipco"
    private const val SECURE = "faipco_secure"

    private fun plain(ctx: Context): SharedPreferences = ctx.getSharedPreferences(PLAIN, Context.MODE_PRIVATE)

    @Volatile private var secureCache: SharedPreferences? = null

    private fun secure(ctx: Context): SharedPreferences {
        secureCache?.let { return it }
        val prefs = try {
            val key = MasterKey.Builder(ctx).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
            EncryptedSharedPreferences.create(
                ctx, SECURE, key,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        } catch (e: Exception) {
            // Keystore خراب (بعضی گوشی‌ها بعد از بازیابی): حافظه‌ی معمولی؛ کاربر در بدترین حالت دوباره فعال‌سازی می‌کند
            ctx.getSharedPreferences(SECURE + "_fallback", Context.MODE_PRIVATE)
        }
        secureCache = prefs
        return prefs
    }

    fun deviceUid(ctx: Context): String {
        val p = plain(ctx)
        return p.getString("device_uid", null) ?: UUID.randomUUID().toString().also { p.edit().putString("device_uid", it).apply() }
    }

    fun deviceToken(ctx: Context): String? = secure(ctx).getString("device_token", null)

    fun setDeviceToken(ctx: Context, token: String?) {
        secure(ctx).edit().apply { if (token == null) remove("device_token") else putString("device_token", token) }.apply()
    }

    /** آخرین پیکربندی محدوده‌ها از سرور (JSON) و وضعیت ثبت در سیستم‌عامل. */
    fun geofenceConfig(ctx: Context): JSONObject? = plain(ctx).getString("geofence_config", null)?.let { JSONObject(it) }

    fun setGeofenceConfig(ctx: Context, json: JSONObject?) {
        plain(ctx).edit().putString("geofence_config", json?.toString()).apply()
    }

    fun registeredVersion(ctx: Context): String? = plain(ctx).getString("registered_version", null)

    fun setRegistered(ctx: Context, version: String?, count: Int, engine: String?) {
        plain(ctx).edit().putString("registered_version", version).putInt("registered_count", count)
            .putString("registered_engine", engine).apply()
    }

    fun registeredCount(ctx: Context): Int = plain(ctx).getInt("registered_count", 0)
    fun registeredEngine(ctx: Context): String? = plain(ctx).getString("registered_engine", null)

    fun registeredSiteIds(ctx: Context): List<Int> =
        (plain(ctx).getString("registered_sites", null) ?: "").split(",").mapNotNull { it.toIntOrNull() }

    fun setRegisteredSiteIds(ctx: Context, ids: List<Int>) {
        plain(ctx).edit().putString("registered_sites", ids.joinToString(",")).apply()
    }

    // ---------- صف رویدادها (تا ارسال موفق در گوشی می‌مانند)

    private val queueLock = Any()

    fun enqueueEvent(ctx: Context, event: JSONObject) = synchronized(queueLock) {
        val arr = queue(ctx)
        arr.put(event)
        // سقف ۲۰۰ رویداد؛ قدیمی‌ترها حذف می‌شوند
        val trimmed = JSONArray()
        val start = maxOf(0, arr.length() - 200)
        for (i in start until arr.length()) trimmed.put(arr.getJSONObject(i))
        plain(ctx).edit().putString("event_queue", trimmed.toString()).apply()
    }

    fun queue(ctx: Context): JSONArray = synchronized(queueLock) {
        JSONArray(plain(ctx).getString("event_queue", null) ?: "[]")
    }

    fun removeEvents(ctx: Context, ids: Set<String>) = synchronized(queueLock) {
        val arr = queue(ctx)
        val kept = JSONArray()
        for (i in 0 until arr.length()) {
            val e = arr.getJSONObject(i)
            if (e.optString("id") !in ids) kept.put(e)
        }
        plain(ctx).edit().putString("event_queue", kept.toString()).apply()
    }
}
