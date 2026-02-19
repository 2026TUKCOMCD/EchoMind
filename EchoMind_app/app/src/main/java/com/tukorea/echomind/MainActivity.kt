package com.tukorea.echomind

import android.app.ProgressDialog
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.data.api.ApiClient
import com.tukorea.echomind.data.local.AppDatabase
import com.tukorea.echomind.data.local.PersonalityEntity
import com.tukorea.echomind.databinding.ActivityMainBinding
import com.tukorea.echomind.models.*
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import org.jsoup.Jsoup
import java.io.Serializable

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val db by lazy { AppDatabase.getDatabase(this) }
    private val matchService = ApiClient.matchService
    
    private var loggedInUserName: String = "회원" 
    private var currentEmail: String = "" 
    private var isSyncing: Boolean = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // 1. 로그인 세션 정보(이메일) 복구 - 계정별 데이터 분리 핵심
        val sharedPref = getSharedPreferences("EchoMindSession", Context.MODE_PRIVATE)
        currentEmail = sharedPref.getString("user_email", "") ?: ""

        setupBottomNavigation()
        setupButtons()
        updateThemeIcon()
        
        // 2. 서버와 실시간 동기화 실행
        performFullSync(false)
    }

    private fun setupButtons() {
        // [지금 분석 시작하기] 버튼
        binding.btnStartAnalysis.setOnClickListener {
            startActivity(Intent(this, AnalysisActivity::class.java))
        }
        
        // [테마 토글] 버튼
        binding.btnThemeToggle.setOnClickListener {
            toggleTheme()
        }

        // [중요] cardAnalysis, cardMatching 등 레이아웃에서 제거된 뷰에 대한 
        // 클릭 리스너 설정을 모두 삭제하여 NoSuchFieldError(앱 꺼짐) 오류를 해결함.
    }

    private fun toggleTheme() {
        val currentMode = resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK
        if (currentMode == Configuration.UI_MODE_NIGHT_YES) {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO)
        } else {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES)
        }
    }

    private fun updateThemeIcon() {
        val currentMode = resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK
        if (currentMode == Configuration.UI_MODE_NIGHT_YES) {
            binding.btnThemeToggle.setImageResource(android.R.drawable.ic_menu_today)
        } else {
            binding.btnThemeToggle.setImageResource(android.R.drawable.ic_menu_day)
        }
    }

    private fun setupBottomNavigation() {
        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_home -> true
                R.id.nav_result -> {
                    checkDataAndNavigate { navigateToResult(it) }
                    true
                }
                R.id.nav_match -> {
                    checkDataAndNavigate { navigateToMatch(it) }
                    true
                }
                R.id.nav_inbox -> {
                    startActivity(Intent(this, InboxActivity::class.java))
                    true
                }
                else -> false
            }
        }
    }

    private fun checkDataAndNavigate(action: (PersonalityEntity) -> Unit) {
        lifecycleScope.launch {
            // 현재 로그인한 계정(currentEmail)의 데이터만 조회
            val result = db.personalityDao().getLatestResultByUser(currentEmail)
            if (result != null) {
                action(result)
            } else {
                val progressDialog = ProgressDialog(this@MainActivity).apply {
                    setMessage("데이터 연동 중...")
                    setCancelable(false)
                    show()
                }
                performFullSync(true) { success ->
                    progressDialog.dismiss()
                    if (success) {
                        lifecycleScope.launch {
                            val refreshed = db.personalityDao().getLatestResultByUser(currentEmail)
                            if (refreshed != null) action(refreshed)
                        }
                    } else {
                        Toast.makeText(this@MainActivity, "분석 데이터가 없습니다. 분석을 먼저 완료해주세요!", Toast.LENGTH_LONG).show()
                        startActivity(Intent(this@MainActivity, AnalysisActivity::class.java))
                    }
                }
            }
        }
    }

    private fun performFullSync(isExplicit: Boolean, onFinish: ((Boolean) -> Unit)? = null) {
        if (isSyncing) return
        isSyncing = true

        lifecycleScope.launch {
            var isSuccess = false
            try {
                // 1. 이름 추출 (로그인 계정 식별)
                val homeResponse = matchService.getHomeHtml()
                if (homeResponse.isSuccessful) {
                    val html = homeResponse.body() ?: ""
                    val doc = Jsoup.parse(html)
                    val nameElement = doc.select("span.font-bold.text-slate-700").first()
                    loggedInUserName = nameElement?.text()?.trim() ?: "회원"
                    binding.tvWelcomeName.text = "안녕하세요, ${loggedInUserName}님"
                }

                // 2. 분석 결과 다운로드
                val profileResponse = matchService.getMyProfileFromServer()
                if (profileResponse.isSuccessful) {
                    val body = profileResponse.body()
                    if (body?.llmProfile != null) {
                        val targetName = body.meta?.name ?: "Unknown"
                        saveProfileToLocal(body.llmProfile.copy(name = targetName))
                        isSuccess = true
                    }
                }
            } catch (e: Exception) {
                Log.e("EchoMindSync", "Sync failed", e)
            } finally {
                isSyncing = false
                onFinish?.invoke(isSuccess)
            }
        }
    }

    private suspend fun saveProfileToLocal(profile: PersonalityProfile) {
        val entity = PersonalityEntity(
            userEmail = currentEmail,
            name = profile.name ?: "Unknown",
            mbti = profile.mbti?.type ?: "",
            mbtiConfidence = profile.mbti?.confidence ?: 0.0,
            mbtiReasons = profile.mbti?.reasons?.joinToString("|") ?: "",
            openness = profile.big5?.scores_0_100?.openness ?: 50.0,
            conscientiousness = profile.big5?.scores_0_100?.conscientiousness ?: 50.0,
            extraversion = profile.big5?.scores_0_100?.extraversion ?: 50.0,
            agreeableness = profile.big5?.scores_0_100?.agreeableness ?: 50.0,
            neuroticism = profile.big5?.scores_0_100?.neuroticism ?: 50.0,
            big5Reasons = profile.big5?.reasons?.joinToString("|") ?: "",
            socionics = profile.socionics?.type ?: "",
            socionicsReasons = profile.socionics?.reasons?.joinToString("|") ?: "",
            lineCount = profile.lineCount,
            summary = profile.summary?.one_paragraph ?: "",
            styleBullets = profile.summary?.communication_style_bullets?.joinToString("|") ?: "",
            caveats = profile.caveats?.joinToString("|") ?: ""
        )
        db.personalityDao().insertResult(entity)
    }

    override fun onResume() {
        super.onResume()
        binding.bottomNav.selectedItemId = R.id.nav_home
        performFullSync(false)
    }

    private fun navigateToResult(entity: PersonalityEntity) {
        val profile = mapEntityToProfile(entity)
        val intent = Intent(this, ResultActivity::class.java)
        intent.putExtra("profile", profile as Serializable)
        startActivity(intent)
    }

    private fun navigateToMatch(entity: PersonalityEntity) {
        val profile = mapEntityToProfile(entity)
        val intent = Intent(this, MatchActivity::class.java)
        intent.putExtra("myProfile", profile as Serializable)
        startActivity(intent)
    }

    private fun mapEntityToProfile(entity: PersonalityEntity): PersonalityProfile {
        return PersonalityProfile(
            userId = "current_user",
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
