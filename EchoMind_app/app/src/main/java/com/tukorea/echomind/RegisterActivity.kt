package com.tukorea.echomind

import android.app.DatePickerDialog
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.data.api.ApiClient
import com.tukorea.echomind.databinding.ActivityRegisterBinding
import kotlinx.coroutines.launch
import java.util.*

class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding
    private val authService = ApiClient.authService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // 생년월일 입력 클릭 시 달력 띄우기
        binding.etBirthDate.setOnClickListener {
            showDatePicker()
        }

        binding.btnRegister.setOnClickListener {
            val email = binding.etEmail.text.toString().trim()
            val password = binding.etPassword.text.toString().trim()
            val username = binding.etUsername.text.toString().trim()
            val nickname = binding.etNickname.text.toString().trim()
            
            // [수정] 성별 값 추출 로직: 남성, 여성, 기타를 명확히 구분
            val gender = when {
                binding.rbMale.isChecked -> "MALE"
                binding.rbFemale.isChecked -> "FEMALE"
                binding.rbOther.isChecked -> "OTHER"
                else -> "OTHER"
            }

            val birthDate = binding.etBirthDate.text.toString().trim()

            if (email.isBlank() || password.isBlank() || username.isBlank() || birthDate.isBlank()) {
                Toast.makeText(this, "모든 필수 항목을 입력해주세요.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            lifecycleScope.launch {
                try {
                    val response = authService.register(email, password, username, nickname, gender, birthDate)
                    if (response.isSuccessful) {
                        Toast.makeText(this@RegisterActivity, "회원가입 성공! 로그인해주세요.", Toast.LENGTH_SHORT).show()
                        finish()
                    } else {
                        Toast.makeText(this@RegisterActivity, "회원가입 실패: 이미 존재하는 계정일 수 있습니다.", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    Toast.makeText(this@RegisterActivity, "서버 연결 오류", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showDatePicker() {
        val calendar = Calendar.getInstance()
        val year = calendar.get(Calendar.YEAR)
        val month = calendar.get(Calendar.MONTH)
        val day = calendar.get(Calendar.DAY_OF_MONTH)

        DatePickerDialog(this, { _, selectedYear, selectedMonth, selectedDay ->
            val formattedDate = String.format("%04d-%02d-%02d", selectedYear, selectedMonth + 1, selectedDay)
            binding.etBirthDate.setText(formattedDate)
        }, year, month, day).show()
    }
}
