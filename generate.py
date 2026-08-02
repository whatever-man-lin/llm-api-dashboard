#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零 token 版：每月生成 data.json，全程不调用任何 LLM。

设计原则（对应"零运行成本"诉求）：
  - 对各平台免费政策的「理解」在构建时一次性写进 PLATFORMS 静态配置（人工/一次性成本，非 recurring）。
  - 运行时只做机械比对：抓社区每日更新的免费模型清单 + OpenRouter 公开接口（均无需鉴权），
    统计各 provider 当前免费模型数，与上月快照 diff，标记 change 与 alerts。
  - 任一数据源抓取失败都自动降级为纯静态（不崩溃、不花 token）。

数据源：
  1) ClawLabsAI/free-ai-models  ->  data/models.json （社区每日 GitHub Actions 更新）
  2) OpenRouter /api/v1/models  ->  筛选 :free 模型（官方公开接口，无需 key）
"""
import os
import json
import datetime
import urllib.request

# ---------------------------------------------------------------------------
# 1) 静态配置：人类对免费政策的理解，构建时一次性写入，运行时零 token
#    provider_keys 用于把本平台映射到 live 免费清单里的 provider 名称（小写），
#    留空表示该平台不在公开免费清单覆盖范围内，change 恒为「无变化」。
# ---------------------------------------------------------------------------
PLATFORMS = [
    {"name": "智谱AI", "region": "cn", "free": "新户2000万tokens；GLM-4-Flash永久免费", "models": "GLM-5.1/4-Flash", "base_url": "https://open.bigmodel.cn/api/paas/v4", "note": "代码强", "provider_keys": []},
    {"name": "硅基流动", "region": "cn", "free": "2000万+任务1000万，1000 RPM", "models": "DeepSeek-V3/R1,Qwen3", "base_url": "https://api.siliconflow.cn/v1", "note": "限速慷慨", "provider_keys": []},
    {"name": "火山引擎豆包", "region": "cn", "free": "每日200万刷新", "models": "Doubao-Seed", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "note": "延迟低", "provider_keys": []},
    {"name": "阿里云百炼", "region": "cn", "free": "每模型100万/90天", "models": "Qwen3,DeepSeek", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "note": "需实名", "provider_keys": []},
    {"name": "魔搭ModelScope", "region": "cn", "free": "每日2000次", "models": "Qwen,GLM,Llama", "base_url": "https://api-inference.modelscope.cn/v1", "note": "需绑阿里云+实名", "provider_keys": []},
    {"name": "Kimi月之暗面", "region": "cn", "free": "约800万tokens", "models": "Kimi-K2.5(262k)", "base_url": "https://api.moonshot.cn/v1", "note": "长文本强,并发3", "provider_keys": []},
    {"name": "腾讯混元", "region": "cn", "free": "100万tokens/年+图像视频3D额度", "models": "Hunyuan", "base_url": "https://console.cloud.tencent.com/tokenhub/", "note": "腾讯生态", "provider_keys": []},
    {"name": "讯飞星火", "region": "cn", "free": "每模型20万永久", "models": "Qwen,DeepSeek-OCR", "base_url": "https://maas.xfyun.cn", "note": "语音强", "provider_keys": []},
    {"name": "百度千帆", "region": "cn", "free": "ERNIE-Speed/Lite永久免费不限量", "models": "ERNIE-4.5", "base_url": "https://aip.baidubce.com/", "note": "限速", "provider_keys": []},
    {"name": "AtomGit AI", "region": "cn", "free": "1000万永久+月1000核时", "models": "Qwen3.5,Llama", "base_url": "https://ai.atomgit.com/v1", "note": "开放原子旗下", "provider_keys": []},
    {"name": "OpenRouter", "region": "overseas", "free": "每日50次免费(:free模型)", "models": "聚合29+", "base_url": "https://openrouter.ai/api/v1", "note": "免信用卡,自动轮询", "provider_keys": ["openrouter"]},
    {"name": "Gemini AI Studio", "region": "overseas", "free": "Flash免费层", "models": "Gemini 2.5 Flash", "base_url": "ai.google.dev", "note": "需Google账号", "provider_keys": ["google"]},
    {"name": "Groq", "region": "overseas", "free": "免费层", "models": "Llama,Mixtral", "base_url": "https://api.groq.com", "note": "极快,免信用卡", "provider_keys": ["groq"]},
    {"name": "NVIDIA NIM", "region": "overseas", "free": "新户1000credits+免费无限", "models": "Kimi,Llama,DeepSeek", "base_url": "https://build.nvidia.com", "note": "国内可直连", "provider_keys": ["nvidia"]},
    {"name": "Mistral", "region": "overseas", "free": "永久tier 6RPM", "models": "Mistral", "base_url": "https://api.mistral.ai/v1", "note": "限速严", "provider_keys": ["mistral"]},
    {"name": "GitHub Models", "region": "overseas", "free": "GitHub账号直用", "models": "Llama,GLM", "base_url": "github.com", "note": "IDE测试", "provider_keys": []},
    {"name": "Cloudflare Workers AI", "region": "overseas", "free": "每日1万次", "models": "多开源", "base_url": "https://api.cloudflare.com", "note": "边缘部署", "provider_keys": []},
    {"name": "LLM7.io", "region": "overseas", "free": "免费GPT-4o-mini", "models": "GPT-4o-mini,DeepSeek", "base_url": "https://api.llm7.io/v1", "note": "第三方,稳定性不保证", "provider_keys": []},
]

# 免费政策特别提醒（静态基线，由人工理解一次性写入；运行时零 token）
STATIC_ALERTS = [
    "智谱 GLM-4-Flash 永久免费无限制",
    "硅基流动 1000 RPM 限速最慷慨（新户 2000万 + 任务 1000万 tokens）",
    "火山引擎豆包 每日刷新 200万 tokens",
    "百度千帆 ERNIE-Speed/Lite 永久免费不限量（限速）",
    "AtomGit 1000万永久 tokens + 每月 1000 核时免费算力",
    "NVIDIA NIM 国内可直连，免费模型无限调用（限速）",
]

# 值得额外提示的新兴免费 provider（不在 18 家配置内时，若出现在 live 清单则报警）
INTERESTING_UNKNOWN = {"openai", "meta", "deepseek", "qwen", "anthropic", "cohere", "poolside", "pollinations ai"}

FREE_MODELS_URL = "https://raw.githubusercontent.com/ClawLabsAI/free-ai-models/main/data/models.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/models"
SNAPSHOT_FILE = "live_snapshot.json"


def fetch_json(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "llm-policy-dashboard/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("  [warn] fetch failed:", url, "->", e)
        return None


def collect_live_free():
    """返回 {provider_lower: 当前免费模型数}。来源：社区清单 + OpenRouter :free。"""
    counts = {}
    # 来源 1：社区每日更新的免费模型清单
    data = fetch_json(FREE_MODELS_URL)
    if isinstance(data, list):
        models = data
    elif isinstance(data, dict):
        models = data.get("models", [])
    else:
        models = []
    for m in models:
        prov = (m.get("provider") if isinstance(m, dict) else "").strip().lower()
        if prov:
            counts[prov] = counts.get(prov, 0) + 1
    # 来源 2：OpenRouter 公开接口，筛选 :free 模型
    or_data = fetch_json(OPENROUTER_URL)
    if isinstance(or_data, dict):
        for m in or_data.get("data", []):
            pid = m.get("id", "")
            if ":free" in pid:
                prov = pid.split("/")[0].lower()
                counts[prov] = counts.get(prov, 0) + 1
    return counts


def load_prev_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            return json.load(open(SNAPSHOT_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def main():
    today = datetime.date.today().isoformat()
    live = collect_live_free()
    prev = load_prev_snapshot()

    # 当前各平台 live 免费模型数
    cur_counts = {}
    for p in PLATFORMS:
        keys = [k.lower() for k in p.get("provider_keys", [])]
        cur_counts[p["name"]] = sum(live.get(k, 0) for k in keys) if keys else None

    dynamic_alerts = []
    platforms_out = []
    for p in PLATFORMS:
        cur = cur_counts[p["name"]]
        change = "无变化"
        if cur is not None:
            old = prev.get(p["name"])
            if old is None:
                change = "无变化"  # 首次运行，不误报
            elif cur > old:
                change = "放宽"
                dynamic_alerts.append(f"{p['name']} 免费模型数由 {old} 增至 {cur}（放宽）")
            elif cur < old:
                change = "收紧"
                dynamic_alerts.append(f"{p['name']} 免费模型数由 {old} 减至 {cur}（收紧）")

        out = {k: p[k] for k in ("name", "region", "free", "models", "base_url", "note")}
        if cur:
            out["free"] = f'{out["free"]}（live 免费模型 {cur} 个）'
        out["change"] = change
        platforms_out.append(out)

    # 新兴免费 provider 提示（不在 18 家配置内）
    known = {k.lower() for p in PLATFORMS for k in p.get("provider_keys", [])}
    for prov, cnt in live.items():
        if prov not in known and prov in INTERESTING_UNKNOWN and cnt >= 1:
            dynamic_alerts.append(f"发现新兴免费 provider：{prov}（{cnt} 个免费模型，建议人工核验）")

    # 动态变动提示 + 静态免费政策基线（精选免费档始终展示）
    alerts = dynamic_alerts + list(STATIC_ALERTS)

    out_data = {
        "updated": today,
        "alerts": alerts,
        "platforms": platforms_out,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    # 写入快照供下月 diff（不展示，仅内部用）
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(cur_counts, f, ensure_ascii=False, indent=2)

    print(f"data.json 已生成（零 token），更新日期 {today}，live providers 覆盖 {len(live)} 个")


if __name__ == "__main__":
    main()
