package com.tukorea.echomind

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.data.api.ApiClient
import com.tukorea.echomind.databinding.ActivityAnalysisBinding
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

class AnalysisActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAnalysisBinding
    private var selectedFileUri: Uri? = null
    private val matchService = ApiClient.matchService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAnalysisBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val filePickerLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == Activity.RESULT_OK) {
                selectedFileUri = result.data?.data
                binding.tvFileName.text = selectedFileUri?.lastPathSegment ?: "파일이 선택되었습니다."
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

    /**
     * [웹 버전 100% 재현] .txt 파일을 서버의 /upload로 직접 전송하여 분석 수행
     */
    private fun runUploadAndAnalysis(targetName: String) {
        val uri = selectedFileUri ?: return
        
        binding.progressBar.visibility = View.VISIBLE
        binding.btnRunAnalysis.isEnabled = false

        lifecycleScope.launch {
            try {
                // 1. 파일 데이터 읽기
                val inputStream = contentResolver.openInputStream(uri)
                val fileBytes = inputStream?.readBytes() ?: ByteArray(0)
                inputStream?.close()

                // 2. 웹 브라우저 업로드와 동일한 Multipart 데이터 생성
                val fileRequestBody = fileBytes.toRequestBody("text/plain".toMediaTypeOrNull())
                val filePart = MultipartBody.Part.createFormData("file", "chat.txt", fileRequestBody)
                val targetNameBody = targetName.toRequestBody("text/plain".toMediaTypeOrNull())

                // 3. 서버의 /upload API 호출
                val response = matchService.uploadChatFile(filePart, targetNameBody)
                
                if (response.isSuccessful) {
                    Toast.makeText(this@AnalysisActivity, "분석 요청 성공! 결과를 가져옵니다.", Toast.LENGTH_SHORT).show()
                    // 4. 분석이 완료되면 메인 화면으로 이동하여 자동 동기화 유도
                    finish()
                } else {
                    Toast.makeText(this@AnalysisActivity, "분석 실패: ${response.code()}", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@AnalysisActivity, "오류 발생: ${e.message}", Toast.LENGTH_SHORT).show()
            } finally {
                binding.progressBar.visibility = View.GONE
                binding.btnRunAnalysis.isEnabled = true
            }
        }
    }
}
