package com.tukorea.echomind

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.tukorea.echomind.data.api.BlindChatResponse
import com.tukorea.echomind.data.api.BlindMessageDto
import com.tukorea.echomind.databinding.ActivityBlindChatBinding
import com.tukorea.echomind.databinding.ItemChatMessageBinding
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

class BlindChatActivity : AppCompatActivity() {
    private lateinit var binding: ActivityBlindChatBinding
    private val service = GlobalClient.blindMatchService
    private var matchCode = ""
    private var matchId = 0
    private var pollingJob: Job? = null
    private lateinit var adapter: BlindChatAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityBlindChatBinding.inflate(layoutInflater)
        setContentView(binding.root)

        matchCode = intent.getStringExtra("matchCode") ?: ""
        matchId = intent.getIntExtra("matchId", 0)

        setupUI()
    }

    private fun setupUI() {
        binding.toolbar.setNavigationOnClickListener { finish() }
        
        adapter = BlindChatAdapter(emptyList())
        binding.rvMessages.layoutManager = LinearLayoutManager(this).apply {
            stackFromEnd = true
        }
        binding.rvMessages.adapter = adapter

        binding.btnSend.setOnClickListener { sendMessage() }
        binding.btnSendProfile.setOnClickListener { sendProfile() }
        binding.btnEnd.setOnClickListener { endMatch() }
    }

    override fun onResume() {
        super.onResume()
        pollingJob?.cancel()
        pollingJob = lifecycleScope.launch {
            while (isActive) {
                loadMessages()
                delay(3000)
            }
        }
    }

    override fun onPause() {
        pollingJob?.cancel()
        super.onPause()
    }

    private suspend fun loadMessages() {
        try {
            val response = service.getMessages(matchCode)
            if (response.isSuccessful && response.body() != null) {
                render(response.body()!!)
            }
        } catch (_: Exception) {}
    }

    private fun render(data: BlindChatResponse) {
        adapter.updateMessages(data.messages)
        
        data.profile_status?.let { status ->
            binding.btnSendProfile.isEnabled = !status.i_sent
            binding.btnSendProfile.text = if (status.i_sent) "프로필 전송 완료" else "프로필 보내기"
        }
        
        if (data.status == "REVEALED") {
            Toast.makeText(this, "프로필이 공개되었습니다.", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    private fun sendMessage() {
        val content = binding.etMessage.text.toString().trim()
        if (content.isBlank()) return
        binding.etMessage.text?.clear()
        lifecycleScope.launch {
            try {
                service.sendMessage(matchCode, mapOf("content" to content))
                loadMessages()
            } catch (_: Exception) {
                Toast.makeText(this@BlindChatActivity, "메시지 전송 실패", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun sendProfile() {
        lifecycleScope.launch {
            try {
                val response = service.sendProfile(matchId)
                Toast.makeText(this@BlindChatActivity, response.body()?.message ?: "프로필을 보냈습니다.", Toast.LENGTH_SHORT).show()
                loadMessages()
            } catch (_: Exception) {
                Toast.makeText(this@BlindChatActivity, "프로필 전송 실패", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun endMatch() {
        lifecycleScope.launch {
            try {
                val response = service.endMatch(matchId)
                Toast.makeText(this@BlindChatActivity, response.body()?.message ?: "대화를 종료했습니다.", Toast.LENGTH_SHORT).show()
                finish()
            } catch (_: Exception) {
                Toast.makeText(this@BlindChatActivity, "대화 종료 실패", Toast.LENGTH_SHORT).show()
            }
        }
    }
}

class BlindChatAdapter(private var items: List<BlindMessageDto>) : RecyclerView.Adapter<BlindChatAdapter.ViewHolder>() {

    fun updateMessages(newItems: List<BlindMessageDto>) {
        if (items != newItems) {
            items = newItems
            notifyDataSetChanged()
        }
    }

    class ViewHolder(val binding: ItemChatMessageBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemChatMessageBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            // 블라인드 채팅이므로 시스템 메시지/날짜 구분선 로직은 단순화하거나 서버 데이터에 맞춤
            layoutSystem.visibility = View.GONE 
            
            val formattedTime = formatToKstTime(item.created_at)

            if (item.is_me) {
                layoutMe.visibility = View.VISIBLE
                layoutPartner.visibility = View.GONE
                tvMeMessage.text = item.content
                tvMeTime.text = formattedTime
                // [핵심] 안 읽었으면 1 표시, 읽었으면 숨김
                tvMeUnread.visibility = if (item.is_read) View.GONE else View.VISIBLE
            } else {
                layoutMe.visibility = View.GONE
                layoutPartner.visibility = View.VISIBLE
                tvPartnerMessage.text = item.content
                tvPartnerTime.text = formattedTime
                tvPartnerUnread.visibility = View.GONE // 상대방 메시지의 안읽음 표시는 내 화면에선 보통 안 보임
                tvPartnerName.visibility = View.GONE // 블라인드 채팅이므로 이름 숨김
            }
        }
    }

    private fun formatToKstTime(timeStr: String): String {
        return try {
            val sdf24 = SimpleDateFormat("HH:mm", Locale.getDefault())
            val date = sdf24.parse(timeStr) ?: return timeStr
            val sdf12 = SimpleDateFormat("a h:mm", Locale.KOREAN)
            sdf12.format(date)
        } catch (e: Exception) {
            timeStr
        }
    }

    override fun getItemCount() = items.size
}
