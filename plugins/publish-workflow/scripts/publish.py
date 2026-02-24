#!/usr/bin/env python3
"""
Publishing Script - Publish to X (Twitter) via Rube MCP
Supports long tweets via proxy_execute (bypasses 280 char Composio limitation)

Features:
- Short tweets (≤280 chars): use run_composio_tool
- Long tweets (>280 chars): use proxy_execute to call Twitter API v2 directly
- No practical character limit (Twitter's actual limit is much higher)
"""

import json
import os
import requests
import base64
from datetime import datetime, timezone
import uuid
import sys
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
DATA_FILE = os.path.join(WORKSPACE_DIR, "data", "posts.json")
LOG_FILE = os.path.join(WORKSPACE_DIR, "logs", "publish.log")

RUBE_URL = "https://rube.app/mcp"
RUBE_TOKEN = os.environ.get("RUBE_MCP_TOKEN") or os.environ.get("RUBE_TOKEN")

# Ensure log directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(level, message):
    """Write log message"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line + '\n')

# Load token from TOOLS.md if not set in environment
if not RUBE_TOKEN:
    try:
        tools_md = os.path.join(WORKSPACE_DIR, "TOOLS.md")
        if os.path.exists(tools_md):
            with open(tools_md, 'r') as f:
                content = f.read()
                match = re.search(r'Token[:\*]*\s*(eyJ[\w\-\.]*)', content)
                if match:
                    RUBE_TOKEN = match.group(1)
                    log("INFO", f"Token loaded from TOOLS.md: {RUBE_TOKEN[:20]}...")
    except Exception as e:
        log("ERROR", f"Failed to load token: {e}")

def load_posts():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"posts": [], "lastUpdated": datetime.now().isoformat()}

def save_posts(data):
    data["lastUpdated"] = datetime.now().isoformat()
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def truncate_text(text, max_chars=10000):
    """
    Truncate text to max_chars, preserving word boundaries.
    Note: This is a safety fallback. Twitter's actual limit is very high (~25k chars).
    In practice, proxy_execute handles long tweets without truncation.
    """
    if len(text) <= max_chars:
        return text

    # Try to break at word boundaries
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')

    if last_space > max_chars * 0.8:  # Break at last space if it's in the last 20%
        truncated = truncated[:last_space]

    return truncated.strip()

def call_rube_tool(name, arguments):
    """Call Rube MCP tool"""
    if not RUBE_TOKEN:
        log("ERROR", "RUBE_TOKEN not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {RUBE_TOKEN}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
        "id": str(uuid.uuid4())[:8]
    }
    
    try:
        resp = requests.post(RUBE_URL, json=payload, headers=headers, timeout=180)
        text = resp.text
        
        if resp.status_code != 200:
            log("ERROR", f"HTTP {resp.status_code}: {text[:200]}")
            return None
        
        # Parse SSE
        if 'data:' in text:
            for line in text.strip().split('\n'):
                if line.startswith('data:'):
                    data_str = line[5:].strip()
                    if data_str:
                        try:
                            result = json.loads(data_str)
                            if result.get("result") and result["result"].get("content"):
                                content = result["result"]["content"]
                                if content and len(content) > 0:
                                    text_content = content[0].get("text", "")
                                    try:
                                        parsed = json.loads(text_content)
                                        if parsed.get("successful") == False:
                                            log("ERROR", f"Rube error: {parsed.get('error')}")
                                            return None
                                        return parsed
                                    except:
                                        return text_content
                            return result.get("result", {})
                        except:
                            continue
        return resp.json().get("result", {})
    except Exception as e:
        log("ERROR", f"Exception: {e}")
        return None

def parse_workbench_result(result):
    """解析 Workbench 执行结果"""
    if not result:
        return None
    
    stdout = ""
    if isinstance(result, dict):
        stdout = result.get('data', {}).get('data', {}).get('stdout', '')
    elif isinstance(result, str):
        stdout = result
    
    if not stdout:
        return None
    
    # 查找 ===RESULT=== 标记
    if "===RESULT===" in stdout:
        try:
            json_str = stdout.split("===RESULT===")[-1].strip()
            return json.loads(json_str)
        except:
            pass
    
    # 查找包含 tweet_id 的 JSON
    match = re.search(r'\{[^}]*"tweet_id"[^}]*\}', stdout)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    
    return None

def post_to_x_via_rube(text, media_paths, post_id=""):
    """
    Publish to X via Rube Workbench

    Uses proxy_execute for long tweets (>280 chars) to bypass Composio's 280 char limit.
    Returns: (success: bool, result_dict or error_msg)
    """
    original_text = text
    is_truncated = False

    # No hard character limit - proxy_execute handles long tweets
    # Safety check for extremely long text (>10k chars is unusual)
    if len(text) > 10000:
        log("WARN", f"[{post_id}] Unusually long text ({len(text)} chars), truncating for safety...")
        text = truncate_text(text, 10000)
        is_truncated = True
        log("INFO", f"[{post_id}] Truncated to {len(text)} characters")

    # Safely escape text for JSON
    text_json = json.dumps(text)
    
    # 编码图片
    image_data = []
    for i, path in enumerate(media_paths[:4]):  # 最多4张图片
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                    ext = path.split('.')[-1].lower()
                    if ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                        ext = 'jpg'
                    mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
                    image_data.append((i, ext, mime, b64))
            except Exception as e:
                log("ERROR", f"[{post_id}] Failed to encode image {path}: {e}")
        else:
            log("WARN", f"[{post_id}] Image not found: {path}")
    
    log("INFO", f"[{post_id}] Publishing: {len(text)} chars, {len(image_data)} images")

    log("INFO", f"[{post_id}] Using proxy_execute for all tweets (length: {len(text)} chars)")

    # 构建 workbench 代码 - 统一使用 proxy_execute 绕过 Composio 限制
    if not image_data:
        # 纯文字 - 全部用 proxy_execute
        python_code = f'''import json
from rube.workbench.tools import proxy_execute

text = {text_json}
print(f"Publishing via proxy_execute: {{len(text)}} chars")

post_res, post_err = proxy_execute("POST", "https://api.twitter.com/2/tweets", "twitter", body={{"text": text}})

print(f"Result: {{post_res}}")
print(f"Error: {{post_err}}")

if post_err:
    result = {{"error": str(post_err)}}
else:
    try:
        tweet_id = post_res.get('data', {{}}).get('id')
        result = {{"tweet_id": tweet_id, "success": True}}
    except Exception as e:
        result = {{"error": f"Parse error: {{e}}"}}

print("\\n===RESULT===")
print(json.dumps(result))'''
    else:
        # 带图片
        decode_parts = []
        upload_parts = []
        media_parts = []

        for i, ext, mime, b64 in image_data:
            decode_parts.append(f'''# Image {i+1}
img_b64_{i} = "{b64}"
img_data_{i} = base64.b64decode(img_b64_{i})
with open("img_{i}.{ext}", "wb") as f:
    f.write(img_data_{i})''')

            upload_parts.append(f'''s3_res_{i}, s3_err_{i} = upload_local_file("img_{i}.{ext}")''')

            media_parts.append(f'''up_res_{i}, up_err_{i} = run_composio_tool('TWITTER_UPLOAD_MEDIA', {{
    'media': {{'name': 'img_{i}.{ext}', 'mimetype': '{mime}', 's3key': s3_res_{i}.get('s3key')}},
    'media_category': 'tweet_image'
}})
if not up_err_{i}:
    mid_{i} = up_res_{i}.get('data', {{}}).get('data', {{}}).get('id')
    if mid_{i}:
        media_ids.append(str(mid_{i}))''')

        indented_media_parts = chr(10).join(['    ' + line for p in media_parts for line in p.split(chr(10))])
        python_code = f'''import base64
import json
from rube.workbench.tools import upload_local_file, run_composio_tool, proxy_execute

text = {text_json}
media_ids = []

{chr(10).join(decode_parts)}

{chr(10).join(upload_parts)}

if s3_res_0 and s3_res_0.get('s3key'):
{indented_media_parts}

# 统一使用 proxy_execute 发布（绕过 Composio 的 run_composio_tool 限制）
post_body = {{'text': text}}
if media_ids:
    post_body['media'] = {{'media_ids': media_ids}}
print(f"Publishing via proxy_execute: text_len={{len(text)}}, media_ids={{media_ids}}")
post_res, post_err = proxy_execute("POST", "https://api.twitter.com/2/tweets", "twitter", body=post_body)
if post_err:
    result = {{"error": str(post_err)}}
else:
    try:
        tweet_id = post_res.get('data', {{}}).get('id')
        result = {{"tweet_id": tweet_id, "success": True}}
    except Exception as e:
        result = {{"error": f"Parse error: {{e}}"}}

print("\\n===RESULT===")
print(json.dumps(result))'''
    
    # 调用 Rube
    result = call_rube_tool("RUBE_REMOTE_WORKBENCH", {
        "code_to_execute": python_code,
        "thought": "Post to X"
    })
    
    if not result:
        return False, "Rube tool call failed"
    
    parsed = parse_workbench_result(result)
    if not parsed:
        return False, "Failed to parse result"
    
    if parsed.get("error"):
        return False, parsed["error"]
    
    if parsed.get("tweet_id"):
        result_dict = {
            "tweet_id": parsed["tweet_id"],
            "truncated": is_truncated,
            "original_length": len(original_text),
            "final_length": len(text)
        }
        return True, result_dict
    
    return False, "Unknown error"

def main():
    now = datetime.now(timezone.utc)
    workspace = os.path.basename(WORKSPACE_DIR)
    
    log("INFO", "="*60)
    log("INFO", f"Publishing to X ({workspace})")
    log("INFO", "All tweets via proxy_execute (bypasses Composio run_composio_tool)")
    log("INFO", "="*60)
    
    if not RUBE_TOKEN:
        log("ERROR", "RUBE_MCP_TOKEN not set")
        sys.exit(1)
    
    data = load_posts()
    posts = data.get("posts", [])
    to_post = []
    for p in posts:
        if p.get("status") == "Approved" and not p.get("tweetId"):
            scheduled_at = p.get("scheduledAt")
            if not scheduled_at:
                to_post.append(p)
                continue
            
            try:
                # Handle ISO format strings
                scheduled_dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                # Ensure now is timezone-aware if scheduled_dt is
                current_now = datetime.now(scheduled_dt.tzinfo) if scheduled_dt.tzinfo else datetime.now()
                
                if current_now >= scheduled_dt:
                    to_post.append(p)
                else:
                    log("INFO", f"Post {p['uid']} skipped, scheduled for {scheduled_at}")
            except Exception as e:
                log("ERROR", f"Failed to parse scheduledAt for {p['uid']}: {e}")
                to_post.append(p) # Fallback to publish
    
    if not to_post:
        log("INFO", "No posts to publish (all scheduled for later or already posted)")
        return
    
    log("INFO", f"Found {len(to_post)} posts to publish (after scheduling check)")
    
    success_count = 0
    fail_count = 0
    
    for post in to_post:
        post_id = post["uid"]
        text = post.get("generatedContent", "")
        media = post.get("media", [])[:4]
        
        # 过滤存在的图片
        valid_media = [p for p in media if os.path.exists(p)]
        
        print(f"\n{'='*60}")
        log("INFO", f"Publishing: {post_id}")
        print(f"  Text: {text[:50]}...")
        print(f"  Chars: {len(text)}")
        print(f"  Images: {len(valid_media)}/{len(media)}")
        
        success, result = post_to_x_via_rube(text, valid_media, post_id)
        
        if success:
            tweet_id = result["tweet_id"]
            tweet_url = f"https://x.com/i/status/{tweet_id}"
            
            post["status"] = "Posted"
            post["postedAt"] = now.isoformat()
            post["tweetId"] = tweet_id
            post["tweetUrl"] = tweet_url
            
            if result.get("truncated"):
                post["truncated"] = True
                post["originalLength"] = result["original_length"]
                log("WARN", f"  ⚠️ Text was truncated from {result['original_length']} to {result['final_length']} chars")
            
            save_posts(data)
            success_count += 1
            log("INFO", f"  ✅ Success: {tweet_url}")
        else:
            fail_count += 1
            error = result if isinstance(result, str) else str(result)
            log("ERROR", f"  ❌ Failed: {error[:100]}")
    
    print(f"\n{'='*60}")
    log("INFO", f"Done: {success_count} success, {fail_count} failed")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
