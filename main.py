import requests
import pytz
import re
from datetime import datetime

# ================= 配置区域 =================

# 4大金刚全员集合，全部使用 ghproxy 加速，确保下载成功率 100%
REMOTE_URLS = [
    # 1. 秋风 (主力)
    "https://ghproxy.net/https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/Filters/AWAvenue-Ads-Rule-QuantumultX.list",
    
    # 2. 毒奶 (补充)
    "https://ghproxy.net/https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/Adblock4limbo.list",
    
    # 3. FMZ200 (老牌)
    "https://ghproxy.net/https://raw.githubusercontent.com/fmz200/wool_scripts/main/QuantumultX/filter/filter.list",
    
    # 4. Zirawell (补充)
    "https://ghproxy.net/https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/All/filter/allAdBlock.list"
]

# ================= 逻辑区域 =================

def clean_line(line):
    """
    清洗函数：去除注释、引号、特殊符号
    """
    # 去除行尾注释 (支持 #, ;, //)
    line = re.split(r'(#|;|//)', line)[0]
    # 去除首尾空格、引号
    line = line.strip().strip("'").strip('"')
    return line

def fetch_and_merge_rules():
    unique_rules = {} 
    source_stats = {} 
    
    # 伪装 Header
    headers = {
        'User-Agent': 'Quantumult%20X/1.0.30 (iPhone; iOS 16.0; Scale/3.00)',
    }
    
    print(f"--- 开始执行 9.0 全员集结版 (共{len(REMOTE_URLS)}个源) ---")

    for url in REMOTE_URLS:
        # 提取名字用于显示
        if "AWAvenue" in url: name = "秋风"
        elif "limbopro" in url: name = "毒奶"
        elif "fmz200" in url: name = "FMZ200"
        elif "zirawell" in url: name = "Zirawell"
        else: name = "未知源"
            
        print(f"正在处理: {name} ...", end="")
        
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            resp.encoding = 'utf-8'
            
            if resp.status_code != 200:
                print(f" [失败] HTTP {resp.status_code}")
                source_stats[name] = 0
                continue

            lines = resp.text.splitlines()
            current_count = 0
            
            for line in lines:
                # === 清洗 ===
                line = clean_line(line)
                
                # 跳过无效行
                if not line or line.startswith(('[', '<', '!', 'no-alert')):
                    continue

                # === 拆分 (兼容逗号和空格) ===
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                else:
                    parts = line.split() # 兼容空格分隔

                if len(parts) < 2: continue

                # === 识别 ===
                rule_type = parts[0].upper()
                target = parts[1]
                
                # 兼容性映射
                if rule_type == "DOMAIN": rule_type = "HOST"
                if rule_type == "DOMAIN-SUFFIX": rule_type = "HOST-SUFFIX"
                if rule_type == "DOMAIN-KEYWORD": rule_type = "HOST-KEYWORD"
                
                # 策略处理
                policy = "reject"
                if len(parts) >= 3:
                    policy = parts[2].lower()
                
                # 统一 reject
                if "reject" in policy: policy = "reject"
                
                # === 过滤 QX 类型 ===
                if rule_type not in ["HOST", "HOST-SUFFIX", "HOST-KEYWORD", "IP-CIDR", "IP-CIDR6", "USER-AGENT"]:
                    continue

                # === 存入 (去重) ===
                unique_key = f"{rule_type},{target}".lower()
                
                # 只有当这个 key 没出现过时才添加 (排在列表前面的源拥有优先权)
                if unique_key not in unique_rules:
                    final_rule = f"{rule_type},{target},{policy}"
                    unique_rules[unique_key] = final_rule
                    current_count += 1
            
            source_stats[name] = current_count
            print(f" [成功提取 {current_count} 条]")
            
        except Exception as e:
            print(f" [出错] {e}")
            source_stats[name] = 0

    return list(unique_rules.values()), source_stats

def sort_priority(line):
    if line.startswith("HOST,"): return 1
    if line.startswith("HOST-SUFFIX,"): return 2
    return 10

def main():
    rules, stats = fetch_and_merge_rules()
    
    # 只要总数不为0就算成功
    if len(rules) == 0:
        print(f"\n错误：所有源提取均为 0，停止写入！")
        exit(1)

    sorted_rules = sorted(rules, key=sort_priority)
    
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    header = [
        f"# QX AdBlock Merged 9.0 (Full Set)",
        f"# 更新时间: {now}",
        f"# 规则总数: {len(sorted_rules)}",
        f"# --- 来源贡献 ---"
    ]
    for n, c in stats.items():
        header.append(f"# {n}: {c}")
    header.append("")
    
    with open("merged_ads.list", "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write("\n".join(sorted_rules))
        
    print(f"\n处理完成！共生成 {len(sorted_rules)} 条规则。")

if __name__ == "__main__":
    main()
