package com.tukorea.echomind

import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.util.TypedValue
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.card.MaterialCardView
import com.tukorea.echomind.databinding.ActivityResultBinding
import com.tukorea.echomind.databinding.ItemBig5BarBinding
import com.tukorea.echomind.models.PersonalityProfile
import java.io.Serializable

class ResultActivity : AppCompatActivity() {

    private lateinit var binding: ActivityResultBinding

    // 웹 서비스(visualize_profile.py)와 동일한 설명 매핑 데이터베이스
    private val traitDescriptions = mapOf(
        "openness" to listOf(
            20 to "익숙함과 안정을 최우선으로 하며, 검증된 방식을 선호합니다.",
            40 to "현실적이고 실용적인 접근 방식을 중요시합니다.",
            60 to "현실 감각과 새로운 시도 사이에서 균형을 유지합니다.",
            80 to "새로운 경험과 지적 탐구를 즐기는 모험가입니다.",
            101 to "끊임없는 호기심과 풍부한 상상력을 가진 혁신가입니다."
        ),
        "conscientiousness" to listOf(
            20 to "즉흥적이고 자유분방하며, 구속받는 것을 싫어합니다.",
            40 to "유연함을 선호하며 계획보다는 흐름을 따릅니다.",
            60 to "필요할 때는 집중하며, 일과 여유의 균형을 찾습니다.",
            80 to "목표 지향적이며 체계적인 계획을 세워 실행합니다.",
            101 to "철저한 자기관리와 완벽함을 추구하는 전략가입니다."
        ),
        "extraversion" to listOf(
            20 to "혼자만의 시간에서 에너지를 얻는 신중한 관찰자입니다.",
            40 to "조용한 환경과 깊이 있는 대화를 선호합니다.",
            60 to "상황에 따라 사교성과 혼자만의 시간을 조절합니다.",
            80 to "사람들과 어울리며 에너지를 얻는 분위기 메이커입니다.",
            101 to "어디서나 활력을 불어넣는 열정적인 사교가입니다."
        ),
        "agreeableness" to listOf(
            20 to "논리와 이성을 중시하며, 직설적으로 의견을 표현합니다.",
            40 to "타인의 시선보다는 자신의 원칙과 주관을 따릅니다.",
            60 to "자신의 이익을 지키면서도 타인을 배려할 줄 압니다.",
            80 to "타인의 감정에 깊이 공감하며, 협력을 중요시합니다.",
            101 to "따뜻한 마음으로 주변을 챙기는 이타적인 평화주의자입니다."
        ),
        "neuroticism" to listOf(
            20 to "어떤 상황에서도 흔들리지 않는 강철 멘탈의 소유자입니다.",
            40 to "스트레스를 잘 관리하며 침착함을 유지합니다.",
            60 to "적당한 긴장감을 느끼지만 일상생활을 잘 영위합니다.",
            80 to "풍부한 감수성을 지녔으며, 변화에 민감하게 반응합니다.",
            101 to "작은 일에도 깊이 고민하고 완벽을 기하려 노력합니다."
        )
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityResultBinding.inflate(layoutInflater)
        setContentView(binding.root)

        @Suppress("DEPRECATION")
        val profile = intent.getSerializableExtra("profile") as? PersonalityProfile

        profile?.let { currentProfile ->
            displayResult(currentProfile)
            setupSpecialCombos(currentProfile)
            setupUI(currentProfile)
        } ?: run {
            Toast.makeText(this, "데이터를 불러올 수 없습니다.", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    private fun setupUI(profile: PersonalityProfile) {
        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.btnFindMatches.setOnClickListener {
            val intent = Intent(this, MatchActivity::class.java)
            intent.putExtra("myProfile", profile as Serializable)
            startActivity(intent)
        }
    }

    private fun displayResult(profile: PersonalityProfile) {
        binding.tvTargetName.text = "분석 대상: ${profile.name ?: "내 프로필"}"
        binding.tvMbtiResult.text = profile.mbti?.type ?: "분석중"
        binding.tvMbtiReasons.text = profile.mbti?.reasons?.joinToString("\n• ", prefix = "• ") ?: ""
        binding.tvSocionicsResult.text = "소시오닉스: ${profile.socionics?.type ?: "분석중"}"
        binding.tvSocionicsReasons.text = profile.socionics?.reasons?.joinToString("\n• ", prefix = "• ") ?: ""

        val scores = profile.big5?.scores_0_100
        val reasons = profile.big5?.reasons ?: emptyList()

        // [해결] 웹 서비스와 동일한 상세 설명 로직 적용
        setupBig5Item(binding.barOpenness, "openness", "개방성", scores?.openness ?: 50.0, reasons)
        setupBig5Item(binding.barConscientiousness, "conscientiousness", "성실성", scores?.conscientiousness ?: 50.0, reasons)
        setupBig5Item(binding.barExtraversion, "extraversion", "외향성", scores?.extraversion ?: 50.0, reasons)
        setupBig5Item(binding.barAgreeableness, "agreeableness", "우호성", scores?.agreeableness ?: 50.0, reasons)
        setupBig5Item(binding.barNeuroticism, "neuroticism", "신경성", scores?.neuroticism ?: 50.0, reasons)

        binding.tvSummary.text = profile.summary?.one_paragraph ?: "성향 요약 정보가 없습니다."
        binding.tvStyleBullets.text = profile.summary?.communication_style_bullets?.joinToString("\n• ", prefix = "• ") ?: ""
        
        profile.caveats?.let {
            if (it.isNotEmpty()) {
                binding.tvCaveats.text = "⚠️ 주의사항 및 한계\n" + it.joinToString("\n")
                binding.tvCaveats.visibility = View.VISIBLE
            }
        }
    }

    private fun setupBig5Item(itemBinding: ItemBig5BarBinding, key: String, name: String, score: Double, reasons: List<String>) {
        itemBinding.tvTraitName.text = name
        itemBinding.tvTraitScore.text = "${score.toInt()}%"
        itemBinding.pbTrait.progress = score.toInt()

        // 1. 웹 서비스 기반 정보성 설명 찾기
        val baseDesc = traitDescriptions[key]?.find { score <= it.first }?.second ?: ""
        
        // 2. AI 분석 노트 (실제 채팅 분석 근거) 찾기
        val aiNote = reasons.find { it.contains(name) || it.contains(key, true) } ?: ""

        // 3. 웹 서비스와 동일한 풍부한 설명 구성
        val fullDescription = buildString {
            append(baseDesc)
            if (aiNote.isNotBlank()) {
                append("\n\n[🤖 AI 분석 노트]\n")
                append(aiNote)
            }
        }

        itemBinding.tvTraitDescription.text = fullDescription
        itemBinding.tvTraitDescription.visibility = View.GONE
        itemBinding.btnToggleDescription.setOnClickListener {
            val isVisible = itemBinding.tvTraitDescription.visibility == View.VISIBLE
            itemBinding.tvTraitDescription.visibility = if (isVisible) View.GONE else View.VISIBLE
            itemBinding.btnToggleDescription.rotation = if (isVisible) 0f else 180f
        }
    }

    private fun setupSpecialCombos(profile: PersonalityProfile) {
        val s = profile.big5?.scores_0_100 ?: return
        val combos = mutableListOf<Pair<String, String>>()

        // 웹 서비스 matcher.py와 100% 동일한 판별 로직
        if (s.openness >= 70 && s.conscientiousness >= 70) combos.add("🚀 창의적 전략가" to "아이디어가 넘치는데 실행력까지 미쳤습니다. 혼자서 기획, 개발, 런칭까지 다 해버리는 '1인 유니콘'!")
        if (s.openness >= 70 && s.conscientiousness <= 40) combos.add("☁️ 몽상가" to "머릿속엔 혁신적인 생각이 가득한데 실천이 어렵네요. 당신의 아이디어를 현실로 만들어줄 파트너가 필요합니다!")
        if (s.extraversion >= 70 && s.agreeableness >= 70) combos.add("🐶 인간 골든 리트리버" to "어딜 가나 사랑받는 인싸! 당신 주변엔 항상 사람들이 모여듭니다. 진정한 분위기 메이커시군요.")
        if (s.extraversion >= 70 && s.agreeableness <= 40) combos.add("🚜 불도저 리더" to "카리스마 넘치는 직진형 리더! 목표를 위해서라면 팩트 폭격도 서슴지 않는 강한 추진력의 소유자입니다.")
        if (s.neuroticism >= 70 && s.conscientiousness >= 70) combos.add("⚡ 불안한 완벽주의자" to "완벽을 위해 끊임없이 자신을 채찍질합니다. 결과물은 훌륭하지만 건강을 위해 조금은 내려놓아도 좋습니다.")
        if (s.neuroticism >= 70 && s.agreeableness >= 70) combos.add("💧 감정 스펀지" to "타인의 감정을 누구보다 깊게 흡수합니다. 공감 능력이 탁월하지만 정작 본인의 마음을 돌보는 시간도 꼭 필요해요.")
        if (s.neuroticism <= 40 && s.conscientiousness <= 40) combos.add("🧘 해탈한 신선" to "세상이 무너져도 '그럴 수 있지' 하고 넘길 수 있는 평온함의 끝판왕! 스트레스가 당신을 비껴갑니다.")
        if (s.extraversion <= 40 && s.conscientiousness >= 70) combos.add("🐺 고독한 늑대" to "혼자일 때 효율이 극대화되는 타입! 팀워크보다는 본인만의 확실한 전문성으로 성과를 내는 스타일입니다.")

        if (combos.isNotEmpty()) {
            binding.layoutSpecialCombo.visibility = View.VISIBLE
            binding.containerCombos.removeAllViews()
            combos.forEach { (title, desc) ->
                val card = MaterialCardView(this).apply {
                    layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(0, 0, 0, 32) }
                    setCardBackgroundColor(Color.parseColor("#154F46E5"))
                    radius = 16f
                    elevation = 0f
                    val inner = LinearLayout(context).apply {
                        orientation = LinearLayout.VERTICAL
                        setPadding(40, 40, 40, 40)
                        addView(TextView(context).apply { 
                            text = title
                            textSize = 16f
                            setTextColor(Color.parseColor("#4F46E5"))
                            setTypeface(null, Typeface.BOLD) 
                        })
                        addView(TextView(context).apply { 
                            text = desc
                            textSize = 13f
                            setTextColor(ContextCompat.getColor(context, R.color.text_primary))
                            setPadding(0, 12, 0, 0)
                            setLineSpacing(0f, 1.2f)
                        })
                    }
                    addView(inner)
                }
                binding.containerCombos.addView(card)
            }
        }
    }
}
