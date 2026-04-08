package com.tukorea.echomind

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.GravityCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.tukorea.echomind.databinding.ActivityGroupChatBinding
import com.tukorea.echomind.databinding.ItemGroupParticipantBinding
import com.tukorea.echomind.databinding.ItemChatMessageBinding
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

data class GroupMessageDto(
    val id: Int,
    val sender_id: Int,
    val sender_nickname: String,
    val content: String,
    val is_system: Boolean,
    val unread_count: Int,
    val created_at: String,
    val is_me: Boolean
)

data class GroupMessagesResponse(val messages: List<GroupMessageDto>)

data class ParticipantDto(
    val user_id: Int,
    val nickname: String,
    val is_me: Boolean,
    val is_creator: Boolean,
    val votes: Int,
    val threshold: Int,
    val voted_by_me: Boolean
)

data class ParticipantsResponse(val participants: List<ParticipantDto>)

interface GroupApiService {
    @GET("api/groups/{roomCode}/messages")
    suspend fun getGroupMessages(@Path("roomCode") roomCode: String): Response<GroupMessagesResponse>

    @POST("api/groups/{roomCode}/send")
    suspend fun sendGroupMessage(@Path("roomCode") roomCode: String, @Body body: Map<String, String>): Response<ResponseBody>

    @GET("api/groups/{roomCode}/participants")
    suspend fun getParticipants(@Path("roomCode") roomCode: String): Response<ParticipantsResponse>

    @POST("api/groups/{roomCode}/kick/{targetId}")
    suspend fun voteKick(@Path("roomCode") roomCode: String, @Path("targetId") targetId: Int): Response<ResponseBody>

    @POST("groups/{roomCode}/delete")
    suspend fun deleteRoom(@Path("roomCode") roomCode: String): Response<ResponseBody>
}

class GroupChatActivity : AppCompatActivity() {

    private lateinit var binding: ActivityGroupChatBinding
    private var roomCode: String = ""
    private var roomName: String = ""

    private val groupService by lazy {
        com.tukorea.echomind.GlobalClient.retrofit.create(GroupApiService::class.java)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityGroupChatBinding.inflate(layoutInflater)
        setContentView(binding.root)

        roomCode = intent.getStringExtra("roomCode") ?: ""
        roomName = intent.getStringExtra("roomName") ?: "그룹 채팅"

        setupUI()
    }

    override fun onResume() {
        super.onResume()
        startPollingMessages()
        loadParticipants()
    }

    private fun setupUI() {
        binding.toolbar.title = roomName
        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.rvMessages.layoutManager = LinearLayoutManager(this).apply { stackFromEnd = true }
        binding.rvParticipants.layoutManager = LinearLayoutManager(this)

        binding.btnSend.setOnClickListener {
            val content = binding.etMessage.text.toString().trim()
            if (content.isNotBlank()) sendMessage(content)
        }

        binding.btnParticipants.setOnClickListener {
            binding.drawerLayout.openDrawer(GravityCompat.END)
            loadParticipants()
        }

        binding.btnDeleteRoom.setOnClickListener { showDeleteConfirmDialog() }
    }

    private fun startPollingMessages() {
        lifecycleScope.launch {
            while (isActive) {
                try {
                    val response = groupService.getGroupMessages(roomCode)
                    if (response.isSuccessful) {
                        updateChatList(response.body()?.messages ?: emptyList())
                    }
                } catch (e: Exception) { e.printStackTrace() }
                delay(2000)
            }
        }
    }

    private fun loadParticipants() {
        lifecycleScope.launch {
            try {
                val response = groupService.getParticipants(roomCode)
                if (response.isSuccessful) {
                    val participants = response.body()?.participants ?: emptyList()
                    val me = participants.find { it.is_me }
                    binding.btnDeleteRoom.visibility = if (me?.is_creator == true) View.VISIBLE else View.GONE
                    binding.rvParticipants.adapter = ParticipantAdapter(participants) { target -> voteKick(target.user_id) }
                }
            } catch (e: Exception) { e.printStackTrace() }
        }
    }

    private fun updateChatList(messages: List<GroupMessageDto>) {
        val adapter = binding.rvMessages.adapter as? GroupChatAdapter
        if (adapter == null) {
            binding.rvMessages.adapter = GroupChatAdapter(messages)
        } else {
            adapter.updateMessages(messages)
            if (messages.isNotEmpty()) binding.rvMessages.scrollToPosition(messages.size - 1)
        }
    }

    private fun sendMessage(content: String) {
        lifecycleScope.launch {
            try {
                val response = groupService.sendGroupMessage(roomCode, mapOf("content" to content))
                if (response.isSuccessful) binding.etMessage.text.clear()
            } catch (e: Exception) { }
        }
    }

    private fun voteKick(targetId: Int) {
        lifecycleScope.launch {
            try {
                val response = groupService.voteKick(roomCode, targetId)
                if (response.isSuccessful) loadParticipants()
            } catch (e: Exception) { }
        }
    }

    private fun showDeleteConfirmDialog() {
        AlertDialog.Builder(this)
            .setTitle("방 해체")
            .setMessage("정말로 이 채팅방을 해체하시겠습니까?")
            .setPositiveButton("해체") { _, _ -> deleteRoom() }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun deleteRoom() {
        lifecycleScope.launch {
            try {
                val response = groupService.deleteRoom(roomCode)
                if (response.isSuccessful) finish()
            } catch (e: Exception) { }
        }
    }
}

class GroupChatAdapter(private var items: List<GroupMessageDto>) : RecyclerView.Adapter<GroupChatAdapter.ViewHolder>() {
    fun updateMessages(newItems: List<GroupMessageDto>) { items = newItems; notifyDataSetChanged() }
    class ViewHolder(val binding: ItemChatMessageBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemChatMessageBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            // [해결] 시스템 메시지 중앙 배치 로직
            if (item.is_system) {
                layoutSystem.visibility = View.VISIBLE
                layoutMe.visibility = View.GONE
                layoutPartner.visibility = View.GONE
                tvSystemMessage.text = item.content
            } else if (item.is_me) {
                layoutSystem.visibility = View.GONE
                layoutMe.visibility = View.VISIBLE
                layoutPartner.visibility = View.GONE
                tvMeMessage.text = item.content
                tvMeTime.text = item.created_at
                tvMeUnread.visibility = if (item.unread_count > 0) View.VISIBLE else View.GONE
                tvMeUnread.text = item.unread_count.toString()
            } else {
                layoutSystem.visibility = View.GONE
                layoutMe.visibility = View.GONE
                layoutPartner.visibility = View.VISIBLE
                tvPartnerName.visibility = View.VISIBLE
                tvPartnerName.text = item.sender_nickname
                tvPartnerMessage.text = item.content
                tvPartnerTime.text = item.created_at
                tvPartnerUnread.visibility = if (item.unread_count > 0) View.VISIBLE else View.GONE
                tvPartnerUnread.text = item.unread_count.toString()
            }
        }
    }
    override fun getItemCount() = items.size
}

class ParticipantAdapter(private val items: List<ParticipantDto>, private val onKickClick: (ParticipantDto) -> Unit) : RecyclerView.Adapter<ParticipantAdapter.ViewHolder>() {
    class ViewHolder(val binding: ItemGroupParticipantBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemGroupParticipantBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvNickname.text = if (item.is_me) "${item.nickname} (나)" else item.nickname
            tvAdminBadge.visibility = if (item.is_creator) View.VISIBLE else View.GONE
            btnVoteKick.visibility = if (!item.is_creator && !item.is_me) View.VISIBLE else View.GONE
            btnVoteKick.text = "강퇴 (${item.votes}/${item.threshold})"
            btnVoteKick.setOnClickListener { onKickClick(item) }
        }
    }
    override fun getItemCount() = items.size
}
