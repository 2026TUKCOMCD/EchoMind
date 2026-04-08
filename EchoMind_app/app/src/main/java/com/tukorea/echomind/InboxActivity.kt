package com.tukorea.echomind

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.tukorea.echomind.databinding.ActivityInboxBinding
import com.tukorea.echomind.databinding.ItemFriendMatchBinding
import com.tukorea.echomind.databinding.ItemInboxRequestBinding
import com.tukorea.echomind.databinding.ItemSentRequestBinding
import com.tukorea.echomind.models.*
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.ResponseBody
import org.jsoup.Jsoup
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import kotlin.random.Random

// [서버 match_manager.py와 100% 동기화된 인터페이스]
interface InboxService {
    @GET("inbox")
    suspend fun getInboxHtml(@Query("t") timestamp: Long): Response<String>
    
    @GET("respond_match/{id}/{act}")
    suspend fun respondMatch(@Path("id") id: Int, @Path("act") act: String): Response<ResponseBody>

    @POST("unmatch/request/{id}")
    suspend fun requestUnmatch(@Path("id") id: Int): Response<ResponseBody>

    @GET("unmatch/respond/{id}/{action}")
    suspend fun respondUnmatch(@Path("id") id: Int, @Path("action") action: String): Response<ResponseBody>

    @POST("unmatch/withdraw/{id}")
    suspend fun withdrawUnmatch(@Path("id") id: Int): Response<ResponseBody>

    @POST("cancel_match_request/{id}")
    suspend fun cancelMatchRequest(@Path("id") id: Int): Response<ResponseBody>
}

class InboxActivity : AppCompatActivity() {

    private lateinit var binding: ActivityInboxBinding
    private val inboxService by lazy { 
        GlobalClient.retrofit.create(InboxService::class.java) 
    }
    
    private lateinit var receivedAdapter: InboxRequestAdapter
    private lateinit var friendsAdapter: FriendsDashboardAdapter
    private lateinit var alertsAdapter: AlertsAdapter
    private lateinit var sentAdapter: SentRequestsAdapter

    private var pollingJob: Job? = null

    private val tips = listOf(
        "최근의 나를 더 잘 설명하고 싶다면? 새로운 대화 로그로 다시 분석해 보세요.",
        "어제와 오늘의 나는 다를 수 있습니다. 정기적인 업데이트가 정확한 매칭의 비결입니다.",
        "매칭 점수 90% 이상의 유저를 발견하셨나요? 망설이지 말고 신청을 보내보세요!",
        "나와는 정반대인 '성격 보완형' 파트너도 찾아보세요.",
        "프로필 분석 시 대화량이 많을수록 매칭 정확도가 한층 더 정교해집니다!"
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityInboxBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupUI()
        showRandomTip()
        fetchInitialData()
    }

    private fun setupUI() {
        binding.btnBack.setOnClickListener { finish() }
        
        binding.rvReceivedRequests.layoutManager = LinearLayoutManager(this)
        binding.rvMatches.layoutManager = LinearLayoutManager(this)
        binding.rvAlerts.layoutManager = LinearLayoutManager(this)
        binding.rvSentRequests.layoutManager = LinearLayoutManager(this)

        receivedAdapter = InboxRequestAdapter(mutableListOf()) { id, act -> 
            handleServerAction("처리") { inboxService.respondMatch(id, act.lowercase()) } 
        }

        friendsAdapter = FriendsDashboardAdapter(mutableListOf(), 
            onChat = { friend -> openChat(friend.matchCode, friend.name) },
            onViewDetail = { friend -> openMatchDetail(friend.requestId) },
            onUnmatchRequest = { friend -> handleServerAction("취소 요청") { inboxService.requestUnmatch(friend.requestId) } },
            onUnmatchRespond = { id, act -> 
                val label = if (act == "accept") "수락" else "거절"
                handleServerAction("$label 완료") { inboxService.respondUnmatch(id, act) } 
            },
            onWithdrawUnmatch = { friend -> handleServerAction("요청 철회") { inboxService.withdrawUnmatch(friend.requestId) } }
        )

        alertsAdapter = AlertsAdapter(mutableListOf())
        sentAdapter = SentRequestsAdapter(mutableListOf()) { id -> 
            handleServerAction("신청 취소") { inboxService.cancelMatchRequest(id) }
        }

        binding.rvReceivedRequests.adapter = receivedAdapter
        binding.rvMatches.adapter = friendsAdapter
        binding.rvAlerts.adapter = alertsAdapter
        binding.rvSentRequests.adapter = sentAdapter
    }

    private fun openChat(code: String, name: String) {
        val intent = Intent(this, ChatActivity::class.java).apply {
            putExtra("matchCode", code)
            putExtra("partnerName", name)
        }
        startActivity(intent)
    }

    private fun openMatchDetail(requestId: Int) {
        val intent = Intent(this, MatchDetailActivity::class.java).apply {
            putExtra("requestId", requestId)
        }
        startActivity(intent)
    }

    private fun showRandomTip() {
        binding.tvRandomTip.text = tips[Random.nextInt(tips.size)]
    }

    private fun handleServerAction(message: String, call: suspend () -> Response<ResponseBody>) {
        lifecycleScope.launch {
            try {
                val response = call()
                if (response.isSuccessful) {
                    Toast.makeText(this@InboxActivity, message, Toast.LENGTH_SHORT).show()
                    updateInbox()
                    delay(1000)
                    updateInbox() 
                } else {
                    Log.e("InboxAction", "실패 코드: ${response.code()}")
                    Toast.makeText(this@InboxActivity, "오류 발생 (${response.code()})", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Log.e("InboxAction", "네트워크 오류", e)
                Toast.makeText(this@InboxActivity, "서버 연결 실패", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun fetchInitialData() {
        lifecycleScope.launch {
            binding.progressBar.visibility = View.VISIBLE
            updateInbox()
            binding.progressBar.visibility = View.GONE
            startPolling()
        }
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = lifecycleScope.launch {
            while (isActive) {
                delay(10000)
                updateInbox()
            }
        }
    }

    private suspend fun updateInbox() {
        try {
            val response = inboxService.getInboxHtml(System.currentTimeMillis())
            if (response.isSuccessful) {
                val html = response.body() ?: ""
                parseHtml(html)
            }
        } catch (e: Exception) { Log.e("InboxSync", "Error", e) }
    }

    private fun parseHtml(html: String) {
        val doc = Jsoup.parse(html)
        val friends = mutableListOf<FriendMatchModel>()
        
        doc.select("section:contains(성사된 매칭) div.bg-white, section:contains(성사된 매칭) div.glass-panel").forEach { card ->
            val name = card.select("h4").text().trim()
            if (name.isEmpty()) return@forEach

            val chatBtn = card.select("a[href*=/chat/]").first() ?: return@forEach
            val matchCode = chatBtn.attr("href").split("/").lastOrNull() ?: ""
            
            val respondLink = card.select("a[href*=/unmatch/respond/]").first()
            var requestId = respondLink?.attr("href")?.split("/")?.find { it.toIntOrNull() != null }?.toIntOrNull() ?: 0
            
            if (requestId == 0) {
                requestId = card.select("a[href*=/match/detail/], form[action*=/unmatch/request/]").map { 
                    val path = if (it.tagName() == "form") it.attr("action") else it.attr("href")
                    path.split("/").find { part -> part.toIntOrNull() != null }?.toIntOrNull() ?: 0
                }.firstOrNull { it != 0 } ?: 0
            }
            
            if (matchCode.isNotEmpty()) {
                val lastMsg = card.select("[id^=last-msg-]").text().trim()
                val unreadCount = card.select("[id^=unread-badge-]").text().trim().toIntOrNull() ?: 0
                val statusText = card.text()
                
                val hasAcceptBtn = card.select("a[href*=/unmatch/respond/][href*=/accept]").isNotEmpty()
                val hasWithdrawBtn = card.select("form[action*=/unmatch/withdraw/]").isNotEmpty()
                
                val unmatchRequester = when {
                    hasAcceptBtn -> "PARTNER"
                    hasWithdrawBtn || statusText.contains("수락을 기다리고") -> "ME"
                    else -> "NONE"
                }
                
                friends.add(FriendMatchModel(requestId, matchCode, name, lastMsg, unmatchRequester, unreadCount))
            }
        }
        friendsAdapter.updateData(friends)

        // 받은 매칭 신청 파싱 강화
        val received = mutableListOf<MatchRequestDtoInternal>()
        doc.select("section:contains(받은 매칭 신청) div.group").forEach { card ->
            val name = card.select("h3").text().trim()
            val score = card.select("span.text-xl").text().trim().replace("%", "")
            val mbti = card.select("span.bg-indigo-50").text().trim()
            val summary = card.select("p.text-sm").text().trim().removePrefix("\"").removeSuffix("\"")
            val id = card.select("a[href*=/respond_match/][href*=/accepted]").attr("href").split("/").find { it.toIntOrNull() != null }?.toIntOrNull() ?: 0
            
            if (id != 0 && name.isNotEmpty()) {
                received.add(MatchRequestDtoInternal(id, name, score, mbti, summary))
            }
        }
        receivedAdapter.updateData(received)
        binding.tvReceivedCount.text = received.size.toString()

        val sentList = mutableListOf<SentMatchRequestDtoInternal>()
        doc.select("section:contains(보낸 신청 현황) div.bg-white").forEach { card ->
            val nameText = card.select("p.text-sm.font-bold").text().replace("님에게", "").trim()
            val id = card.select("form").attr("action").split("/").find { it.toIntOrNull() != null }?.toIntOrNull() ?: 0
            if (nameText.isNotBlank()) sentList.add(SentMatchRequestDtoInternal(id, nameText, "대기중"))
        }
        sentAdapter.updateData(sentList)

        val alerts = mutableListOf<String>()
        doc.select("section:contains(시스템 알림) .pl-5").forEach { el -> alerts.add(el.select("p").text()) }
        alertsAdapter.updateData(alerts)
    }

    override fun onDestroy() { super.onDestroy(); pollingJob?.cancel() }
}

// --- 어댑터 및 내부 모델 ---

data class FriendMatchModel(val requestId: Int, val matchCode: String, val name: String, val lastMessage: String, val unmatchRequester: String, val unreadCount: Int)
data class MatchRequestDtoInternal(val requestId: Int, val senderName: String, val matchScore: String = "", val mbti: String = "", val summary: String = "")
data class SentMatchRequestDtoInternal(val requestId: Int, val receiverName: String, val status: String)

class InboxRequestAdapter(private var items: MutableList<MatchRequestDtoInternal>, private val onAction: (Int, String) -> Unit) : RecyclerView.Adapter<InboxRequestAdapter.ViewHolder>() {
    fun updateData(newItems: List<MatchRequestDtoInternal>) { items.clear(); items.addAll(newItems); notifyDataSetChanged() }
    class ViewHolder(val binding: ItemInboxRequestBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemInboxRequestBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvSenderName.text = item.senderName
            tvMatchScore.text = "${item.matchScore}점"
            tvSenderInfo.text = if (item.mbti.isNotEmpty()) item.mbti else "MBTI · 소시오닉스"
            tvSummary.text = if (item.summary.isNotEmpty()) item.summary else "상대방의 성향 요약 내용이 여기에 표시됩니다."
            
            btnAccept.setOnClickListener { onAction(item.requestId, "ACCEPTED") }
            btnReject.setOnClickListener { onAction(item.requestId, "REJECTED") }
        }
    }
    override fun getItemCount() = items.size
}

class FriendsDashboardAdapter(private var items: MutableList<FriendMatchModel>, val onChat: (FriendMatchModel) -> Unit, val onViewDetail: (FriendMatchModel) -> Unit, val onUnmatchRequest: (FriendMatchModel) -> Unit, val onUnmatchRespond: (Int, String) -> Unit, val onWithdrawUnmatch: (FriendMatchModel) -> Unit) : RecyclerView.Adapter<FriendsDashboardAdapter.ViewHolder>() {
    fun updateData(newItems: List<FriendMatchModel>) { items.clear(); items.addAll(newItems); notifyDataSetChanged() }
    class ViewHolder(val binding: ItemFriendMatchBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemFriendMatchBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvFriendName.text = item.name
            tvProfileInitial.text = item.name.firstOrNull()?.toString() ?: ""
            tvLastMessage.text = item.lastMessage.ifBlank { "대화를 시작해보세요." }
            tvUnreadBadge.visibility = if (item.unreadCount > 0) View.VISIBLE else View.GONE
            tvUnreadBadge.text = item.unreadCount.toString()
            
            btnViewDetail.setOnClickListener { onViewDetail(item) }
            btnChat.setOnClickListener { onChat(item) }
            btnRequestUnmatch.setOnClickListener { onUnmatchRequest(item) }
            btnWithdrawUnmatch.setOnClickListener { onWithdrawUnmatch(item) }
            
            btnUnmatchAccept.setOnClickListener { onUnmatchRespond(item.requestId, "accept") }
            btnUnmatchReject.setOnClickListener { onUnmatchRespond(item.requestId, "reject") }

            layoutMyUnmatchRequest.visibility = if (item.unmatchRequester == "ME") View.VISIBLE else View.GONE
            layoutPartnerUnmatchRequest.visibility = if (item.unmatchRequester == "PARTNER") View.VISIBLE else View.GONE
            btnRequestUnmatch.visibility = if (item.unmatchRequester == "NONE") View.VISIBLE else View.GONE
        }
    }
    override fun getItemCount() = items.size
}

class AlertsAdapter(private var items: MutableList<String>) : RecyclerView.Adapter<AlertsAdapter.ViewHolder>() {
    fun updateData(newItems: List<String>) { items.clear(); items.addAll(newItems); notifyDataSetChanged() }
    class ViewHolder(val view: TextView) : RecyclerView.ViewHolder(view)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(TextView(parent.context).apply { setPadding(16, 8, 16, 8); setTextColor(Color.WHITE); textSize = 13f })
    override fun onBindViewHolder(holder: ViewHolder, position: Int) { holder.view.text = "• ${items[position]}" }
    override fun getItemCount() = items.size
}

class SentRequestsAdapter(private var items: MutableList<SentMatchRequestDtoInternal>, private val onCancel: (Int) -> Unit) : RecyclerView.Adapter<SentRequestsAdapter.ViewHolder>() {
    fun updateData(newItems: List<SentMatchRequestDtoInternal>) { items.clear(); items.addAll(newItems); notifyDataSetChanged() }
    class ViewHolder(val binding: ItemSentRequestBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemSentRequestBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.tvReceiverName.text = item.receiverName
        holder.binding.tvStatusBadge.text = item.status
        holder.binding.btnCancelRequest.setOnClickListener { onCancel(item.requestId) }
    }
    override fun getItemCount() = items.size
}
