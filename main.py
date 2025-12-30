import requests
import pytz
import re
from datetime import datetime

# ================= 配置区域 =================

REMOTE_URLS = [
    # 秋风 (GhProxy 代理)
    "https://ghproxy.net/https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/Filters/AWAvenue-Ads-Rule-QuantumultX.list",
    # 毒奶 (GhProxy 代理)
    "https://ghproxy.net/https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/Adblock4limbo.list"
]

# ================= 逻辑区域 =================

def clean_line(line):
    """
    超级清洗函数：去除各种注释、特殊符号
    """
    # 1. 去除行尾注释 (支持 #, ;, //)
    # 比如: "HOST, a.com, reject # 广告" -> "HOST, a.com, reject"
    line = re.split(r'(#|;|//)', line)[0]
    
    # 2. 去除首尾空格、引号
    line = line.strip().strip("'").strip('"')
    
    return line

def fetch_and_merge_rules():
    unique_rules = {} 
    source_stats = {} 
    
    headers = {
        'User-Agent': 'Quantumult%20X/1.0.30 (iPhone; iOS 16.0; Scale/3.00)',
    }
    
    print(f"--- 开始执行 8.0 万能解析版 ---")

    for url in REMOTE_URLS:
        name = "秋风" if "AWAvenue" in url else "毒奶" if "limbopro" in url else "未知源"
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
            skipped_examples = [] # 记录被丢弃的行用于调试
            
            for line in lines:
                # === 清洗阶段 ===
                raw_line = line # 保留原始行用于报错
                line = clean_line(line)
                
                # 跳过空行和明显非规则行
                if not line or line.startswith(('[', '<', '!', 'no-alert')):
                    continue

                # === 拆分阶段 ===
                # 尝试用逗号拆分
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                else:
                    # 如果没有逗号，尝试用空格拆分 (兼容 Surge/Clash 格式)
                    # 比如: "DOMAIN-SUFFIX ad.com REJECT"
                    parts = line.split()

                # 长度检查
                if len(parts) < 2:
                    if len(skipped_examples) < 3: skipped_examples.append(f"[过短] {raw_line}")
                    continue

                # === 识别阶段 ===
                rule_type = parts[0].upper()
                target = parts[1]
                
                # 兼容性映射 (把其他软件的格式转为 QX)
                if rule_type == "DOMAIN": rule_type = "HOST"
                if rule_type == "DOMAIN-SUFFIX": rule_type = "HOST-SUFFIX"
                if rule_type == "DOMAIN-KEYWORD": rule_type = "HOST-KEYWORD"
                if rule_type == "IP-CIDR": rule_type = "IP-CIDR" 
                
                # 策略处理
                policy = "reject"
                if len(parts) >= 3:
                    policy = parts[2].lower()
                
                # 再次清洗策略 (比如 "reject,no-resolve" -> "reject")
                if "reject" in policy:
                    policy = "reject" # 统一简化为 reject，防止复杂参数导致失效
                
                # === 过滤阶段 ===
                # 只保留 QX 支持的去广告类型
                if rule_type not in ["HOST", "HOST-SUFFIX", "HOST-KEYWORD", "IP-CIDR", "IP-CIDR6", "USER-AGENT"]:
                    if len(skipped_examples) < 3 and not line.startswith("hostname"): 
                        skipped_examples.append(f"[类型不支持] {rule_type} -> {raw_line}")
                    continue

                # === 存入阶段 ===
                unique_key = f"{rule_type},{target}".lower()
                if unique_key not in unique_rules:
                    final_rule = f"{rule_type},{target},{policy}"
                    unique_rules[unique_key] = final_rule
                    current_count += 1
            
            source_stats[name] = current_count
            print(f" [成功提取 {current_count} 条]")
            
            # === 如果提取很少，打印丢弃样本 ===
            if current_count < 100:
                print(f"\n[调试] {name} 提取数量过低，查看被丢弃的行(前3条):")
                for example in skipped_examples:
                    print(f"  {example}")
                print("-" * 30)
            
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
    
    # 只有当总量真的是0时才报错 (防止其中一个源挂了影响另一个)
    if len(rules) == 0:
        print(f"\n错误：所有源提取均为 0，停止写入！")
        exit(1)

    sorted_rules = sorted(rules, key=sort_priority)
    
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    header = [
        f"# QX AdBlock Merged 8.0",
        f"# 更新时间: {now}",
        f"# 规则总数: {len(sorted_rules)}",
        f"# --- 来源详情 ---"
    ]
    for n, c in stats.items():
        header.append(f"# {n}: {c}")
    header.append("")
    
    with open("merged_ads.list", "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write("\n".join(sorted_rules))
        
    print(f"\n处理完成！merged_ads.list 已生成。")

if __name__ == "__main__":
    main()
