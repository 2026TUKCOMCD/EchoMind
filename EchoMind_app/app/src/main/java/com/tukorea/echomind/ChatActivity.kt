package com.tukorea.echomind

import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.tukorea.echomind.data.api.ApiClient
import com.tukorea.echomind.data.api.MessageDto
import com.tukorea.echomind.data.api.SendMessageRequest
import com.tukorea.echomind.databinding.ActivityChatBinding
import com.tukorea.echomind.databinding.ItemChatMessageBinding
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class ChatActivity : AppCompatActivity() {

    private lateinit var binding: ActivityChatBinding
    private var requestId: Int = -1
    private var partnerName: String = "상대방"
    
    private val chatService = ApiClient.chatService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityChatBinding.inflate(layoutInflater)
        setContentView(binding.root)

        requestId = intent.getIntExtra("requestId", -1)
        partnerName = intent.getStringExtra("partnerName") ?: "상대방"

        setupUI()
    }

    override fun onResume() {
        super.onResume()
        // [100% 동기화 핵심] 채팅방에 들어온 '이 순간'부터만 서버와 통신하여 읽음 처리를 유발함
        startPollingMessages()
    }

    private fun setupUI() {
        binding.toolbar.title = partnerName
        binding.toolbar.setNavigationOnClickListener { finish() }

        binding.rvMessages.layoutManager = LinearLayoutManager(this).apply {
            stackFromEnd = true
        }

        binding.btnSend.setOnClickListener {
            val content = binding.etMessage.text.toString().trim()
            if (content.isNotBlank()) {
                sendMessage(content)
            }
        }
    }

    private fun startPollingMessages() {
        lifecycleScope.launch {
            while (isActive) {
                try {
                    // 서버의 이 API를 호출해야만 MySQL의 is_read 상태가 true로 업데이트됨
                    val response = chatService.getChatMessages(requestId)
                    if (response.isSuccessful) {
                        val messages = response.body()?.messages ?: emptyList()
                        updateChatList(messages)
                    }
                } catch (e: Exception) {
                    Log.e("ChatPolling", "Failed to fetch messages", e)
                }
                delay(3000) // 3초 간격
            }
        }
    }

    private fun updateChatList(messages: List<MessageDto>) {
        val adapter = binding.rvMessages.adapter as? ChatAdapter
        if (adapter == null) {
            binding.rvMessages.adapter = ChatAdapter(messages)
        } else {
            adapter.updateMessages(messages)
            if (messages.isNotEmpty()) {
                binding.rvMessages.scrollToPosition(messages.size - 1)
            }
        }
    }

    private fun sendMessage(content: String) {
        lifecycleScope.launch {
            try {
                val response = chatService.sendMessage(requestId, SendMessageRequest(content))
                if (response.isSuccessful) {
                    binding.etMessage.text.clear()
                    // 전송 즉시 동기화
                    val msgResponse = chatService.getChatMessages(requestId)
                    if (msgResponse.isSuccessful) {
                        updateChatList(msgResponse.body()?.messages ?: emptyList())
                    }
                }
            } catch (e: Exception) {
                Toast.makeText(this@ChatActivity, "메시지 전송 실패", Toast.LENGTH_SHORT).show()
            }
        }
    }
}

class ChatAdapter(private var items: List<MessageDto>) : RecyclerView.Adapter<ChatAdapter.ViewHolder>() {

    fun updateMessages(newItems: List<MessageDto>) {
        items = newItems
        notifyDataSetChanged()
    }

    class ViewHolder(val binding: ItemChatMessageBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemChatMessageBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            if (item.isMe) {
                layoutMe.visibility = View.VISIBLE
                layoutPartner.visibility = View.GONE
                tvMeMessage.text = item.content
                tvMeTime.text = item.createdAt
                // 상대방이 아직 안 읽었으면(isRead == false) 노란색 숫자 1 표시
                tvMeUnread.visibility = if (item.isRead) View.GONE else View.VISIBLE
            } else {
                layoutMe.visibility = View.GONE
                layoutPartner.visibility = View.VISIBLE
                tvPartnerMessage.text = item.content
                tvPartnerTime.text = item.createdAt
                // 상대방 메시지 옆의 1은 보통 내 화면에선 보이지 않음
                tvPartnerUnread.visibility = View.GONE
            }
        }
    }

    override fun getItemCount() = items.size
}
