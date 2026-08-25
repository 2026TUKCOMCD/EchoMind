package com.tukorea.echomind

import android.app.DatePickerDialog
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.databinding.ActivityRegisterBinding
import kotlinx.coroutines.launch
import java.util.*

class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding
    private val authService = GlobalClient.authService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupUI()

        binding.btnRegister.setOnClickListener {
            val email = binding.etEmail.text.toString().trim()
            val password = binding.etPassword.text.toString()
            val username = binding.etUsername.text.toString().trim()
            val nickname = binding.etNickname.text.toString().trim()
            val birthDate = binding.etBirthDate.text.toString().trim()
            val gender = when (binding.rgGender.checkedRadioButtonId) {
                R.id.rbMale -> "male"
                R.id.rbFemale -> "female"
                R.id.rbOther -> "other"
                else -> null
            }

            if (email.isBlank() || password.isBlank() || username.isBlank()) {
                Toast.makeText(this, "필수 정보를 입력해주세요.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            lifecycleScope.launch {
                try {
                    val response = authService.register(
                        email = email,
                        password = password,
                        username = username,
                        nickname = if (nickname.isNotBlank()) nickname else null,
                        gender = gender,
                        birthDate = if (birthDate.isNotBlank()) birthDate else null
                    )

                    if (response.isSuccessful) {
                        Toast.makeText(this@RegisterActivity, "회원가입 성공! 로그인해주세요.", Toast.LENGTH_SHORT).show()
                        finish()
                    } else {
                        Toast.makeText(this@RegisterActivity, "회원가입 실패: 중복된 이메일일 수 있습니다.", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    Toast.makeText(this@RegisterActivity, "서버 연결 오류", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun setupUI() {
        binding.etBirthDate.setOnClickListener {
            val calendar = Calendar.getInstance()
            DatePickerDialog(
                this,
                { _, year, month, dayOfMonth ->
                    val date = String.format("%04d-%02d-%02d", year, month + 1, dayOfMonth)
                    binding.etBirthDate.setText(date)
                },
                calendar.get(Calendar.YEAR),
                calendar.get(Calendar.MONTH),
                calendar.get(Calendar.DAY_OF_MONTH)
            ).show()
        }

        binding.tvBackToLogin.setOnClickListener {
            finish()
        }
    }
}
