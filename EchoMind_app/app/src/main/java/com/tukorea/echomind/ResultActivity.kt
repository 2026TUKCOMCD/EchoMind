package com.tukorea.echomind

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import com.tukorea.echomind.databinding.ActivityResultBinding
import com.tukorea.echomind.databinding.ItemBig5BarBinding
import com.tukorea.echomind.models.PersonalityProfile
import java.io.Serializable

class ResultActivity : AppCompatActivity() {

    private lateinit var binding: ActivityResultBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityResultBinding.inflate(layoutInflater)
        setContentView(binding.root)

        @Suppress("DEPRECATION")
        val profile = intent.getSerializableExtra("profile") as? PersonalityProfile

        profile?.let { currentProfile ->
            displayResult(currentProfile)
            setupToggles()
            
            binding.btnFindMatches.setOnClickListener {
                val intent = Intent(this, MatchActivity::class.java)
                intent.putExtra("myProfile", currentProfile as Serializable)
                startActivity(intent)
            }
        }
    }

    private fun setupToggles() {
        // [요구사항] 소시오닉스란? 섹션 접이식 기능
        binding.btnToggleSocionicsInfo.setOnClickListener {
            if (binding.cardSocionicsInfo.visibility == View.VISIBLE) {
                binding.cardSocionicsInfo.visibility = View.GONE
                binding.btnToggleSocionicsInfo.rotation = 0f
            } else {
                binding.cardSocionicsInfo.visibility = View.VISIBLE
                binding.btnToggleSocionicsInfo.rotation = 180f
            }
        }
    }

    private fun displayResult(profile: PersonalityProfile) {
        binding.tvTargetName.text = "분석 대상: ${profile.name ?: "Unknown"}"

        binding.tvMbtiResult.text = profile.mbti?.type ?: "Unknown"
        binding.tvMbtiReasons.text = profile.mbti?.reasons?.joinToString("\n• ", prefix = "• ") ?: ""
        
        binding.tvSocionicsResult.text = "소시오닉스: ${profile.socionics?.type ?: "Unknown"}"
        binding.tvSocionicsReasons.text = profile.socionics?.reasons?.joinToString("\n• ", prefix = "• ") ?: ""

        // Big-5 항목별 접이식 상세 설명 설정
        val reasons = profile.big5?.reasons ?: emptyList()
        val scores = profile.big5?.scores_0_100

        setupBig5Item(binding.barOpenness, "개방성", scores?.openness ?: 50.0, 
            reasons.find { it.contains("Openness", true) || it.contains("개방성") } ?: "")
        
        setupBig5Item(binding.barConscientiousness, "성실성", scores?.conscientiousness ?: 50.0, 
            reasons.find { it.contains("Conscientiousness", true) || it.contains("성실성") } ?: "")
        
        setupBig5Item(binding.barExtraversion, "외향성", scores?.extraversion ?: 50.0, 
            reasons.find { it.contains("Extraversion", true) || it.contains("외향성") } ?: "")
        
        setupBig5Item(binding.barAgreeableness, "우호성", scores?.agreeableness ?: 50.0, 
            reasons.find { it.contains("Agreeableness", true) || it.contains("우호성") } ?: "")
        
        setupBig5Item(binding.barNeuroticism, "신경성", scores?.neuroticism ?: 50.0, 
            reasons.find { it.contains("Neuroticism", true) || it.contains("신경성") } ?: "")

        // [요구사항] "💡 핵심 요약" 데이터 바인딩
        binding.tvSummary.text = profile.summary?.one_paragraph ?: "요약 정보가 없습니다."
        binding.tvStyleBullets.text = profile.summary?.communication_style_bullets?.joinToString("\n• ", prefix = "• ") ?: ""

        val caveats = profile.caveats
        if (!caveats.isNullOrEmpty()) {
            binding.tvCaveats.text = "주의사항:\n" + caveats.joinToString("\n")
            binding.tvCaveats.visibility = View.VISIBLE
        } else {
            binding.tvCaveats.visibility = View.GONE
        }
    }

    private fun setupBig5Item(itemBinding: ItemBig5BarBinding, name: String, score: Double, description: String) {
        itemBinding.tvTraitName.text = name
        itemBinding.tvTraitScore.text = "${score.toInt()}%"
        itemBinding.pbTrait.progress = score.toInt()
        
        // [요구사항] Big-5 요인별 역삼각형 버튼 접이식 로직
        if (description.isNotBlank()) {
            itemBinding.tvTraitDescription.text = description
            itemBinding.btnToggleDescription.visibility = View.VISIBLE
            itemBinding.btnToggleDescription.setOnClickListener {
                if (itemBinding.tvTraitDescription.visibility == View.VISIBLE) {
                    itemBinding.tvTraitDescription.visibility = View.GONE
                    itemBinding.btnToggleDescription.rotation = 0f
                } else {
                    itemBinding.tvTraitDescription.visibility = View.VISIBLE
                    itemBinding.btnToggleDescription.rotation = 180f
                }
            }
        } else {
            itemBinding.btnToggleDescription.visibility = View.GONE
            itemBinding.tvTraitDescription.visibility = View.GONE
        }
    }
}
