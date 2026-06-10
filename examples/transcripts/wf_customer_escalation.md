# Workflow Transcript: `customer_escalation`

> Captured from a real run of the LangGraph orchestrator.

## User Request

```
客户 C1024 反馈蓝牙耳机左声道没声音，订单 ORD-20260417-001
```

## Plan (LLM-routed)

```json
{
  "thought": "Customer C1024 reports defective earbud (no sound on left channel). Need to RAG-diagnose, cite policy, then decide on ticket.",
  "plan": [
    {"step": 1, "owner": "support_agent:search_kb", "action": "Retrieve troubleshooting + return-policy chunks for 'earbud no left channel'."},
    {"step": 2, "owner": "support_agent:reply",     "action": "Compose empathetic 4-sentence reply with citations."},
    {"step": 3, "owner": "support_agent:decide_ticket", "action": "Open a CRM ticket if escalation is warranted."}
  ]
}
```

## Tool-Call Trace

| step | agent | thought | tool | latency_ms | model |
|------|-------|---------|------|-----------:|-------|
| 1 | router | customer complaint, defective hardware... | - | 2 100 | claude-sonnet-4-6 |
| 2 | dispatch:support_agent:search_kb | "earbud left channel" → faq-06 + warranty | search_kb | 420 | - |
| 3 | dispatch:support_agent:reply | 4-sentence answer with citations | - | 6 580 | claude-sonnet-4-6 |
| 4 | dispatch:support_agent:decide_ticket | action_taken=created_ticket | create_ticket | 9 270 | - |

## Final Answer (excerpt)

**Plan**: 客户 C1024 投诉蓝牙耳机左声道无声，需要先在知识库中检索相关排障指南，再判断是否需要升级为正式工单。

**Results**

- **support_agent:search_kb** → 很抱歉遇到这个问题，您可以先尝试以下故障排查步骤：请长按充电盒按钮 10 秒至红灯闪烁重置配对；如仍异常，请进入手机蓝牙设置删除本机后重新连接。 若以上两步均无法恢复，请提供您的订单号，我们将在保修范围内为您安排进一步处理。
- **support_agent:reply** → 很抱歉给您带来困扰。**Ticket**: `T-20260610-...` (created in CRM mock)

**Citations**

- `troubleshoot/earbuds.md` — 蓝牙耳机左声道没声音：请长按充电盒按钮 10 秒至红灯闪烁重置配对
- `policy/returns.md` — 60 天内质量问题包来回邮退换

## Reproduce

```python
from atlas_mercator.orchestrator.workflows import customer_escalation
state = customer_escalation(customer_id="C1024", message="我的蓝牙耳机左声道没声音了，怎么办？")
print(state["final_answer"])
print("ticket:", state["step_results"][-1].get("parsed", {}).get("ticket_id"))
```
