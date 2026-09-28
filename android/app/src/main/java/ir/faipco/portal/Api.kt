package ir.faipco.portal

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** خطای پاسخ سرور؛ code=401 یعنی توکن دستگاه باطل شده است. */
class ApiException(val code: Int, message: String) : IOException(message)

/**
 * ارتباط با API پرتال (/api/v1/mobile/...). فقط از رشته‌ی پس‌زمینه صدا زده می‌شود.
 * احراز هویت دستگاه با هدر X-Device-Token است، نه رمز کاربر.
 */
object Api {
    private val base = BuildConfig.PORTAL_URL + "/api/v1/mobile"

    private fun request(method: String, path: String, token: String?, body: JSONObject?): JSONObject {
        val conn = (URL(base + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 15000
            readTimeout = 20000
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "FaipcoAndroid/${BuildConfig.VERSION_NAME}")
            if (token != null) setRequestProperty("X-Device-Token", token)
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
        }
        try {
            if (body != null) conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
            if (code !in 200..299) {
                val detail = runCatching { JSONObject(text).optString("detail") }.getOrNull()
                throw ApiException(code, if (detail.isNullOrBlank()) "خطای سرور ($code)" else detail)
            }
            if (text.isBlank() || text == "null") return JSONObject()
            return JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }

    fun register(code: String, info: JSONObject): JSONObject = request("POST", "/devices/register", null, info.put("code", code))

    fun status(token: String, status: JSONObject): JSONObject = request("POST", "/device/status", token, status)

    fun geofences(token: String): JSONObject = request("GET", "/device/geofences", token, null)

    fun events(token: String, events: JSONArray): JSONObject =
        request("POST", "/device/events", token, JSONObject().put("events", events))
}
