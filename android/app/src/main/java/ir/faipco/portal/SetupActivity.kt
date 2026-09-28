package ir.faipco.portal

import android.Manifest
import android.annotation.SuppressLint
import android.content.ComponentName
import android.content.Intent
import android.graphics.Typeface
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * بخش بومی اپ: اتصال گوشی به حساب (با کد یک‌بارمصرف از پرتال: faipco://pair?code=...) و راهنمای گام‌به‌گام
 * دسترسی‌ها (faipco://setup). هر ردیف وضعیت فعلی را نشان می‌دهد و دکمه‌ی «ادامه» اولین مورد ناقص را درست می‌کند.
 * متن توضیحی بالای صفحه همان «اطلاع‌رسانی آشکار» است که اندروید پیش از درخواست موقعیت پس‌زمینه لازم می‌داند.
 */
class SetupActivity : AppCompatActivity() {

    private enum class Step { ACCOUNT, LOCATION, BACKGROUND, GPS_ON, NOTIFICATIONS, BATTERY, AUTOSTART }

    private data class Row(val title: TextView, val status: TextView, val action: Button)

    private val rows = mutableMapOf<Step, Row>()
    private lateinit var mainButton: Button
    private lateinit var messageView: TextView
    private var pairing = false
    private var pairError: String? = null

    private val prefs by lazy { getSharedPreferences("faipco", MODE_PRIVATE) }

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { refresh() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        refresh()
        // هر بار برگشت به این صفحه (مثلاً از تنظیمات گوشی): ثبت محدوده‌ها و گزارش وضعیت
        if (Prefs.deviceToken(this) != null) Work.syncNow(this, forceRegister = false)
    }

    // ------------------------------------------------------------------ اتصال به حساب

    private fun handleIntent(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.host == "pair") {
            val code = data.getQueryParameter("code")
            if (!code.isNullOrBlank()) pair(code)
        }
    }

    private fun pair(code: String) {
        pairing = true
        pairError = null
        refresh()
        lifecycleScope.launch {
            val error = withContext(Dispatchers.IO) {
                try {
                    val res = Api.register(code, DeviceState.registerInfo(this@SetupActivity))
                    Prefs.setDeviceToken(this@SetupActivity, res.getString("device_token"))
                    null
                } catch (e: ApiException) {
                    e.message
                } catch (e: Exception) {
                    "ارتباط با سرور برقرار نشد؛ اینترنت را بررسی کنید و از پرتال دوباره «فعال‌سازی» را بزنید."
                }
            }
            pairing = false
            pairError = error
            if (error == null) Work.syncNow(this@SetupActivity, forceRegister = true)
            refresh()
        }
    }

    // ------------------------------------------------------------------ وضعیت هر مرحله

    private fun needsAutostart(): Boolean {
        val m = (Build.MANUFACTURER ?: "").lowercase()
        return listOf("xiaomi", "redmi", "poco", "huawei", "honor", "oppo", "vivo", "realme").any { m.contains(it) }
    }

    private fun applicable(step: Step): Boolean = when (step) {
        Step.BACKGROUND -> Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
        Step.NOTIFICATIONS -> true
        Step.AUTOSTART -> needsAutostart()
        else -> true
    }

    private fun done(step: Step): Boolean = when (step) {
        Step.ACCOUNT -> Prefs.deviceToken(this) != null
        Step.LOCATION -> DeviceState.fineLocation(this)
        Step.BACKGROUND -> DeviceState.backgroundLocation(this)
        Step.GPS_ON -> DeviceState.locationEnabled(this)
        Step.NOTIFICATIONS -> DeviceState.notifications(this)
        Step.BATTERY -> DeviceState.batteryUnrestricted(this)
        Step.AUTOSTART -> prefs.getBoolean("autostart_confirmed", false)
    }

    private fun nextMissing(): Step? = Step.values().firstOrNull { applicable(it) && !done(it) }

    @SuppressLint("SetTextI18n")
    private fun refresh() {
        for ((step, row) in rows) {
            val visible = applicable(step)
            (row.title.parent as View).visibility = if (visible) View.VISIBLE else View.GONE
            if (!visible) continue
            val ok = done(step)
            row.status.text = when {
                step == Step.ACCOUNT && pairing -> "در حال اتصال…"
                step == Step.ACCOUNT && pairError != null -> pairError
                ok -> "✓ انجام شد"
                else -> "انجام نشده"
            }
            row.status.setTextColor(
                ContextCompat.getColor(this, if (ok) R.color.ok else if (step == Step.ACCOUNT && pairError != null) R.color.bad else R.color.warn)
            )
            row.action.visibility = if (ok || (step == Step.ACCOUNT && pairing)) View.GONE else View.VISIBLE
        }
        val missing = nextMissing()
        mainButton.text = if (missing == null) "بازگشت به پرتال" else "ادامه"
        messageView.text = if (missing == null) "همه‌چیز آماده است. ورود و خروج شما از این پس خودکار ثبت می‌شود." else ""
    }

    // ------------------------------------------------------------------ انجام هر مرحله

    private fun perform(step: Step) {
        when (step) {
            Step.ACCOUNT -> openPortal("/mobile-app")
            Step.LOCATION -> permissionLauncher.launch(
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            )
            Step.BACKGROUND -> requestBackground()
            Step.GPS_ON -> startActivitySafe(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS))
            Step.NOTIFICATIONS -> requestNotifications()
            Step.BATTERY -> requestBattery()
            Step.AUTOSTART -> openAutostart()
        }
    }

    private fun requestBackground() {
        if (!DeviceState.fineLocation(this)) {
            perform(Step.LOCATION)
            return
        }
        AlertDialog.Builder(this)
            .setTitle("موقعیت «همیشه مجاز»")
            .setMessage(
                "برای ثبت خودکار ورود و خروج وقتی اپ بسته است، در صفحه‌ی بعد گزینه‌ی «همیشه مجاز» " +
                    "(Allow all the time) را انتخاب کنید و برگردید."
            )
            .setPositiveButton("باشه") { _, _ ->
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    if (shouldShowRequestPermissionRationale(Manifest.permission.ACCESS_BACKGROUND_LOCATION) ||
                        Build.VERSION.SDK_INT == Build.VERSION_CODES.Q ||
                        !prefs.getBoolean("bg_asked", false)
                    ) {
                        prefs.edit().putBoolean("bg_asked", true).apply()
                        permissionLauncher.launch(arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION))
                    } else {
                        openAppSettings()
                    }
                }
            }
            .setNegativeButton("انصراف", null)
            .show()
    }

    private fun requestNotifications() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !prefs.getBoolean("notif_asked", false)) {
            prefs.edit().putBoolean("notif_asked", true).apply()
            permissionLauncher.launch(arrayOf(Manifest.permission.POST_NOTIFICATIONS))
        } else {
            val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
            startActivitySafe(intent) { openAppSettings() }
        }
    }

    @SuppressLint("BatteryLife")
    private fun requestBattery() {
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName"))
        startActivitySafe(intent) { startActivitySafe(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
    }

    private fun openAutostart() {
        val candidates = listOf(
            ComponentName("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"),
            ComponentName("com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
            ComponentName("com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity"),
            ComponentName("com.hihonor.systemmanager", "com.hihonor.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
            ComponentName("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity"),
            ComponentName("com.oppo.safe", "com.oppo.safe.permission.startup.StartupAppListActivity"),
            ComponentName("com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity"),
        )
        val opened = candidates.any { c ->
            runCatching { startActivity(Intent().setComponent(c).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); true }.getOrDefault(false)
        }
        if (!opened) openAppSettings()
        AlertDialog.Builder(this)
            .setTitle("اجرای خودکار")
            .setMessage("در صفحه‌ای که باز شد، اجرای خودکار (Autostart) را برای FAIPCO روشن کنید. انجام دادید؟")
            .setPositiveButton("بله، روشن کردم") { _, _ ->
                prefs.edit().putBoolean("autostart_confirmed", true).apply()
                refresh()
            }
            .setNegativeButton("هنوز نه", null)
            .show()
    }

    private fun openAppSettings() {
        startActivitySafe(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
    }

    private fun startActivitySafe(intent: Intent, fallback: (() -> Unit)? = null) {
        try {
            startActivity(intent)
        } catch (e: Exception) {
            fallback?.invoke()
        }
    }

    private fun openPortal(path: String) {
        val uri = Uri.parse(BuildConfig.PORTAL_URL + path).buildUpon().appendQueryParameter("source", "android-app").build()
        startActivity(Intent(this, MainLauncherActivity::class.java).setData(uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        finish()
    }

    // ------------------------------------------------------------------ رابط کاربری (بدون فایل XML)

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun text(size: Float, bold: Boolean = false, color: Int = R.color.colorPrimary) = TextView(this).apply {
        textSize = size
        setTextColor(ContextCompat.getColor(this@SetupActivity, color))
        if (bold) setTypeface(typeface, Typeface.BOLD)
        gravity = Gravity.START
        textDirection = View.TEXT_DIRECTION_RTL
        setLineSpacing(0f, 1.3f)
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutDirection = View.LAYOUT_DIRECTION_RTL
            setPadding(dp(20), dp(24), dp(20), dp(24))
        }
        root.addView(text(22f, bold = true).apply { text = "فعال‌سازی اپ FAIPCO" })
        root.addView(text(14f, color = R.color.muted).apply {
            text = "این اپ برای ثبت خودکار ورود و خروج، فقط لحظه‌ی رسیدن به محدوده‌ی کارخانه و ترک آن از موقعیت " +
                "گوشی استفاده می‌کند؛ حتی وقتی اپ بسته است. موقعیت شما دائم دنبال یا ذخیره نمی‌شود و مصرف باتری ناچیز است. " +
                "برای این کار دسترسی‌های زیر لازم است."
            setPadding(0, dp(8), 0, dp(16))
        })

        val titles = mapOf(
            Step.ACCOUNT to ("اتصال به حساب" to "این گوشی به حساب پرتال شما متصل می‌شود."),
            Step.LOCATION to ("اجازه‌ی موقعیت" to "برای تشخیص محدوده‌ی کارخانه."),
            Step.BACKGROUND to ("موقعیت «همیشه مجاز»" to "تا ورود و خروج با اپ بسته هم ثبت شود."),
            Step.GPS_ON to ("روشن بودن موقعیت‌یاب" to "موقعیت‌یاب (GPS) گوشی باید روشن باشد."),
            Step.NOTIFICATIONS to ("اجازه‌ی اعلان" to "برای اطلاعیه‌های پرتال و تأیید ثبت ورود و خروج."),
            Step.BATTERY to ("بدون محدودیت باتری" to "تا گوشی اپ را در پس‌زمینه نبندد."),
            Step.AUTOSTART to ("اجرای خودکار" to "مخصوص گوشی‌های شیائومی، هواوی و مشابه."),
        )
        for (step in Step.values()) {
            val (title, desc) = titles.getValue(step)
            val box = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(14), dp(12), dp(14), dp(12))
                background = ContextCompat.getDrawable(this@SetupActivity, android.R.drawable.dialog_holo_light_frame)
            }
            val t = text(16f, bold = true).apply { text = title }
            val d = text(13f, color = R.color.muted).apply { text = desc }
            val s = text(13f, bold = true)
            val a = Button(this).apply {
                text = if (step == Step.ACCOUNT) "رفتن به پرتال" else "انجام"
                setOnClickListener { perform(step) }
            }
            box.addView(t)
            box.addView(d)
            box.addView(s)
            box.addView(a, LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT))
            root.addView(box, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                bottomMargin = dp(8)
            })
            rows[step] = Row(t, s, a)
        }

        messageView = text(14f, bold = true, color = R.color.ok).apply { setPadding(0, dp(8), 0, dp(8)) }
        root.addView(messageView)
        mainButton = Button(this).apply {
            textSize = 16f
            setOnClickListener {
                val missing = nextMissing()
                if (missing == null) openPortal("/mobile-app") else perform(missing)
            }
        }
        root.addView(mainButton, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(52)))

        setContentView(ScrollView(this).apply { addView(root) })
    }
}
