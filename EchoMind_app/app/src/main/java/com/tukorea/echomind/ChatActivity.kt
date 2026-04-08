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
import com.tukorea.echomind.databinding.ActivityChatBinding
import com.tukorea.echomind.databinding.ItemChatMessageBinding
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

// [독립 연동] 1:1 채팅 전용 인터페이스 정의
data class MessageDto(
    val id: Int,
    val sender_id: Int,
    val content: String,
    val created_at: String,
    val is_me: Boolean,
    val is_read: Boolean
)

data class MessagesResponse(
    val messages: List<MessageDto>
)

interface ChatApiService {
    @GET("api/chat/{matchCode}/messages")
    suspend fun getMessages(@Path("matchCode") matchCode: String): Response<MessagesResponse>

    @POST("api/chat/{matchCode}/send")
    suspend fun sendMessage(
        @Path("matchCode") matchCode: String,
        @Body body: Map<String, String>
    ): Response<ResponseBody>
}

class ChatActivity : AppCompatActivity() {

    private lateinit var binding: ActivityChatBinding
    private var matchCode: String = ""
    private var partnerName: String = "상대방"
    
    // [동기화 핵심] 전역 세션을 공유하는 sharedRetrofit 사용
    private val chatService: ChatApiService by lazy {
        GlobalClient.retrofit.create(ChatApiService::class.java)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityChatBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // InboxActivity에서 전달받은 매칭 코드와 이름
        matchCode = intent.getStringExtra("matchCode") ?: ""
        partnerName = intent.getStringExtra("partnerName") ?: "상대방"

        setupUI()
    }

    override fun onResume() {
        super.onResume()
        startPollingMessages()
    }

    private fun setupUI() {
        // [해결] 툴바에 상대방 이름을 확실하게 표시
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
                    // [동기화] 매칭 코드를 사용하여 서버와 통신 (세션 쿠키 포함)
                    val response = chatService.getMessages(matchCode)
                    if (response.isSuccessful) {
                        val messages = response.body()?.messages ?: emptyList()
                        updateChatList(messages)
                    }
                } catch (e: Exception) { e.printStackTrace() }
                delay(3000) // 3초 간격 실시간 동기화
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
                // [해결] 전역 세션이 적용된 서비스로 메시지 전송
                val response = chatService.sendMessage(matchCode, mapOf("content" to content))
                if (response.isSuccessful) {
                    binding.etMessage.text.clear()
                    // 전송 즉시 갱신
                    val msgResponse = chatService.getMessages(matchCode)
                    if (msgResponse.isSuccessful) {
                        updateChatList(msgResponse.body()?.messages ?: emptyList())
                    }
                } else {
                    Toast.makeText(this@ChatActivity, "메시지 전송 실패", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@ChatActivity, "네트워크 오류", Toast.LENGTH_SHORT).show()
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
            if (item.is_me) {
                layoutMe.visibility = View.VISIBLE
                layoutPartner.visibility = View.GONE
                tvMeMessage.text = item.content
                tvMeTime.text = item.created_at
                tvMeUnread.visibility = if (item.is_read) View.GONE else View.VISIBLE
            } else {
                layoutMe.visibility = View.GONE
                layoutPartner.visibility = View.VISIBLE
                tvPartnerMessage.text = item.content
                tvPartnerTime.text = item.created_at
                tvPartnerUnread.visibility = View.GONE
                // 1:1 채팅에서도 상대방 닉네임을 보여주고 싶다면 tvPartnerName 사용 가능
                try {
                    val tvName = root.findViewById<android.widget.TextView>(R.id.tvPartnerName)
                    tvName?.visibility = View.GONE // 1:1은 보통 이름 생략
                } catch(e: Exception) {}
            }
        }
    }

    override fun getItemCount() = items.size
}
