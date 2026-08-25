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
import com.google.android.material.tabs.TabLayout
import com.tukorea.echomind.data.api.BlindMatchSummary
import com.tukorea.echomind.databinding.ActivityBlindInboxBinding
import com.tukorea.echomind.databinding.ItemBlindMatchBinding
import kotlinx.coroutines.*
import java.text.SimpleDateFormat
import java.util.*

class BlindInboxActivity : AppCompatActivity() {
    private lateinit var binding: ActivityBlindInboxBinding
    private val service = GlobalClient.blindMatchService
    private lateinit var adapter: BlindMatchAdapter
    
    private var activeMatches: List<BlindMatchSummary> = emptyList()
    private var completedMatches: List<BlindMatchSummary> = emptyList()
    
    private var pollingJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityBlindInboxBinding.inflate(layoutInflater)
        setContentView(binding.root)
        
        setupUI()
    }

    override fun onResume() {
        super.onResume()
        startPolling()
    }

    override fun onPause() {
        super.onPause()
        stopPolling()
    }

    private fun setupUI() {
        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.btnStart.setOnClickListener { startActivity(Intent(this, BlindMatchActivity::class.java)) }

        adapter = BlindMatchAdapter { match ->
            if (binding.tabLayout.selectedTabPosition == 0) {
                startActivity(Intent(this, BlindChatActivity::class.java).apply {
                    putExtra("matchCode", match.match_code)
                    putExtra("matchId", match.match_id)
                })
            } else {
                if (match.status == "PENDING") {
                    respond(match.match_id, "accept")
                }
            }
        }

        binding.rvMatches.layoutManager = LinearLayoutManager(this)
        binding.rvMatches.adapter = adapter

        binding.tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab?) {
                updateList(tab?.position ?: 0)
            }
            override fun onTabUnselected(tab: TabLayout.Tab?) {}
            override fun onTabReselected(tab: TabLayout.Tab?) {}
        })
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = lifecycleScope.launch {
            while (isActive) {
                loadInbox(showProgress = activeMatches.isEmpty() && completedMatches.isEmpty())
                delay(5000) // 5초마다 실시간 갱신
            }
        }
    }

    private fun stopPolling() {
        pollingJob?.cancel()
    }

    private suspend fun loadInbox(showProgress: Boolean) {
        if (showProgress) binding.progressBar.visibility = View.VISIBLE
        try {
            val response = service.getInbox()
            val data = response.body()?.data
            if (response.isSuccessful && response.body()?.success == true && data != null) {
                activeMatches = data.active
                completedMatches = data.completed
                
                // 탭 텍스트 갱신 (PC 스타일)
                binding.tabLayout.getTabAt(0)?.text = if (activeMatches.isNotEmpty()) "진행중인 대화 (${activeMatches.size})" else "진행중인 대화"
                binding.tabLayout.getTabAt(1)?.text = "완료된 매칭"
                
                updateList(binding.tabLayout.selectedTabPosition)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        } finally {
            if (showProgress) binding.progressBar.visibility = View.GONE
        }
    }

    private fun updateList(tabPosition: Int) {
        val list = if (tabPosition == 0) activeMatches else completedMatches
        adapter.submitList(list)
        binding.tvEmpty.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
    }

    private fun respond(matchId: Int, action: String) {
        lifecycleScope.launch {
            try {
                val response = service.respond(matchId, action)
                Toast.makeText(this@BlindInboxActivity, response.body()?.message ?: "처리되었습니다.", Toast.LENGTH_SHORT).show()
                loadInbox(true)
            } catch (_: Exception) {
                Toast.makeText(this@BlindInboxActivity, "서버 연결 오류", Toast.LENGTH_SHORT).show()
            }
        }
    }
}

class BlindMatchAdapter(private val onItemClick: (BlindMatchSummary) -> Unit) : RecyclerView.Adapter<BlindMatchAdapter.ViewHolder>() {
    private var items: List<BlindMatchSummary> = emptyList()

    fun submitList(newItems: List<BlindMatchSummary>) {
        if (items != newItems) {
            items = newItems
            notifyDataSetChanged()
        }
    }

    class ViewHolder(val binding: ItemBlindMatchBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemBlindMatchBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvPartnerNickname.text = item.partner_nickname
            tvLastMessage.text = item.last_message.ifBlank { "대화를 시작해보세요." }
            
            // [해결] 시간을 PC 버전처럼 KST 포맷으로 변환 (MM-DD HH:mm)
            tvDate.text = formatKstTime(item.updated_at)
            
            if (item.unread_count > 0) {
                tvUnreadBadge.visibility = View.VISIBLE
                tvUnreadBadge.text = item.unread_count.toString()
            } else {
                tvUnreadBadge.visibility = View.GONE
            }

            root.setOnClickListener { onItemClick(item) }
        }
    }

    private fun formatKstTime(rawDate: String?): String {
        if (rawDate.isNullOrBlank()) return ""
        return try {
            // 서버 시간(UTC) -> KST 변환 로직
            val inputFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
                timeZone = TimeZone.getTimeZone("UTC")
            }
            val date = inputFormat.parse(rawDate) ?: return rawDate
            
            val outputFormat = SimpleDateFormat("MM-dd HH:mm", Locale.KOREAN).apply {
                timeZone = TimeZone.getTimeZone("Asia/Seoul")
            }
            outputFormat.format(date)
        } catch (e: Exception) {
            // 변환 실패 시 원본에서 날짜 부분만 추출하여 표시
            rawDate.substringBefore("T").substring(5) + " " + rawDate.substringAfter("T").take(5)
        }
    }

    override fun getItemCount() = items.size
}
