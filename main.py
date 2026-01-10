import requests
import pytz
import re
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# === 配置区域 ===
OUTPUT_FILENAME = "block.list"
MAX_WORKERS = 8
TIMEOUT = 30
POLICY_NAME = "reject"  # 策略名，对应你范例里的 AdvertisingLite，这里统一用 reject

REMOTE_URLS = [
    "https://ghproxy.net/https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/Filters/AWAvenue-Ads-Rule-QuantumultX.list",
    "https://ghproxy.net/https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/Adblock4limbo.list",
    "https://ghproxy.net/https://raw.githubusercontent.com/fmz200/wool_scripts/main/QuantumultX/filter/filter.list",
    "https://ghproxy.net/https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/All/filter/allAdBlock.list",
    "https://ghproxy.net/https://raw.githubusercontent.com/VirgilClyne/GetSomeFries/main/ruleset/HTTPDNS.Block.list",
    "https://ghproxy.net/https://raw.githubusercontent.com/async-smith8845bn/QuantumultX_config/main/ClashRuleSet/List/ip/banhttpdns.conf",
    "https://ghproxy.net/https://raw.githubusercontent.com/enriquephl/QuantumultX_config/main/filters/NoMalwares.conf",
    "https://ghproxy.net/https://raw.githubusercontent.com/SukkaLab/ruleset.skk.moe/master/List/non_ip/reject-no-drop.conf"
]

# === 类型映射 (全部转为大写，符合你的范例) ===
TYPE_MAP = {
    # 兼容其他格式 -> QX 标准大写
    "DOMAIN": "HOST",
    "DOMAIN-SUFFIX": "HOST-SUFFIX",
    "DOMAIN-KEYWORD": "HOST-KEYWORD",
    "IP-CIDR": "IP-CIDR",
    "IP-CIDR6": "IP6-CIDR",
    "USER-AGENT": "USER-AGENT",
    
    # QX 原生格式保留 -> 统一大写
    "HOST": "HOST",
    "HOST-SUFFIX": "HOST-SUFFIX",
    "HOST-KEYWORD": "HOST-KEYWORD",
    "HOST-WILDCARD": "HOST-WILDCARD",
    "IP6-CIDR": "IP6-CIDR",
    "GEOIP": "GEOIP",
    "IP-ASN": "IP-ASN"
}

# === 输出顺序 ===
# 决定文件里谁排前面，谁排后面
OUTPUT_ORDER = [
    "HOST",
    "HOST-SUFFIX",
    "HOST-KEYWORD",
    "HOST-WILDCARD",
    "USER-AGENT",
    "IP-CIDR",
    "IP6-CIDR",
    "GEOIP",
    "IP-ASN"
]

def get_source_name(url):
    if "AWAvenue" in url: return "秋风"
    if "limbopro" in url: return "毒奶"
    if "fmz200" in url: return "FMZ200"
    if "zirawell" in url: return "Zirawell"
    if "VirgilClyne" in url: return "HTTPDNS(Virgil)"
    if "async-smith" in url: return "HTTPDNS(IP)"
    if "NoMalwares" in url: return "Malware"
    if "Sukka" in url: return "Sukka"
    return "Unknown"

def fetch_single_url(url):
    name = get_source_name(url)
    rules_dict = defaultdict(set) # 按类型存储
    
    headers = {
        'User-Agent': 'Quantumult%20X/1.5.0 (iPhone; iOS 17.0; Scale/3.00)',
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"❌ [{name}] HTTP {resp.status_code}")
            return name, rules_dict
        
        resp.encoding = 'utf-8'
        lines = resp.text.splitlines()
        count = 0
        
        for line in lines:
            line = re.split(r'(#|;|//)', line)[0].strip()
            if not line: continue
            if line.startswith(('[', '<', '!', 'no-alert', 'payload:')): continue

            # 分割逻辑
            if ',' in line:
                parts = [p.strip() for p in line.split(',')]
            else:
                parts = line.split()

            if len(parts) < 2: continue

            raw_type = parts[0].upper()
            
            # 处理 payload 格式
            if raw_type == "-" and len(parts) > 2:
                raw_type = parts[1].upper()
                target = parts[2]
            else:
                target = parts[1]

            # 映射类型
            final_type = TYPE_MAP.get(raw_type)
            if not final_type: continue
            
            target = target.strip("'").strip('"')

            # === 格式组装 ===
            # 严格按照：TYPE,Target,Policy
            # IP 规则保留 no-resolve 以防 DNS 泄露，但保持格式紧凑
            if final_type in ["IP-CIDR", "IP6-CIDR"]:
                rule_str = f"{final_type},{target},{POLICY_NAME},no-resolve"
            else:
                rule_str = f"{final_type},{target},{POLICY_NAME}"
            
            rules_dict[final_type].add(rule_str)
            count += 1
            
        print(f"✅ [{name}] Parsed {count}")
        return name, rules_dict

    except Exception as e:
        print(f"❌ [{name}] Error: {e}")
        return name, rules_dict

def main():
    print(f"--- Starting Download ({MAX_WORKERS} threads) ---")
    
    # 用于汇总所有规则：结构 { "HOST": set(...), "IP-CIDR": set(...) }
    global_rules = defaultdict(set)
    source_stats = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_single_url, url): url for url in REMOTE_URLS}
        for future in as_completed(futures):
            name, rules_dict = future.result()
            total_source = 0
            for r_type, r_set in rules_dict.items():
                global_rules[r_type].update(r_set)
                total_source += len(r_set)
            source_stats[name] = total_source

    # === 生成统计数据 ===
    total_count = sum(len(s) for s in global_rules.values())
    if total_count == 0:
        print("No rules found.")
        exit(1)

    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    # 文件头
    header = [
        f"# QX AdBlock All-in-One",
        f"# Updated: {now}",
        f"# Total Rules: {total_count}",
        f"#"
    ]

    # 添加分类统计 (类似你发的示范)
    header.append("# [ Rule Statistics ]")
    for r_type in OUTPUT_ORDER:
        count = len(global_rules[r_type])
        if count > 0:
            # 对齐显示
            header.append(f"# {r_type:<15} : {count}")
    
    header.append("#")
    header.append("# [ Source Statistics ]")
    for n, c in sorted(source_stats.items(), key=lambda x: x[1], reverse=True):
        header.append(f"# {n:<15} : {c}")
    header.append("")

    # === 写入文件 ===
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write("\n")
        
        # 按照指定顺序输出
        for r_type in OUTPUT_ORDER:
            rules = global_rules[r_type]
            if not rules: continue
            
            # 该类型的规则按字母排序
            sorted_rules = sorted(list(rules))
            
            # 写入该类型的块
            # f.write(f"\n; --- {r_type} ---\n") # 可选：是否加分隔符，为了保持纯净，这里不加
            f.write("\n".join(sorted_rules))
            f.write("\n") # 类型之间空一行，方便阅读

    print(f"\nDone. Saved to {OUTPUT_FILENAME}")
    print(f"Total: {total_count}")

if __name__ == "__main__":
    main()
