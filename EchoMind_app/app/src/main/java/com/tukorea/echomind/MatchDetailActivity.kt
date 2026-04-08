package com.tukorea.echomind

import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.util.Log
import android.util.TypedValue
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.github.mikephil.charting.animation.Easing
import com.github.mikephil.charting.charts.HorizontalBarChart
import com.github.mikephil.charting.charts.PieChart
import com.github.mikephil.charting.charts.RadarChart
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.components.Legend
import com.github.mikephil.charting.data.*
import com.github.mikephil.charting.formatter.IndexAxisValueFormatter
import com.github.mikephil.charting.formatter.ValueFormatter
import com.google.android.material.card.MaterialCardView
import com.google.gson.Gson
import com.tukorea.echomind.databinding.ActivityMatchDetailBinding
import com.tukorea.echomind.databinding.ItemBig5BarBinding
import com.tukorea.echomind.models.*
import kotlinx.coroutines.launch
import org.jsoup.Jsoup
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import java.io.Serializable

// 매칭 상세 정보를 위한 API 서비스
interface MatchDetailService {
    @GET("match/detail/{requestId}")
    suspend fun getMatchDetailHtml(@Path("requestId") requestId: Int): Response<String>
}

// 서버에서 실시간으로 계산된 상세 매칭 데이터를 받기 위한 DTO
data class RealMatchDetailDto(
    val similarity: Double,
    val chemistry: Double,
    val activity: Double,
    val myBig5: List<Double>,
    val candBig5: List<Double>,
    val candName: String,
    val myLineCount: Int,
    val candLineCount: Int,
    val mbtiScore: Double,
    val socioScore: Double,
    val mbtiWeight: Float,
    val socioWeight: Float
)

class MatchDetailActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMatchDetailBinding
    private val detailService by lazy { GlobalClient.retrofit.create(MatchDetailService::class.java) }
    private var requestId: Int = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMatchDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)

        requestId = intent.getIntExtra("requestId", 0)
        binding.toolbar.setNavigationOnClickListener { finish() }
        loadData()
    }

    private fun loadData() {
        lifecycleScope.launch {
            try {
                val response = detailService.getMatchDetailHtml(requestId)
                if (response.isSuccessful) {
                    parseHtml(response.body() ?: "")
                }
            } catch (e: Exception) {
                Toast.makeText(this@MatchDetailActivity, "데이터 로드 실패", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun parseHtml(html: String) {
        val doc = Jsoup.parse(html)
        val gson = Gson()
        
        // 1. 웹의 숨겨진 JSON 데이터(data-chart-info) 추출 - 실시간 수치 반영 핵심
        val dataContainer = doc.getElementById("detail-chart-data")
        val chartJson = dataContainer?.attr("data-chart-info") ?: ""
        val d = try { gson.fromJson(chartJson, RealMatchDetailDto::class.java) } catch(e: Exception) { null }

        if (d == null) {
            Toast.makeText(this, "분석 데이터를 파싱할 수 없습니다.", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        // 2. 기본 정보 바인딩
        val partnerName = d.candName.ifEmpty { "상대방" }
        val matchScore = (d.similarity * 50 + d.chemistry * 40 + d.activity * 10).toInt()
        val summaryText = doc.select("section:has(h2:contains(요약)) p").first()?.text()?.trim() ?: ""
        
        binding.tvMatchHeader.text = "${partnerName} 님과의 분석"
        binding.tvPartnerName.text = partnerName
        binding.tvPartnerSummary.text = summaryText
        binding.tvReportPartnerName.text = partnerName

        // 3. 관계 설명 및 점수 배지
        binding.tvMbtiRelation.text = doc.select("p.text-lg.font-bold").first()?.text()?.trim() ?: "관계 분석"
        binding.tvMbtiRelationDesc.text = doc.select("p.text-sm.text-slate-500").first()?.text()?.trim() ?: ""
        binding.tvSocioQuadra.text = doc.select("p.text-sm.font-semibold").last()?.text()?.trim() ?: ""

        binding.tvBig5ScoreBadge.text = "${(d.similarity * 100).toInt()}점"
        binding.tvMbtiScoreBadge.text = "${(d.mbtiScore * 100).toInt()}점"
        binding.tvSocioScoreBadge.text = "${(d.socioScore * 100).toInt()}점"

        // 4. 상세 리포트 텍스트 바인딩
        val mbtiType = doc.select("span.text-4xl.font-bold.text-indigo-600").text().trim()
        val socioType = doc.select("span.text-4xl.font-bold.text-rose-600").text().trim()
        
        binding.tvReportMbti.text = mbtiType
        binding.tvReportMbtiReasons.text = doc.select("section:has(h3:contains(MBTI)) li").map { it.text() }.joinToString("\n• ", prefix = "• ")
        binding.tvReportSocionics.text = socioType
        binding.tvReportSocionicsReasons.text = doc.select("section:has(h3:contains(소시오닉스)) li").map { it.text() }.joinToString("\n• ", prefix = "• ")
        binding.tvReportSummary.text = summaryText
        binding.tvPartnerMbtiSocio.text = "$mbtiType · $socioType"

        // [해결 핵심] 웹의 Big-5 "진짜" 상세 분석 내용 추출 (Description + Witty Comment + AI Note 통합)
        val big5Rows = doc.select("section:has(h2:contains(Big 5)) .grid")
        val fullDetailedReasons = big5Rows.map { row ->
            val desc = row.select("div.md\\:col-span-9 div.font-medium").text().trim()
            val witty = row.select("div.md\\:col-span-9 div.bg-indigo-50\\/30").text().trim()
            val aiNote = row.select("div.md\\:col-span-9 div.bg-slate-50\\/50").text().trim()

            // 모든 정보를 하나로 합쳐서 "나의 분석" 탭과 동일한 정보량 확보
            buildString {
                append(desc)
                if (witty.isNotEmpty()) append("\n\n").append(witty)
                if (aiNote.isNotEmpty()) append("\n\n[AI 분석 노트]\n").append(aiNote)
            }
        }

        val isDark = (resources.configuration.uiMode and android.content.res.Configuration.UI_MODE_NIGHT_MASK) == android.content.res.Configuration.UI_MODE_NIGHT_YES
        val chartLabelColor = if (isDark) Color.WHITE else Color.parseColor("#0F172A")

        setupBig5Details(d.candBig5, fullDetailedReasons)
        setupSpecialCombos(d.candBig5, chartLabelColor)

        // 차트 렌더링
        setupDonutChart(binding.chartDonut, matchScore, d, chartLabelColor)
        setupRadarChart(binding.chartRadar, partnerName, d.myBig5, d.candBig5, chartLabelColor)
        setupChemBreakdownChart(binding.chartChemBreakdown, (d.chemistry * 100).toInt(), d, chartLabelColor)
        setupActivityCompareChart(binding.chartActivityCompare, partnerName, (d.activity * 100).toInt(), d, chartLabelColor)
    }

    private fun setupBig5Details(scores: List<Double>, reasons: List<String>) {
        val r = if (reasons.size >= 5) reasons else listOf("", "", "", "", "")

        setupBig5Item(binding.barOpenness, "개방성", scores[0], r[0])
        setupBig5Item(binding.barConscientiousness, "성실성", scores[1], r[1])
        setupBig5Item(binding.barExtraversion, "외향성", scores[2], r[2])
        setupBig5Item(binding.barAgreeableness, "우호성", scores[3], r[3])
        setupBig5Item(binding.barNeuroticism, "신경성", scores[4], r[4])
    }

    private fun setupBig5Item(itemBinding: ItemBig5BarBinding, name: String, score: Double, desc: String) {
        itemBinding.tvTraitName.text = name
        itemBinding.tvTraitScore.text = "${score.toInt()}%"
        itemBinding.pbTrait.progress = score.toInt()
        itemBinding.tvTraitDescription.text = desc
        
        // [해결] 역삼각형 아이콘 클릭 시 상세 설명 토글
        itemBinding.btnToggleDescription.setOnClickListener {
            val isVisible = itemBinding.tvTraitDescription.visibility == View.VISIBLE
            itemBinding.tvTraitDescription.visibility = if (isVisible) View.GONE else View.VISIBLE
            // 아이콘 회전 효과 (선택 사항)
            itemBinding.btnToggleDescription.animate().rotation(if (isVisible) 0f else 180f).setDuration(200).start()
        }
        
        // 초기 상태: 숨김
        itemBinding.tvTraitDescription.visibility = View.GONE
    }

    private fun setupSpecialCombos(s: List<Double>, labelColor: Int) {
        val combos = mutableListOf<Pair<String, String>>()
        if (s[0] >= 70 && s[1] >= 70) combos.add("🚀 창의적 전략가" to "아이디어가 넘치는데 실행력까지 미쳤습니다!")
        if (s[2] >= 70 && s[3] >= 70) combos.add("🐶 인간 골든 리트리버" to "어딜 가나 사랑받는 인싸!")
        if (s[4] <= 40 && s[1] <= 40) combos.add("🧘 해탈한 신선" to "세상이 무너져도 평온함을 유지합니다.")
        if (s[2] <= 40 && s[1] >= 70) combos.add("🐺 고독한 늑대" to "혼자일 때 효율이 극대화되는 타입!")

        if (combos.isNotEmpty()) {
            binding.layoutReportSpecialCombo.visibility = View.VISIBLE
            binding.containerReportCombos.removeAllViews()
            combos.forEach { (title, desc) ->
                val card = MaterialCardView(this).apply {
                    layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(0, 0, 0, 16) }
                    setCardBackgroundColor(Color.parseColor("#154F46E5"))
                    radius = 16f
                    elevation = 0f
                    val inner = LinearLayout(context).apply {
                        orientation = LinearLayout.VERTICAL; setPadding(24, 24, 24, 24)
                        addView(TextView(context).apply { text = title; setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f); setTextColor(Color.parseColor("#4F46E5")); setTypeface(null, Typeface.BOLD) })
                        addView(TextView(context).apply { text = desc; setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f); setTextColor(labelColor); setPadding(0, 8, 0, 0) })
                    }
                    addView(inner)
                }
                binding.containerReportCombos.addView(card)
            }
        }
    }

    private fun setupDonutChart(chart: PieChart, totalScore: Int, d: RealMatchDetailDto, labelColor: Int) {
        val entries = listOf(PieEntry((d.similarity * 50).toFloat(), "유사도"), PieEntry((d.chemistry * 40).toFloat(), "케미"), PieEntry((d.activity * 10).toFloat(), "활동"))
        val dataSet = PieDataSet(entries, "").apply {
            colors = listOf(Color.parseColor("#3B82F6"), Color.parseColor("#F43F5E"), Color.parseColor("#F59E0B"))
            setDrawValues(true); valueTextColor = Color.WHITE; valueTextSize = 10f
        }
        chart.apply {
            data = PieData(dataSet); isDrawHoleEnabled = true; holeRadius = 60f
            centerText = "${totalScore}점"; setCenterTextSize(24f); setCenterTextColor(labelColor)
            description.isEnabled = false; legend.isEnabled = false; animateY(1000, Easing.EaseInOutQuad); invalidate()
        }
    }

    private fun setupRadarChart(chart: RadarChart, partnerName: String, myScores: List<Double>, candScores: List<Double>, labelColor: Int) {
        val mySet = RadarDataSet(myScores.map { RadarEntry(it.toFloat()) }, "나").apply {
            color = Color.parseColor("#3B82F6"); fillColor = Color.parseColor("#3B82F6")
            setDrawFilled(true); fillAlpha = 40; lineWidth = 2.5f; setDrawHighlightCircleEnabled(true)
        }
        val candSet = RadarDataSet(candScores.map { RadarEntry(it.toFloat()) }, partnerName).apply {
            color = Color.parseColor("#F43F5E"); fillColor = Color.parseColor("#F43F5E")
            setDrawFilled(true); fillAlpha = 40; lineWidth = 2.5f; setDrawHighlightCircleEnabled(true)
        }

        val radarData = RadarData(); radarData.addDataSet(mySet); radarData.addDataSet(candSet)
        radarData.setDrawValues(false)

        chart.apply {
            data = radarData
            webColor = Color.GRAY; webColorInner = Color.GRAY; webAlpha = 100
            xAxis.apply {
                valueFormatter = IndexAxisValueFormatter(listOf("개방성", "성실성", "외향성", "우호성", "신경성"))
                textColor = labelColor; textSize = 11f
            }
            yAxis.apply { axisMinimum = 0f; axisMaximum = 100f; setDrawLabels(false) }
            legend.apply {
                isEnabled = true; textColor = labelColor; verticalAlignment = Legend.LegendVerticalAlignment.BOTTOM
                horizontalAlignment = Legend.LegendHorizontalAlignment.CENTER; orientation = Legend.LegendOrientation.HORIZONTAL
                setDrawInside(false)
            }
            description.isEnabled = false; animateXY(1000, 1000); invalidate()
        }
    }

    private fun setupChemBreakdownChart(chart: HorizontalBarChart, score: Int, d: RealMatchDetailDto, labelColor: Int) {
        binding.tvSocioScoreBadge.text = "${(d.socioScore * 100).toInt()}점"
        binding.tvChemScoreBadge.text = "${score}점"
        val totalW = d.mbtiWeight + d.socioWeight + 1e-9
        val mbtiPart = (d.mbtiScore * d.mbtiWeight / totalW * 100).toFloat()
        val socioPart = (d.socioScore * d.socioWeight / totalW * 100).toFloat()

        val entries = listOf(BarEntry(0f, floatArrayOf(mbtiPart, socioPart)))
        val dataSet = BarDataSet(entries, "").apply {
            colors = listOf(Color.parseColor("#6366F1"), Color.parseColor("#F43F5E"))
            setDrawValues(true); valueTextColor = labelColor; valueTextSize = 10f
        }
        chart.apply {
            data = BarData(dataSet); description.isEnabled = false; legend.isEnabled = false
            xAxis.isEnabled = false; axisLeft.isEnabled = false; axisRight.isEnabled = false; invalidate()
        }
    }

    private fun setupActivityCompareChart(chart: HorizontalBarChart, partnerName: String, score: Int, d: RealMatchDetailDto, labelColor: Int) {
        binding.tvActivityScoreBadge.text = "${score}점"
        val dataSet = BarDataSet(listOf(BarEntry(0f, d.myLineCount.toFloat()), BarEntry(1f, d.candLineCount.toFloat())), "").apply {
            colors = listOf(Color.parseColor("#3B82F6"), Color.parseColor("#F43F5E"))
            setDrawValues(true); valueTextSize = 11f; valueTextColor = labelColor
            valueFormatter = object : ValueFormatter() { override fun getFormattedValue(v: Float): String = "${v.toInt()} 라인" }
        }
        chart.apply {
            data = BarData(dataSet); xAxis.apply {
                valueFormatter = IndexAxisValueFormatter(listOf("나", partnerName))
                position = XAxis.XAxisPosition.BOTTOM; textColor = labelColor
            }
            axisLeft.textColor = labelColor; description.isEnabled = false; legend.isEnabled = false; animateY(1000); invalidate()
        }
    }
}
