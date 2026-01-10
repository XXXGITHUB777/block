import requests
import pytz
import re
import os  # 新增：用于文件操作
from datetime import datetime

# ================= 配置区域 =================

OUTPUT_FILENAME = "block.list"  # 修改：输出文件名改为 block.list

# 4大金刚全员集合，全部使用 ghproxy 加速
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
    line = re.split(r'(#|;|//)', line)[0]
    line = line.strip().strip("'").strip('"')
    return line

def fetch_and_merge_rules():
    unique_rules = {} 
    source_stats = {} 
    
    headers = {
        'User-Agent': 'Quantumult%20X/1.0.30 (iPhone; iOS 16.0; Scale/3.00)',
    }
    
    print(f"--- 开始执行 9.1 增量统计版 (共{len(REMOTE_URLS)}个源) ---")

    for url in REMOTE_URLS:
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
                line = clean_line(line)
                if not line or line.startswith(('[', '<', '!', 'no-alert')):
                    continue

                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                else:
                    parts = line.split()

                if len(parts) < 2: continue

                rule_type = parts[0].upper()
                target = parts[1]
                
                if rule_type == "DOMAIN": rule_type = "HOST"
                if rule_type == "DOMAIN-SUFFIX": rule_type = "HOST-SUFFIX"
                if rule_type == "DOMAIN-KEYWORD": rule_type = "HOST-KEYWORD"
                
                policy = "reject"
                if len(parts) >= 3:
                    policy = parts[2].lower()
                if "reject" in policy: policy = "reject"
                
                if rule_type not in ["HOST", "HOST-SUFFIX", "HOST-KEYWORD", "IP-CIDR", "IP-CIDR6", "USER-AGENT"]:
                    continue

                unique_key = f"{rule_type},{target}".lower()
                
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

def get_old_rule_count(filepath):
    """
    读取旧文件，统计其中的有效规则行数
    """
    if not os.path.exists(filepath):
        return 0, False # 不存在
    
    count = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 排除空行和注释行，只统计实际规则
                if line and not line.startswith(('#', ';', '//')):
                    count += 1
        return count, True # 存在且统计完成
    except Exception:
        return 0, False

def main():
    # 1. 获取新规则
    rules, stats = fetch_and_merge_rules()
    
    if len(rules) == 0:
        print(f"\n错误：所有源提取均为 0，停止写入！")
        exit(1)

    sorted_rules = sorted(rules, key=sort_priority)
    current_count = len(sorted_rules)

    # 2. 对比逻辑 (关键修改)
    old_count, file_exists = get_old_rule_count(OUTPUT_FILENAME)
    
    diff_msg = ""
    diff_val = current_count - old_count
    
    if not file_exists:
        diff_msg = "(首次生成)"
        console_msg = "🆕 首次运行，建立基准"
    else:
        if diff_val > 0:
            diff_msg = f"(+{diff_val})"
            console_msg = f"📈 增加 {diff_val} 条"
        elif diff_val < 0:
            diff_msg = f"({diff_val})" # 负数自带负号
            console_msg = f"📉 减少 {abs(diff_val)} 条"
        else:
            diff_msg = "(持平)"
            console_msg = "⚖️ 数量无变化"

    # 3. 生成文件
    tz = pytz.timezone('Asia/Shanghai')
    现在 = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    header = [
        f"# QX AdBlock All-in-One",
        f"# 更新时间: {now}",
        f"# 规则统计: {current_count} 条 {diff_msg}", # 写入文件头的统计
        f"# --- 来源明细 ---"
    ]
    for n, c in stats.items():
        header.append(f"# {n}: {c}")
    header.append("")
    
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write("\n".join(sorted_rules))
        
    print(f"\n" + "="*30)
    print(f"处理完成！文件已保存为: {OUTPUT_FILENAME}")
    print(f"本次规则: {current_count}")
    print(f"上次规则: {old_count}")
    print(f"变化统计: {console_msg}")
    print(f"="*30)

if __name__ == "__main__":
    main()
