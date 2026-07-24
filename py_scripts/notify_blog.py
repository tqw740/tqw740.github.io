import os
import re
import json
import requests
import yaml

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
        meta = yaml.safe_load(meta_yaml)
        return meta, body
    return {}, content

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
        
        title = meta.get("title", os.path.basename(filepath).replace(".md", ""))
        
        # 构建文章 URL (根据你的 _config.yml 中的 permalink 格式适配)
        # 如果你用了 hexo-abbrlink 并且生成时写入了 abbrlink 到 md：
        if "abbrlink" in meta:
            post_url = f"{BLOG_BASE_URL.rstrip('/')}/p/{meta['abbrlink']}/"
        elif "permalink" in meta:
            post_url = f"{BLOG_BASE_URL.rstrip('/')}/{meta['permalink']}/"
        else:
            # 默认使用文件名做 slug
            slug = os.path.basename(filepath).replace(".md", "")
            post_url = f"{BLOG_BASE_URL.rstrip('/')}/posts/{slug}/"

        # 1. 生成 AI 总结
        summary = get_ai_summary(body)
        
        # 2. 发送给 QQ 机器人
        headers = {"X-Secret": SECRET_KEY, "Content-Type": "application/json"}
        data = {
            "title": title,
            "url": post_url,
            "summary": summary
        }
        resp = requests.post(ROBOT_WEBHOOK_URL, json=data, headers=headers)
        print(f"推送响应结果: {resp.text}")

if __name__ == "__main__":
    main()