package com.tukorea.echomind

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.chip.Chip
import com.tukorea.echomind.databinding.ActivityGroupCreateBinding
import kotlinx.coroutines.launch
import okhttp3.*
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST

// 서버의 /groups/create 엔드포인트와 데이터 구조 일치
interface GroupCreateApiService {
    @POST("groups/create")
    suspend fun createGroup(@Body body: RequestBody): Response<ResponseBody>
}

class GroupCreateActivity : AppCompatActivity() {

    private lateinit var binding: ActivityGroupCreateBinding
    
    // GlobalClient 세션 공유
    private val createService by lazy {
        com.tukorea.echomind.GlobalClient.retrofit.create(GroupCreateApiService::class.java)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityGroupCreateBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setupUI()
    }

    private fun setupUI() {
        binding.toolbar.setNavigationOnClickListener { finish() }
        
        // MBTI 칩 동적 추가 (16종)
        val mbtis = listOf("INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP", "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP")
        if (binding.cgMbti.childCount == 0) {
            mbtis.forEach { mbti ->
                val chip = Chip(this).apply { 
                    text = mbti
                    isCheckable = true 
                    setChipBackgroundColorResource(android.R.color.transparent)
                    setChipStrokeColorResource(R.color.border)
                    setChipStrokeWidthResource(R.dimen.chip_stroke_width)
                }
                binding.cgMbti.addView(chip)
            }
        }

        binding.btnCreate.setOnClickListener {
            val name = binding.etName.text.toString().trim()
            if (name.isEmpty()) {
                Toast.makeText(this, "방 제목을 입력해주세요.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            runCreateGroup(name)
        }
    }

    private fun runCreateGroup(name: String) {
        lifecycleScope.launch {
            try {
                // 웹 서비스 Form 전송 방식 100% 재현
                val bodyBuilder = FormBody.Builder()
                    .add("name", name)
                    .add("description", binding.etDescription.text.toString())
                    .add("max_participants", binding.etMaxParticipants.text.toString().ifEmpty { "10" })

                // 1. 성별 (genders 리스트)
                if (binding.cbMale.isChecked) bodyBuilder.add("genders", "MALE")
                if (binding.cbFemale.isChecked) bodyBuilder.add("genders", "FEMALE")
                if (binding.cbOther.isChecked) bodyBuilder.add("genders", "OTHER")

                // 2. 나이 (min_age, max_age)
                binding.etMinAge.text.toString().let { if(it.isNotEmpty()) bodyBuilder.add("min_age", it) }
                binding.etMaxAge.text.toString().let { if(it.isNotEmpty()) bodyBuilder.add("max_age", it) }

                // 3. MBTI (mbtis 리스트)
                for (i in 0 until binding.cgMbti.childCount) {
                    val chip = binding.cgMbti.getChildAt(i) as Chip
                    if (chip.isChecked) bodyBuilder.add("mbtis", chip.text.toString())
                }

                // 4. 소시오닉스 쿼드라 (quadras 리스트) - [해결] 레이아웃 ID(chipAlpha 등)에 맞게 수정
                if (binding.chipAlpha.isChecked) bodyBuilder.add("quadras", "Alpha")
                if (binding.chipBeta.isChecked) bodyBuilder.add("quadras", "Beta")
                if (binding.chipGamma.isChecked) bodyBuilder.add("quadras", "Gamma")
                if (binding.chipDelta.isChecked) bodyBuilder.add("quadras", "Delta")

                // 5. Big 5 성격 점수 제한
                addBig5Param(bodyBuilder, "openness", binding.etOpennessMin.text.toString(), binding.etOpennessMax.text.toString())
                addBig5Param(bodyBuilder, "conscientiousness", binding.etConscientiousnessMin.text.toString(), binding.etConscientiousnessMax.text.toString())
                addBig5Param(bodyBuilder, "extraversion", binding.etExtraversionMin.text.toString(), binding.etExtraversionMax.text.toString())
                addBig5Param(bodyBuilder, "agreeableness", binding.etAgreeablenessMin.text.toString(), binding.etAgreeablenessMax.text.toString())
                addBig5Param(bodyBuilder, "neuroticism", binding.etNeuroticismMin.text.toString(), binding.etNeuroticismMax.text.toString())

                val response = createService.createGroup(bodyBuilder.build())
                if (response.isSuccessful) {
                    Toast.makeText(this@GroupCreateActivity, "방이 개설되었습니다!", Toast.LENGTH_SHORT).show()
                    finish()
                } else {
                    Toast.makeText(this@GroupCreateActivity, "개설 실패: ${response.code()}", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@GroupCreateActivity, "오류: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun addBig5Param(builder: FormBody.Builder, trait: String, min: String, max: String) {
        if (min.isNotEmpty() && max.isNotEmpty()) {
            builder.add("big5_${trait}_min", min)
            builder.add("big5_${trait}_max", max)
        }
    }
}
