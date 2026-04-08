package com.tukorea.echomind

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.tukorea.echomind.data.local.AppDatabase
import com.tukorea.echomind.data.local.PersonalityEntity
import com.tukorea.echomind.databinding.ActivityHistoryBinding
import com.tukorea.echomind.databinding.ItemAnalysisHistoryBinding
import com.tukorea.echomind.models.*
import kotlinx.coroutines.launch
import okhttp3.ResponseBody
import org.jsoup.Jsoup
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import java.io.Serializable

// [양방향 동기화 강화] 특정 ID의 리포트 데이터를 가져오는 기능 추가
interface HistoryApiService {
    @GET("download_json") // 대표 결과 다운로드
    suspend fun getRepresentativeJson(): Response<ProfileRootDto>

    @POST("set_representative/{resultId}")
    suspend fun setRepresentative(@Path("resultId") resultId: Int): Response<ResponseBody>
}

class HistoryActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHistoryBinding
    private val db by lazy { AppDatabase.getDatabase(applicationContext) }
    private var currentEmail: String = ""
    
    private val historyService: HistoryApiService by lazy {
        GlobalClient.retrofit.create(HistoryApiService::class.java)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityHistoryBinding.inflate(layoutInflater)
        setContentView(binding.root)

        currentEmail = getSharedPreferences("EchoMindSession", Context.MODE_PRIVATE).getString("user_email", "") ?: ""

        setupUI()
    }

    override fun onResume() {
        super.onResume()
        // [해결 핵심] 화면이 열릴 때마다 서버의 모든 기록을 검사하고 누락된 것을 강제 동기화
        syncFullHistoryFromServer()
    }

    private fun setupUI() {
        binding.btnBack.setOnClickListener { finish() }
        binding.rvHistory.layoutManager = LinearLayoutManager(this)
        
        binding.btnResetFilter.setOnClickListener {
            syncFullHistoryFromServer()
            Toast.makeText(this, "서버와 데이터를 완벽하게 동기화합니다.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun syncFullHistoryFromServer() {
        lifecycleScope.launch {
            try {
                // 1. 서버의 히스토리 페이지 HTML을 가져옴
                val response = GlobalClient.apiService.getHistoryHtml()
                if (response.isSuccessful) {
                    val html = response.body() ?: ""
                    val doc = Jsoup.parse(html)
                    val allLocal = db.personalityDao().getAllResultsByUser(currentEmail)
                    
                    // 2. 웹의 모든 기록 카드 탐색
                    doc.select("div.glass-panel").forEach { element ->
                        val mbti = element.select("h3").text().let { 
                            val match = Regex("\\(([A-Z]{4})\\)").find(it)
                            match?.groupValues?.get(1) ?: ""
                        }
                        val summaryPart = element.select("p.text-sm").text().trim().take(20)
                        val detailUrl = element.select("a:contains(상세 보기)").attr("href")
                        val serverId = detailUrl.split("/").lastOrNull()?.toIntOrNull() ?: 0
                        val isRepresentative = element.select("span:contains(ACTIVE PROFILE)").isNotEmpty()

                        if (serverId != 0) {
                            // 3. 로컬 DB에 해당 기록이 있는지 확인
                            val localMatch = allLocal.find { it.serverResultId == serverId || (it.mbti == mbti && it.summary.contains(summaryPart)) }
                            
                            if (localMatch != null) {
                                // 이미 있다면 상태만 업데이트
                                val updated = localMatch.copy(serverResultId = serverId, isRepresentative = isRepresentative)
                                db.personalityDao().insertResult(updated)
                            } else {
                                // [해결] 없다면 서버에서 이 리포트 정보를 긁어와야 함
                                // 웹의 내용을 기반으로 뼈대를 만들고, 상세 데이터는 서버에서 가져옵니다.
                                fetchAndSaveMissingProfile(serverId, isRepresentative)
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e("Sync", "Full Sync Error", e)
            } finally {
                loadHistoryData()
            }
        }
    }

    // 서버에만 있고 앱에는 없는 기록을 다운로드하여 저장
    private suspend fun fetchAndSaveMissingProfile(serverId: Int, isRepresentative: Boolean) {
        try {
            // 임시로 해당 ID를 대표로 설정한 뒤 JSON을 가져오는 방식으로 데이터 무결성을 확보합니다.
            // (서버에 개별 결과 JSON 조회 API가 없으므로 이 방식을 사용)
            historyService.setRepresentative(serverId)
            val jsonResp = historyService.getRepresentativeJson()
            if (jsonResp.isSuccessful) {
                val root = jsonResp.body()
                val profile = root?.llmProfile
                if (profile != null) {
                    val newEntity = PersonalityEntity(
                        serverResultId = serverId,
                        userEmail = currentEmail,
                        name = root.meta?.name ?: "Unknown",
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
                        caveats = profile.caveats?.joinToString("|") ?: "",
                        isRepresentative = isRepresentative
                    )
                    db.personalityDao().insertResult(newEntity)
                }
            }
        } catch (e: Exception) {
            Log.e("Sync", "Download Fail", e)
        }
    }

    private fun loadHistoryData() {
        lifecycleScope.launch {
            try {
                val allHistory = db.personalityDao().getAllResultsByUser(currentEmail)
                val activeProfile = allHistory.find { it.isRepresentative } ?: allHistory.firstOrNull()
                
                if (activeProfile != null) {
                    binding.cardActiveProfile.visibility = View.VISIBLE
                    displayActiveProfile(activeProfile)
                } else {
                    binding.cardActiveProfile.visibility = View.GONE
                }

                binding.rvHistory.adapter = HistoryAdapter(allHistory, activeProfile?.id ?: -1,
                    onViewDetail = { navigateToResult(it) },
                    onSetRepresentative = { setAsRep(it) }
                )
            } catch (e: Exception) {
                Log.e("History", "DB Error", e)
            }
        }
    }

    private fun displayActiveProfile(entity: PersonalityEntity) {
        binding.apply {
            tvActiveMbti.text = entity.mbti
            tvActiveName.text = entity.name
            tvActiveSummary.text = entity.summary
            
            // [해결] 대표 프로필 Big5 항목별 수치 및 레이블 개별 설정
            miniOpen.apply {
                tvMiniScore.text = entity.openness.toInt().toString()
                tvMiniLabel.text = "OPEN"
            }
            miniCons.apply {
                tvMiniScore.text = entity.conscientiousness.toInt().toString()
                tvMiniLabel.text = "CONS"
            }
            miniExtr.apply {
                tvMiniScore.text = entity.extraversion.toInt().toString()
                tvMiniLabel.text = "EXTR"
            }
            miniAgre.apply {
                tvMiniScore.text = entity.agreeableness.toInt().toString()
                tvMiniLabel.text = "AGRE"
            }
            miniNeur.apply {
                tvMiniScore.text = entity.neuroticism.toInt().toString()
                tvMiniLabel.text = "NEUR"
            }

            btnActiveDetail.setOnClickListener { navigateToResult(entity) }
        }
    }

    private fun setAsRep(entity: PersonalityEntity) {
        lifecycleScope.launch {
            try {
                val targetId = if (entity.serverResultId != 0) entity.serverResultId else {
                    Toast.makeText(this@HistoryActivity, "서버 동기화 중...", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                
                val response = historyService.setRepresentative(targetId)
                if (response.isSuccessful) {
                    db.personalityDao().clearRepresentative(currentEmail)
                    val updated = entity.copy(isRepresentative = true)
                    db.personalityDao().insertResult(updated)
                    Toast.makeText(this@HistoryActivity, "대표 프로필이 변경되었습니다.", Toast.LENGTH_SHORT).show()
                    loadHistoryData()
                }
            } catch (e: Exception) {
                Toast.makeText(this@HistoryActivity, "네트워크 오류", Toast.LENGTH_SHORT).show()
            }
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

class HistoryAdapter(
    private var items: List<PersonalityEntity>,
    private val activeId: Int,
    private val onViewDetail: (PersonalityEntity) -> Unit,
    private val onSetRepresentative: (PersonalityEntity) -> Unit
) : RecyclerView.Adapter<HistoryAdapter.ViewHolder>() {

    class ViewHolder(val binding: ItemAnalysisHistoryBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        ViewHolder(ItemAnalysisHistoryBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvHistoryNameMbti.text = "${item.name} (${item.mbti})"
            tvHistorySummary.text = item.summary
            val isActive = item.id == activeId
            tvActiveBadge.visibility = if (isActive) View.VISIBLE else View.GONE
            btnSetRep.visibility = if (isActive) View.GONE else View.VISIBLE
            btnViewDetail.setOnClickListener { onViewDetail(item) }
            btnSetRep.setOnClickListener { onSetRepresentative(item) }
        }
    }

    override fun getItemCount() = items.size
}
