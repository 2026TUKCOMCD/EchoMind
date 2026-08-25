package com.tukorea.echomind

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.data.api.CreditResponse
import com.tukorea.echomind.databinding.ActivityCreditsBinding
import kotlinx.coroutines.launch

class CreditActivity : AppCompatActivity() {
    private lateinit var binding: ActivityCreditsBinding
    private val creditService = GlobalClient.creditService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCreditsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.btnCredit500.setOnClickListener { purchase(500) }
        binding.btnCredit1000.setOnClickListener { purchase(1000) }
        binding.btnCredit2000.setOnClickListener { purchase(2000) }
        binding.btnCredit3000.setOnClickListener { purchase(3000) }
        binding.btnCredit5000.setOnClickListener { purchase(5000) }
        binding.btnCredit10000.setOnClickListener { purchase(10000) }
    }

    override fun onResume() {
        super.onResume()
        loadCredits()
    }

    private fun loadCredits() {
        setLoading(true)
        lifecycleScope.launch {
            try {
                val response = creditService.getCredits()
                if (response.isSuccessful && response.body()?.success == true) {
                    render(response.body()!!)
                } else {
                    showError("크레딧 정보를 불러오지 못했습니다.")
                }
            } catch (exception: Exception) {
                showError("서버 연결 오류")
            } finally {
                setLoading(false)
            }
        }
    }

    private fun purchase(amount: Int) {
        setLoading(true)
        lifecycleScope.launch {
            try {
                val response = creditService.purchaseCredits(amount)
                if (response.isSuccessful && response.body()?.success == true) {
                    render(response.body()!!)
                    Toast.makeText(this@CreditActivity, "$amount 크레딧이 충전되었습니다.", Toast.LENGTH_SHORT).show()
                } else {
                    showError(response.body()?.message ?: "크레딧 구매에 실패했습니다.")
                }
            } catch (exception: Exception) {
                showError("서버 연결 오류")
            } finally {
                setLoading(false)
            }
        }
    }

    private fun render(data: CreditResponse) {
        binding.tvBalance.text = "%,d 크레딧".format(data.balance)
        binding.tvAnalysisInfo.text = "추가 분석 비용: ${data.analysisCost} 크레딧"
        binding.tvTransactions.text = data.transactions.joinToString("\n\n") { transaction ->
            val sign = if (transaction.amount >= 0) "+" else ""
            "${transaction.description}\n$sign%,d 크레딧".format(transaction.amount)
        }.ifBlank { "거래 내역이 없습니다." }
    }

    private fun setLoading(loading: Boolean) {
        binding.progressBar.visibility = if (loading) View.VISIBLE else View.GONE
        val enabled = !loading
        binding.btnCredit500.isEnabled = enabled
        binding.btnCredit1000.isEnabled = enabled
        binding.btnCredit2000.isEnabled = enabled
        binding.btnCredit3000.isEnabled = enabled
        binding.btnCredit5000.isEnabled = enabled
        binding.btnCredit10000.isEnabled = enabled
    }

    private fun showError(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }
}
