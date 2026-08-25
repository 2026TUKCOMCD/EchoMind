package com.tukorea.echomind

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.data.local.AppDatabase
import com.tukorea.echomind.data.local.PersonalityEntity
import com.tukorea.echomind.databinding.ActivityMainBinding
import com.tukorea.echomind.models.*
import kotlinx.coroutines.launch
import org.jsoup.Jsoup
import java.io.Serializable

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val db by lazy { AppDatabase.getDatabase(this) }
    private val apiService = GlobalClient.apiService
    private var currentEmail: String = "" 

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        currentEmail = getSharedPreferences("EchoMindSession", Context.MODE_PRIVATE).getString("user_email", "") ?: ""

        setupUI()
        updateThemeIcon()
        syncDataWithSafety()
    }

    private fun setupUI() {
        binding.btnMenuToggle.setOnClickListener {
            if (binding.menuOverlay.visibility == View.VISIBLE) closeMenu() 
            else {
                binding.menuOverlay.visibility = View.VISIBLE
                binding.btnMenuToggle.setImageResource(android.R.drawable.ic_menu_close_clear_cancel)
            }
        }
        binding.btnThemeToggle.setOnClickListener { toggleTheme() }
        binding.btnStartAnalysis.setOnClickListener { startActivity(Intent(this, AnalysisActivity::class.java)) }
        binding.btnViewResult.setOnClickListener { checkDataAndNavigate { navigateToResult(it) } }
        setupMenuListeners()
    }

    private fun setupMenuListeners() {
        binding.menuHome.setOnClickListener { closeMenu() }
        binding.menuResult.setOnClickListener { checkDataAndNavigate { navigateToResult(it) }; closeMenu() }
        binding.menuHistory.setOnClickListener { startActivity(Intent(this, HistoryActivity::class.java)); closeMenu() }
        binding.menuMatch.setOnClickListener { startActivity(Intent(this, MatchActivity::class.java)); closeMenu() }
        binding.menuGroupLounge.setOnClickListener { startActivity(Intent(this, GroupLoungeActivity::class.java)); closeMenu() }
        binding.menuInbox.setOnClickListener { startActivity(Intent(this, InboxActivity::class.java)); closeMenu() }
        binding.menuCredits.setOnClickListener { startActivity(Intent(this, CreditActivity::class.java)); closeMenu() }
        binding.menuActivity.setOnClickListener { startActivity(Intent(this, UserActivityActivity::class.java)); closeMenu() }
        binding.menuBlindMatch.setOnClickListener { startActivity(Intent(this, BlindInboxActivity::class.java)); closeMenu() }
        binding.menuLogout.setOnClickListener {
            getSharedPreferences("EchoMindSession", Context.MODE_PRIVATE).edit().clear().apply()
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
        }
    }

    private fun closeMenu() {
        binding.menuOverlay.visibility = View.GONE
        binding.btnMenuToggle.setImageResource(android.R.drawable.ic_menu_sort_by_size)
    }

    private fun toggleTheme() {
        val mode = if (AppCompatDelegate.getDefaultNightMode() == AppCompatDelegate.MODE_NIGHT_YES) AppCompatDelegate.MODE_NIGHT_NO else AppCompatDelegate.MODE_NIGHT_YES
        AppCompatDelegate.setDefaultNightMode(mode)
    }

    private fun updateThemeIcon() {
        val currentMode = resources.configuration.uiMode and android.content.res.Configuration.UI_MODE_NIGHT_MASK
        if (currentMode == android.content.res.Configuration.UI_MODE_NIGHT_YES) binding.btnThemeToggle.setImageResource(R.drawable.ic_sun)
        else binding.btnThemeToggle.setImageResource(R.drawable.ic_moon)
    }

    private fun syncDataWithSafety() {
        lifecycleScope.launch {
            try {
                // 1. 사용자 정보 동기화 (프로필 JSON 우선, HTML 차선)
                val profileResp = apiService.getMyProfileJson()
                if (profileResp.isSuccessful) {
                    val root = profileResp.body()
                    val serverName = root?.meta?.name
                    if (serverName != null && serverName != "Unknown") {
                        binding.tvMenuUserName.text = "${serverName}님"
                    } else {
                        // JSON에 이름이 없으면 HTML에서 파싱 시도 (더 넓은 범위 탐색)
                        val homeResp = apiService.getHomeHtml()
                        if (homeResp.isSuccessful) {
                            val name = Jsoup.parse(homeResp.body() ?: "")
                                .select("span.font-bold, p.font-bold")
                                .firstOrNull { it.text().length < 10 }?.text()?.replace("님", "")?.trim() ?: "회원"
                            binding.tvMenuUserName.text = "${name}님"
                        }
                    }

                    // 프로필 데이터 동기화
                    val profile = root?.llmProfile
                    val serverResultId = root?.meta?.resultId ?: 0
                    if (profile != null) {
                        handleSmartSync(profile.copy(name = serverName ?: "Unknown"), serverResultId)
                    }
                }
            } catch (e: Exception) { Log.e("Sync", "Fail", e) }
        }
    }

    private suspend fun handleSmartSync(serverProfile: PersonalityProfile, serverId: Int) {
        if (currentEmail.isBlank()) return
        
        val allLocal = db.personalityDao().getAllResultsByUser(currentEmail)
        
        val existing = allLocal.find { 
            (it.serverResultId != 0 && it.serverResultId == serverId) || 
            (it.mbti == serverProfile.mbti?.type && it.summary == serverProfile.summary?.one_paragraph)
        }

        db.personalityDao().clearRepresentative(currentEmail)

        if (existing != null) {
            val updatedEntity = existing.copy(
                isRepresentative = true,
                serverResultId = serverId
            )
            db.personalityDao().insertResult(updatedEntity)
        } else {
            val newEntity = PersonalityEntity(
                serverResultId = serverId,
                userEmail = currentEmail,
                name = serverProfile.name ?: "Unknown",
                mbti = serverProfile.mbti?.type ?: "",
                mbtiConfidence = serverProfile.mbti?.confidence ?: 0.0,
                mbtiReasons = serverProfile.mbti?.reasons?.joinToString("|") ?: "",
                openness = serverProfile.big5?.scores_0_100?.openness ?: 50.0,
                conscientiousness = serverProfile.big5?.scores_0_100?.conscientiousness ?: 50.0,
                extraversion = serverProfile.big5?.scores_0_100?.extraversion ?: 50.0,
                agreeableness = serverProfile.big5?.scores_0_100?.agreeableness ?: 50.0,
                neuroticism = serverProfile.big5?.scores_0_100?.neuroticism ?: 50.0,
                big5Reasons = serverProfile.big5?.reasons?.joinToString("|") ?: "",
                socionics = serverProfile.socionics?.type ?: "",
                socionicsReasons = serverProfile.socionics?.reasons?.joinToString("|") ?: "",
                lineCount = serverProfile.lineCount,
                summary = serverProfile.summary?.one_paragraph ?: "",
                styleBullets = serverProfile.summary?.communication_style_bullets?.joinToString("|") ?: "",
                caveats = serverProfile.caveats?.joinToString("|") ?: "",
                isRepresentative = true
            )
            db.personalityDao().insertResult(newEntity)
        }
    }

    private fun checkDataAndNavigate(action: (PersonalityEntity) -> Unit) {
        lifecycleScope.launch {
            val results = db.personalityDao().getAllResultsByUser(currentEmail)
            val target = results.find { it.isRepresentative } ?: results.firstOrNull()
            if (target != null) action(target)
            else Toast.makeText(this@MainActivity, "성향 분석을 진행해주세요.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun navigateToResult(entity: PersonalityEntity) {
        val intent = Intent(this, ResultActivity::class.java)
        intent.putExtra("profile", mapEntityToProfile(entity) as Serializable)
        startActivity(intent)
    }

    private fun mapEntityToProfile(entity: PersonalityEntity): PersonalityProfile {
        return PersonalityProfile(
            name = entity.name,
            summary = SummaryData(entity.summary, entity.styleBullets.split("|").filter { it.isNotBlank() }),
            mbti = MbtiData(entity.mbti, entity.mbtiConfidence, entity.mbtiReasons.split("|").filter { it.isNotBlank() }),
            big5 = Big5Data(Big5Scores(entity.openness, entity.conscientiousness, entity.extraversion, entity.agreeableness, entity.neuroticism), 1.0, entity.big5Reasons.split("|").filter { it.isNotBlank() }),
            socionics = SocionicsData(entity.socionics, 1.0, entity.socionicsReasons.split("|").filter { it.isNotBlank() }),
            caveats = entity.caveats.split("|").filter { it.isNotBlank() },
            lineCount = entity.lineCount
        )
    }
}
