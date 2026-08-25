package com.tukorea.echomind

import android.app.DatePickerDialog
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
import java.text.SimpleDateFormat
import java.util.*

interface HistoryApiService {
    @GET("download_json/{resultId}")
    suspend fun getProfileJson(@Path("resultId") resultId: Int): Response<ProfileRootDto>
    @POST("set_representative/{resultId}")
    suspend fun setRepresentative(@Path("resultId") resultId: Int): Response<ResponseBody>
}

class HistoryActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHistoryBinding
    private val db by lazy { AppDatabase.getDatabase(applicationContext) }
    private var currentEmail: String = ""
    private val historyService: HistoryApiService by lazy { GlobalClient.retrofit.create(HistoryApiService::class.java) }

    private var allHistory: List<PersonalityEntity> = emptyList()
    private var isNewestFirst = true
    private var startDate: Calendar? = null
    private var endDate: Calendar? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityHistoryBinding.inflate(layoutInflater)
        setContentView(binding.root)
        currentEmail = getSharedPreferences("EchoMindSession", Context.MODE_PRIVATE).getString("user_email", "") ?: ""
        setupUI()
    }

    override fun onResume() {
        super.onResume()
        syncFullHistoryFromServer()
    }

    private fun setupUI() {
        binding.btnBack.setOnClickListener { finish() }
        binding.rvHistory.layoutManager = LinearLayoutManager(this)

        // 시작일 선택
        binding.etStartDate.setOnClickListener {
            showDatePicker { calendar ->
                startDate = calendar
                binding.etStartDate.setText(SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(calendar.time))
                applyFiltersAndSort()
            }
        }

        // 종료일 선택
        binding.etEndDate.setOnClickListener {
            showDatePicker { calendar ->
                endDate = calendar
                binding.etEndDate.setText(SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(calendar.time))
                applyFiltersAndSort()
            }
        }

        // 정렬 순서 토글
        binding.btnSortOrder.setOnClickListener {
            isNewestFirst = !isNewestFirst
            binding.btnSortOrder.text = if (isNewestFirst) "▼ 최신 순" else "▲ 오래된 순"
            applyFiltersAndSort()
        }

        // 초기화 버튼
        binding.btnResetFilter.setOnClickListener {
            startDate = null
            endDate = null
            isNewestFirst = true
            binding.etStartDate.text.clear()
            binding.etEndDate.text.clear()
            binding.btnSortOrder.text = "▼ 최신 순"
            syncFullHistoryFromServer()
        }
    }

    private fun showDatePicker(onDateSelected: (Calendar) -> Unit) {
        val current = Calendar.getInstance()
        DatePickerDialog(this, { _, year, month, day ->
            val selected = Calendar.getInstance().apply { set(year, month, day) }
            onDateSelected(selected)
        }, current.get(Calendar.YEAR), current.get(Calendar.MONTH), current.get(Calendar.DAY_OF_MONTH)).show()
    }

    private fun syncFullHistoryFromServer() {
        lifecycleScope.launch {
            try {
                cleanupLocalDuplicates()
                val response = GlobalClient.apiService.getHistoryHtml()
                if (response.isSuccessful) {
                    val doc = Jsoup.parse(response.body() ?: "")
                    val localList = db.personalityDao().getAllResultsByUser(currentEmail)
                    
                    doc.select("div.glass-panel").forEach { element ->
                        val fullTitle = element.select("h3").text()
                        val mbti = Regex("\\(([A-Z]{4})\\)").find(fullTitle)?.groupValues?.get(1) ?: ""
                        val detailLink = element.select("a[href*=/result/]").firstOrNull()?.attr("href") ?: ""
                        val serverId = detailLink.split("/").lastOrNull()?.toIntOrNull() ?: 0
                        val isRep = element.select("span:contains(ACTIVE PROFILE)").isNotEmpty()
                        val dateStr = element.select("span.text-xs.font-mono").text().trim()
                        val fullSummary = element.select("p.text-sm").text().trim()

                        if (serverId != 0) {
                            val existing = localList.find { 
                                it.serverResultId == serverId || 
                                (it.mbti == mbti && it.summary.substringAfter(":::") == fullSummary)
                            }
                            
                            val parsedTimestamp = parseDateToLong(dateStr)

                            if (existing != null) {
                                val updated = existing.copy(
                                    serverResultId = serverId,
                                    isRepresentative = isRep,
                                    summary = if (dateStr.isNotEmpty()) "$dateStr:::$fullSummary" else fullSummary,
                                    timestamp = if (parsedTimestamp != 0L) parsedTimestamp else existing.timestamp
                                )
                                db.personalityDao().insertResult(updated)
                            } else {
                                fetchAndSaveMissingProfile(serverId, isRep, dateStr, parsedTimestamp)
                            }
                        }
                    }
                }
            } catch (e: Exception) { Log.e("Sync", "Error", e) }
            finally { loadHistoryData() }
        }
    }

    private fun parseDateToLong(dateStr: String): Long {
        return try {
            val sdf = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())
            sdf.parse(dateStr)?.time ?: 0L
        } catch (e: Exception) { 0L }
    }

    private suspend fun cleanupLocalDuplicates() {
        val results = db.personalityDao().getAllResultsByUser(currentEmail)
        val seen = mutableSetOf<String>()
        results.forEach { res ->
            val contentKey = "${res.mbti}|${res.summary.substringAfter(":::")}"
            if (seen.contains(contentKey)) {
                if (!res.isRepresentative) db.personalityDao().deleteResult(res)
            } else {
                seen.add(contentKey)
            }
        }
    }

    private suspend fun fetchAndSaveMissingProfile(serverId: Int, isRep: Boolean, dateStr: String, timestamp: Long) {
        try {
            val jsonResp = historyService.getProfileJson(serverId)
            val profile = jsonResp.body()?.llmProfile
            if (jsonResp.isSuccessful && profile != null) {
                val rawSummary = profile.summary?.one_paragraph ?: ""
                val newEntity = PersonalityEntity(
                    serverResultId = serverId, userEmail = currentEmail,
                    name = jsonResp.body()?.meta?.name ?: "Unknown",
                    mbti = profile.mbti?.type ?: "", mbtiConfidence = profile.mbti?.confidence ?: 0.0,
                    mbtiReasons = profile.mbti?.reasons?.joinToString("|") ?: "",
                    openness = profile.big5?.scores_0_100?.openness ?: 50.0,
                    conscientiousness = profile.big5?.scores_0_100?.conscientiousness ?: 50.0,
                    extraversion = profile.big5?.scores_0_100?.extraversion ?: 50.0,
                    agreeableness = profile.big5?.scores_0_100?.agreeableness ?: 50.0,
                    neuroticism = profile.big5?.scores_0_100?.neuroticism ?: 50.0,
                    big5Reasons = profile.big5?.reasons?.joinToString("|") ?: "",
                    socionics = profile.socionics?.type ?: "", socionicsReasons = profile.socionics?.reasons?.joinToString("|") ?: "",
                    lineCount = profile.lineCount,
                    summary = if (dateStr.isNotEmpty()) "$dateStr:::$rawSummary" else rawSummary,
                    styleBullets = profile.summary?.communication_style_bullets?.joinToString("|") ?: "",
                    caveats = profile.caveats?.joinToString("|") ?: "", isRepresentative = isRep,
                    timestamp = if (timestamp != 0L) timestamp else System.currentTimeMillis()
                )
                db.personalityDao().insertResult(newEntity)
            }
        } catch (e: Exception) { }
    }

    private fun loadHistoryData() {
        lifecycleScope.launch {
            try {
                allHistory = db.personalityDao().getAllResultsByUser(currentEmail)
                applyFiltersAndSort()
            } catch (e: Exception) { Log.e("History", "Error", e) }
        }
    }

    private fun applyFiltersAndSort() {
        // 상단 대표 프로필 표시 (필터링과 무관하게 항상 대표 프로필 표시)
        val activeProfile = allHistory.find { it.isRepresentative } ?: allHistory.firstOrNull()
        if (activeProfile != null) {
            binding.cardActiveProfile.visibility = View.VISIBLE
            displayActiveProfile(activeProfile)
        } else {
            binding.cardActiveProfile.visibility = View.GONE
        }

        // 하단 리스트 필터링 및 정렬
        var filtered = allHistory.filter { item ->
            var keep = true
            val itemTime = item.timestamp
            
            startDate?.let {
                val start = it.apply { set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0) }.timeInMillis
                if (itemTime < start) keep = false
            }
            endDate?.let {
                val end = it.apply { set(Calendar.HOUR_OF_DAY, 23); set(Calendar.MINUTE, 59) }.timeInMillis
                if (itemTime > end) keep = false
            }
            keep
        }

        // 정렬
        filtered = if (isNewestFirst) {
            filtered.sortedByDescending { it.timestamp }
        } else {
            filtered.sortedBy { it.timestamp }
        }

        binding.rvHistory.adapter = HistoryAdapter(filtered, activeProfile?.id ?: -1,
            onViewDetail = { navigateToResult(it) },
            onSetRepresentative = { setAsRep(it) }
        )
        binding.rvHistory.adapter?.notifyDataSetChanged()
    }

    private fun displayActiveProfile(entity: PersonalityEntity) {
        binding.apply {
            val parts = entity.summary.split(":::")
            tvActiveMbti.text = entity.mbti
            tvActiveName.text = entity.name
            if (parts.size > 1) { tvActiveDate.text = parts[0]; tvActiveSummary.text = parts[1] }
            else { tvActiveDate.text = "날짜 정보 없음"; tvActiveSummary.text = entity.summary }
            
            miniOpen.apply { tvMiniScore.text = entity.openness.toInt().toString(); tvMiniLabel.text = "OPEN" }
            miniCons.apply { tvMiniScore.text = entity.conscientiousness.toInt().toString(); tvMiniLabel.text = "CONS" }
            miniExtr.apply { tvMiniScore.text = entity.extraversion.toInt().toString(); tvMiniLabel.text = "EXTR" }
            miniAgre.apply { tvMiniScore.text = entity.agreeableness.toInt().toString(); tvMiniLabel.text = "AGRE" }
            miniNeur.apply { tvMiniScore.text = entity.neuroticism.toInt().toString(); tvMiniLabel.text = "NEUR" }
            btnActiveDetail.setOnClickListener { navigateToResult(entity) }
        }
    }

    private fun setAsRep(entity: PersonalityEntity) {
        lifecycleScope.launch {
            try {
                val targetId = if (entity.serverResultId != 0) entity.serverResultId else return@launch
                val response = historyService.setRepresentative(targetId)
                if (response.isSuccessful) {
                    db.personalityDao().clearRepresentative(currentEmail)
                    db.personalityDao().insertResult(entity.copy(isRepresentative = true))
                    Toast.makeText(this@HistoryActivity, "대표 프로필이 변경되었습니다.", Toast.LENGTH_SHORT).show()
                    loadHistoryData()
                }
            } catch (e: Exception) { }
        }
    }

    private fun navigateToResult(entity: PersonalityEntity) {
        val intent = Intent(this, ResultActivity::class.java)
        intent.putExtra("profile", mapEntityToProfile(entity) as Serializable)
        startActivity(intent)
    }

    private fun mapEntityToProfile(entity: PersonalityEntity): PersonalityProfile {
        val pureSummary = entity.summary.substringAfter(":::")
        return PersonalityProfile(
            name = entity.name,
            summary = SummaryData(pureSummary, entity.styleBullets.split("|").filter { it.isNotBlank() }),
            mbti = MbtiData(entity.mbti, entity.mbtiConfidence, entity.mbtiReasons.split("|").filter { it.isNotBlank() }),
            big5 = Big5Data(Big5Scores(entity.openness, entity.conscientiousness, entity.extraversion, entity.agreeableness, entity.neuroticism), 1.0, entity.big5Reasons.split("|").filter { it.isNotBlank() }),
            socionics = SocionicsData(entity.socionics, 1.0, entity.socionicsReasons.split("|").filter { it.isNotBlank() }),
            caveats = entity.caveats.split("|").filter { it.isNotBlank() },
            lineCount = entity.lineCount
        )
    }
}

class HistoryAdapter(private var items: List<PersonalityEntity>, private val activeId: Int, private val onViewDetail: (PersonalityEntity) -> Unit, private val onSetRepresentative: (PersonalityEntity) -> Unit) : RecyclerView.Adapter<HistoryAdapter.ViewHolder>() {
    class ViewHolder(val binding: ItemAnalysisHistoryBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemAnalysisHistoryBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            val parts = item.summary.split(":::")
            tvHistoryNameMbti.text = "${item.name} (${item.mbti})"
            if (parts.size > 1) { tvHistoryDate.text = parts[0]; tvHistorySummary.text = parts[1] }
            else { tvHistoryDate.text = "분석 완료"; tvHistorySummary.text = item.summary }
            val isActive = item.id == activeId
            tvActiveBadge.visibility = if (isActive) View.VISIBLE else View.GONE
            btnSetRep.visibility = if (isActive) View.GONE else View.VISIBLE
            btnViewDetail.setOnClickListener { onViewDetail(item) }
            btnSetRep.setOnClickListener { onSetRepresentative(item) }
        }
    }
    override fun getItemCount() = items.size
}
