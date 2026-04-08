package com.tukorea.echomind

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.tukorea.echomind.databinding.ActivityLoginBinding
import kotlinx.coroutines.launch
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.POST

// [독립 연동] 로그인 전용 인터페이스
interface LoginApiService {
    @FormUrlEncoded
    @POST("login")
    suspend fun login(
        @Field("email") email: String,
        @Field("password") password: String
    ): Response<ResponseBody>
}

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding
    
    // GlobalClient의 전역 Retrofit 사용
    private val apiService: LoginApiService by lazy {
        GlobalClient.retrofit.create(LoginApiService::class.java)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnLogin.setOnClickListener {
            val email = binding.etEmail.text.toString().trim()
            val password = binding.etPassword.text.toString()

            if (email.isBlank() || password.isBlank()) {
                Toast.makeText(this, "정보를 입력해주세요.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            lifecycleScope.launch {
                try {
                    // 웹의 Form 전송 방식과 100% 일치
                    val response = apiService.login(email, password)
                    if (response.isSuccessful) {
                        // 세션 쿠키는 GlobalClient.sharedClient에 자동 저장됨
                        val sharedPref = getSharedPreferences("EchoMindSession", Context.MODE_PRIVATE)
                        sharedPref.edit().putString("user_email", email).apply()

                        Toast.makeText(this@LoginActivity, "로그인 성공!", Toast.LENGTH_SHORT).show()
                        startActivity(Intent(this@LoginActivity, MainActivity::class.java))
                        finish()
                    } else {
                        Toast.makeText(this@LoginActivity, "로그인 실패: 계정을 확인하세요.", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    Toast.makeText(this@LoginActivity, "서버 연결 오류: https://echomind.gleeze.com/ 확인", Toast.LENGTH_SHORT).show()
                }
            }
        }

        binding.tvGoToRegister.setOnClickListener {
            startActivity(Intent(this, RegisterActivity::class.java))
        }
    }
}
