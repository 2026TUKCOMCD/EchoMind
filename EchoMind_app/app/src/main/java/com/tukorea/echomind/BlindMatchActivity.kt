package com.tukorea.echomind

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.databinding.ActivityBlindMatchBinding
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import retrofit2.Response

class BlindMatchActivity : AppCompatActivity() {
    private lateinit var binding: ActivityBlindMatchBinding
    private val service = GlobalClient.blindMatchService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityBlindMatchBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.btnQueue.setOnClickListener { enterQueue() }
        binding.btnLeave.setOnClickListener { leaveQueue() }
        refreshStatus()
    }

    private fun refreshStatus() {
        lifecycleScope.launch {
            while (isActive) {
                try {
                    val response = service.getQueueStatus()
                    if (response.isSuccessful) {
                        val status = response.body()
                        when (status?.status) {
                            "WAITING" -> binding.tvStatus.text = "매칭 상대를 찾고 있습니다. 잠시만 기다려주세요."
                            "MATCHED" -> binding.tvStatus.text = "매칭이 완료되었습니다. 블라인드 인박스를 확인해주세요."
                            else -> binding.tvStatus.text = "현재 대기열에 참여하고 있지 않습니다."
                        }
                    }
                } catch (_: Exception) {
                    binding.tvStatus.text = "서버 연결을 확인해주세요."
                }
                delay(5000)
            }
        }
    }

    private fun enterQueue() {
        runAction { service.enterQueue() }
    }

    private fun leaveQueue() {
        runAction { service.leaveQueue() }
    }

    private fun runAction(action: suspend () -> Response<com.tukorea.echomind.data.api.BlindActionResponse>) {
        binding.progressBar.visibility = View.VISIBLE
        lifecycleScope.launch {
            try {
                val response = action()
                Toast.makeText(this@BlindMatchActivity, response.body()?.message ?: "처리되었습니다.", Toast.LENGTH_SHORT).show()
            } catch (_: Exception) {
                Toast.makeText(this@BlindMatchActivity, "서버 연결 오류", Toast.LENGTH_SHORT).show()
            } finally {
                binding.progressBar.visibility = View.GONE
            }
        }
    }
}
