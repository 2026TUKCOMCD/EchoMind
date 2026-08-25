package com.tukorea.echomind

import android.content.res.ColorStateList
import android.graphics.Color
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
import com.tukorea.echomind.data.api.ActivityDto
import com.tukorea.echomind.databinding.ActivityUserActivityBinding
import com.tukorea.echomind.databinding.ItemActivityLogBinding
import kotlinx.coroutines.launch
import org.jsoup.Jsoup
import java.util.*

class UserActivityActivity : AppCompatActivity() {
    private lateinit var binding: ActivityUserActivityBinding
    private val apiService = GlobalClient.apiService
    private lateinit var adapter: ActivityLogAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityUserActivityBinding.inflate(layoutInflater)
        setContentView(binding.root)
        
        setupUI()
        loadActivitiesFromWeb()
    }

    private fun setupUI() {
        binding.toolbar.setNavigationOnClickListener { finish() }
        
        adapter = ActivityLogAdapter()
        binding.rvActivities.layoutManager = LinearLayoutManager(this)
        binding.rvActivities.adapter = adapter

        // 초기 카드 제목 설정 (하단 설명은 XML에서 제거됨)
        binding.cardTotal.tvCardTitle.text = "전체 활동"
        binding.cardLogin.tvCardTitle.text = "로그인 기록"
        binding.cardAnalysis.tvCardTitle.text = "프로필 분석"
        binding.cardMatch.tvCardTitle.text = "매칭 활동"
        binding.cardDays.tvCardTitle.text = "활동 일수"
        binding.cardAverage.tvCardTitle.text = "일평균"
        binding.cardRecent.tvCardTitle.text = "최근 활동"
        binding.cardPeak.tvCardTitle.text = "최다 활동일"
    }

    private fun loadActivitiesFromWeb() {
        binding.progressBar.visibility = View.VISIBLE
        lifecycleScope.launch {
            try {
                // 웹 서비스의 활동 페이지 HTML을 직접 가져와서 파싱
                val response = apiService.getActivityHtml()
                if (response.isSuccessful) {
                    val html = response.body() ?: ""
                    parseAndRender(html)
                } else {
                    showError("활동 내역을 불러오지 못했습니다. 로그인을 확인해주세요.")
                }
            } catch (e: Exception) {
                showError("연결 오류: ${e.message}")
                Log.e("UserActivity", "Parse Error", e)
            } finally {
                binding.progressBar.visibility = View.GONE
            }
        }
    }

    private fun parseAndRender(html: String) {
        val doc = Jsoup.parse(html)
        
        // 1. 8개 요약 카드 데이터 파싱 (웹의 grid 내 카드들 탐색)
        val cards = doc.select("div.grid div.rounded-xl")
        if (cards.size >= 8) {
            binding.cardTotal.tvCardValue.text = cards[0].select("p.text-2xl").text()
            binding.cardLogin.tvCardValue.text = cards[1].select("p.text-2xl").text()
            binding.cardAnalysis.tvCardValue.text = cards[2].select("p.text-2xl").text()
            binding.cardMatch.tvCardValue.text = cards[3].select("p.text-2xl").text()
            binding.cardDays.tvCardValue.text = cards[4].select("p.text-2xl").text()
            binding.cardAverage.tvCardValue.text = cards[5].select("p.text-2xl").text()
            binding.cardRecent.tvCardValue.text = cards[6].select("p.text-2xl").text()
            binding.cardPeak.tvCardValue.text = cards[7].select("p.text-2xl").text()
        }

        // 2. 활동 리스트 파싱
        val activityList = mutableListOf<ActivityDto>()
        
        // 로그인 기록 섹션
        doc.select("h2:contains(로그인 기록) + div li").forEach { li ->
            val msg = li.select("p.font-semibold").text()
            val detail = li.select("p.text-sm").first()?.text()?.trim() ?: ""
            val time = li.select("p.text-sm").last()?.text()?.trim() ?: ""
            
            activityList.add(ActivityDto(type = "login", message = msg, detail = detail, createdAt = time))
        }

        // 분석 기록 섹션
        doc.select("h2:contains(프로필 분석 기록) + div li").forEach { li ->
            val msg = li.select("p.font-semibold").text()
            val detail = li.select("p.text-sm").text().trim()
            
            activityList.add(ActivityDto(type = "analysis", message = msg, detail = detail, createdAt = "분석 완료"))
        }

        if (activityList.isEmpty()) {
            binding.tvEmpty.visibility = View.VISIBLE
            adapter.submitList(emptyList())
        } else {
            binding.tvEmpty.visibility = View.GONE
            adapter.submitList(activityList)
        }
    }

    private fun showError(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }
}

class ActivityLogAdapter : RecyclerView.Adapter<ActivityLogAdapter.ViewHolder>() {
    private var items: List<ActivityDto> = emptyList()

    fun submitList(newItems: List<ActivityDto>) {
        items = newItems
        notifyDataSetChanged()
    }

    class ViewHolder(val binding: ItemActivityLogBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemActivityLogBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        holder.binding.apply {
            tvMessage.text = item.message
            tvDetail.text = item.detail ?: ""
            tvDate.text = item.createdAt

            if (item.type == "login") {
                ivIcon.setImageResource(android.R.drawable.checkbox_on_background)
                ivIcon.imageTintList = ColorStateList.valueOf(Color.parseColor("#4CAF50"))
            } else {
                ivIcon.setImageResource(android.R.drawable.ic_menu_edit)
                ivIcon.imageTintList = ColorStateList.valueOf(Color.parseColor("#6366F1"))
            }
        }
    }

    override fun getItemCount() = items.size
}
