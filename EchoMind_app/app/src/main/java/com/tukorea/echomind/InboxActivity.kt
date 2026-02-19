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
import com.tukorea.echomind.data.api.*
import com.tukorea.echomind.databinding.ActivityInboxBinding
import com.tukorea.echomind.databinding.ItemFriendMatchBinding
import com.tukorea.echomind.databinding.ItemInboxRequestBinding
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.jsoup.Jsoup

class InboxActivity : AppCompatActivity() {

    private lateinit var binding: ActivityInboxBinding
    private val matchService = ApiClient.matchService
    
    private lateinit var alertsAdapter: AlertsAdapter
    private lateinit var receivedAdapter: InboxRequestAdapter
    private lateinit var friendsAdapter: FriendsDashboardAdapter
    private lateinit var sentAdapter: SentRequestsAdapter

    private var pollingJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityInboxBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupUI()
        
        lifecycleScope.launch {
            fetchInboxData(showProgress = true)
        }
    }

    override fun onStart() {
        super.onStart()
        startPollingInbox()
    }

    override fun onStop() {
        super.onStop()
        pollingJob?.cancel()
    }

    private fun setupUI() {
        binding.toolbar.setNavigationOnClickListener { finish() }
        
        alertsAdapter = AlertsAdapter(mutableListOf())
        receivedAdapter = InboxRequestAdapter(mutableListOf()) { id, act -> respondToMatch(id, act) }
        friendsAdapter = FriendsDashboardAdapter(mutableListOf(), 
            onChat = { friend -> openChat(friend.requestId, friend.name) },
            onUnmatchRequest = { friend -> requestUnmatch(friend.requestId) },
            onUnmatchRespond = { id, act -> respondToUnmatch(id, act) },
            onWithdrawUnmatch = { friend -> withdrawUnmatch(friend.requestId) }
        )
        sentAdapter = SentRequestsAdapter(mutableListOf())

        binding.rvAlerts.adapter = alertsAdapter
        binding.rvReceivedRequests.adapter = receivedAdapter
        binding.rvMatches.adapter = friendsAdapter
        binding.rvSentRequests.adapter = sentAdapter

        binding.rvAlerts.layoutManager = LinearLayoutManager(this)
        binding.rvReceivedRequests.layoutManager = LinearLayoutManager(this)
        binding.rvMatches.layoutManager = LinearLayoutManager(this)
        binding.rvSentRequests.layoutManager = LinearLayoutManager(this)
    }

    private fun startPollingInbox() {
        pollingJob?.cancel()
        pollingJob = lifecycleScope.launch {
            while (isActive) {
                fetchInboxData(showProgress = false)
                delay(3000)
            }
        }
    }

    private suspend fun fetchInboxData(showProgress: Boolean) {
        if (showProgress) binding.progressBar.visibility = View.VISIBLE
        try {
            val response = matchService.getInboxHtml()
            if (response.isSuccessful) {
                val html = response.body() ?: ""
                parseHtmlAndUpdateUI(html)
            }
        } catch (e: Exception) {
            Log.e("InboxPolling", "Fetch failed: ${e.message}")
        } finally {
            if (showProgress) binding.progressBar.visibility = View.GONE
        }
    }

    private fun parseHtmlAndUpdateUI(html: String) {
        val doc = Jsoup.parse(html)
        
        val received = mutableListOf<MatchRequestDto>()
        doc.select("section:has(h2:contains(받은 매칭 신청)) .group").forEach { el ->
            val name = el.select("h3").text()
            if (name.isNotBlank()) {
                val respondUrl = el.select("a:contains(매칭 수락)").attr("href")
                val actualId = respondUrl.split("/").getOrNull(2)?.toIntOrNull() ?: 0
                
                received.add(MatchRequestDto(actualId, 0, name, name, el.select(".uppercase").text(), el.select(".italic").text(), 0, "PENDING", ""))
            }
        }
        receivedAdapter.updateData(received)

        val friends = mutableListOf<FriendMatchModel>()
        doc.select("section:has(h2:contains(성사된 매칭)) .bg-white").forEach { el ->
            val name = el.select("h4").text()
            if (name.isNotBlank()) {
                val statusText = el.select(".rounded").text()
                val hasUnmatchRequest = el.select(".bg-red-50").isNotEmpty()
                val unreadCount = el.select(".bg-red-600").text().trim().toIntOrNull() ?: 0
                
                // ID 추출 로직 강화: 채팅 또는 보기 링크에서 추출
                val linkElement = el.select("a:contains(채팅), a:contains(보기)").first()
                val requestId = linkElement?.attr("href")?.split("/")?.lastOrNull()?.toIntOrNull() ?: 0

                friends.add(FriendMatchModel(requestId, name, el.select("p.text-xs").text(), 
                    if (hasUnmatchRequest) "PARTNER" else if (statusText.contains("취소 대기")) "ME" else "NONE",
                    unreadCount))
            }
        }
        friendsAdapter.updateData(friends)

        val alerts = mutableListOf<NotificationDto>()
        doc.select("section:contains(시스템 알림) .pl-5").forEach { el ->
            alerts.add(NotificationDto(0, el.select("p").text(), false, el.select("span").text()))
        }
        alertsAdapter.updateData(alerts)
    }

    private fun openChat(id: Int, name: String) {
        if (id == 0) return
        val intent = Intent(this, ChatActivity::class.java)
        intent.putExtra("requestId", id)
        intent.putExtra("partnerName", name)
        startActivity(intent)
    }

    private fun respondToMatch(id: Int, action: String) {
        if (id == 0) return
        lifecycleScope.launch {
            try {
                val res = matchService.respondMatch(id, action.lowercase())
                if (res.isSuccessful) {
                    Toast.makeText(this@InboxActivity, "처리되었습니다.", Toast.LENGTH_SHORT).show()
                    fetchInboxData(true)
                }
            } catch (e: Exception) {
                Toast.makeText(this@InboxActivity, "연결 오류가 발생했습니다.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun requestUnmatch(id: Int) {
        if (id == 0) {
            Toast.makeText(this, "요청 ID를 찾을 수 없습니다.", Toast.LENGTH_SHORT).show()
            return
        }
        lifecycleScope.launch {
            try {
                val res = matchService.requestUnmatch(id)
                if (res.isSuccessful) {
                    Toast.makeText(this@InboxActivity, "취소 요청을 보냈습니다.", Toast.LENGTH_SHORT).show()
                    fetchInboxData(true)
                }
            } catch (e: Exception) {
                Toast.makeText(this@InboxActivity, "요청 실패: 네트워크 상태를 확인하세요.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun respondToUnmatch(id: Int, action: String) {
        if (id == 0) return
        lifecycleScope.launch {
            try {
                val res = matchService.respondUnmatch(id, action)
                if (res.isSuccessful) fetchInboxData(true)
            } catch (e: Exception) {
                Toast.makeText(this@InboxActivity, "연결 실패", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun withdrawUnmatch(id: Int) {
        if (id == 0) return
        lifecycleScope.launch {
            try {
                val response = matchService.respondUnmatch(id, "REJECT")
                if (response.isSuccessful) {
                    Toast.makeText(this@InboxActivity, "요청이 철회되었습니다.", Toast.LENGTH_SHORT).show()
                    fetchInboxData(true)
                }
            } catch (e: Exception) {
                Toast.makeText(this@InboxActivity, "철회 실패", Toast.LENGTH_SHORT).show()
            }
        }
    }
}

data class FriendMatchModel(
    val requestId: Int,
    val name: String,
    val lastMessage: String,
    val unmatchRequester: String,
    val unreadCount: Int
)

class AlertsAdapter(private var items: MutableList<NotificationDto>) : RecyclerView.Adapter<AlertsAdapter.ViewHolder>() {
    fun updateData(newItems: List<NotificationDto>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }
    class ViewHolder(val view: TextView) : RecyclerView.ViewHolder(view)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(TextView(parent.context).apply {
        setPadding(16, 8, 16, 8)
        setTextColor(Color.WHITE)
        textSize = 13f
    })
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.view.text = "• ${items[position].message}"
    }
    override fun getItemCount() = items.size
}

class InboxRequestAdapter(private var items: MutableList<MatchRequestDto>, private val onAction: (Int, String) -> Unit) : RecyclerView.Adapter<InboxRequestAdapter.ViewHolder>() {
    fun updateData(newItems: List<MatchRequestDto>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }
    class ViewHolder(val binding: ItemInboxRequestBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemInboxRequestBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvSenderName.text = item.senderName
            tvMatchScore.text = "${item.matchScore}%"
            tvSummary.text = item.senderSummary
            btnAccept.setOnClickListener { onAction(item.requestId, "ACCEPTED") }
            btnReject.setOnClickListener { onAction(item.requestId, "REJECTED") }
        }
    }
    override fun getItemCount() = items.size
}

class FriendsDashboardAdapter(
    private var items: MutableList<FriendMatchModel>,
    private val onChat: (FriendMatchModel) -> Unit,
    private val onUnmatchRequest: (FriendMatchModel) -> Unit,
    private val onUnmatchRespond: (Int, String) -> Unit,
    private val onWithdrawUnmatch: (FriendMatchModel) -> Unit
) : RecyclerView.Adapter<FriendsDashboardAdapter.ViewHolder>() {
    fun updateData(newItems: List<FriendMatchModel>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }
    class ViewHolder(val binding: ItemFriendMatchBinding) : RecyclerView.ViewHolder(binding.root)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(ItemFriendMatchBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvFriendName.text = item.name
            tvLastMessage.text = item.lastMessage
            if (item.unreadCount > 0) {
                tvUnreadBadge.visibility = View.VISIBLE
                tvUnreadBadge.text = item.unreadCount.toString()
            } else {
                tvUnreadBadge.visibility = View.GONE
            }
            when (item.unmatchRequester) {
                "PARTNER" -> {
                    layoutPartnerUnmatchRequest.visibility = View.VISIBLE
                    layoutMyUnmatchRequest.visibility = View.GONE
                    btnRequestUnmatch.visibility = View.GONE
                    btnUnmatchAccept.setOnClickListener { onUnmatchRespond(item.requestId, "accept") }
                    btnUnmatchReject.setOnClickListener { onUnmatchRespond(item.requestId, "reject") }
                }
                "ME" -> {
                    layoutPartnerUnmatchRequest.visibility = View.GONE
                    layoutMyUnmatchRequest.visibility = View.VISIBLE
                    btnRequestUnmatch.visibility = View.GONE
                    btnWithdrawUnmatch.setOnClickListener { onWithdrawUnmatch(item) }
                }
                else -> {
                    layoutPartnerUnmatchRequest.visibility = View.GONE
                    layoutMyUnmatchRequest.visibility = View.GONE
                    btnRequestUnmatch.visibility = View.VISIBLE
                    btnRequestUnmatch.setOnClickListener { onUnmatchRequest(item) }
                }
            }
            root.setOnClickListener { onChat(item) }
        }
    }
    override fun getItemCount() = items.size
}

class SentRequestsAdapter(private var items: MutableList<SentMatchRequestDto>) : RecyclerView.Adapter<SentRequestsAdapter.ViewHolder>() {
    fun updateData(newItems: List<SentMatchRequestDto>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }
    class ViewHolder(val view: View) : RecyclerView.ViewHolder(view)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(View(parent.context))
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {}
    override fun getItemCount() = 0
}
