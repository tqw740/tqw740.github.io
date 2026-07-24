import os
import re
import json
import requests
import yaml
from datetime import datetime

# 配置项
BLOG_BASE_URL = "https://blog.tqw740.top"  # 你的域名
ROBOT_WEBHOOK_URL = "https://bot.tqw740.top/api/hexo-update"  # 机器人 API 地址
SECRET_KEY = os.environ.get("ROBOT_SECRET_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

def get_ai_summary(text_content):
    """调用 LLM 生成 100 字总结"""
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = f"请用中文为以下博客文章生成一段精炼的 100 字左右总结，直接输出总结内容，不要包含多余的废话和前缀：\n\n{text_content[:3000]}"
    
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"AI 总结生成失败: {e}")
        return "总结生成失败，请点击链接直接阅读原文。"

def parse_md_file(filepath):
    """解析 Markdown 文件头部的 YAML Front-matter 和正文"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 匹配 --- ... --- 之间的 YAML 头
    yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.search(yaml_pattern, content, re.DOTALL)
    
    if match:
        meta_yaml = match.group(1)
        body = match.group(2)
        try:
            meta = yaml.safe_load(meta_yaml) or {}
        except Exception as e:
            print(f"YAML 解析警告 ({filepath}): {e}")
            meta = {}
        return meta, body
    return {}, content

def build_post_url(filepath, meta):
    """根据 Hexo 配置动态构建文章 URL"""
    # 1. 优先保留 Front-matter 中显式指定的 abbrlink 或 permalink
    if "abbrlink" in meta:
        return f"{BLOG_BASE_URL.rstrip('/')}/p/{meta['abbrlink']}/"
    if "permalink" in meta:
        permalink_str = str(meta['permalink']).strip('/')
        return f"{BLOG_BASE_URL.rstrip('/')}/{permalink_str}/"

    # 2. 默认适配 Hexo 的 :year/:month/:day/:slug/ 链接规则
    slug = os.path.basename(filepath).replace(".md", "")
    post_date = meta.get("date")

    # 提取年/月/日
    if isinstance(post_date, datetime):
        dt = post_date
    elif isinstance(post_date, str):
        try:
            dt = datetime.strptime(str(post_date).split('.')[0], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                dt = datetime.strptime(str(post_date).split()[0], '%Y-%m-%d')
            except ValueError:
                dt = datetime.now()
    else:
        dt = datetime.now()

    year = dt.strftime('%Y')
    month = dt.strftime('%m')
    day = dt.strftime('%d')

    return f"{BLOG_BASE_URL.rstrip('/')}/{year}/{month}/{day}/{slug}/"

def main():
    # 从 GitHub Actions 环境变量中获取改动的文件列表
    added_files = os.environ.get("ADDED_FILES", "").split()
    
    # 过滤出 source/_posts/ 下新增的 .md 文件
    post_files = [f for f in added_files if f.startswith("source/_posts/") and f.endswith(".md")]
    
    if not post_files:
        print("本次提交没有新增的文章，跳过通知。")
        return

    for filepath in post_files:
        print(f"正在处理新文章: {filepath}")
        meta, body = parse_md_file(filepath)
        
        # 1. 提取标题与动态构建链接
        title = meta.get("title", os.path.basename(filepath).replace(".md", ""))
        post_url = build_post_url(filepath, meta)

        print(f"解析到标题: {title}")
        print(f"生成对应链接: {post_url}")

        # 2. 生成 AI 总结
        summary = get_ai_summary(body)
        
        # 3. 发送给 QQ 机器人
        headers = {"X-Secret": SECRET_KEY, "Content-Type": "application/json"}
        data = {
            "title": title,
            "url": post_url,
            "summary": summary
        }
        try:
            resp = requests.post(ROBOT_WEBHOOK_URL, json=data, headers=headers, timeout=15)
            print(f"推送响应结果: {resp.text}")
        except Exception as e:
            print(f"发送 Webhook 到机器人失败: {e}")

if __name__ == "__main__":
    main()