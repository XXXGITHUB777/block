import requests
import pytz
import re
from datetime import datetime

# ================= 配置区域 =================

# 优先级顺序：排在上面的会覆盖下面的策略
REMOTE_URLS = [
    # 1. 秋风 (主力，质量高)
    "https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/Filters/AWAvenue-Ads-Rule-QuantumultX.list",
    
    # 2. FMZ200 (老牌，补充)
    "https://raw.githubusercontent.com/fmz200/wool_scripts/main/QuantumultX/filter/filter.list",
    
    # 3. Zirawell (补充)
    "https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/All/filter/allAdBlock.list",
    
    # 4. 毒奶 Limbopro (包含 xxxjmp 等特殊规则)
    # 修正：使用官方推荐的直连 Raw 链接，之前的链接可能会导致下载失败
    "https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/Adblock4limbo.list"
]

# 有效的拒绝策略关键词
VALID_POLICIES = {
    "reject", "reject-200", "reject-tinygif", "reject-img", 
    "reject-dict", "reject-array", "reject-video"
}

# ================= 逻辑区域 =================

def fetch_and_merge_rules():
    unique_rules = {} # Key: "TYPE,Target" -> Value: Complete Rule
    source_stats = {} # 统计每个源的贡献
    
    headers = {
        'User-Agent': 'Quantumult X/1.0.30 (iPhone; iOS 16.0; Scale/3.00)',
        'Accept': 'text/plain, text/html'
    }
    
    print(f"--- 开始执行 5.0 合并 (源数量: {len(REMOTE_URLS)}) ---")

    for url in REMOTE_URLS:
        source_name = url.split('/')[-1]
        # 如果是毒奶，特殊标记一下名字以便观察
        if "Adblock4limbo" in url:
            source_name = "Limbopro(毒奶)"
            
        print(f"正在处理: {source_name} ...", end="")
        
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                print(f" [失败] HTTP Code: {resp.status_code}")
                source_stats[source_name] = 0
                continue

            lines = resp.text.splitlines()
            current_source_count = 0
            
            for line in lines:
                line = line.strip()
                
                # 1. 基础清理
                if not line or line.startswith(('#', ';', '//', '[', '<', '!')):
                    continue
                if "//" in line:
                    line = line.split("//")[0].strip()
                    
                # 2. 必须包含逗号
                if ',' not in line:
                    continue
                    
                parts = [p.strip() for p in line.split(',')]
                
                # 3. 智能补全策略
                # 如果规则是 "HOST, ad.com" (长度2)，我们强制认为是 reject
                if len(parts) == 2:
                    parts.append("reject")
                
                if len(parts) < 3:
                    continue

                rule_type = parts[0].upper()
                target = parts[1]
                policy = parts[2].lower() # 策略转小写

                # 4. 类型过滤 (包含 HOST-KEYWORD 以支持 xxxjmp)
                if rule_type not in ["HOST", "HOST-SUFFIX", "HOST-KEYWORD", "IP-CIDR", "IP-CIDR6", "USER-AGENT"]:
                    continue

                # 5. 策略清洗
                # 只要包含 reject 关键字，就认为是有效拒绝策略；否则强制设为 reject
                is_valid_policy = False
                for p in VALID_POLICIES:
                    if p in policy:
                        is_valid_policy = True
                        break
                
                if not is_valid_policy:
                    # 如果大神写了 direct，我们这里强制改成 reject，确保去广告
                    policy = "reject"
                    # 重新构建 parts
                    if len(parts) >= 3:
                        parts[2] = "reject"

                # 6. 生成唯一Key (不区分大小写，防止 Google.com 和 google.com 重复)
                unique_key = f"{rule_type},{target}".lower()

                # 7. 存入字典 (如果 Key 已存在，跳过，因为排在前面的源优先级更高)
                if unique_key not in unique_rules:
                    # 重组为标准格式
                    final_rule = f"{rule_type},{target},{policy}"
                    unique_rules[unique_key] = final_rule
                    current_source_count += 1
            
            source_stats[source_name] = current_source_count
            print(f" [新增 {current_source_count} 条]")
            
        except Exception as e:
            print(f" [出错] {e}")
            source_stats[source_name] = 0

    return list(unique_rules.values()), source_stats

def sort_priority(line):
    line = line.upper()
    if line.startswith("HOST,"): return 1
    if line.startswith("HOST-SUFFIX,"): return 2
    if line.startswith("HOST-KEYWORD,"): return 3
    if line.startswith("IP-CIDR"): return 4
    return 10

def main():
    rules, stats = fetch_and_merge_rules()
    
    if not rules:
        raise ValueError("严重错误：没有抓取到任何规则！")

    sorted_rules = sorted(rules, key=sort_priority)
    
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    header = [
        f"# QX AdBlock Merged 5.0",
        f"# 更新时间: {now}",
        f"# 规则总数: {len(sorted_rules)}",
        f"# --- 来源详情 ---"
    ]
    
    # 把来源统计写入文件头，让你一目了然
    for name, count in stats.items():
        header.append(f"# {name}: 贡献 {count} 条")
    header.append("")
    
    with open("merged_ads.list", "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write("\n".join(sorted_rules))
        
    print(f"\n合并完成！共 {len(sorted_rules)} 条。")
    print("来源统计:", stats)

if __name__ == "__main__":
    main()
