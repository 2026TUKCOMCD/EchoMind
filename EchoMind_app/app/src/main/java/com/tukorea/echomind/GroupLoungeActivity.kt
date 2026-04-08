package com.tukorea.echomind

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.tukorea.echomind.databinding.ActivityGroupLoungeBinding
import com.tukorea.echomind.databinding.ItemGroupRoomBinding
import com.tukorea.echomind.models.GroupRoom
import kotlinx.coroutines.launch
import okhttp3.ResponseBody
import org.jsoup.Jsoup
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface LoungeApiService {
    @GET("groups")
    suspend fun getGroupLobbyHtml(): Response<String>

    @POST("groups/{roomCode}/join")
    suspend fun joinGroupRoom(@Path("roomCode") roomCode: String): Response<ResponseBody>
}

class GroupLoungeActivity : AppCompatActivity() {

    private lateinit var binding: ActivityGroupLoungeBinding
    private val loungeService: LoungeApiService by lazy {
        com.tukorea.echomind.GlobalClient.retrofit.create(LoungeApiService::class.java)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityGroupLoungeBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupUI()
    }

    override fun onResume() {
        super.onResume()
        loadGroupRooms()
    }

    private fun setupUI() {
        binding.btnBack.setOnClickListener { finish() }
        binding.rvGroupRooms.layoutManager = LinearLayoutManager(this)
        binding.swipeRefresh.setOnRefreshListener { loadGroupRooms() }
        
        binding.btnCreateGroup.setOnClickListener {
            startActivity(Intent(this, GroupCreateActivity::class.java))
        }
    }

    private fun loadGroupRooms() {
        binding.swipeRefresh.isRefreshing = true
        lifecycleScope.launch {
            try {
                val response = loungeService.getGroupLobbyHtml()
                if (response.isSuccessful) {
                    val html = response.body() ?: ""
                    val rooms = parseGroupLobbyHtml(html)
                    
                    binding.rvGroupRooms.adapter = GroupAdapter(rooms) { room: GroupRoom ->
                        if (room.isJoined) {
                            startActivity(Intent(this@GroupLoungeActivity, GroupChatActivity::class.java).apply {
                                putExtra("roomCode", room.roomCode)
                                putExtra("roomName", room.name)
                            })
                        } else if (room.canJoin) {
                            joinGroupRoom(room.roomCode)
                        }
                    }
                }
            } catch (e: Exception) {
                Toast.makeText(this@GroupLoungeActivity, "서버 연결 실패", Toast.LENGTH_SHORT).show()
            } finally {
                binding.swipeRefresh.isRefreshing = false
            }
        }
    }

    private fun parseGroupLobbyHtml(html: String): List<GroupRoom> {
        val doc = Jsoup.parse(html)
        val rooms = mutableListOf<GroupRoom>()
        
        // [정밀 파싱] 웹 서비스의 모든 채팅방 카드 탐색
        doc.select("div.bg-white, div.bg-slate-800").forEachIndexed { index, element ->
            val name = element.select("h2").text().trim()
            if (name.isEmpty()) return@forEachIndexed
            
            // 인원 수 파싱
            val participantsText = element.select("span.shrink-0").text().trim()
            val parts = participantsText.replace("명", "").split("/")
            val current = parts.getOrNull(0)?.trim()?.toIntOrNull() ?: 0
            val max = parts.getOrNull(1)?.trim()?.toIntOrNull() ?: 0
            
            val description = element.select("p.text-sm").first()?.text()?.trim() ?: ""
            
            // 버튼 상태 판별
            val footer = element.select("div.mt-auto")
            val footerText = footer.text()
            
            val isJoined = footerText.contains("입장하기")
            val canJoin = footerText.contains("참여하기")
            
            // [핵심] 참여 불가 사유 추출 (빨간색 텍스트 타겟팅)
            val reason = element.select("p.text-red-500, p.text-red-400").text().trim()
            
            // roomCode 추출
            val roomCode = if (isJoined) {
                footer.select("a").attr("href").split("/").lastOrNull() ?: ""
            } else {
                // /groups/CODE/join 형태의 form action에서 추출
                footer.select("form").attr("action").split("/").getOrNull(2) ?: ""
            }

            // [수정] 방 코드가 없더라도 (참여 불가 방 포함) 목록에 추가
            rooms.add(GroupRoom(index, roomCode, name, description, current, max, isJoined, canJoin, reason.ifBlank { null }))
        }
        return rooms
    }

    private fun joinGroupRoom(roomCode: String) {
        lifecycleScope.launch {
            try {
                val response = loungeService.joinGroupRoom(roomCode)
                if (response.isSuccessful) {
                    Toast.makeText(this@GroupLoungeActivity, "입장 성공!", Toast.LENGTH_SHORT).show()
                    loadGroupRooms()
                }
            } catch (e: Exception) {}
        }
    }
}

class GroupAdapter(
    private val items: List<GroupRoom>,
    private val onItemClick: (GroupRoom) -> Unit
) : RecyclerView.Adapter<GroupAdapter.ViewHolder>() {

    class ViewHolder(val binding: ItemGroupRoomBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        ViewHolder(ItemGroupRoomBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvRoomName.text = item.name
            tvParticipantCount.text = "${item.currentParticipants}/${item.maxParticipants}명"
            tvRoomDescription.text = item.description
            
            if (item.isJoined) {
                btnJoinRoom.text = "입장하기 (참여중)"
                btnJoinRoom.isEnabled = true
                btnJoinRoom.alpha = 1.0f
                tvJoinReason.visibility = View.GONE
            } else if (item.canJoin) {
                btnJoinRoom.text = "조건 일치! 참여하기"
                btnJoinRoom.isEnabled = true
                btnJoinRoom.alpha = 1.0f
                tvJoinReason.visibility = View.GONE
            } else {
                // [해결] 참여 불가 방 표시 및 사유 바인딩
                btnJoinRoom.text = "참여 불가"
                btnJoinRoom.isEnabled = false
                btnJoinRoom.alpha = 0.5f
                tvJoinReason.text = item.reason ?: "입장 조건이 맞지 않습니다."
                tvJoinReason.visibility = View.VISIBLE
            }
            
            root.setOnClickListener { if(item.isJoined || item.canJoin) onItemClick(item) }
            btnJoinRoom.setOnClickListener { if(item.isJoined || item.canJoin) onItemClick(item) }
        }
    }

    override fun getItemCount() = items.size
}
