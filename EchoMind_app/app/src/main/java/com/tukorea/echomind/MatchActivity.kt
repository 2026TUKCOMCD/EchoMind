package com.tukorea.echomind

import android.graphics.Color
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.github.mikephil.charting.animation.Easing
import com.github.mikephil.charting.charts.HorizontalBarChart
import com.github.mikephil.charting.charts.PieChart
import com.github.mikephil.charting.charts.RadarChart
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.components.Legend
import com.github.mikephil.charting.data.*
import com.github.mikephil.charting.formatter.IndexAxisValueFormatter
import com.github.mikephil.charting.formatter.ValueFormatter
import com.google.gson.Gson
import com.tukorea.echomind.databinding.ActivityMatchBinding
import com.tukorea.echomind.databinding.ItemMatchCandidateBinding
import com.tukorea.echomind.models.*
import kotlinx.coroutines.launch
import okhttp3.ResponseBody
import org.jsoup.Jsoup
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

// 웹 서비스의 상세 데이터 수신용 DTO
data class ChartInfoDto(
    val similarity: Double = 0.0,
    val chemistry: Double = 0.0,
    val activity: Double = 0.0,
    val myBig5: List<Double> = emptyList(),
    val candBig5: List<Double> = emptyList(),
    val myLineCount: Int = 0,
    val candLineCount: Int = 0,
    val mbtiScore: Double = 0.0,
    val socioScore: Double = 0.0,
    val mbtiWeight: Float = 1.0f,
    val socioWeight: Float = 1.0f,
    val candName: String = ""
)

interface MatchApiService {
    @GET("matching")
    suspend fun getMatchingHtml(): Response<String>
    @POST("apply_match/{receiverId}")
    suspend fun applyMatch(@Path("receiverId") receiverId: Int): Response<ResponseBody>
}

class MatchActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMatchBinding
    private val matchService by lazy {
        com.tukorea.echomind.GlobalClient.retrofit.create(MatchApiService::class.java)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMatchBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.rvMatches.layoutManager = LinearLayoutManager(this)
        loadMatchingData()
    }

    private fun loadMatchingData() {
        binding.progressBar.visibility = View.VISIBLE
        lifecycleScope.launch {
            try {
                val response = matchService.getMatchingHtml()
                if (response.isSuccessful) parseMatchingHtml(response.body() ?: "")
            } catch (e: Exception) {
                Log.e("MatchSync", "Error", e)
                Toast.makeText(this@MatchActivity, "서버 연결 실패", Toast.LENGTH_SHORT).show()
            } finally {
                binding.progressBar.visibility = View.GONE
            }
        }
    }

    private fun parseMatchingHtml(html: String) {
        val doc = Jsoup.parse(html)
        val gson = Gson()
        val candidates = mutableListOf<MatchCandidate>()

        doc.select("div.glass-panel").forEach { element ->
            val name = element.select("h3").text().trim()
            if (name.isEmpty()) return@forEach

            val scoreRaw = element.select("span.text-3xl").text().replace("점", "").trim()
            val totalScore = scoreRaw.toIntOrNull() ?: 0

            val summaryText = element.select("p.text-slate-600, p.dark\\:text-slate-300").first()?.text()?.trim() ?: ""
            val formAction = element.select("form").attr("action")
            val userId = formAction.split("/").lastOrNull() ?: ""

            val detailBtn = element.select("button[data-chart-info]").first()
            val chartJson = detailBtn?.attr("data-chart-info") ?: ""
            val c = try { gson.fromJson(chartJson, ChartInfoDto::class.java) } catch(e: Exception) { null }

            val cand = MatchCandidate(
                profile = PersonalityProfile(
                    userId = userId,
                    name = name,
                    mbti = MbtiData(type = element.select("span.bg-indigo-100").first()?.text()?.trim() ?: "MBTI"),
                    summary = SummaryData(one_paragraph = summaryText)
                ),
                matchScore = totalScore,
                similarityScore = (c?.similarity ?: 0.0) * 100,
                chemistryScore = (c?.chemistry ?: 0.0) * 100,
                activityScore = (c?.activity ?: 0.0) * 100,
                myBig5 = c?.myBig5 ?: listOf(50.0, 50.0, 50.0, 50.0, 50.0),
                candBig5 = c?.candBig5 ?: listOf(50.0, 50.0, 50.0, 50.0, 50.0),
                myLineCount = c?.myLineCount ?: 0,
                candLineCount = c?.candLineCount ?: 0,
                mbtiScore = ((c?.mbtiScore ?: 0.5) * 100).toInt(),
                socioScore = ((c?.socioScore ?: 0.5) * 100).toInt(),
                mbtiLabel = element.select("h4:contains(관계)").first()?.text()?.trim() ?: "Neutral",
                mbtiWeight = c?.mbtiWeight ?: 1.0f,
                socioWeight = c?.socioWeight ?: 1.0f,
                socioQuadraSame = element.select("p:contains(같은 쿼드라)").isNotEmpty()
            )
            candidates.add(cand)
        }

        candidates.sortByDescending { it.matchScore }
        binding.rvMatches.adapter = MatchAdapter(candidates) { cand ->
            cand.profile.userId?.toIntOrNull()?.let { runApplyMatch(it) }
        }
    }

    private fun runApplyMatch(receiverId: Int) {
        if (receiverId == 0) return
        lifecycleScope.launch {
            try {
                val response = matchService.applyMatch(receiverId)
                if (response.isSuccessful) Toast.makeText(this@MatchActivity, "매칭 신청 완료!", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) { }
        }
    }
}

class MatchAdapter(private val items: List<MatchCandidate>, private val onApply: (MatchCandidate) -> Unit) : RecyclerView.Adapter<MatchAdapter.ViewHolder>() {
    class ViewHolder(val binding: ItemMatchCandidateBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemMatchCandidateBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        val context = holder.itemView.context

        // 다크모드 감지 및 색상 설정
        val isDark = (context.resources.configuration.uiMode and android.content.res.Configuration.UI_MODE_NIGHT_MASK) == android.content.res.Configuration.UI_MODE_NIGHT_YES
        val labelColor = if (isDark) Color.WHITE else Color.parseColor("#0F172A")

        holder.binding.apply {
            tvRankBadge.text = when(position) {
                0 -> "🥇 1st"
                1 -> "🥈 2nd"
                2 -> "🥉 3rd"
                else -> "${position + 1}th"
            }
            tvCandidateName.text = item.profile.name
            tvMatchScore.text = item.matchScore.toString()
            tvCandidateSummary.text = item.profile.summary?.one_paragraph ?: "분석 내용이 없습니다."

            tvMbtiRelation.text = item.mbtiLabel
            tvSocioQuadra.text = if(item.socioQuadraSame) "✅ 같은 쿼드라! 가치관이 잘 통합니다." else "다른 쿼드라에 속합니다."

            tvDetailSimilarity.text = "${item.similarityScore.toInt()}%"
            tvDetailChemistry.text = "${item.chemistryScore.toInt()}%"
            tvDetailActivity.text = "${item.activityScore.toInt()}점"

            // [해결] 항목별 우측 상단 점수 배지 실시간 연동
            tvBig5ScoreBadge.text = "${item.similarityScore.toInt()}점"
            tvMbtiScoreBadge.text = "${item.mbtiScore}점"
            tvSocioScoreBadge.text = "${item.socioScore}점"
            tvChemScoreBadge.text = "${item.chemistryScore.toInt()}점"
            tvActivityScoreBadge.text = "${item.activityScore.toInt()}점"

            btnToggleDetail.setOnClickListener {
                val isVisible = layoutExpandableDetail.visibility == View.VISIBLE
                layoutExpandableDetail.visibility = if (isVisible) View.GONE else View.VISIBLE
                btnToggleDetail.text = if (isVisible) "매칭 산출 상세 보기 ▼" else "매칭 산출 상세 보기 ▲"
                if (!isVisible) {
                    setupDonutChart(chartDonut, item, labelColor)
                    setupRadarChart(chartRadar, item, labelColor)
                    setupChemBreakdownChart(chartChemBreakdown, item, labelColor)
                    setupActivityChart(chartActivityCompare, item, labelColor)
                }
            }
            btnApplyMatch.setOnClickListener { onApply(item) }
        }
    }

    private fun setupDonutChart(chart: PieChart, item: MatchCandidate, labelColor: Int) {
        val entries = listOf(PieEntry(item.similarityScore.toFloat() * 0.5f, ""), PieEntry(item.chemistryScore.toFloat() * 0.4f, ""), PieEntry(item.activityScore.toFloat() * 0.1f, ""))
        val dataSet = PieDataSet(entries, "").apply {
            colors = listOf(Color.parseColor("#3B82F6"), Color.parseColor("#F43F5E"), Color.parseColor("#F59E0B"))
            setDrawValues(false)
        }
        chart.apply {
            data = PieData(dataSet); isDrawHoleEnabled = true; holeRadius = 65f
            centerText = "${item.matchScore}점"; setCenterTextColor(labelColor); setCenterTextSize(18f)
            description.isEnabled = false; legend.isEnabled = false; animateY(800); invalidate()
        }
    }

    private fun setupRadarChart(chart: RadarChart, item: MatchCandidate, labelColor: Int) {
        val myEntries = item.myBig5.map { RadarEntry(it.toFloat()) }
        val candEntries = item.candBig5.map { RadarEntry(it.toFloat()) }

        val mySet = RadarDataSet(myEntries, "나").apply {
            color = Color.parseColor("#3B82F6"); fillColor = Color.parseColor("#3B82F6"); setDrawFilled(true); fillAlpha = 80; lineWidth = 2.5f
        }
        val candSet = RadarDataSet(candEntries, item.profile.name).apply {
            color = Color.parseColor("#F43F5E"); fillColor = Color.parseColor("#F43F5E"); setDrawFilled(true); fillAlpha = 80; lineWidth = 2.5f
        }

        val radarData = RadarData().apply {
            addDataSet(mySet); addDataSet(candSet); setDrawValues(false)
        }

        chart.apply {
            data = radarData
            setExtraOffsets(30f, 50f, 30f, 30f)
            webColor = Color.GRAY; webColorInner = Color.GRAY; webAlpha = 100
            xAxis.apply {
                valueFormatter = IndexAxisValueFormatter(listOf("개방성", "성실성", "외향성", "우호성", "신경성"))
                textColor = labelColor
                textSize = 11f
            }
            yAxis.apply {
                axisMinimum = 0f; axisMaximum = 100f; setDrawLabels(false)
            }
            legend.apply { isEnabled = true; textColor = labelColor; verticalAlignment = Legend.LegendVerticalAlignment.BOTTOM; horizontalAlignment = Legend.LegendHorizontalAlignment.CENTER }
            description.isEnabled = false; animateXY(800, 800); invalidate()
        }
    }

    private fun setupChemBreakdownChart(chart: HorizontalBarChart, item: MatchCandidate, labelColor: Int) {
        val totalW = item.mbtiWeight + item.socioWeight + 1e-9f
        val mbtiPart = (item.mbtiScore * item.mbtiWeight / totalW).toFloat()
        val socioPart = (item.socioScore * item.socioWeight / totalW).toFloat()

        val entries = listOf(BarEntry(0f, floatArrayOf(mbtiPart, socioPart)))
        val dataSet = BarDataSet(entries, "").apply {
            colors = listOf(Color.parseColor("#6366F1"), Color.parseColor("#F43F5E"))
            setDrawValues(true)
            valueTextColor = labelColor // [해결] 라이트 모드 대응 컬러 적용
            valueTextSize = 10f
            valueFormatter = object : ValueFormatter() {
                override fun getBarStackedLabel(v: Float, e: BarEntry?): String = "${v.toInt()}점"
            }
        }
        chart.apply {
            data = BarData(dataSet); description.isEnabled = false; legend.isEnabled = false
            xAxis.isEnabled = false; axisLeft.isEnabled = false; axisRight.isEnabled = false; invalidate()
        }
    }

    private fun setupActivityChart(chart: HorizontalBarChart, item: MatchCandidate, labelColor: Int) {
        val dataSet = BarDataSet(listOf(BarEntry(0f, item.myLineCount.toFloat()), BarEntry(1f, item.candLineCount.toFloat())), "").apply {
            colors = listOf(Color.parseColor("#3B82F6"), Color.parseColor("#F43F5E"))
            setDrawValues(true)
            valueTextColor = labelColor // [해결] 라이트 모드 대응 컬러 적용
            valueTextSize = 10f
            valueFormatter = object : ValueFormatter() { override fun getFormattedValue(v: Float): String = "${v.toInt()}" }
        }
        chart.apply {
            data = BarData(dataSet)
            setExtraRightOffset(60f)
            xAxis.apply {
                valueFormatter = IndexAxisValueFormatter(listOf("나", item.profile.name))
                position = XAxis.XAxisPosition.BOTTOM; textColor = labelColor
                granularity = 1f; isGranularityEnabled = true; setLabelCount(2, true)
            }
            axisLeft.apply { textColor = labelColor; axisMinimum = 0f; setDrawLabels(true); setDrawGridLines(false) }
            axisRight.isEnabled = false
            description.isEnabled = false; legend.isEnabled = false; animateY(800); invalidate()
        }
    }

    override fun getItemCount() = items.size
}
