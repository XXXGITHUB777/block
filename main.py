import requests
import pytz
import re
import os
from datetime import datetime

# ================= 配置区域 =================

OUTPUT_FILENAME = "block.list"

# 整合了原有的4大金刚 + 你新提供的 HTTPDNS/Malware 规则
# 全部使用 ghproxy 加速 (GitHub Action 环境下虽非必须，但加上更稳)
REMOTE_URLS = [
    # --- 原有广告拦截组 ---
    "https://ghproxy.net/https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/Filters/AWAvenue-Ads-Rule-QuantumultX.list",
    "https://ghproxy.net/https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/Adblock4limbo.list",
    "https://ghproxy.net/https://raw.githubusercontent.com/fmz200/wool_scripts/main/QuantumultX/filter/filter.list",
    "https://ghproxy.net/https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/All/filter/allAdBlock.list",
    
    # --- 新增 HTTPDNS & 安全组 ---
    # 1. VirgilClyne HTTPDNS
    "https://ghproxy.net/https://raw.githubusercontent.com/VirgilClyne/GetSomeFries/main/ruleset/HTTPDNS.Block.list",
    
    # 2. Ban HTTPDNS (IP rules)
    "https://ghproxy.net/https://raw.githubusercontent.com/async-smith8845bn/QuantumultX_config/main/ClashRuleSet/List/ip/banhttpdns.conf",
    
    # 3. NoMalwares
    "https://ghproxy.net/https://raw.githubusercontent.com/enriquephl/QuantumultX_config/main/filters/NoMalwares.conf",
    
    # 4. Sukka Reject No Drop
    "https://ghproxy.net/https://raw.githubusercontent.com/SukkaLab/ruleset.skk.moe/master/List/non_ip/reject-no-drop.conf"
]

# ================= 逻辑区域 =================

def clean_line(line):
    # 去除注释和特殊符号
    line = re.split(r'(#|;|//)', line)[0]
    line = line.strip().strip("'").strip('"')
    return line

def fetch_and_merge_rules():
    unique_rules = {} 
    source_stats = {} 
    
    headers = {'User-Agent': 'Quantumult%20X/1.0.30 (iPhone; iOS 16.0; Scale/3.00)'}
    
    print(f"--- 开始执行 9.2 全能版 (共{len(REMOTE_URLS)}个源) ---")

    for url in REMOTE_URLS:
        # 简单的名字提取，用于日志显示
        if "AWAvenue" in url: name = "秋风广告"
        elif "limbopro" in url: name = "毒奶广告"
        elif "fmz200" in url: name = "FMZ200"
        elif "zirawell" in url: name = "Zirawell"
        elif "HTTPDNS.Block" in url: name = "HTTPDNS(Virgil)"
        elif "banhttpdns" in url: name = "HTTPDNS(IP)"
        elif "NoMalwares" in url: name = "去恶意软件"
        elif "ruleset.skk.moe" in url: name = "Sukka规则"
        else: name = "其他源"
            
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
                # 跳过无效行或html标签
                if not line or line.startswith(('[', '<', '!', 'no-alert', 'title', 'description')):
                    continue

                # 兼容逗号或空格分隔
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                else:
                    parts = line.split()

                if len(parts) < 2: continue

                rule_type = parts[0].upper()
                target = parts[1]
                
                # 类型标准化
                if rule_type == "DOMAIN": rule_type = "HOST"
                if rule_type == "DOMAIN-SUFFIX": rule_type = "HOST-SUFFIX"
                if rule_type == "DOMAIN-KEYWORD": rule_type = "HOST-KEYWORD"
                if rule_type == "IP-CIDR6": rule_type = "IP-CIDR6" 
                
                # 策略强制设为 reject (因为这是屏蔽列表)
                policy = "reject"
                
                # 只保留 QX 支持的拦截类型
                if rule_type not in ["HOST", "HOST-SUFFIX", "HOST-KEYWORD", "IP-CIDR", "IP-CIDR6", "USER-AGENT"]:
                    continue

                # 生成去重键值 (类型+目标)
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
    # 排序：HOST > SUFFIX > 其他
    if line.startswith("HOST,"): return 1
    if line.startswith("HOST-SUFFIX,"): return 2
    if line.startswith("IP-CIDR"): return 3
    return 10

def get_old_rule_count(filepath):
    if not os.path.exists(filepath):
        return 0, False
    count = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.strip().startswith(('#', ';', '//')):
                    count += 1
        return count, True
    except Exception:
        return 0, False

def main():
    rules, stats = fetch_and_merge_rules()
    
    if len(rules) == 0:
        print(f"\n错误：所有源提取均为 0，停止写入！")
        exit(1)

    sorted_rules = sorted(rules, key=sort_priority)
    current_count = len(sorted_rules)

    old_count, file_exists = get_old_rule_count(OUTPUT_FILENAME)
    
    diff_msg = ""
    diff_val = current_count - old_count
    
    if not file_exists:
        diff_msg = "(首次生成)"
        console_msg = "🆕 首次运行"
    else:
        if diff_val > 0:
            diff_msg = f"(+{diff_val})"
            console_msg = f"📈 增加 {diff_val} 条"
        elif diff_val < 0:
            diff_msg = f"({diff_val})"
            console_msg = f"📉 减少 {abs(diff_val)} 条"
        else:
            diff_msg = "(持平)"
            console_msg = "⚖️ 无变化"

    tz = pytz.timezone('Asia/Shanghai')
    现在 = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    header = [
        f"# QX Block List Ultimate (AdBlock + HTTPDNS + Malware)",
        f"# 更新时间: {now}",
        f"# 规则统计: {current_count} 条 {diff_msg}",
        f"# --- 来源明细 ---"
    ]
    for n, c in stats.items():
        header.append(f"# {n}: {c}")
    header.append("")
    
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write("\n".join(sorted_rules))
        
    print(f"\n" + "="*30)
    print(f"处理完成！文件: {OUTPUT_FILENAME}")
    print(f"规则总数: {current_count} {console_msg}")
    print(f"="*30)

if __name__ == "__main__":
    main()
