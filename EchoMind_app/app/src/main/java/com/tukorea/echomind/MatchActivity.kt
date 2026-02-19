package com.tukorea.echomind

import android.content.res.ColorStateList
import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.chip.Chip
import com.tukorea.echomind.data.api.ApiClient
import com.tukorea.echomind.databinding.ActivityMatchBinding
import com.tukorea.echomind.databinding.ItemMatchCandidateBinding
import com.tukorea.echomind.domain.MatchEngine
import com.tukorea.echomind.models.*
import kotlinx.coroutines.launch
import org.jsoup.Jsoup
import java.io.Serializable

class MatchActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMatchBinding
    private val matchEngine = MatchEngine()
    private val matchService = ApiClient.matchService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMatchBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.rvMatches.layoutManager = LinearLayoutManager(this)
        loadMatchingData()
    }

    private fun loadMatchingData() {
        lifecycleScope.launch {
            try {
                val response = matchService.getMatchingHtml()
                if (response.isSuccessful) {
                    val html = response.body() ?: ""
                    parseMatchingHtml(html)
                } else {
                    Toast.makeText(this@MatchActivity, "서버 연결 실패", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@MatchActivity, "데이터를 불러오는 중 오류 발생", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun parseMatchingHtml(html: String) {
        val doc = Jsoup.parse(html)
        val candidates = mutableListOf<MatchCandidate>()

        doc.select(".glass-panel").forEach { element ->
            val name = element.select("h3.text-2xl").text().trim()
            val totalScoreText = element.select(".text-indigo-600").first()?.text()?.replace("점", "")?.trim()
            val totalScore = totalScoreText?.toIntOrNull() ?: 0

            if (name.isEmpty() || name == "." || totalScore == 0) return@forEach

            val mbti = element.select(".bg-indigo-100").text()
            val socionics = element.select(".bg-rose-100").text()
            val summary = element.select("p.text-slate-600").text()

            val detailScores = element.select(".text-xl.font-bold")
            val sim = detailScores.getOrNull(0)?.text()?.replace("%", "")?.toDoubleOrNull()?.div(100) ?: 0.0
            val chem = detailScores.getOrNull(1)?.text()?.replace("%", "")?.toDoubleOrNull()?.div(100) ?: 0.0
            val act = detailScores.getOrNull(2)?.text()?.replace("점", "")?.toDoubleOrNull()?.div(100) ?: 0.0

            val traits = mutableListOf<RelativeTrait>()
            element.select(".px-2.py-1.rounded.text-xs").forEach { traitElement ->
                val traitText = traitElement.text().trim().split(" ")
                if (traitText.size >= 2) {
                    val color = if (traitElement.hasClass("bg-blue-100")) "#3B82F6" else "#94A3B8"
                    traits.add(RelativeTrait(traitText[0], traitText[1], color))
                }
            }

            val formAction = element.select("form").attr("action")
            val extractedUserId = formAction.split("/").lastOrNull() ?: "unknown"

            val profile = PersonalityProfile(
                userId = extractedUserId,
                name = name,
                summary = SummaryData(summary, emptyList()),
                mbti = MbtiData(mbti, 1.0, emptyList()),
                socionics = SocionicsData(socionics, 1.0, emptyList()),
                big5 = Big5Data(Big5Scores(50.0, 50.0, 50.0, 50.0, 50.0), 1.0, emptyList()),
                caveats = emptyList(),
                lineCount = 0
            )

            candidates.add(MatchCandidate(profile, totalScore, sim, chem, act, traits))
        }

        binding.rvMatches.adapter = MatchAdapter(candidates) { candidate ->
            candidate.profile.userId?.toIntOrNull()?.let { id ->
                applyMatch(id)
            }
        }
    }

    private fun applyMatch(receiverId: Int) {
        lifecycleScope.launch {
            try {
                // 응답 본문을 파싱하지 않고 성공 여부만 확인하여 오류 해결
                val response = matchService.applyMatch(receiverId)
                if (response.isSuccessful) {
                    Toast.makeText(this@MatchActivity, "매칭 신청을 보냈습니다!", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this@MatchActivity, "신청 처리 중 문제가 발생했습니다.", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@MatchActivity, "네트워크 오류가 발생했습니다.", Toast.LENGTH_SHORT).show()
            }
        }
    }
}

class MatchAdapter(
    private val items: List<MatchCandidate>,
    private val onApplyClick: (MatchCandidate) -> Unit
) : RecyclerView.Adapter<MatchAdapter.ViewHolder>() {
    class ViewHolder(val binding: ItemMatchCandidateBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemMatchCandidateBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvCandidateName.text = item.profile.name ?: "Unknown"
            tvCandidateMbti.text = "${item.profile.mbti?.type ?: "Unknown"} · ${item.profile.socionics?.type ?: "Unknown"}"
            tvMatchScore.text = item.matchScore.toString()
            chipGroupTraits.removeAllViews()
            item.relativeTraits.forEach { trait ->
                val chip = Chip(holder.itemView.context).apply {
                    text = "${trait.name} ${trait.label}"
                    chipBackgroundColor = ColorStateList.valueOf(Color.parseColor(trait.color))
                    setTextColor(Color.WHITE)
                    textSize = 10f
                }
                chipGroupTraits.addView(chip)
            }
            root.setOnClickListener { onApplyClick(item) }
        }
    }
    override fun getItemCount() = items.size
}
