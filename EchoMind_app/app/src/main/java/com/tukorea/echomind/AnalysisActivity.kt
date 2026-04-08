package com.tukorea.echomind

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.data.local.AppDatabase
import com.tukorea.echomind.data.local.PersonalityEntity
import com.tukorea.echomind.databinding.ActivityAnalysisBinding
import com.tukorea.echomind.models.*
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part

interface AnalysisApiService {
    @Multipart
    @POST("upload")
    suspend fun uploadChatFile(
        @Part file: MultipartBody.Part,
        @Part("target_name") targetName: okhttp3.RequestBody
    ): Response<ResponseBody>
}

class AnalysisActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAnalysisBinding
    private var selectedFileUri: Uri? = null
    
    private val analysisService by lazy {
        com.tukorea.echomind.GlobalClient.retrofit.create(AnalysisApiService::class.java)
    }
    private val db by lazy { AppDatabase.getDatabase(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAnalysisBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val filePickerLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == Activity.RESULT_OK) {
                selectedFileUri = result.data?.data
                binding.tvFileName.text = "선택된 파일: ${selectedFileUri?.lastPathSegment ?: "chat.txt"}"
                binding.btnRunAnalysis.isEnabled = true
            }
        }

        binding.btnSelectFile.setOnClickListener {
            val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
                type = "text/plain"
                addCategory(Intent.CATEGORY_OPENABLE)
            }
            filePickerLauncher.launch(intent)
        }

        binding.btnRunAnalysis.setOnClickListener {
            val targetName = binding.etTargetName.text.toString().trim()
            if (targetName.isBlank()) {
                Toast.makeText(this, "대상자 이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            runUploadAndAnalysis(targetName)
        }
    }

    private fun runUploadAndAnalysis(targetName: String) {
        val uri = selectedFileUri ?: return
        binding.progressBar.visibility = View.VISIBLE
        binding.btnRunAnalysis.isEnabled = false

        lifecycleScope.launch {
            try {
                val inputStream = contentResolver.openInputStream(uri)
                val fileBytes = inputStream?.readBytes() ?: ByteArray(0)
                inputStream?.close()

                val fileRequestBody = fileBytes.toRequestBody("text/plain".toMediaTypeOrNull())
                val filePart = MultipartBody.Part.createFormData("file", "chat.txt", fileRequestBody)
                val targetNameBody = targetName.toRequestBody("text/plain".toMediaTypeOrNull())

                val response = analysisService.uploadChatFile(filePart, targetNameBody)
                
                if (response.isSuccessful) {
                    syncNewResult()
                } else {
                    Toast.makeText(this@AnalysisActivity, "분석 실패: ${response.code()}", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@AnalysisActivity, "오류: ${e.message}", Toast.LENGTH_SHORT).show()
            } finally {
                binding.progressBar.visibility = View.GONE
                binding.btnRunAnalysis.isEnabled = true
            }
        }
    }

    private suspend fun syncNewResult() {
        try {
            val profileResp = com.tukorea.echomind.GlobalClient.apiService.getMyProfileJson()
            if (profileResp.isSuccessful) {
                val root = profileResp.body()
                val profile = root?.llmProfile
                if (profile != null) {
                    // [해결] 서버에서 내려준 진짜 result_id를 사용하여 저장
                    val serverId = root.meta?.resultId ?: 0
                    saveToLocal(profile.copy(name = root.meta?.name ?: "Unknown"), serverId)
                    
                    Toast.makeText(this, "분석 완료! 결과가 반영되었습니다.", Toast.LENGTH_SHORT).show()
                    finish()
                }
            }
        } catch (e: Exception) {
            finish()
        }
    }

    private suspend fun saveToLocal(profile: PersonalityProfile, serverId: Int) {
        val email = getSharedPreferences("EchoMindSession", Context.MODE_PRIVATE).getString("user_email", "") ?: ""
        if (email.isBlank()) return

        val entity = PersonalityEntity(
            serverResultId = serverId, 
            userEmail = email,
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
            caveats = profile.caveats?.joinToString("|") ?: "",
            isRepresentative = true
        )
        
        db.personalityDao().clearRepresentative(email)
        db.personalityDao().insertResult(entity)
    }
}
