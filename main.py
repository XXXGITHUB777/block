import requests
import pytz
import re
from datetime import datetime

# ================= 配置区域 =================

# ！！！关键修改：全部换成 CDN 链接，解决 0 条的问题！！！
REMOTE_URLS = [
    # 1. 秋风 (CDN 加速版)
    "https://cdn.jsdelivr.net/gh/TG-Twilight/AWAvenue-Ads-Rule@main/Filters/AWAvenue-Ads-Rule-QuantumultX.list",
    
    # 2. 毒奶 Limbopro (CDN 加速版)
    "https://cdn.jsdelivr.net/gh/limbopro/Adblock4limbo@main/Adblock4limbo.list"
]

# 备用：如果上面的都挂了，保留这两个稳健的作为兜底（可选，不想用可以注释掉）
# REMOTE_URLS.append("https://cdn.jsdelivr.net/gh/fmz200/wool_scripts@main/QuantumultX/filter/filter.list")
# REMOTE_URLS.append("https://cdn.jsdelivr.net/gh/zirawell/R-Store@main/Rule/QuanX/Adblock/All/filter/allAdBlock.list")

# 有效的拒绝策略关键词
VALID_POLICIES = {
    "reject", "reject-200", "reject-tinygif", "reject-img", 
    "reject-dict", "reject-array", "reject-video"
}

# ================= 逻辑区域 =================

def fetch_and_merge_rules():
    unique_rules = {} 
    source_stats = {} 
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    }
    
    print(f"--- 开始执行 6.0 CDN 加速合并 ---")

    for url in REMOTE_URLS:
        # 提取文件名
        source_name = url.split('/')[-1]
        if "AWAvenue" in url: source_name = "秋风(AWAvenue)"
        if "limbopro" in url: source_name = "毒奶(Limbopro)"
            
        print(f"正在下载: {source_name} ...", end="")
        
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            
            # 强制设置编码，防止中文乱码
            resp.encoding = 'utf-8'
            
            if resp.status_code != 200:
                print(f" [失败] HTTP Code: {resp.status_code}")
                source_stats[source_name] = 0
                continue

            lines = resp.text.splitlines()
            current_source_count = 0
            
            # --- 调试：如果下载内容太短，打印出来看看是啥 ---
            if len(lines) < 10:
                print(f"\n[警告] {source_name} 内容异常短，可能不是规则文件，前3行内容:")
                for i in range(min(3, len(lines))):
                    print(f"  Line {i}: {lines[i]}")
            # ---------------------------------------------
            
            for line in lines:
                line = line.strip()
                
                # 1. 基础清理
                if not line or line.startswith(('#', ';', '//', '[', '<', '!')):
                    continue
                # 2. 必须包含逗号
                if ',' not in line:
                    continue
                    
                parts = [p.strip() for p in line.split(',')]
                
                # 3. 智能补全 (HOST,baidu.com -> HOST,baidu.com,reject)
                if len(parts) == 2:
                    parts.append("reject")
                
                if len(parts) < 3:
                    continue

                rule_type = parts[0].upper()
                target = parts[1]
                policy = parts[2].lower()

                # 4. 类型过滤
                if rule_type not in ["HOST", "HOST-SUFFIX", "HOST-KEYWORD", "IP-CIDR", "IP-CIDR6", "USER-AGENT"]:
                    continue

                # 5. 策略清洗
                is_valid_policy = False
                for p in VALID_POLICIES:
                    if p in policy:
                        is_valid_policy = True
                        break
                
                if not is_valid_policy:
                    policy = "reject"

                # 6. 生成Key (小写去重)
                unique_key = f"{rule_type},{target}".lower()

                # 7. 存入
                if unique_key not in unique_rules:
                    final_rule = f"{rule_type},{target},{policy}"
                    unique_rules[unique_key] = final_rule
                    current_source_count += 1
            
            source_stats[source_name] = current_source_count
            print(f" [成功提取 {current_source_count} 条]")
            
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
    
    # 安全检查：如果规则太少，抛出异常，防止覆盖
    if len(rules) < 100:
        print("错误：生成的规则数量过少，放弃写入，保留旧文件。")
        # 这里 exit(1) 会让 Action 报错变红，提醒你注意
        exit(1)

    sorted_rules = sorted(rules, key=sort_priority)
    
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    header = [
        f"# QX AdBlock Merged 6.0 (CDN)",
        f"# 更新时间: {now}",
        f"# 规则总数: {len(sorted_rules)}",
        f"# --- 来源详情 ---"
    ]
    
    for name, count in stats.items():
        header.append(f"# {name}: {count}")
    header.append("")
    
    with open("merged_ads.list", "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write("\n".join(sorted_rules))
        
    print(f"\n处理完成！Merged List 已生成。")

if __name__ == "__main__":
    main()
