import asyncio
import websockets
import json
import requests
import random
import re
import time

# 读取配置
def load_config():
    with open("server.txt", "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]
        clean = [i for i in lines if not i.startswith("#") and i]
        base = clean[:14]
        setting = "\n".join(clean[14:])
        return base, setting

# 加载知识库
def load_knowledge():
    data = {}
    with open("knowledge.txt","r",encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            if "===" in line:
                q,a = line.split("===")
                data[q] = a
    return data

# 加载用户数据配置文件
def load_user_data():
    data = {
        "end_excuses": [],
        "default_replies": [],
        "error_replies": {},
        "ai_error_replies": {}
    }
    try:
        with open("user.txt", "r", encoding="utf-8") as f:
            for line in f.readlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "|" in line:
                    key, value = line.split("|", 1)
                    if key == "结束对话借口":
                        data["end_excuses"].append(value)
                    elif key == "默认回复":
                        data["default_replies"].append(value)
                    elif key.startswith("网络错误-"):
                        error_type = key.replace("网络错误-", "")
                        data["error_replies"][error_type] = value
                    elif key.startswith("AI错误-"):
                        error_type = key.replace("AI错误-", "")
                        data["ai_error_replies"][error_type] = value
    except:
        pass
    
    # 如果加载失败或文件为空，使用默认数据
    if not data["end_excuses"]:
        data["end_excuses"] = [
            "我有点事情要处理，先忙啦~",
            "哎呀，时间不早了，我该休息了，明天再聊吧~",
            "有点困了，想睡一会儿，下次再聊哦~"
        ]
    if not data["default_replies"]:
        data["default_replies"] = ["一切都还挺好的", "都挺好的呢"]
    if not data["error_replies"]:
        data["error_replies"] = {
            "连接超时": "网络有点慢呢，稍等一下~",
            "读取超时": "网络有点卡呢，我想想~",
            "连接错误": "网络不太稳定呢，稍后再聊~"
        }
    if not data["ai_error_replies"]:
        data["ai_error_replies"] = {
            "HTTP错误": "挺好的呢",
            "响应无choices": "都挺好的呢",
            "内容不合规": "这个话题不太合适呢，换个话题吧~",
            "最终内容为空": "一切都还挺好的"
        }
    
    return data

# 模糊匹配
def fuzzy_match(text,know):
    for q,a in know.items():
        if q in text:
            return a
    return None

# 清理所有思考内容
def clear_thought(text):
    text = re.sub(r'（[\s\S]*?）','',text)
    text = re.sub(r'\([\s\S]*?\)','',text)
    text = text.replace("\n","").strip()
    return text

# 加载用户印象数据
def load_love_data():
    data = {}
    try:
        with open("love.txt","r",encoding="utf-8") as f:
            for line in f.readlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("|")
                    if len(parts) >= 2:
                        user_id = parts[0]
                        affection = int(parts[1])
                        tags = parts[2].split(",") if len(parts) > 2 else []
                        last_emotion = parts[3] if len(parts) > 3 else ""
                        data[user_id] = {"affection": affection, "tags": tags, "last_emotion": last_emotion}
    except:
        pass
    return data

# 保存用户印象数据
def save_love_data(love_data):
    with open("love.txt","w",encoding="utf-8") as f:
        f.write("# ==================== 用户印象数据文件 ====================\n")
        f.write("# 此文件存储每个用户的好感度和上次对话情绪\n")
        f.write("# 格式: user_id|好感度|印象标签|上次情绪\n")
        f.write("# - user_id: 用户的QQ号\n")
        f.write("# - 好感度: -100 到 100，初始为0\n")
        f.write("# - 印象标签: 用逗号分隔，暂未启用\n")
        f.write("# - 上次情绪: AI上次对话时的情绪状态\n\n")
        for user_id, info in love_data.items():
            tags = ",".join(info["tags"])
            last_emotion = info.get("last_emotion", "")
            f.write(f"{user_id}|{info['affection']}|{tags}|{last_emotion}\n")

# 根据对话内容更新好感度
def update_affection(text, current_affection):
    affection_change = 0
    
    positive_words = ["喜欢","爱","可爱","漂亮","温柔","好","棒","厉害","谢谢","想你","抱抱","亲亲"]
    negative_words = ["讨厌","烦","滚","去死","垃圾","恶心","丑","笨","傻","讨厌你","走开"]
    
    for word in positive_words:
        if word in text:
            affection_change += 2
    
    for word in negative_words:
        if word in text:
            affection_change -= 3
    
    new_affection = max(-100, min(100, current_affection + affection_change))
    return new_affection, affection_change

# 根据好感度获取语气前缀
def get_tone_prefix(affection):
    if affection >= 60:
        prefix = random.choice(["~", "喵~", "❤", "♡", "(*^▽^*)"])
    elif affection >= 30:
        prefix = random.choice(["", "~", "呀", "呢"])
    elif affection >= 0:
        prefix = ""
    elif affection >= -30:
        prefix = random.choice(["。", "...", ""])
    else:
        prefix = random.choice(["。", "...", "切"])
    return prefix

# 根据好感度调整语气描述
def get_tone_description(affection):
    if affection >= 80:
        return "非常亲热，撒娇语气"
    elif affection >= 60:
        return "亲热，温柔语气"
    elif affection >= 30:
        return "友好，正常语气"
    elif affection >= 0:
        return "平淡，普通语气"
    elif affection >= -30:
        return "冷淡，敷衍语气"
    elif affection >= -60:
        return "冷酷，生硬语气"
    else:
        return "非常冷酷，敌对语气"

# 初始化
base_cfg, system_msg = load_config()
knowledge = load_knowledge()
love_data = load_love_data()
user_data = load_user_data()

api_key       = base_cfg[0]
api_url       = base_cfg[1]
model_name    = base_cfg[2]
max_tokens    = int(base_cfg[3])
host          = base_cfg[4]
http_port     = int(base_cfg[5])
ws_port       = int(base_cfg[6])
listen_mode   = base_cfg[7]
target_id     = base_cfg[8]
token         = base_cfg[9]
follow_enabled = int(base_cfg[10])
follow_time   = int(base_cfg[11])
random_prob   = int(base_cfg[12])
end_prob      = int(base_cfg[13])

ws_link = f"ws://{host}:{ws_port}"
if listen_mode == "group":
    send_link = f"http://{host}:{http_port}/send_group_msg"
else:
    send_link = f"http://{host}:{http_port}/send_private_msg"
chat_api = f"{api_url}/v1/chat/completions"

header = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

user_record = {}
chat_list = [{"role":"system","content":system_msg}]

# AI请求 修复截断核心
def get_ai_reply(content, history="", uid="", affection=0, nickname="", last_emotion=""):
    global chat_list
    print(f"【AI请求】开始处理，历史消息长度:{len(chat_list)}")
    
    if len(chat_list) > 5:
        chat_list = chat_list[:1] + chat_list[-4:]
        print(f"【AI请求】历史消息已截断，当前长度:{len(chat_list)}")
    
    affection_desc = ""
    if affection >= 60:
        affection_desc = "（当前好感度很高，语气要非常亲热、温柔、撒娇）"
    elif affection >= 30:
        affection_desc = "（当前好感度较高，语气友好、亲切）"
    elif affection >= 0:
        affection_desc = "（当前好感度一般，语气平淡、普通）"
    elif affection >= -30:
        affection_desc = "（当前好感度较低，语气冷淡、敷衍）"
    else:
        affection_desc = "（当前好感度很低，语气冷酷、生硬）"
    
    emotion_desc = f"，上次对话你的情绪是{last_emotion}" if last_emotion else ""
    
    if nickname and nickname != "未知用户":
        prompt = f'请回答完整语句，不要中断结尾，直接回复聊天内容。称呼对方为"{nickname}"。{affection_desc}{emotion_desc}'
    else:
        prompt = f"请回答完整语句，不要中断结尾，直接回复聊天内容。不要称呼对方，直接回复即可。{affection_desc}{emotion_desc}"
        
    if history:
        content = f"{prompt} 上文:{history} 当前:{content}"
    else:
        content = f"{prompt} {content}"
        
    chat_list.append({"role":"user","content":content})
    print(f"【AI请求】构建完成，请求内容长度:{len(content)}")

    post_data = {
        "model":model_name,
        "messages":chat_list,
        "max_tokens":max_tokens,
        "temperature":0.5,
        "stop":[]
    }
    ai_head = {
        "Authorization":f"Bearer {api_key}",
        "Content-Type":"application/json"
    }
    
    try:
        print(f"【AI请求】正在调用API: {chat_api}")
        res = requests.post(chat_api, headers=ai_head, json=post_data, timeout=15)
        print(f"【AI请求】HTTP状态码: {res.status_code}")
        
        if res.status_code != 200:
            try:
                error_data = res.json()
                error_msg = error_data.get("error", {}).get("message", "未知错误")
                error_type = error_data.get("error", {}).get("type", "unknown")
                print(f"【AI请求错误】API返回错误 - 类型: {error_type}, 消息: {error_msg}")
                
                if "content_policy" in error_type.lower() or "moderation" in error_type.lower() or "unsafe" in error_msg.lower():
                    print("【AI请求错误】检测到内容不合规/审核失败")
                    return user_data["error_replies"].get("内容不合规", "这个话题不太合适呢，换个话题吧~"), "无奈"
                elif "invalid_api_key" in error_type.lower() or "authentication" in error_type.lower():
                    print("【AI请求错误】API密钥无效或认证失败")
                    return user_data["error_replies"].get("API密钥错误", "我的连接出了点小问题，请稍后再试~"), "困惑"
                elif "quota" in error_type.lower() or "rate_limit" in error_type.lower():
                    print("【AI请求错误】API额度不足或限流")
                    return user_data["error_replies"].get("额度不足", "我有点累了，休息一会儿再聊~"), "疲惫"
                else:
                    print(f"【AI请求错误】HTTP错误 {res.status_code}")
                    return user_data["ai_error_replies"].get("HTTP错误", "挺好的呢"), ""
            except:
                print(f"【AI请求错误】HTTP错误 {res.status_code}，无法解析错误信息")
                return user_data["ai_error_replies"].get("HTTP错误", "挺好的呢"), ""
        
        res_data = res.json()
        print(f"【AI请求】响应数据结构: {list(res_data.keys())}")
        
        if "error" in res_data:
            error_msg = res_data["error"].get("message", "未知错误")
            error_type = res_data["error"].get("type", "unknown")
            print(f"【AI请求错误】响应包含错误 - 类型: {error_type}, 消息: {error_msg}")
            
            if "content_policy" in error_type.lower() or "moderation" in error_msg.lower() or "unsafe" in error_msg.lower():
                print("【AI请求错误】检测到内容不合规")
                return user_data["ai_error_replies"].get("内容不合规", "这个话题不太合适呢，换个话题吧~"), "无奈"
            else:
                return user_data["ai_error_replies"].get("HTTP错误", "挺好的呢"), ""
        
        if "choices" not in res_data or not res_data["choices"]:
            print("【AI请求错误】响应中没有choices字段")
            return user_data["ai_error_replies"].get("响应无choices", "都挺好的呢"), ""
            
        finish_reason = res_data["choices"][0]["finish_reason"]
        msg = res_data["choices"][0]["message"]
        print(f"【AI请求】finish_reason: {finish_reason}")
        print(f"【AI请求】message内容: {msg}")
        
        ans = msg.get("content","").strip()
        print(f"【AI请求】提取content: '{ans}'")
        
        if not ans:
            ans = msg.get("reasoning_content","").strip()
            print(f"【AI请求】content为空，尝试reasoning_content: '{ans}'")
            
        ans = clear_thought(ans)
        print(f"【AI请求】清理后内容: '{ans}'")
        
        emotion = ""
        if ans.startswith("【") and "】" in ans:
            end_idx = ans.find("】")
            emotion = ans[1:end_idx]
            ans = ans[end_idx+1:].strip()
            print(f"【AI请求】提取情绪: '{emotion}'")
            print(f"【AI请求】去除情绪标记后: '{ans}'")
        
        if finish_reason == "length":
            print("【AI请求】检测到内容截断")
            if not ans.endswith(("。","？","！","啦","呀","呢")):
                ans += "就很不错哦"
                print(f"【AI请求】已自动补全: '{ans}'")
                
        if not ans:
            ans = user_data["ai_error_replies"].get("最终内容为空", "一切都还挺好的")
            emotion = "平淡"
            print("【AI请求】最终内容为空，使用默认回复")
            
        chat_list.append({"role":"assistant","content":ans})
        print(f"【AI请求】完成，返回: '{ans}'，情绪: '{emotion}'")
        return ans, emotion
        
    except requests.exceptions.ConnectTimeout:
        print("【AI请求错误】连接超时 - 无法连接到API服务器")
        return user_data["error_replies"].get("连接超时", "网络有点慢呢，稍等一下~"), "疲惫"
    except requests.exceptions.ReadTimeout:
        print("【AI请求错误】读取超时 - API响应时间过长")
        return user_data["error_replies"].get("读取超时", "网络有点卡呢，我想想~"), "困惑"
    except requests.exceptions.ConnectionError:
        print("【AI请求错误】连接错误 - 网络不可用或API服务器宕机")
        return user_data["error_replies"].get("连接错误", "网络不太稳定呢，稍后再聊~"), "担忧"
    except requests.exceptions.RequestException as e:
        print(f"【AI请求错误】其他网络请求失败: {str(e)}")
        return user_data["ai_error_replies"].get("HTTP错误", "都挺好的呢"), ""
    except json.JSONDecodeError as e:
        print(f"【AI请求错误】JSON解析失败: {str(e)}")
        return user_data["ai_error_replies"].get("HTTP错误", "都挺好的呢"), ""
    except KeyError as e:
        print(f"【AI请求错误】缺少必要字段: {str(e)}")
        return user_data["ai_error_replies"].get("HTTP错误", "都挺好的呢"), ""
    except Exception as e:
        print(f"【AI请求错误】未知错误: {str(e)}")
        return user_data["ai_error_replies"].get("HTTP错误", "都挺好的呢"), ""

# 发送消息
def send_msg(target, msg):
    if not msg:
        return
    if listen_mode == "group":
        data = {"group_id": int(target), "message": msg}
    else:
        data = {"user_id": int(target), "message": msg}
    requests.post(send_link, headers=header, json=data, timeout=3)

# 保存对话记录
def save_conversation(nickname, question, answer):
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        with open("conversation.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {nickname}: {question}\n")
            f.write(f"[{timestamp}] AI: {answer}\n\n")
        print(f"【对话记录】已保存")
    except Exception as e:
        print(f"【对话记录】保存失败: {str(e)}")

# 主程序
async def main():
    print("机器人已启动")
    while True:
        try:
            async with websockets.connect(ws_link) as ws:
                while True:
                    raw = await ws.recv()
                    try:
                        data = json.loads(raw)
                    except:
                        continue
                    if data.get("post_type") != "message":
                        continue
                    
                    message_type = data.get("message_type")
                    nickname = data.get("sender", {}).get("nickname", "") or data.get("nickname", "") or "未知用户"
                    
                    if listen_mode == "group":
                        if message_type != "group":
                            continue
                        target = str(data.get("group_id"))
                        uid = str(data.get("user_id"))
                        text = data.get("raw_message", "").strip()
                        if target != target_id:
                            continue
                        print(f"【群{target}】用户{uid}({nickname})：{text}")
                    else:
                        if message_type != "private":
                            continue
                        uid = str(data.get("user_id"))
                        text = data.get("raw_message", "").strip()
                        if uid != target_id:
                            continue
                        print(f"【私聊】用户{uid}({nickname})：{text}")

                    now_time = time.time()
                    reply_flag = False
                    his_text = ""
                    reply_text = ""

                    user_info = love_data.get(uid, {"affection": 0, "tags": [], "last_emotion": ""})
                    user_affection = user_info["affection"]
                    last_emotion = user_info.get("last_emotion", "")
                    print(f"【情感系统】用户{uid}当前好感度: {user_affection} ({get_tone_description(user_affection)})")
                    if last_emotion:
                        print(f"【情感系统】上次对话情绪: {last_emotion}")

                    kb_ans = fuzzy_match(text,knowledge)
                    if kb_ans:
                        print(f"【触发检测】知识库匹配成功: '{kb_ans}'")
                        reply_text = kb_ans
                        reply_flag = True
                    else:
                        print("【触发检测】知识库未匹配")
                        
                        if listen_mode == "private":
                            print("【触发检测】私聊模式，自动触发回复")
                            reply_flag = True
                        else:
                            at_detected = "@" in text or "[CQ:at" in text
                            if at_detected:
                                print(f"【触发检测】检测到@艾特（原始文本包含: {'@' in text and '@' or '[CQ:at'}），触发回复")
                                reply_flag = True
                            else:
                                print("【触发检测】未检测到@艾特")
                            
                        if not reply_flag and follow_enabled == 1 and uid in user_record:
                            reply_time = user_record[uid].get("reply_time", 0)
                            time_diff = now_time - reply_time
                            print(f"【触发检测】用户{uid}存在历史记录，距离上次回复时间: {time_diff:.2f}秒")
                            if time_diff <= follow_time:
                                his_text = user_record[uid].get("reply_text", "")
                                print(f"【触发检测】时间差≤{follow_time}秒，自动延续对话（仅对同一用户），上文: '{his_text}'")
                                reply_flag = True
                            else:
                                print(f"【触发检测】时间差>{follow_time}秒，不触发延续对话")
                        else:
                            if not reply_flag:
                                if follow_enabled != 1:
                                    print("【触发检测】追问功能已禁用")
                                else:
                                    print(f"【触发检测】用户{uid}无历史记录或已触发其他条件")
                        
                        if reply_flag:
                            print("【触发检测】开始调用AI生成回复")
                            reply_text, emotion = get_ai_reply(text, his_text, uid, user_affection, nickname, last_emotion)
                            print(f"【触发检测】AI返回结果: '{reply_text}'，情绪: '{emotion}'")
                            if not reply_text:
                                print("【触发检测】AI返回为空，使用默认回复")
                                reply_text = random.choice(user_data["default_replies"])

                    if reply_flag and reply_text:
                        if end_prob > 0 and random.randint(1, end_prob) == 1:
                            final_reply = random.choice(user_data["end_excuses"])
                            print(f"【随机结束】触发随机结束对话，使用借口: '{final_reply}'")
                            if uid in user_record:
                                del user_record[uid]
                                print("【随机结束】已清除用户对话记录")
                        else:
                            tone_prefix = get_tone_prefix(user_affection)
                            final_reply = tone_prefix + reply_text
                            print(f"【情感系统】根据好感度添加语气前缀: '{tone_prefix}'")
                        
                        if listen_mode == "group":
                            print(f"【发送消息】准备发送给群{target}")
                            send_msg(target, final_reply)
                        else:
                            print(f"【发送消息】准备发送给用户{uid}")
                            send_msg(uid, final_reply)
                        print(f"👉 回复{uid}：{final_reply}\n")
                        
                        save_conversation(nickname, text, final_reply)
                        
                        user_record[uid] = {"reply_time": time.time(), "reply_text": final_reply}
                        print(f"【记录更新】已记录回复时间，追问窗口开启")
                    else:
                        if not reply_flag:
                            print("【发送消息】未触发回复条件，跳过发送\n")
                        elif not reply_text:
                            print("【发送消息】回复内容为空，跳过发送\n")
                    
                    new_affection, change = update_affection(text, user_affection)
                    if change != 0:
                        print(f"【情感系统】好感度变化: {user_affection} → {new_affection} ({'+' if change > 0 else ''}{change})")
                    
                    if uid not in love_data:
                        love_data[uid] = {"affection": 0, "tags": [], "last_emotion": ""}
                    love_data[uid]["affection"] = new_affection
                    if reply_flag and emotion:
                        love_data[uid]["last_emotion"] = emotion
                        print(f"【情感系统】记录情绪: {emotion}")
                    save_love_data(love_data)
        except:
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())